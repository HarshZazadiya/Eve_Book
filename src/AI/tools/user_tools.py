from langchain_core.tools import tool
import json
from database import SessionLocal
from model import Users, Events, Bookings, Wallets, Hosts, HostPromotions

@tool
def get_user_profile(authenticated_user_id: int) -> dict:
    """
    Get your profile information.
    
    Args:
        authenticated_user_id: Your user ID
    
    Returns:
        Your profile details
    """
    db = SessionLocal()
    try:
        user = db.query(Users).filter(Users.id == authenticated_user_id).first()
        if not user:
            return {"error": "User not found"}
        
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role
        }
    finally:
        db.close()


@tool
def get_all_available_events() -> list:
    """
    Get all events available in the system.
    Returns list of events with basic details.
    """
    db = SessionLocal()
    try:
        events = db.query(Events).all()
        
        result = []
        for event in events:
            host = db.query(Hosts).filter(Hosts.id == event.host_id).first()
            result.append({
                "id": event.id,
                "title": event.title,
                "venue": event.venue,
                "date": str(event.date),
                "available_seats": event.available_seats,
                "total_seats": event.seats,
                "ticket_price": event.ticket_price,
                "host": host.company_name if host else f"Host {event.host_id}"
            })
        
        return result
    finally:
        db.close()


@tool
def get_user_bookings(authenticated_user_id: int) -> list:
    """
    Get all your bookings.
    
    Args:
        authenticated_user_id: Your user ID
    
    Returns:
        List of your bookings
    """
    db = SessionLocal()
    try:
        bookings = db.query(Bookings).filter(
            Bookings.user_id == authenticated_user_id
        ).all()
        
        result = []
        for b in bookings:
            event = db.query(Events).filter(Events.id == b.event_id).first()
            result.append({
                "booking_id": b.id,
                "event_id": b.event_id,
                "event_title": event.title if event else "Unknown",
                "ticket_count": b.ticket_count,
                "booking_date": str(b.created_at) if hasattr(b, 'created_at') else None
            })
        
        return result
    finally:
        db.close()


@tool
def book_event_for_user(event_id: int, authenticated_user_id: int) -> dict:
    """
    Book a ticket for an event.
    
    Args:
        event_id: ID of event to book
        authenticated_user_id: Your user ID
    
    Returns:
        Booking confirmation
    """
    db = SessionLocal()
    try:
        # Get event
        event = db.query(Events).filter(Events.id == event_id).first()
        if not event:
            return {"error": "Event not found"}
        
        if event.available_seats < 1:
            return {"error": "No seats available"}
        
        # Check if already booked
        existing = db.query(Bookings).filter(
            Bookings.user_id == authenticated_user_id,
            Bookings.event_id == event_id
        ).first()
        
        if existing:
            return {"error": "You have already booked this event"}
        
        # Check wallet
        wallet = db.query(Wallets).filter(
            Wallets.owner_type == "user",
            Wallets.owner_id == authenticated_user_id
        ).first()
        
        if not wallet or wallet.balance < event.ticket_price:
            return {"error": f"Insufficient balance. Need ₹{event.ticket_price}"}
        
        # Process booking
        wallet.balance -= event.ticket_price
        event.available_seats -= 1
        
        booking = Bookings(
            user_id=authenticated_user_id,
            event_id=event_id,
            ticket_count=1
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)
        
        return {
            "message": f"Successfully booked {event.title}",
            "booking_id": booking.id,
            "event": event.title
        }
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


@tool
def cancel_user_booking(booking_id: int, authenticated_user_id: int) -> dict:
    """
    Cancel a booking and get refund.
    
    Args:
        booking_id: ID of booking to cancel
        authenticated_user_id: Your user ID
    
    Returns:
        Cancellation confirmation
    """
    db = SessionLocal()
    try:
        booking = db.query(Bookings).filter(
            Bookings.id == booking_id,
            Bookings.user_id == authenticated_user_id
        ).first()
        
        if not booking:
            return {"error": "Booking not found"}
        
        event = db.query(Events).filter(Events.id == booking.event_id).first()
        if not event:
            return {"error": "Event not found"}
        
        # Refund (ticket price from event)
        wallet = db.query(Wallets).filter(
            Wallets.owner_type == "user",
            Wallets.owner_id == authenticated_user_id
        ).first()
        
        if wallet:
            wallet.balance += event.ticket_price
        
        event.available_seats += booking.ticket_count
        db.delete(booking)
        db.commit()
        
        return {"message": f"Booking cancelled. ₹{event.ticket_price} refunded."}
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


@tool
def promote_user_to_host(authenticated_user_id: int) -> dict:
    """
    Promote yourself to host (costs ₹10,000).
    
    Args:
        authenticated_user_id: Your user ID
    
    Returns:
        Promotion confirmation
    """
    PROMOTION_FEE = 10000
    
    db = SessionLocal()
    try:
        user = db.query(Users).filter(Users.id == authenticated_user_id).first()
        if not user:
            return {"error": "User not found"}
        
        if user.role == "host":
            return {"error": "You are already a host"}
        
        # Check wallet
        wallet = db.query(Wallets).filter(
            Wallets.owner_type == "user",
            Wallets.owner_id == authenticated_user_id
        ).first()
        
        if not wallet or wallet.balance < PROMOTION_FEE:
            return {"error": f"Insufficient balance. Need ₹{PROMOTION_FEE}"}
        
        # Process promotion
        wallet.balance -= PROMOTION_FEE
        user.role = "host"
        
        # Create host record
        new_host = Hosts(
            company_name=user.username,
            email=user.email,
            hashed_password=user.hashed_password,
            is_fee_paid=True,
            user_id=user.id
        )
        db.add(new_host)
        db.flush()
        
        # Transfer wallet to host
        wallet.owner_type = "host"
        wallet.owner_id = new_host.id
        
        # Record promotion
        promotion = HostPromotions(
            user_id=user.id,
            amount=PROMOTION_FEE,
            status="success"
        )
        db.add(promotion)
        
        db.commit()
        
        return {"message": "Successfully promoted to host!"}
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


user_tools = [
    get_user_profile,
    get_all_available_events,
    get_user_bookings,
    book_event_for_user,
    cancel_user_booking,
    promote_user_to_host
]