from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Form
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Annotated
from sqlalchemy.orm import Session
from database import SessionLocal
from routers.auth import authenticate_host, create_access_token, get_current_host
from model import Events, Hosts, HostingPayments, BookingPayments, Bookings, Wallets
import redis.asyncio as redis
import json
import os
import shutil
from datetime import date, datetime
from pathlib import Path
from AI.RAG import process_event_document, delete_event_documents
from langchain_core.tools import tool
# --------------------------------------------------
# Router Setup
# --------------------------------------------------

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

REDIS_URL = os.getenv("REDIS_URL")
redis_client = redis.from_url(REDIS_URL, decode_responses=True) if REDIS_URL else None


# --------------------------------------------------
# Schemas
# --------------------------------------------------

class EventRequest(BaseModel):
    title: str
    venue: str
    date: date
    seats: int
    ticket_price: int

class PaymentRequest(BaseModel):
    amount : int
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


# --------------------------------------------------
# HOST INFO
# --------------------------------------------------
@tool
async def get_info(host: host_dependency):

    cache_key = f"host:{host.id}"

    if redis_client:
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

    data = {
        "id": host.id,
        "company_name": host.company_name,
        "email": host.email
    }

    if redis_client:
        await redis_client.set(cache_key, json.dumps(data), ex=300)

    return data


# --------------------------------------------------
# GET HOST EVENTS
# --------------------------------------------------
@tool
async def get_events(host: host_dependency, db: db_dependency):

    cache_key = f"host_events:{host.id}"

    if redis_client:
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

    events = db.query(Events).filter(Events.host_id == host.id).all()

    result = []
    for e in events:
        result.append({
            "id" : e.id,
            "title" : e.title,
            "venue" : e.venue,
            "date" : str(e.date),
            "seats" : e.seats,
            "available_seats" : e.available_seats,
            "ticket_price" : e.ticket_price,
            "more_details" : f"/uploads/{e.document_path}" if e.document_path else None
        })

    if redis_client:
        await redis_client.set(cache_key, json.dumps(result), ex=10)

    return result


# --------------------------------------------------
# CREATE EVENT
# --------------------------------------------------
@tool
async def host_event(
    host : host_dependency,
    db : db_dependency,
    title : str = Form(...),
    venue : str = Form(...),
    date : str = Form(...),
    seats : int = Form(...),
    ticket_price : int = Form(...),
    document : UploadFile = File(None)
):

    HOSTING_FEE = 500
    wallet = db.query(Wallets).filter(Wallets.owner_type == "host", Wallets.owner_id == host.id).first()
    if not wallet or wallet.balance < HOSTING_FEE:
        raise HTTPException(403, "Insufficient wallet balance")
    wallet.balance -= HOSTING_FEE
    payment = HostingPayments(
        host_id = host.id,
        amount = HOSTING_FEE,
        status = "success"
    )
    db.add(payment)

    event = Events(
        title = title,
        venue = venue,
        date = datetime.strptime(date, "%Y-%m-%d").date(),
        seats = seats,
        available_seats = seats,
        host_id = host.id,
        ticket_price = ticket_price
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    event_host = db.query(Hosts).filter(Hosts.id == host.id).first()

    # -------- File Handling --------

    safe_title = title.replace(" ", "_").replace("/", "").replace("\\", "")
    filename = f"{host.id}_{event.id}_{safe_title}.pdf"
    file_path = os.path.join(UPLOAD_DIR, filename)

    if document:
        if document.content_type != "application/pdf":
            raise HTTPException(400, "Only PDF files are allowed")

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(document.file, buffer)
    else:
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(file_path)
        c.drawString(100, 800, f"Host : {event_host.company_name}")
        c.drawString(100, 780, f"Event : {title}")
        c.drawString(100, 760, f"Venue : {venue}")
        c.drawString(100, 740, f"Date : {date}")
        c.drawString(100, 720, f"Seats : {seats}")
        c.drawString(100, 700, f"Price : {ticket_price} INR")
        c.save()

    event.document_path = filename
    db.commit()

   # After saving the document, add this:
    if document:
        # Process the uploaded PDF for RAG
        process_event_document(event.id, file_path)
    else:
        # Process the generated default PDF
        process_event_document(event.id, file_path)

    # In the host_event function, after process_event_document:
    if document:
        process_event_document(event.id, file_path)
        event.document_processed = True  # Add this line
        db.commit()
    else:
        process_event_document(event.id, file_path)
        event.document_processed = True  # Add this line
        db.commit()
    if redis_client:
        await redis_client.delete(f"host_events : {host.id}")
    
    return {"event_id" : event.id, "message" : "Event created successfully"}


# --------------------------------------------------
# DELETE EVENT (WITH FULL REFUNDS)
# --------------------------------------------------
@tool
async def delete_event(host: host_dependency, db: db_dependency, event_id: int):
    HOSTING_FEE = 500

    event = db.query(Events).filter(Events.id == event_id, Events.host_id == host.id).first()
    if not event:
        raise HTTPException(404, "Event not found")

    # Delete from vector store FIRST
    from AI.RAG import delete_event_documents
    delete_event_documents(event_id)

    bookings = db.query(Bookings).filter(Bookings.event_id == event.id).all()

    for booking in bookings:
        payment = db.query(BookingPayments).filter(BookingPayments.booking_id == booking.id).first()
        user_wallet = db.query(Wallets).filter(Wallets.owner_type == "user", Wallets.owner_id == booking.user_id).first()
        host_wallet = db.query(Wallets).filter(Wallets.owner_type == "host", Wallets.owner_id == host.id).first()

        if payment and user_wallet:
            user_wallet.balance += payment.amount
            if host_wallet:
                host_wallet.balance -= payment.amount
            db.delete(payment)

        db.delete(booking)

    # Refund hosting fee
    wallet = db.query(Wallets).filter(Wallets.owner_type == "host", Wallets.owner_id == host.id).first()
    if wallet:
        wallet.balance += HOSTING_FEE

    # Delete document file
    if event.document_path:
        file_path = os.path.join(UPLOAD_DIR, event.document_path)
        if os.path.exists(file_path):
            os.remove(file_path)

    db.delete(event)
    db.commit()

    if redis_client:
        await redis_client.delete(f"host_events : {host.id}")

    return {"message": "Event deleted successfully with refunds"}


# --------------------------------------------------
# UPDATE EVENT
# --------------------------------------------------

@tool
async def update_event(event_id: int,  host: host_dependency,  db: db_dependency,  event_request: EventRequest):
    event = db.query(Events).filter(Events.id == event_id,  Events.host_id == host.id).first()
    if not event:
        raise HTTPException(404, "Event not found")

    # Store old values to check what changed
    old_title = event.title
    old_venue = event.venue
    old_date = event.date
    
    # Update fields
    diff = event_request.seats - event.seats
    event.title = event_request.title
    event.venue = event_request.venue
    event.date = event_request.date
    event.seats = event_request.seats
    event.available_seats += diff
    event.ticket_price = event_request.ticket_price
    
    db.commit()
    
    # Check if any important details changed that should be reflected in the document
    details_changed = (
        old_title != event.title or
        old_venue != event.venue or
        old_date != event.date or
        event_request.ticket_price != event.ticket_price
    )
    
    # Handle document update
    if details_changed:
        print(f"📝 Event details changed, updating document for event {event_id}")
        
        # Delete old document from vector store FIRST
        try:
            from AI.RAG import delete_event_documents
            delete_event_documents(event_id)
            print(f"✅ Removed old event {event_id} from vector store")
        except Exception as e:
            print(f"⚠️ Error removing from vector store: {e}")
        
        # Generate new PDF with updated details
        from reportlab.pdfgen import canvas
        
        # Delete old PDF file if exists
        if event.document_path:
            old_path = os.path.join("uploads", event.document_path)
            if os.path.exists(old_path):
                os.remove(old_path)
                print(f"🗑️ Deleted old PDF: {old_path}")
        
        # Generate new PDF filename
        safe_title = event.title.replace(" ", "_").replace("/", "").replace("\\", "")
        filename = f"{host.id}_{event.id}_{safe_title}.pdf"
        file_path = os.path.join("uploads", filename)
        
        # Create new PDF with updated details
        c = canvas.Canvas(file_path)
        c.drawString(100, 800, f"Event: {event.title}")
        c.drawString(100, 780, f"Venue: {event.venue}")
        c.drawString(100, 760, f"Date: {event.date}")
        c.drawString(100, 740, f"Seats: {event.seats}")
        c.drawString(100, 720, f"Price: {event.ticket_price} INR")
        c.drawString(100, 700, f"Host: {host.company_name}")
        c.save()
        
        # Update database with new filename
        event.document_path = filename
        db.commit()
        
        # Add to vector store
        try:
            from AI.RAG import process_event_document
            process_event_document(event.id, file_path)
            print(f"✅ Added updated event {event_id} to vector store")
        except Exception as e:
            print(f"⚠️ Error adding to vector store: {e}")
    
    return {"message": "Event updated successfully"}


# --------------------------------------------------
# UPDATE EVENT DOCUMENT
# --------------------------------------------------
@tool
async def update_event_document(event_id: int, host: host_dependency, db: db_dependency, document: UploadFile = File(...)):
    """Update ONLY the document for an event (keep event details same)"""
    
    event = db.query(Events).filter(Events.id == event_id, Events.host_id == host.id).first()
    
    if not event:
        raise HTTPException(404, "Event not found")
    
    # Validate file type
    if document.content_type != "application/pdf":
        raise HTTPException(400, "Only PDF files allowed")
    
    # Delete old document from vector store
    try:
        from AI.RAG import delete_event_documents
        delete_event_documents(event_id)
        print(f"✅ Removed old event {event_id} from vector store")
    except Exception as e:
        print(f"⚠️ Error removing from vector store: {e}")
    
    # Delete old PDF file
    if event.document_path:
        old_path = os.path.join("uploads", event.document_path)
        if os.path.exists(old_path):
            os.remove(old_path)
            print(f"🗑️ Deleted old PDF: {old_path}")
    
    # Save new PDF
    safe_title = event.title.replace(" ", "_").replace("/", "").replace("\\", "")
    filename = f"{host.id}_{event.id}_{safe_title}.pdf"
    file_path = os.path.join("uploads", filename)
    
    # Save uploaded file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(document.file, buffer)
    
    # Update database
    event.document_path = filename
    db.commit()
    
    # Add to vector store
    try:
        from AI.RAG import process_event_document
        process_event_document(event.id, file_path)
        print(f"✅ Added new document for event {event_id} to vector store")
    except Exception as e:
        print(f"⚠️ Error adding to vector store: {e}")
    
    return {"message": "Document updated successfully"}
# --------------------------------------------------
# LOGIN
# --------------------------------------------------
@tool
async def login(form_data : OAuth2PasswordRequestForm = Depends(), db : Session = Depends(get_db)):
    host = authenticate_host(form_data.username, form_data.password, db)
    if not host:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(
        entity_id = host.id,
        entity_type = "host",
        role = "host"
    )

    return {
        "access_token" : access_token,
        "token_type" : "bearer",
        "type" : "host"
    }


host_toolkit = [
    get_info,
    get_events,
    host_event,
    delete_event,
    update_event,
    update_event_document
]