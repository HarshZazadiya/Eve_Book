from fastapi import APIRouter, Depends, HTTPException, Body
from typing import Annotated
from sqlalchemy.orm import Session
from database import SessionLocal
from model import Users, Hosts, Events, Bookings, Wallets, BookingPayments
from routers.auth import oauth2_bearer, SECRET_KEY, ALGORITHM
from jose import jwt
from model import HostingPayments
from model import HostingPayments, HostPromotions
router = APIRouter(prefix="/admin", tags=["Admin"])

# ---------------- DB ----------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]

# ---------------- ADMIN AUTH ----------------

async def get_current_admin(
    token: Annotated[str, Depends(oauth2_bearer)],
    db: db_dependency
):
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

    if payload.get("role") != "admin":
        raise HTTPException(403, "Admin only")

    admin = db.query(Users).filter(Users.id == payload.get("id")).first()

    if not admin:
        raise HTTPException(401, "Invalid admin")

    return admin

admin_dependency = Annotated[Users, Depends(get_current_admin)]

def refund_booking(db: Session, booking: Bookings):
    wallet = db.query(Wallets).filter(Wallets.owner_type == "user", Wallets.owner_id == booking.user_id).first()
    payment = db.query(BookingPayments).filter(BookingPayments.booking_id == booking.id).first()
    event = db.query(Events).filter(Events.id == booking.event_id).first()
    host = db.query(Hosts).filter(Hosts.id == event.host_id).first() if event else None
    host_wallet = db.query(Wallets).filter(Wallets.owner_type == "host", Wallets.owner_id == host.id).first() if host else None
    if wallet and payment:
        wallet.balance += payment.amount
        db.delete(payment)
    if host and host_wallet:
        host_wallet.balance -= payment.amount
    if event:
        event.available_seats += booking.ticket_count
    db.delete(booking)

# CREATE ADMIN

@router.post("/create-admin")
async def create_admin(db: db_dependency,email: str = Body(...),setup_key: str = Body(...)):
    from main import ADMIN_SETUP_KEY
    if setup_key != ADMIN_SETUP_KEY:
        raise HTTPException(403, "Invalid setup key")
    user = db.query(Users).filter(Users.email == email).first()
    if not user:
        raise HTTPException(404, "User not found")
    user.role = "admin"
    db.commit()
    return {"message": f"{email} promoted to admin"}

# VIEW USERS

@router.get("/users")
async def get_all_users(admin: admin_dependency, db: db_dependency):
    users = db.query(Users).all()

    return [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role
        }
        for u in users
    ]

# VIEW HOSTS

@router.get("/hosts")
async def get_all_hosts(admin: admin_dependency, db: db_dependency):
    hosts = db.query(Hosts).all()

    return [
        {
            "id": h.id,
            "company_name": h.company_name,
            "email": h.email
        }
        for h in hosts
    ]

# DELETE EVENT 

@router.delete("/event/{event_id}")
async def delete_event(event_id: int, admin: admin_dependency, db: db_dependency):

    event = db.query(Events).filter(Events.id == event_id).first()

    if not event:
        raise HTTPException(404, "Event not found")

    bookings = db.query(Bookings).filter(Bookings.event_id == event_id).all()

    for booking in bookings:
        refund_booking(db, booking)

    db.delete(event)
    db.commit()

    return {"message": "Event deleted and refunds processed"}

# DELETE BOOKING

@router.delete("/booking/{booking_id}")
async def delete_booking(booking_id: int, admin: admin_dependency, db: db_dependency):

    booking = db.query(Bookings).filter(Bookings.id == booking_id).first()

    if not booking:
        raise HTTPException(404, "Booking not found")

    refund_booking(db, booking)

    db.commit()

    return {"message": "Booking deleted & refunded"}

# DEMOTE HOST 

@router.post("/demote-host/{host_id}")
async def demote_host(host_id: int, admin: admin_dependency, db: db_dependency):
    host = db.query(Hosts).filter(Hosts.id == host_id).first()
    if not host:
        raise HTTPException(404, "Host not found")
    try:
        host_wallet = db.query(Wallets).filter(Wallets.owner_type == "host", Wallets.owner_id == host.id).first()


        events = db.query(Events).filter(Events.host_id == host.id).all()

        for event in events:
            bookings = db.query(Bookings).filter(Bookings.event_id == event.id).all()
            for booking in bookings:
                payment = db.query(BookingPayments).filter(BookingPayments.booking_id == booking.id).first()
                user_wallet = db.query(Wallets).filter(Wallets.owner_type == "user", Wallets.owner_id == booking.user_id).first()

                if payment and user_wallet:
                    user_wallet.balance += payment.amount
                    db.delete(payment)

                db.delete(booking)
            db.delete(event)

        if host.user_id and host_wallet:
            promotions = db.query(HostPromotions).filter(HostPromotions.user_id == host.user_id).all()
            for promo in promotions:
                if promo.amount and promo.amount > 0:
                    host_wallet.balance += promo.amount
                db.delete(promo)

        if host_wallet:
            host_payments = db.query(HostingPayments).filter(HostingPayments.host_id == host.id).all()
            for hp in host_payments:
                if hp.amount and hp.amount > 0:
                    host_wallet.balance += hp.amount
                db.delete(hp)

        if host.user_id:
            user = db.query(Users).filter(Users.id == host.user_id).first()
            if user:
                user.role = "user"

        if host_wallet and host.user_id:
            user_wallet = db.query(Wallets).filter(Wallets.owner_type == "user", Wallets.owner_id == host.user_id).first()
            if user_wallet:
                user_wallet.balance += host_wallet.balance
                db.delete(host_wallet)
            else:
                host_wallet.owner_type = "user"
                host_wallet.owner_id = host.user_id
        db.delete(host)
        db.commit()

        return {"message": "Host demoted successfully with full refunds"}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Failed to demote host: {str(e)}")

# VIEW ALL EVENTS

@router.get("/events")
async def get_all_events(admin: admin_dependency, db: db_dependency):
    events = db.query(Events).all()
    result = []
    for event in events:
        host = db.query(Hosts).filter(Hosts.id == event.host_id).first()
        result.append({
            "event_id": event.id,
            "title": event.title,
            "venue": event.venue,
            "date": event.date,
            "total_seats": event.seats,
            "available_seats": event.available_seats,
            "ticket_price": event.ticket_price,
            "host_company": host.company_name if host else None,
            "host_email": host.email if host else None
        })

    return result

# VIEW BOOKINGS

@router.get("/bookings")
async def get_all_bookings(admin: admin_dependency, db: db_dependency):
    bookings = db.query(Bookings).all()
    result = []
    for booking in bookings:
        user = db.query(Users).filter(Users.id == booking.user_id).first()
        event = db.query(Events).filter(Events.id == booking.event_id).first()
        payment = db.query(BookingPayments).filter(BookingPayments.booking_id == booking.id).first()

        result.append({
            "booking_id": booking.id,
            "user_username": user.username if user else None,
            "user_email": user.email if user else None,
            "event_title": event.title if event else None,
            "event_id": booking.event_id,
            "ticket_count": booking.ticket_count,
            "payment_amount": payment.amount if payment else None,
            "payment_status": payment.status if payment else None
        })

    return result

# get all wallets
# VIEW ALL WALLETS

@router.get("/wallets")
async def get_all_wallets(admin: admin_dependency, db: db_dependency):
    wallets = db.query(Wallets).all()
    result = []
    for wallet in wallets:
        if wallet.owner_type == "user":
            user = db.query(Users).filter(Users.id == wallet.owner_id).first()
            result.append({
                "owner_type": "user",
                "owner_id": wallet.owner_id,
                "username": user.username if user else None,
                "email": user.email if user else None,
                "balance": wallet.balance
            })
        elif wallet.owner_type == "host":
            host = db.query(Hosts).filter(Hosts.id == wallet.owner_id).first()
            result.append({
                "owner_type": "host",
                "owner_id": wallet.owner_id,
                "company_name": host.company_name if host else None,
                "email": host.email if host else None,
                "balance": wallet.balance
            })
    
    return result