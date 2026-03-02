from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated
from sqlalchemy.orm import Session
from database import SessionLocal
from routers.auth import authenticate_host, create_access_token, get_current_host
from model import Hosts
import os
import shutil
from datetime import datetime
from pydantic import BaseModel
from AI.tools.host_tools import (
    get_host_info,
    get_host_events,
    create_host_event,
    delete_host_event,
    update_host_event,
    update_event_document,
    host_tools
)

router = APIRouter(prefix="/host", tags=["Host"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --------------------------------------------------
# Dependencies
# --------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
host_dependency = Annotated[Hosts, Depends(get_current_host)]

class PaymentRequest(BaseModel):
    amount : int

class EventUpdateRequest(BaseModel):
    title: str
    venue: str
    date: str
    seats: int
    ticket_price: int
# --------------------------------------------------
# HOST INFO
# --------------------------------------------------
@router.get("/")
async def get_info(host: host_dependency):
    """Get host information"""
    result = get_host_info.invoke({
        "host_id": host.id
    })
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result

# --------------------------------------------------
# GET HOST EVENTS
# --------------------------------------------------
@router.get("/events")
async def get_events(host: host_dependency):
    """Get all events created by this host"""
    result = get_host_events.invoke({
        "host_id": host.id
    })
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result

# --------------------------------------------------
# CREATE EVENT
# --------------------------------------------------
@router.post("/event")
async def create_event(
    host: host_dependency,
    title: str = Form(...),
    venue: str = Form(...),
    date: str = Form(...),
    seats: int = Form(...),
    ticket_price: int = Form(...),
    document: UploadFile = File(None)
):
    """Create a new event"""
    
    # Handle document upload if provided
    document_path = None
    if document:
        if document.content_type != "application/pdf":
            raise HTTPException(400, "Only PDF files are allowed")
        
        # Save temporarily
        temp_path = os.path.join(UPLOAD_DIR, f"temp_{document.filename}")
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(document.file, buffer)
        document_path = temp_path
    
    # Call the tool
    result = create_host_event.invoke({
        "host_id": host.id,
        "title": title,
        "venue": venue,
        "date": date,
        "seats": seats,
        "ticket_price": ticket_price,
        "document_path": document_path
    })
    
    # Clean up temp file
    if document_path and os.path.exists(document_path):
        os.remove(document_path)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result

# --------------------------------------------------
# DELETE EVENT
# --------------------------------------------------
@router.delete("/event/{event_id}")
async def delete_event(host: host_dependency, event_id: int):
    """Delete an event and process refunds"""
    result = delete_host_event.invoke({
        "host_id": host.id,
        "event_id": event_id
    })
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result

# --------------------------------------------------
# UPDATE EVENT
# --------------------------------------------------
@router.put("/event/{event_id}")
async def update_event(event_id: int, event_data: EventUpdateRequest, host: host_dependency):
    """Update event details"""
    result = update_host_event.invoke({
        "host_id": host.id,
        "event_id": event_id,
        "title": event_data.title,
        "venue": event_data.venue,
        "date": event_data.date,
        "seats": event_data.seats,
        "ticket_price": event_data.ticket_price
    })
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result

# --------------------------------------------------
# UPDATE EVENT DOCUMENT
# --------------------------------------------------
@router.put("/event_document/{event_id}")
async def update_document(event_id: int, host: host_dependency, document: UploadFile = File(...)):
    """Update just the document for an event"""
    
    # Validate file type
    if document.content_type != "application/pdf":
        raise HTTPException(400, "Only PDF files allowed")
    
    # Save temporarily
    temp_path = os.path.join(UPLOAD_DIR, f"temp_doc_{document.filename}")
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(document.file, buffer)
    
    try:
        # Call the tool
        result = update_event_document.invoke({
            "host_id": host.id,
            "event_id": event_id,
            "pdf_path": temp_path
        })
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
        
    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)

# --------------------------------------------------
# LOGIN
# --------------------------------------------------
@router.post("/token")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Host login endpoint"""
    host = authenticate_host(form_data.username, form_data.password, db)
    if not host:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(
        entity_id=host.id,
        entity_type="host",
        role="host"
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "type": "host"
    }

# --------------------------------------------------
# TOOLKIT ENDPOINT (for agent)
# --------------------------------------------------
@router.get("/tools")
async def get_tools():
    """Return list of available host tools"""
    return [tool.name for tool in host_tools]