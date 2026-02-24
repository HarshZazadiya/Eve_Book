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


# --------------------------------------------------
# Router Setup
# --------------------------------------------------

router = APIRouter(prefix="/host", tags=["Host"])

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

@router.get("/")
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

@router.get("/events")
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

@router.post("/event")
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
        c.drawString(100, 800, f"Event: {title}")
        c.drawString(100, 780, f"Venue: {venue}")
        c.drawString(100, 760, f"Date: {date}")
        c.drawString(100, 740, f"Seats: {seats}")
        c.drawString(100, 720, f"Price: {ticket_price}")
        c.save()

    event.document_path = filename
    db.commit()

    if redis_client:
        await redis_client.delete(f"host_events : {host.id}")

    return {"event_id" : event.id, "message" : "Event created successfully"}


# --------------------------------------------------
# DELETE EVENT (WITH FULL REFUNDS)
# --------------------------------------------------

@router.delete("/event/{event_id}")
async def delete_event(host: host_dependency, db: db_dependency, event_id: int):
    HOSTING_FEE = 500

    event = db.query(Events).filter(Events.id == event_id, Events.host_id == host.id).first()
    if not event:
        raise HTTPException(404, "Event not found")

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

    return {"message" : "Event deleted successfully with refunds"}


# --------------------------------------------------
# UPDATE EVENT
# --------------------------------------------------

@router.put("/event/{event_id}")
async def update_event(event_id:  int, host : host_dependency, db : db_dependency, event_request : EventRequest):
    event = db.query(Events).filter(Events.id == event_id, Events.host_id == host.id).first()
    if not event:
        raise HTTPException(404, "Event not found")

    diff = event_request.seats - event.seats

    event.title = event_request.title
    event.venue = event_request.venue
    event.date = event_request.date
    event.seats = event_request.seats
    event.available_seats += diff
    event.ticket_price = event_request.ticket_price

    db.commit()

    return {"message" : "Event updated successfully"}


# --------------------------------------------------
# UPDATE EVENT DOCUMENT
# --------------------------------------------------

@router.put("/event_document/{event_id}")
async def update_event_document(event_id : int, host : host_dependency, db : db_dependency, document : UploadFile = File(...)):
    event = db.query(Events).filter(Events.id == event_id, Events.host_id == host.id).first()
    if not event:
        raise HTTPException(404, "Event not found")

    if document.content_type != "application/pdf":
        raise HTTPException(400, "Only PDF files allowed")

    if event.document_path:
        old_path = os.path.join(UPLOAD_DIR, event.document_path)
        if os.path.exists(old_path):
            os.remove(old_path)

    safe_title = event.title.replace(" ", "_").replace("/", "").replace("\\", "")
    filename = f"{host.id}_{event.id}_{safe_title}.pdf"
    file_path = os.path.join(UPLOAD_DIR, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(document.file, buffer)

    event.document_path = filename
    db.commit()

    return {"message" : "Document updated successfully"}

# --------------------------------------------------
# LOGIN
# --------------------------------------------------

@router.post("/token")
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