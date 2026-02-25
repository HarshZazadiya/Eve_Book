from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from database import SessionLocal
from model import ChatThread, ChatMessage, Users
from routers.auth import get_current_user
from langchain_core.messages import HumanMessage, AIMessage
from AI.RAG import ask_agent

router = APIRouter(
    prefix = "/chat", 
    tags = ["Chat"]
)
# ==============================
# DB Dependency
# ==============================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==============================
# Request Schema
# ==============================
class ChatRequest(BaseModel):
    question: str

# ==============================
# CREATE OR GET THREAD
# ==============================
def get_or_create_thread(db: Session, user_id: int):
    thread = db.query(ChatThread).filter(ChatThread.user_id == user_id).first()

    if not thread:
        thread = ChatThread(user_id=user_id)
        db.add(thread)
        db.commit()
        db.refresh(thread)

    return thread

# ==============================
# ASK ENDPOINT
# ==============================
@router.post("/ask")
def ask_chat(request : ChatRequest, db : Session = Depends(get_db), current_user : Users = Depends(get_current_user),):
    # 1️⃣ Get or create chat thread
    thread = get_or_create_thread(db, current_user.id)

    # 2️⃣ Store user message
    user_message = ChatMessage(
        thread_id = thread.id,
        role = "user",
        content = request.question,
    )
    db.add(user_message)
    db.commit()

    # 3️⃣ Load conversation history
    history = db.query(ChatMessage).filter(ChatMessage.thread_id == thread.id).order_by(ChatMessage.created_at).all()

    # 4️⃣ Convert to LangChain messages
    conversation: List = []

    for msg in history:
        if msg.role == "user":
            conversation.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            conversation.append(AIMessage(content=msg.content))

    # 5️⃣ Call LangGraph Agent
    try:
        response = ask_agent(
            question = request.question,
            db = db,
            conversation = conversation
        )
    except Exception as e:
        print("Chat error:", e)
        raise HTTPException(status_code = 500, detail = "AI processing error")

    if response is None:
        response = "No response."

    # 6️⃣ Store assistant response
    assistant_message = ChatMessage(
        thread_id = thread.id,
        role = "assistant",
        content = response,
    )
    db.add(assistant_message)
    db.commit()

    # 7️⃣ Return response
    return {"response": response}