from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated
from sqlalchemy.orm import Session
from redis.asyncio import Redis
import json
from database import SessionLocal
from routers.auth import get_current_user
from model import HostPromotions, Hosts, Users, Events, Bookings, Wallets, BookingPayments
import os
import redis.asyncio as redis

router = APIRouter(
    prefix="/user",
    tags=["User"],
)

# ---------------- Redis ----------------
REDIS_URL = os.getenv("REDIS_URL")
redis_client = redis.from_url(REDIS_URL, decode_responses=True) if REDIS_URL else None

EVENTS_LIST_KEY = "events_list"

def user_key(user_id: int):
    return f"user:{user_id}"

def user_events_key(user_id: int):
    return f"my_events:{user_id}"

# ---------------- DB Dependency ----------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[Users, Depends(get_current_user)]

# ---------------- Serialization ----------------
def serialize_event(event: Events):
    return {
        "id": event.id,
        "title": event.title,
        "venue": event.venue,   # ADD THIS
        "date": event.date.isoformat() if event.date else None,
        "available_seats": event.available_seats,
        "host_id": event.host_id,
        "ticket_price": event.ticket_price
    }


def serialize_booking(booking: Bookings):
    return {
        "booking_id" : booking.id,
        "event_id" : booking.event_id,
        "ticket_count" : booking.ticket_count
    }

# ---------------- Routes ----------------
@router.get("/")
async def get_user_info(user: user_dependency):
    key = user_key(user.id)

    if redis_client:
        cached = await redis_client.get(key)
    else:
        cached = None

    if cached:
        return json.loads(cached)

    data = {
        "id" : user.id,
        "username" : user.username,
        "email" : user.email
    }
    if redis_client:
        await redis_client.set(key, json.dumps(data), ex = 300)
    return data


@router.get("/events")
async def get_all_events(db: db_dependency, user: user_dependency):

    cached = await redis_client.get(EVENTS_LIST_KEY)
    if cached:
        return json.loads(cached)

    events = db.query(Events).all()
    if not events:
        raise HTTPException(status_code = 404, detail = "No events found")

    serialized = [serialize_event(e) for e in events]
    if redis_client:
        await redis_client.set(EVENTS_LIST_KEY, json.dumps(serialized), ex = 5)
    return serialized


@router.get("/myEvents")
async def get_my_events(user: user_dependency, db: db_dependency):

    bookings = db.query(Bookings).filter(Bookings.user_id == user.id).all()

    serialized = [serialize_booking(b) for b in bookings]
    return serialized

@router.post("/promote-to-host")
async def promote_to_host(current_user: user_dependency, db: db_dependency):
    user = db.query(Users).filter(Users.id == current_user.id).first()
    PROMOTION_FEE = 10000
    wallet = db.query(Wallets).filter(Wallets.owner_type == "user", Wallets.owner_id == user.id).first()

    if not wallet or wallet.balance < PROMOTION_FEE:
        raise HTTPException(403, "Insufficient balance")
    wallet.balance -= PROMOTION_FEE

    user.role = "host"

    new_host = Hosts(
        company_name = user.username,
        email = user.email,
        hashed_password = user.hashed_password,
        is_fee_paid = True,
        user_id = user.id 
    )

    db.add(new_host)
    db.flush()

    wallet.owner_type = "host"
    wallet.owner_id = new_host.id

    promotion = HostPromotions(
        user_id = user.id,
        amount = PROMOTION_FEE,
        status = "success"
    )

    db.add(promotion)

    db.commit()

    return {"message": "User promoted to host successfully"}


@router.post("/event/{event_id}")
async def book_event(event_id: int, user: user_dependency, db: db_dependency):
    event = db.query(Events).filter(Events.id == event_id).with_for_update().first()
    if not event:
        raise HTTPException(404, "Event not found")

    BOOKING_FEE = event.ticket_price
    if event.available_seats < 1:
        raise HTTPException(400, "No seats available")
    existing = db.query(Bookings).filter(Bookings.user_id == user.id, Bookings.event_id == event_id).first()
    if existing:
        raise HTTPException(400, "Already booked")

    wallet = db.query(Wallets).filter(Wallets.owner_type == "user", Wallets.owner_id == user.id).with_for_update().first()
    if not wallet or wallet.balance < BOOKING_FEE:
        raise HTTPException(403, "Insufficient balance")

    host = db.query(Hosts).filter(Hosts.id == event.host_id).with_for_update().first()
    if not host:
        raise HTTPException(404, "Host not found")
    host_wallet = db.query(Wallets).filter(Wallets.owner_type == "host", Wallets.owner_id == host.id).with_for_update().first()
    if not host_wallet:
        raise HTTPException(404, "Host wallet not found")
    
    host_wallet.balance += BOOKING_FEE

    wallet.balance -= BOOKING_FEE
    event.available_seats -= 1

    booking = Bookings(
        user_id = user.id,
        event_id = event_id,
        ticket_count = 1
    )

    db.add(booking)
    db.flush()

    payment = BookingPayments(
        user_id = user.id,
        booking_id = booking.id,
        amount = BOOKING_FEE,
        status = "success"
    )

    db.add(payment)
    db.commit()

    if redis_client:
        await redis_client.delete(
            EVENTS_LIST_KEY,
            user_events_key(user.id),
            f"wallet:user:{user.id}"
        )

    return {"message": "Event booked successfully"}


@router.delete("/booking/{booking_id}")
async def cancel_event(booking_id: int, user: user_dependency, db: db_dependency):
    booking = db.query(Bookings).filter(Bookings.id == booking_id, Bookings.user_id == user.id).first()

    if not booking:
        raise HTTPException(404, "Booking not found")

    event = db.query(Events).filter(Events.id == booking.event_id).with_for_update().first()

    if not event:
        raise HTTPException(404, "Event not found")

    wallet = db.query(Wallets).filter(Wallets.owner_type == "user", Wallets.owner_id == user.id).with_for_update().first()

    if not wallet:
        raise HTTPException(404, "Wallet not found")

    payment = db.query(BookingPayments).filter(BookingPayments.booking_id == booking.id).first()

    if payment:
        wallet.balance += payment.amount
        payment.status = "refunded"
        db.delete(payment)

    event.available_seats += booking.ticket_count
    host = db.query(Hosts).filter(Hosts.id == event.host_id).with_for_update().first()

    if not host:
        raise HTTPException(404, "Host not found")
    host_wallet = db.query(Wallets).filter(Wallets.owner_type == "host", Wallets.owner_id == host.id).with_for_update().first()
    if host_wallet:
        host_wallet.balance -= payment.amount

    db.delete(booking)

    try:
        db.commit()
    except:
        db.rollback()
        raise

    if redis_client:
        await redis_client.delete(
            EVENTS_LIST_KEY,
            user_events_key(user.id),
            f"wallet:user:{user.id}"
        )

    return {"message": "Event cancelled successfully"}
