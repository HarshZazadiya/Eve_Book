from fastapi import FastAPI, APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import Annotated, List
import model
from database import SessionLocal
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from routers.auth import authenticate_host, authenticate_user, create_access_token, get_current_user, get_current_host
from model import Users, Events, Hosts, HostingPayments, BookingPayments, Bookings, Wallets
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import jwt, JWTError
import redis.asyncio as redis
import json
from datetime import date
import os
from routers.user import serialize_event

router = APIRouter(
    prefix="/host",
    tags=["Host"],
)

class EventRequest(BaseModel):
    title: str
    venue: str
    date: date
    seats: int
    ticket_price: int

class PaymentRequest(BaseModel):
    amount : int

REDIS_URL = os.getenv("REDIS_URL")
redis_client = redis.from_url(REDIS_URL, decode_responses=True) if REDIS_URL else None

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
host_dependency = Annotated[Hosts, Depends(get_current_host)]

@router.get("/")
async def get_info(host: host_dependency, db: db_dependency):

    cache_key = f"host:{host.id}"

    cached = None
    if redis_client:
        cached = await redis_client.get(cache_key)

    if cached:
        return json.loads(cached)

    host_data = {
        "id": host.id,
        "company_name": host.company_name,
        "email": host.email,
    }

    if redis_client:
        await redis_client.set(cache_key, json.dumps(host_data), ex=300)

    return host_data

@router.get("/events")
async def get_events(host: host_dependency, db: db_dependency):

    cache_key = f"host_events:{host.id}"

    cached = None
    if redis_client:
        cached = await redis_client.get(cache_key)

    if cached:
        return json.loads(cached)

    events = db.query(Events).filter(Events.host_id == host.id).all()
    serialized = [serialize_event(e) for e in events]

    if redis_client:
        await redis_client.set(cache_key, json.dumps(serialized), ex=5)

    return serialized


@router.post("/event")
async def host_event(host: host_dependency, db: db_dependency, event_request: EventRequest):
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
        title = event_request.title,
        venue = event_request.venue,
        date = event_request.date,
        seats = event_request.seats,
        available_seats = event_request.seats,
        host_id = host.id,
        ticket_price = event_request.ticket_price
    )

    db.add(event)
    db.commit()
    db.refresh(event)
    if redis_client:
        await redis_client.delete(f"host_events:{host.id}")
        await redis_client.delete(f"wallet:host:{host.id}")

    return {"event_id": event.id, "message": "Event created successfully"}

@router.delete("/event/{event_id}")
async def delete_event(host: host_dependency, db: db_dependency, event_id: int):
    HOSTING_FEE = 500
    event = db.query(Events).filter(Events.id == event_id, Events.host_id == host.id).first()

    if not event:
        raise HTTPException(404, "Event not found")
    wallet = db.query(Wallets).filter(Wallets.owner_type == "host", Wallets.owner_id == host.id).first()

    if wallet:
        wallet.balance += HOSTING_FEE

    db.delete(event)
    db.commit()

    await redis_client.delete(f"host_events:{host.id}")
    await redis_client.delete(f"wallet:host:{host.id}")

    return {"message": "Event deleted successfully"}

@router.put("/event/{event_id}")
async def update_event(event_id: int, host: host_dependency, db: db_dependency, event_request: EventRequest):

    event = db.query(Events).filter(Events.id == event_id,Events.host_id == host.id).first()

    if not event:
        raise HTTPException(404, "Event not found")

    event.title = event_request.title
    event.venue = event_request.venue
    event.date = event_request.date
    diff = event_request.seats - event.seats
    event.available_seats += diff
    event.seats = event_request.seats

    event.ticket_price = event_request.ticket_price

    db.commit()

    return {"message": "Event updated"}


@router.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    host = authenticate_host(form_data.username, form_data.password, db)

    if not host:
        raise HTTPException(status_code = 401, detail = "Invalid credentials")
    user_type = "host"
    access_token = create_access_token(
        entity_id=host.id,
        entity_type="host",
        role="host"
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "type": user_type
    }
