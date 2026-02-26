from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Annotated, Optional, List
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from datetime import datetime
import os
import re
from database import SessionLocal
from model import Users, Hosts, ChatThread, ChatMessage
from AI.RAG import llm, search_documents
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from AI.RAG import get_vector_store

router = APIRouter(prefix="/chat", tags=["Chat"])

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
ALGORITHM = "HS256"

# ============================================================
# DATABASE
# ============================================================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]

# ============================================================
# MODELS
# ============================================================
class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[int] = None

class ChatResponse(BaseModel):
    response: str
    thread_id: int
    role: str

class ThreadInfo(BaseModel):
    id: int
    created_at: str
    last_message: Optional[str] = None
    message_count: int

# ============================================================
# AUTH - FIXED FOR ADMIN
# ============================================================
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
security = HTTPBearer()

def get_user_from_token(token: str, db: Session):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("id")
        user_type = payload.get("type") 
        role = payload.get("role") 
        
        # Determine the correct owner_type
        if role == "admin":
            # Admin overrides everything
            owner_type = "admin"
            name = "Admin"
        elif user_type == "host":
            owner_type = "host"
            host = db.query(Hosts).filter(Hosts.id == user_id).first()
            name = host.company_name if host else "Host"
        else:
            owner_type = "user"
            user = db.query(Users).filter(Users.id == user_id).first()
            name = user.username if user else "User"
        
        return {
            "id": user_id,
            "type": user_type,
            "role": role,
            "owner_type": owner_type, 
            "name": name,
        }
        
    except JWTError:
        return None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    user = get_user_from_token(credentials.credentials, db)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user

# ============================================================
# THREAD MANAGEMENT - FIXED
# ============================================================
def get_or_create_thread(db: Session, user_info: dict, thread_id: Optional[int] = None):
    """
    Get existing thread or create new one with correct owner_type
    user_info contains: id, type, role, owner_type, name
    """
    if thread_id:
        thread = db.query(ChatThread).filter(ChatThread.id == thread_id, ChatThread.owner_id == user_info["id"]).first()
        if thread:
            return thread
    
    thread = ChatThread(owner_id=user_info["id"], owner_type=user_info["owner_type"])
    db.add(thread)
    db.commit()
    db.refresh(thread)
    print(f"✅ Created new thread: id={thread.id}, owner_id={thread.owner_id}, owner_type={thread.owner_type}")
    return thread

def save_message(db: Session, thread_id: int, role: str, content: str):
    msg = ChatMessage(thread_id=thread_id, role=role, content=content)
    db.add(msg)
    db.commit()

def get_conversation_context(db: Session, thread_id: int, limit: int = 4) -> List[dict]:
    """Get last N messages as context"""
    messages = db.query(ChatMessage).filter(ChatMessage.thread_id == thread_id).order_by(ChatMessage.created_at.desc()).limit(limit).all()
    
    # Return in chronological order
    context = []
    for msg in reversed(messages):
        context.append({
            "role": msg.role,
            "content": msg.content
        })
    
    return context

# ============================================================
# SYSTEM PROMPT - Based on role
# ============================================================
def get_base_prompt(user_info: dict) -> str:
    """Get base system prompt based on user role"""
    
    if user_info["role"] == "admin":
        return f"You are an AI assistant for EveBook. You are talking to an ADMIN. Be professional and helpful."
    elif user_info["role"] == "host":
        return f"You are an AI assistant for EveBook. You are talking to a HOST named {user_info['name']}. Be helpful with event management."
    else:
        return f"You are an AI assistant for EveBook. You are talking to a USER named {user_info['name']}. Be friendly and helpful."

# ============================================================
# MAIN CHAT ENDPOINT
# ============================================================
@router.post("/ask", response_model=ChatResponse)
async def ask_chat(request: ChatRequest, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        # Get or create thread - PASS THE USER INFO
        thread = get_or_create_thread(db, user, request.thread_id)
        
        # Save user message
        save_message(db, thread.id, "user", request.message)
        
        # Get conversation context (last 4 messages)
        conversation = get_conversation_context(db, thread.id, limit=4)
        
        # Format conversation for prompt
        conversation_text = ""
        for msg in conversation[:-1]:  # Exclude current message
            conversation_text += f"{msg['role'].upper()}: {msg['content']}\n"
        
        # Search for relevant documents
        search_query = request.message
        if len(conversation) > 1:
            # Add previous user message for context if available
            prev_user_msgs = [msg for msg in conversation[:-1] if msg['role'] == 'user']
            if prev_user_msgs:
                search_query = f"{prev_user_msgs[-1]['content']} {request.message}"
        
        print(f"🔍 Searching documents with query: {search_query}")
        doc_context = search_documents(search_query, k=5)
        
        # Build the prompt
        if doc_context:
            prompt = f"""{get_base_prompt(user)}
                        RELEVANT DOCUMENTS:
                        {doc_context}

                        CONVERSATION HISTORY:
                        {conversation_text}
                        USER: {request.message}

                        IMPORTANT RULES:
                        1. Answer based ONLY on the documents above
                        2. Use the conversation history to understand context
                        3. If asked about something mentioned earlier, refer back to it
                        4. If documents don't have the answer, say "I don't have that information"
                        5. Be natural and conversational

                        ASSISTANT:
                    """
        else:
            prompt = f"""{get_base_prompt(user)}
                        CONVERSATION HISTORY:
                        {conversation_text}
                        USER: {request.message}

                        I searched but found NO relevant documents.
                        Say you don't have that information.

                        ASSISTANT:
                    """
        
        # Get response
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content=request.message)
        ]
        
        response = llm.invoke(messages)
        answer = response.content.strip()
        
        # Save assistant response
        save_message(db, thread.id, "assistant", answer)
        
        return ChatResponse(
            response=answer,
            thread_id=thread.id,
            role=user["role"]
        )
        
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# THREAD MANAGEMENT ENDPOINTS
# ============================================================
@router.get("/threads", response_model=List[ThreadInfo])
async def get_threads(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get all threads for the current user (based on owner_id only)"""
    threads = db.query(ChatThread).filter(ChatThread.owner_id == user["id"]).order_by(ChatThread.created_at.desc()).all()
    
    result = []
    for thread in threads:
        last_msg = db.query(ChatMessage).filter(ChatMessage.thread_id == thread.id).order_by(ChatMessage.created_at.desc()).first()
        
        msg_count = db.query(ChatMessage).filter(ChatMessage.thread_id == thread.id).count()
        
        result.append(ThreadInfo(
            id=thread.id,
            created_at=thread.created_at.isoformat() if thread.created_at else "",
            last_message=last_msg.content if last_msg else None,
            message_count=msg_count
        ))
    
    return result

@router.get("/threads/{thread_id}/messages")
async def get_thread_messages(thread_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get messages in a thread - verify ownership by owner_id only"""
    thread = db.query(ChatThread).filter(ChatThread.id == thread_id, ChatThread.owner_id == user["id"]).first()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    messages = db.query(ChatMessage).filter(ChatMessage.thread_id == thread_id).order_by(ChatMessage.created_at).all()
    
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat() if m.created_at else None
        }
        for m in messages
    ]

@router.delete("/threads/{thread_id}")
async def delete_thread(thread_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a thread - verify ownership by owner_id only"""
    thread = db.query(ChatThread).filter(ChatThread.id == thread_id, ChatThread.owner_id == user["id"]).first()
    
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    db.delete(thread)
    db.commit()
    
    return {"message": "Thread deleted"}

# ============================================================
# DEBUG ENDPOINTS
# ============================================================
@router.get("/debug/status")
async def debug_status():
    store = get_vector_store()
    return {
        "vectors": store.index.ntotal,
        "has_docs": store.index.ntotal > 1
    }

@router.get("/debug/threads")
async def debug_threads(db: Session = Depends(get_db)):
    """Debug endpoint to see all threads"""
    threads = db.query(ChatThread).all()
    return [
        {
            "id": t.id,
            "owner_id": t.owner_id,
            "owner_type": t.owner_type,
            "created_at": str(t.created_at)
        }
        for t in threads
    ]