# AI/tools/host_tools.py
from langchain_core.tools import tool
import os
import json
import shutil
from datetime import datetime
from pathlib import Path
import redis.asyncio as redis
from typing import Optional
from sqlalchemy.orm import Session
from database import SessionLocal
from model import Events, Hosts, HostingPayments, BookingPayments, Bookings, Wallets
from AI.RAG import process_event_document, delete_event_documents

# --------------------------------------------------
# Configuration
# --------------------------------------------------
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

REDIS_URL = os.getenv("REDIS_URL")
redis_client = redis.from_url(REDIS_URL, decode_responses=True) if REDIS_URL else None

# --------------------------------------------------
# Helper Functions
# --------------------------------------------------
def get_host_by_id(host_id: int):
    """Get host by ID"""
    db = SessionLocal()
    try:
        return db.query(Hosts).filter(Hosts.id == host_id).first()
    finally:
        db.close()

def get_host_wallet(host_id: int):
    """Get host wallet"""
    db = SessionLocal()
    try:
        return db.query(Wallets).filter(
            Wallets.owner_type == "host", 
            Wallets.owner_id == host_id
        ).first()
    finally:
        db.close()

def refund_booking(db: Session, booking: Bookings, host_id: int):
    """Refund a booking"""
    payment = db.query(BookingPayments).filter(
        BookingPayments.booking_id == booking.id
    ).first()
    
    user_wallet = db.query(Wallets).filter(
        Wallets.owner_type == "user", 
        Wallets.owner_id == booking.user_id
    ).first()
    
    host_wallet = db.query(Wallets).filter(
        Wallets.owner_type == "host", 
        Wallets.owner_id == host_id
    ).first()

    if payment and user_wallet:
        user_wallet.balance += payment.amount
        if host_wallet:
            host_wallet.balance -= payment.amount
        db.delete(payment)

    db.delete(booking)

# --------------------------------------------------
# HOST TOOLS
# --------------------------------------------------

@tool
def get_host_info(host_id: int) -> dict:
    """
    Get information about the current host.
    Requires host_id.
    """
    cache_key = f"host:{host_id}"
    
    # Try cache first
    if redis_client:
        import asyncio
        try:
            cached = asyncio.run(redis_client.get(cache_key))
            if cached:
                return json.loads(cached)
        except:
            pass
    
    db = SessionLocal()
    try:
        host = db.query(Hosts).filter(Hosts.id == host_id).first()
        if not host:
            return {"error": "Host not found"}
        
        data = {
            "id": host.id,
            "company_name": host.company_name,
            "email": host.email
        }
        
        # Cache it
        if redis_client:
            try:
                asyncio.run(redis_client.set(cache_key, json.dumps(data), ex=300))
            except:
                pass
        
        return data
    finally:
        db.close()


@tool
def get_host_events(host_id: int) -> list:
    """
    Get all events created by the host.
    Requires host_id.
    """
    cache_key = f"host_events:{host_id}"
    
    # Try cache first
    if redis_client:
        import asyncio
        try:
            cached = asyncio.run(redis_client.get(cache_key))
            if cached:
                return json.loads(cached)
        except:
            pass
    
    db = SessionLocal()
    try:
        events = db.query(Events).filter(Events.host_id == host_id).all()
        
        result = []
        for e in events:
            result.append({
                "id": e.id,
                "title": e.title,
                "venue": e.venue,
                "date": str(e.date),
                "seats": e.seats,
                "available_seats": e.available_seats,
                "ticket_price": e.ticket_price,
                "more_details": f"/uploads/{e.document_path}" if e.document_path else None
            })
        
        # Cache it
        if redis_client:
            try:
                asyncio.run(redis_client.set(cache_key, json.dumps(result), ex=10))
            except:
                pass
        
        return result
    finally:
        db.close()


@tool
def create_host_event(
    host_id: int,
    title: str,
    venue: str,
    date: str,
    seats: int,
    ticket_price: int,
    document_path: Optional[str] = None
) -> dict:
    """
    Create a new event as a host.
    Requires host_id, title, venue, date (YYYY-MM-DD), seats, ticket_price.
    Optional: document_path to an existing PDF file.
    """
    HOSTING_FEE = 500
    
    db = SessionLocal()
    try:
        # Check wallet balance
        wallet = db.query(Wallets).filter(
            Wallets.owner_type == "host", 
            Wallets.owner_id == host_id
        ).first()
        
        if not wallet or wallet.balance < HOSTING_FEE:
            return {"error": "Insufficient wallet balance (need ₹500)"}
        
        # Deduct fee
        wallet.balance -= HOSTING_FEE
        
        # Record payment
        payment = HostingPayments(
            host_id=host_id,
            amount=HOSTING_FEE,
            status="success"
        )
        db.add(payment)
        
        # Create event
        event = Events(
            title=title,
            venue=venue,
            date=datetime.strptime(date, "%Y-%m-%d").date(),
            seats=seats,
            available_seats=seats,
            host_id=host_id,
            ticket_price=ticket_price
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        
        # Handle document
        safe_title = title.replace(" ", "_").replace("/", "").replace("\\", "")
        filename = f"{host_id}_{event.id}_{safe_title}.pdf"
        file_path = os.path.join(UPLOAD_DIR, filename)
        host_name = db.query(Hosts).filter(Hosts.id == host_id).first().company_name
        if document_path and os.path.exists(document_path):
            # Copy provided document
            shutil.copy2(document_path, file_path)
        else:
            # Generate default PDF
            from reportlab.pdfgen import canvas
            c = canvas.Canvas(file_path)
            c.drawString(100, 820, f"Host: {host_name}")
            c.drawString(100, 800, f"Host ID: {host_id}")
            c.drawString(100, 780, f"Event: {title}")
            c.drawString(100, 760, f"Venue: {venue}")
            c.drawString(100, 740, f"Date: {date}")
            c.drawString(100, 720, f"Seats: {seats}")
            c.drawString(100, 700, f"Price: INR {ticket_price}")
            c.save()
        
        # Update event with document path
        event.document_path = filename
        db.commit()
        
        # Add to vector store
        process_event_document(event.id, file_path)
        
        # Clear cache
        if redis_client:
            import asyncio
            try:
                asyncio.run(redis_client.delete(f"host_events:{host_id}"))
            except:
                pass
        
        return {
            "event_id": event.id,
            "message": "Event created successfully"
        }
        
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


@tool
def delete_host_event(host_id: int, event_id: int) -> dict:
    """
    Delete an event created by the host.
    Requires host_id and event_id.
    Processes refunds for all bookings.
    """
    HOSTING_FEE = 500
    
    db = SessionLocal()
    try:
        event = db.query(Events).filter(
            Events.id == event_id,
            Events.host_id == host_id
        ).first()
        
        if not event:
            return {"error": "Event not found"}
        
        # Delete from vector store
        delete_event_documents(event_id)
        
        # Process all bookings
        bookings = db.query(Bookings).filter(Bookings.event_id == event.id).all()
        for booking in bookings:
            refund_booking(db, booking, host_id)
        
        # Refund hosting fee
        wallet = db.query(Wallets).filter(
            Wallets.owner_type == "host", 
            Wallets.owner_id == host_id
        ).first()
        if wallet:
            wallet.balance += HOSTING_FEE
        
        # Delete document file
        if event.document_path:
            file_path = os.path.join(UPLOAD_DIR, event.document_path)
            if os.path.exists(file_path):
                os.remove(file_path)
        
        db.delete(event)
        db.commit()
        
        # Clear cache
        if redis_client:
            import asyncio
            try:
                asyncio.run(redis_client.delete(f"host_events:{host_id}"))
            except:
                pass
        
        return {"message": "Event deleted successfully with refunds"}
        
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


@tool
def update_host_event(
    host_id: int,
    event_id: int,
    title: str,
    venue: str,
    date: str,
    seats: int,
    ticket_price: int
) -> dict:
    """
    Update an existing event's details.
    Requires host_id, event_id, and all event fields.
    """
    db = SessionLocal()
    try:
        event = db.query(Events).filter(
            Events.id == event_id,
            Events.host_id == host_id
        ).first()
        
        if not event:
            return {"error": "Event not found"}
        
        # Store old values
        old_title = event.title
        old_venue = event.venue
        old_date = event.date
        
        # Update fields
        diff = seats - event.seats
        event.title = title
        event.venue = venue
        event.date = datetime.strptime(date, "%Y-%m-%d").date()
        event.seats = seats
        event.available_seats += diff
        event.ticket_price = ticket_price
        
        db.commit()
        
        # Check if details changed
        details_changed = (
            old_title != title or
            old_venue != venue or
            old_date != event.date
        )
        
        if details_changed:
            # Remove old from vector store
            delete_event_documents(event_id)
            
            # Delete old PDF
            if event.document_path:
                old_path = os.path.join(UPLOAD_DIR, event.document_path)
                if os.path.exists(old_path):
                    os.remove(old_path)
            
            # Generate new PDF
            safe_title = title.replace(" ", "_").replace("/", "").replace("\\", "")
            filename = f"{host_id}_{event_id}_{safe_title}.pdf"
            file_path = os.path.join(UPLOAD_DIR, filename)
            
            from reportlab.pdfgen import canvas
            c = canvas.Canvas(file_path)
            c.drawString(100, 800, f"Event: {title}")
            c.drawString(100, 780, f"Venue: {venue}")
            c.drawString(100, 760, f"Date: {date}")
            c.drawString(100, 740, f"Seats: {seats}")
            c.drawString(100, 720, f"Price: ₹{ticket_price}")
            c.save()
            
            # Update database
            event.document_path = filename
            db.commit()
            
            # Add to vector store
            process_event_document(event_id, file_path)
        
        # Clear cache
        if redis_client:
            import asyncio
            try:
                asyncio.run(redis_client.delete(f"host_events:{host_id}"))
            except:
                pass
        
        return {"message": "Event updated successfully"}
        
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


@tool
def update_event_document(host_id: int, event_id: int, pdf_path: str) -> dict:
    """
    Update just the document for an event.
    Requires host_id, event_id, and path to new PDF file.
    """
    db = SessionLocal()
    try:
        event = db.query(Events).filter(
            Events.id == event_id,
            Events.host_id == host_id
        ).first()
        
        if not event:
            return {"error": "Event not found"}
        
        if not os.path.exists(pdf_path):
            return {"error": "PDF file not found"}
        
        # Remove old from vector store
        delete_event_documents(event_id)
        
        # Delete old PDF
        if event.document_path:
            old_path = os.path.join(UPLOAD_DIR, event.document_path)
            if os.path.exists(old_path):
                os.remove(old_path)
        
        # Save new PDF
        safe_title = event.title.replace(" ", "_").replace("/", "").replace("\\", "")
        filename = f"{host_id}_{event_id}_{safe_title}.pdf"
        file_path = os.path.join(UPLOAD_DIR, filename)
        
        shutil.copy2(pdf_path, file_path)
        
        # Update database
        event.document_path = filename
        db.commit()
        
        # Add to vector store
        process_event_document(event_id, file_path)
        
        return {"message": "Document updated successfully"}
        
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


# --------------------------------------------------
# Tool List
# --------------------------------------------------
host_tools = [
    get_host_info,
    get_host_events,
    create_host_event,
    delete_host_event,
    update_host_event,
    update_event_document
]