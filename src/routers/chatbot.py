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
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from AI.user_config import get_user_sensitive_tools, update_user_sensitive_tools


router = APIRouter(
        prefix = "/chat", 
        tags = ["Chat"]
    )

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
ALGORITHM = "HS256"

# ============================================================
# DATABASE DEPENDENCY
# ============================================================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
security = HTTPBearer()

# ============================================================
# PYDANTIC MODELS
# ============================================================
class ChatRequest(BaseModel):
    message : str
    thread_id : Optional[int] = None
    human_approval : Optional[str] = None     # "yes" / "no" — sent on HITL resume

class ChatResponse(BaseModel):
    response : str
    thread_id : int
    role : str
    hitl_required : bool = False              # True when waiting for user approval
    hitl_tools : Optional[List[str]] = None   # which sensitive tools need approval
    tools_used : Optional[List[dict]] = None  # tool calls made: [{name, args}, ...]

class ThreadInfo(BaseModel):
    id : int
    created_at : str
    last_message : Optional[str] = None
    message_count : int
    thread_name : Optional[str] = None        # from ChatThread.thread_name column

class MessageInfo(BaseModel):
    id : int
    role : str
    content : str
    created_at : Optional[str] = None

class RenameRequest(BaseModel):
    thread_name: str

class UpdateSettingsRequest(BaseModel):
    tools: list[str]

# ============================================================
# AUTHENTICATION
# ============================================================
def get_user_from_token(token : str, db : Session):
    """Extract user info from JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms = [ALGORITHM])
        user_id = payload.get("id")
        user_type = payload.get("type")  # 'user' or 'host'
        role = payload.get("role")  # 'user', 'host', 'admin'
        
        # Determine owner_type and get name
        if role == "admin":
            user = db.query(Users).filter(Users.id == user_id).first()
            name = user.username if user else "Admin"
        elif user_type == "host":
            host = db.query(Hosts).filter(Hosts.id == user_id).first()
            name = host.company_name if host else "Host"
        else:
            user = db.query(Users).filter(Users.id == user_id).first()
            name = user.username if user else "User"
        
        return {
            "id" : user_id,
            "role" : role,
            "name" : name,
        }
    except JWTError:
        return None

async def get_current_user(credentials : HTTPAuthorizationCredentials = Depends(security), db : Session = Depends(get_db)):
    """Dependency to get current authenticated user"""
    current_user = get_user_from_token(credentials.credentials, db)
    if not current_user:
        raise HTTPException(status_code = 401, detail = "Invalid token")
    return current_user

# ============================================================
# THREAD MANAGEMENT
# ============================================================
def get_or_create_thread(db : Session, user_info : dict, thread_id : Optional[int] = None):
    """Get existing thread or create new one (with owner isolation)"""
    if thread_id:
        # Verify thread belongs to user
        thread = db.query(ChatThread).filter(
            ChatThread.id == thread_id,
            ChatThread.owner_id == user_info["id"],
            ChatThread.owner_type == user_info["role"]
        ).first()
        if thread:
            return thread
    
    # Create new thread
    thread = ChatThread(
        owner_id = user_info["id"],
        owner_type = user_info["role"]
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    print(f"✅ Created new thread: {thread.id} for {user_info['name']}")
    return thread

def save_message(db: Session, thread_id: int, role: str, content: str):
    """Save a message to database"""
    msg = ChatMessage(thread_id = thread_id, role = role, content = content)
    db.add(msg)
    db.commit()

def get_conversation_history(db : Session, thread_id: int, limit : int = 10) -> List[dict]:
    """Get conversation history for context"""
    messages = db.query(ChatMessage).filter(ChatMessage.thread_id == thread_id).order_by(ChatMessage.created_at.desc()).limit(limit).all()
    
    # Return in chronological order
    context = []
    for msg in reversed(messages):
        context.append({
            "role" : msg.role,
            "content" : msg.content
        })
    
    return context

# ============================================================
# MAIN CHAT ENDPOINT
# ============================================================
@router.post("/ask", response_model = ChatResponse)
async def ask_chat(request : ChatRequest, user : dict = Depends(get_current_user), db : Session = Depends(get_db)):
    """Main chat endpoint - handles normal messages and HITL approval responses"""
    try:
        thread = get_or_create_thread(db, user, request.thread_id)

        print(f"\n{'='*60}")
        print(f"💬 Processing message from {user['name']} ({user['role']})")
        print(f"📝 Thread: {thread.id}")
        print(f"📨 Message: {request.message}")
        if request.human_approval:
            print(f"👤 Human approval: {request.human_approval}")
        print(f"{'='*60}")


        user_sensitive_tools = get_user_sensitive_tools(db, user["id"], user["role"])

        user_info = {
            "id": user["id"],
            "role": user["role"],
            "name": user["name"],
            "sensitive_tools": user_sensitive_tools
        }

        # ── HITL resume: user replied yes/no ─────────────────
        if request.human_approval is not None:
            approval = request.human_approval.strip().lower()

            save_message(db, thread.id, "user", f"[Approval : {request.human_approval}] {request.message}")

            result = await run_agent(
                user_input = request.message,
                user_info = user_info,
                thread_id = thread.id,
                human_approval = approval,
            )

            save_message(db, thread.id, "assistant", result["content"])
            return ChatResponse(
                response = result["content"],
                thread_id = thread.id,
                role = user["role"],
                tools_used = result.get("tools_used", []),
            )

        # ── Normal first-turn message ─────────────────────────
        save_message(db, thread.id, "user", request.message)

        result = await run_agent(
            user_input = request.message,
            user_info = user_info,
            thread_id = thread.id,
        )

        # ── HITL interrupt: agent needs approval ──────────────
        if result["type"] == "hitl_required":
            save_message(db, thread.id, "assistant", result["content"])
            return ChatResponse(
                response = result["content"],
                thread_id = thread.id,
                role = user["role"],
                hitl_required = True,
                hitl_tools = result.get("tools", []),
            )

        # ── Normal response ───────────────────────────────────
        save_message(db, thread.id, "assistant", result["content"])
        return ChatResponse(
            response = result["content"],
            thread_id = thread.id,
            role = user["role"],
            tools_used = result.get("tools_used", []),
        )

    except Exception as e:
        print(f"❌ Error in chat: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code = 500, detail = str(e))

# ============================================================
# THREAD MANAGEMENT ENDPOINTS
# ============================================================
@router.get("/threads", response_model=List[ThreadInfo])
async def get_threads(user : dict = Depends(get_current_user), db : Session = Depends(get_db)):
    """Get all threads for current user"""
    threads = db.query(ChatThread).filter(ChatThread.owner_id == user["id"], ChatThread.owner_type == user["role"]).order_by(ChatThread.created_at.desc()).all()
    
    result = []
    for thread in threads:
        last_msg = db.query(ChatMessage).filter(ChatMessage.thread_id == thread.id).order_by(ChatMessage.created_at.desc()).first()
        
        msg_count = db.query(ChatMessage).filter(ChatMessage.thread_id == thread.id).count()
        
        result.append(ThreadInfo(
            id = thread.id,
            created_at = thread.created_at.isoformat() if thread.created_at else "",
            last_message = last_msg.content if last_msg else None,
            message_count = msg_count,
            thread_name = thread.thread_name,
        ))
    
    return result

@router.get("/threads/{thread_id}/messages", response_model=List[MessageInfo])
async def get_thread_messages(thread_id: int, user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)):
    """Get all messages in a thread"""
    # Verify thread belongs to user
    thread = db.query(ChatThread).filter(ChatThread.id == thread_id,
        ChatThread.owner_id == user["id"],
        ChatThread.owner_type == user["role"]).first()
    
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    messages = db.query(ChatMessage).filter(ChatMessage.thread_id == thread_id).order_by(ChatMessage.created_at).all()
    
    return [
        MessageInfo(
            id = m.id,
            role = m.role,
            content = m.content,
            created_at = m.created_at.isoformat() if m.created_at else None
        )
        for m in messages
    ]

@router.delete("/threads/{thread_id}")
async def delete_thread(thread_id: int,user: dict = Depends(get_current_user),db: Session = Depends(get_db)):
    """Delete a thread and all its messages"""
    thread = db.query(ChatThread).filter(ChatThread.id == thread_id, ChatThread.owner_id == user["id"], ChatThread.owner_type == user["role"]).first()
    
    if not thread:
        raise HTTPException(status_code = 404, detail = "Thread not found")
    
    db.delete(thread)
    db.commit()
    
    return {"message": "Thread deleted successfully"}

@router.patch("/threads/{thread_id}/rename")
async def rename_thread(thread_id : int, body : RenameRequest, user : dict = Depends(get_current_user), db : Session = Depends(get_db)):
    """Rename a thread using the thread_name column on ChatThread"""
    thread = db.query(ChatThread).filter(
        ChatThread.id == thread_id,
        ChatThread.owner_id == user["id"],
        ChatThread.owner_type == user["role"]
    ).first()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    thread.thread_name = body.thread_name.strip()[:200]
    db.commit()
    return {"id": thread_id, "thread_name": thread.thread_name}

@router.post("/settings/hitl")
async def update_hitl_settings(body : UpdateSettingsRequest, user : dict = Depends(get_current_user), db : Session = Depends(get_db)):
    settings = update_user_sensitive_tools(db, user["id"], user["role"], body.tools)

    return {
        "message" : "Settings updated",
        "sensitive_tools" : settings.sensitive_tools
    }

@router.get("/settings/hitl")
async def get_hitl_settings(user : dict = Depends(get_current_user), db : Session = Depends(get_db)):
    tools = get_user_sensitive_tools(db, user["id"], user["role"])
    return {"sensitive_tools": tools}


@router.get("/tools")
async def get_available_tools(user: dict = Depends(get_current_user)):

    role = user["role"]

    # Import here to avoid circular imports
    from AI.tools.admin_tools import admin_tools
    from AI.tools.host_tools import host_tools
    from AI.tools.user_tools import user_tools
    from AI.tools.default_tools import default_tools
    from AI.mcp_manager import get_mcp_tools
    from AI.graph import search_event_documents

    tools = [search_event_documents]
    mcp_tools = await get_mcp_tools()
    if role == "admin":
        tools.extend(admin_tools)
    elif role == "host":
        tools.extend(host_tools)
    elif role == "user":
        tools.extend(user_tools)

    tools.extend(default_tools)
    tools.extend(mcp_tools)
    # Format response
    tool_list = []

    for t in tools:
        try:
            name = getattr(t, "name", None)
            description = getattr(t, "description", None)

            # fallback for weird tools
            if not name:
                name = str(t)

            tool_list.append({
                "name": str(name),
                "description": str(description) if description else ""
            })

        except Exception as e:
            print(f"⚠️ Skipping tool due to error: {e}")
            continue
    return {"tools": tool_list}