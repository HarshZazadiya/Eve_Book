from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Annotated, Optional, List
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from datetime import datetime
import os
from AI.graph import run_agent
from database import SessionLocal
from model import Users, Hosts, ChatThread, ChatMessage
from AI.RAG import llm, search_documents
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from AI.RAG import get_vector_store
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

router = APIRouter(prefix="/chat", tags=["Chat"])

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
ALGORITHM = "HS256"

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]


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


security = HTTPBearer()

def get_user_from_token(token: str, db: Session):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("id")
        user_type = payload.get("type")  # 'user' or 'host'
        role = payload.get("role")  # 'user', 'host', 'admin'
        
        # Determine the correct owner_type and get name
        if role == "admin":
            # Admin comes from users table with role='admin'
            owner_type = "admin"
            user = db.query(Users).filter(Users.id == user_id).first()
            name = user.username if user else "Admin"
            
        elif user_type == "host":
            # Host comes from hosts table
            owner_type = "host"
            host = db.query(Hosts).filter(Hosts.id == user_id).first()
            name = host.company_name if host else "Host"
            
        else:
            # Regular user comes from users table with role='user'
            owner_type = "user"
            user = db.query(Users).filter(Users.id == user_id).first()
            name = user.username if user else "User"
        
        return {
            "id": user_id,
            "type": user_type,
            "role": role,
            "owner_type": owner_type,  # This is what we store in chat_threads
            "name": name,
        }
        
    except JWTError:
        return None

async def get_current_user(credentials : HTTPAuthorizationCredentials = Depends(security),  db : Session = Depends(get_db)):
    user = get_user_from_token(credentials.credentials, db)
    if not user:
        raise HTTPException(status_code = 401, detail = "Invalid token")
    return user


def get_or_create_thread(db: Session, user_info: dict, thread_id: Optional[int] = None):
    """
    Get existing thread or create new one.
    Uses both owner_id AND owner_type for isolation.
    """
    if thread_id:
        # When retrieving a specific thread, check BOTH id AND owner_id AND owner_type
        thread = db.query(ChatThread).filter(ChatThread.id == thread_id, ChatThread.owner_id == user_info["id"], ChatThread.owner_type == user_info["owner_type"]).first()
        if thread:
            return thread
    
    # Create new thread with both owner_id and owner_type
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
# MAIN CHAT ENDPOINT
# ============================================================
@router.post("/ask", response_model=ChatResponse)
async def ask_chat(request: ChatRequest, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        # Get or create thread - uses both owner_id and owner_type
        thread = get_or_create_thread(db, user, request.thread_id)
        
        # Save user message
        save_message(db, thread.id, "user", request.message)
        
        # Get conversation history
        conversation = get_conversation_context(db, thread.id, limit=10)
        
        print(f"\n{'='*60}")
        print(f"🤖 Processing: {user['name']} ({user['role']}, {user['owner_type']}, ID: {user['id']})")
        print(f"💬 Thread: {thread.id}")
        print(f"💬 Message: {request.message}")
        print(f"{'='*60}")
        
        response = await run_agent(
            user_input=request.message,
            user_info={
                "id" : user["id"],
                "role" : user["role"],
                "name" : user["name"],
                "type" : user.get("type", user["role"]),
                "owner_type" : user["owner_type"]
            },
            conversation_history = conversation
        )
        
        # Save assistant response
        save_message(db, thread.id, "assistant", response)
        
        return ChatResponse(
            response = response,
            thread_id = thread.id,
            role = user["role"]
        )
        
    except Exception as e:
        print(f"❌ Error : {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code = 500, detail = str(e))



@router.get("/threads", response_model=List[ThreadInfo])
async def get_threads(user: dict = Depends(get_current_user),  db: Session = Depends(get_db)):
    """
    Get all threads for the current user.
    Checks BOTH owner_id AND owner_type for proper isolation.
    """
    threads = db.query(ChatThread).filter(ChatThread.owner_id == user["id"], ChatThread.owner_type == user["owner_type"]).order_by(ChatThread.created_at.desc()).all()
    
    result = []
    for thread in threads:
        last_msg = db.query(ChatMessage).filter(ChatMessage.thread_id == thread.id).order_by(ChatMessage.created_at.desc()).first()
        
        msg_count = db.query(ChatMessage).filter(ChatMessage.thread_id == thread.id).count()
        
        result.append(ThreadInfo(
            id = thread.id,
            created_at = thread.created_at.isoformat() if thread.created_at else "",
            last_message = last_msg.content if last_msg else None,
            message_count = msg_count
        ))
    
    return result


@router.get("/threads/{thread_id}/messages")
async def get_thread_messages(thread_id : int, user : dict = Depends(get_current_user), db : Session = Depends(get_db)):
    """
    Get messages in a specific thread
    Verifies BOTH owner_id AND owner_type.
    """
    thread = db.query(ChatThread).filter(ChatThread.id == thread_id, ChatThread.owner_id == user["id"], ChatThread.owner_type == user["owner_type"]).first()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    messages = db.query(ChatMessage).filter(ChatMessage.thread_id == thread_id).order_by(ChatMessage.created_at).all()
    
    return [
        {
            "id" : m.id,
            "role" : m.role,
            "content" : m.content,
            "created_at" : m.created_at.isoformat() if m.created_at else None
        }
        for m in messages
    ]


@router.delete("/threads/{thread_id}")
async def delete_thread(thread_id : int, user : dict = Depends(get_current_user), db : Session = Depends(get_db)):
    """
    Delete a thread.
    Verifies BOTH owner_id AND owner_type.
    """
    thread = db.query(ChatThread).filter(ChatThread.id == thread_id, ChatThread.owner_id == user["id"], ChatThread.owner_type == user["owner_type"]).first()
    
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    db.delete(thread)
    db.commit()
    
    return {"message" : "Thread deleted"}

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
async def debug_threads(db : Session = Depends(get_db)):
    """Debug endpoint to see all threads (admin only - add auth in production)"""
    threads = db.query(ChatThread).all()
    return [
        {
            "id" : t.id,
            "owner_id" : t.owner_id,
            "owner_type" : t.owner_type,
            "created_at" : str(t.created_at)
        }
        for t in threads
    ]

@router.get("/debug/my-threads")
async def debug_my_threads(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Debug endpoint to see your threads with both checks"""
    threads = db.query(ChatThread).filter(ChatThread.owner_id == user["id"], ChatThread.owner_type == user["owner_type"]).all()
    
    return [
        {
            "id" : t.id,
            "owner_id" : t.owner_id,
            "owner_type" : t.owner_type,
            "created_at" : str(t.created_at),
            "message_count" : db.query(ChatMessage).filter(ChatMessage.thread_id == t.id).count()
        }
        for t in threads
    ]