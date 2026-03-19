import os
from database import SessionLocal
from sqlalchemy.orm import Session
from langchain_core.tools import tool
from model import Users, Hosts, Events, Bookings, Wallets, BookingPayments, HostingPayments, HostPromotions

# ==================================================
# HELPER FUNCTION (NOT A TOOL)
# ==================================================

def refund_booking_logic(db: Session, booking: Bookings):
    """Helper function to refund a booking - not exposed as tool"""
    wallet = db.query(Wallets).filter(Wallets.owner_type == "user",  Wallets.owner_id == booking.user_id).first()
    
    payment = db.query(BookingPayments).filter( BookingPayments.booking_id == booking.id).first()
    
    event = db.query(Events).filter(Events.id == booking.event_id).first()
    host = db.query(Hosts).filter(Hosts.id == event.host_id).first() if event else None
    host_wallet = db.query(Wallets).filter(Wallets.owner_type == "host",  Wallets.owner_id == host.id).first() if host else None

    if wallet and payment:
        wallet.balance += payment.amount
        db.delete(payment)

    if host and host_wallet and payment:
        host_wallet.balance -= payment.amount

    if event:
        event.available_seats += booking.ticket_count

    db.delete(booking)


# ==================================================
# VERIFY ADMIN FUNCTION
# ==================================================
def verify_admin(db: Session, admin_id: int) -> bool:
    """Verify that the user is an admin"""
    admin = db.query(Users).filter(Users.id == admin_id,  Users.role == "admin").first()
    return admin is not None


# ==================================================
# ADMIN TOOLS - WITH PROPER AUTHENTICATION
# ==================================================

@tool
def promote_to_admin(email: str, setup_key: str, admin_id: int) -> dict:
    """
    Promote a user to admin role.
    Requires email, setup key, and admin authentication.
    
    Args:
        email: Email of user to promote
        setup_key: Setup key for verification
        admin_id: ID of admin performing action (automatically provided)
    """
    ADMIN_SETUP_KEY = os.environ.get("ADMIN_SETUP_KEY")
    from database import SessionLocal
    
    # Verify setup key
    if setup_key != ADMIN_SETUP_KEY:
        return {"error": "Invalid setup key"}
    
    db = SessionLocal()
    try:
        # Verify caller is admin
        if not verify_admin(db, admin_id):
            return {"error": "Admin access required"}
        
        user = db.query(Users).filter(Users.email == email).first()
        
        if not user:
            return {"error": "User not found"}
        
        user.role = "admin"
        db.commit()
        return {"message": f"{email} promoted to admin"}
    finally:
        db.close()


@tool
def get_all_users(admin_id: int) -> dict:
    """
    Get all regular users in the system.
    Admin only.
    
    Args:
        admin_id: ID of admin performing action (automatically provided)
    """
    from database import SessionLocal
    
    db = SessionLocal()
    try:
        # Verify caller is admin
        if not verify_admin(db, admin_id):
            return {"error": "Admin access required"}
        
        users = db.query(Users).filter(Users.role == "user").all()
        
        return {
            "total_users": len(users),
            "users": [
                {
                    "id": u.id,
                    "username": u.username,
                    "email": u.email,
                    "role": u.role
                }
                for u in users
            ]
        }
    finally:
        db.close()


@tool
def get_all_hosts(admin_id: int) -> dict:
    """
    Get all hosts in the system.
    Admin only.
    
    Args:
        admin_id: ID of admin performing action (automatically provided)
    """
    from database import SessionLocal
    
    db = SessionLocal()
    try:
        # Verify caller is admin
        if not verify_admin(db, admin_id):
            return {"error": "Admin access required"}
        
        # Get all hosts directly
        hosts = db.query(Hosts).all()
        
        result = []
        for host in hosts:
            result.append({
                "id": host.id,
                "user_id": host.user_id,
                "email": host.email,
                "company_name": host.company_name,
                "is_fee_paid": host.is_fee_paid
            })
        
        return {
            "total_hosts": len(result),
            "hosts": result
        }
    except Exception as e:
        return {"error": f"Failed to fetch hosts: {str(e)}"}
    finally:
        db.close()


@tool
def delete_event_by_id(event_id: int, admin_id: int) -> dict:
    """
    Delete an event by ID and process refunds for all bookings.
    Admin only.
    
    Args:
        event_id: ID of event to delete
        admin_id: ID of admin performing action (automatically provided)
    """
    from database import SessionLocal
    
    db = SessionLocal()
    try:
        # Verify caller is admin
        if not verify_admin(db, admin_id):
            return {"error": "Admin access required"}
        
        event = db.query(Events).filter(Events.id == event_id).first()

        if not event:
            return {"error": "Event not found"}

        bookings = db.query(Bookings).filter(Bookings.event_id == event_id).all()

        for booking in bookings:
            refund_booking_logic(db, booking)

        # Delete document file if exists
        if event.document_path:
            file_path = os.path.join("uploads", event.document_path)
            if os.path.exists(file_path):
                os.remove(file_path)

        db.delete(event)
        db.commit()
        return {"message": f"Event {event_id} deleted and refunds processed"}
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


@tool
def delete_booking_by_id(booking_id: int, admin_id: int) -> dict:
    """
    Delete a booking by ID and process refund.
    Admin only.
    
    Args:
        booking_id: ID of booking to delete
        admin_id: ID of admin performing action (automatically provided)
    """
    from database import SessionLocal
    
    db = SessionLocal()
    try:
        # Verify caller is admin
        if not verify_admin(db, admin_id):
            return {"error": "Admin access required"}
        
        booking = db.query(Bookings).filter(Bookings.id == booking_id).first()

        if not booking:
            return {"error": "Booking not found"}

        refund_booking_logic(db, booking)
        db.commit()
        return {"message": f"Booking {booking_id} deleted & refunded"}
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


@tool
def demote_host_by_id(host_id: int, admin_id: int) -> dict:
    """
    Demote a host back to regular user.
    Cancels all their events, processes refunds, transfers wallet balance.
    Admin only.
    
    Args:
        host_id: ID of host to demote
        admin_id: ID of admin performing action (automatically provided)
    """
    from database import SessionLocal
    
    db = SessionLocal()
    try:
        # Verify caller is admin
        if not verify_admin(db, admin_id):
            return {"error": "Admin access required"}
        
        host = db.query(Hosts).filter(Hosts.id == host_id).first()

        if not host:
            return {"error": "Host not found"}

        host_wallet = db.query(Wallets).filter(
            Wallets.owner_type == "host", 
            Wallets.owner_id == host.id
        ).first()

        # Process all events by this host
        events = db.query(Events).filter(Events.host_id == host.id).all()

        for event in events:
            # Delete document file
            if event.document_path:
                file_path = os.path.join("uploads", event.document_path)
                if os.path.exists(file_path):
                    os.remove(file_path)

            # Cancel all bookings for this event
            bookings = db.query(Bookings).filter(Bookings.event_id == event.id).all()
            for booking in bookings:
                refund_booking_logic(db, booking)

            db.delete(event)

        # Update user role
        if host.user_id:
            user = db.query(Users).filter(Users.id == host.user_id).first()
            if user:
                user.role = "user"

        # Transfer wallet balance to user wallet
        if host_wallet and host.user_id:
            user_wallet = db.query(Wallets).filter(
                Wallets.owner_type == "user", 
                Wallets.owner_id == host.user_id
            ).first()

            if user_wallet:
                user_wallet.balance += host_wallet.balance
                db.delete(host_wallet)

        db.delete(host)
        db.commit()
        return {"message": f"Host {host_id} demoted successfully"}

    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


@tool
def get_all_events(admin_id: int) -> dict:
    """
    Get all events in the system with host details.
    Admin only.
    
    Args:
        admin_id: ID of admin performing action (automatically provided)
    """
    from database import SessionLocal
    
    db = SessionLocal()
    try:
        # Verify caller is admin
        if not verify_admin(db, admin_id):
            return {"error": "Admin access required"}
        
        events = db.query(Events).all()
        result = []

        for event in events:
            host = db.query(Hosts).filter(Hosts.id == event.host_id).first()
            host_user = db.query(Users).filter(Users.id == host.user_id).first() if host else None
            
            result.append({
                "event_id": event.id,
                "title": event.title,
                "venue": event.venue,
                "date": str(event.date),
                "total_seats": event.seats,
                "available_seats": event.available_seats,
                "ticket_price": event.ticket_price,
                "host_id": event.host_id,
                "host_company": host.company_name if host else None,
                "host_email": host.email if host else None,
                "host_username": host_user.username if host_user else None,
                "more_details": f"/uploads/{event.document_path}" if event.document_path else None,
                "document_available": bool(event.document_path)
            })
        
        return {
            "total_events": len(result),
            "events": result
        }
    finally:
        db.close()


@tool
def get_all_bookings(admin_id: int) -> dict:
    """
    Get all bookings in the system.
    Admin only.
    
    Args:
        admin_id: ID of admin performing action (automatically provided)
    """
    from database import SessionLocal
    
    db = SessionLocal()
    try:
        # Verify caller is admin
        if not verify_admin(db, admin_id):
            return {"error": "Admin access required"}
        
        bookings = db.query(Bookings).all()
        result = []
        
        for b in bookings:
            user = db.query(Users).filter(Users.id == b.user_id).first()
            event = db.query(Events).filter(Events.id == b.event_id).first()
            
            result.append({
                "booking_id": b.id,
                "user_id": b.user_id,
                "username": user.username if user else "Unknown",
                "user_email": user.email if user else "Unknown",
                "event_id": b.event_id,
                "total_amount" : event.ticket_price * b.ticket_count,
                "event_title": event.title if event else "Unknown",
                "ticket_count": b.ticket_count
            })
        
        return {
            "total_bookings": len(result),
            "bookings": result
        }
    finally:
        db.close()


@tool
def get_all_wallets(admin_id: int) -> dict:
    """
    Get all wallets in the system.
    Admin only.
    
    Args:
        admin_id: ID of admin performing action (automatically provided)
    """
    from database import SessionLocal
    
    db = SessionLocal()
    try:
        # Verify caller is admin
        if not verify_admin(db, admin_id):
            return {"error": "Admin access required"}
        
        wallets = db.query(Wallets).filter(Wallets.owner_type != "admin").all()
        result = []
        
        for w in wallets:
            owner_info = {}
            if w.owner_type == "user":
                user = db.query(Users).filter(Users.id == w.owner_id).first()
                owner_info = {
                    "username": user.username if user else "Unknown",
                    "email": user.email if user else "Unknown",
                    "role": user.role if user else "Unknown"
                }
            elif w.owner_type == "host":
                host = db.query(Hosts).filter(Hosts.id == w.owner_id).first()
                owner_info = {
                    "company_name": host.company_name if host else "Unknown",
                    "email": host.email if host else "Unknown"
                }
            
            result.append({
                "owner_type": w.owner_type,
                "owner_id": w.owner_id,
                "balance": w.balance,
                **owner_info
            })
        
        return {
            "total_wallets": len(result),
            "wallets": result
        }
    finally:
        db.close()


@tool
def get_all_promotions(admin_id: int) -> dict:
    """
    Get all host promotion records.
    Admin only.
    
    Args:
        admin_id: ID of admin performing action (automatically provided)
    """
    from database import SessionLocal
    
    db = SessionLocal()
    try:
        # Verify caller is admin
        if not verify_admin(db, admin_id):
            return {"error": "Admin access required"}
        
        promotions = db.query(HostPromotions).all()
        result = []
        
        for p in promotions:
            user = db.query(Users).filter(Users.id == p.user_id).first()
            host = db.query(Hosts).filter(Hosts.user_id == p.user_id).first() if user else None
            
            result.append({
                "promotion_id": p.id,
                "user_id": p.user_id,
                "username": user.username if user else "Unknown",
                "company_name": host.company_name if host else None,
                "amount": p.amount,
                "status": p.status,
                "created_at": str(p.created_at)
            })
        
        return {
            "total_promotions": len(result),
            "promotions": result
        }
    finally:
        db.close()


@tool
def get_all_booking_transactions(admin_id: int) -> dict:
    """
    Get all booking payment transactions.
    Admin only.
    
    Args:
        admin_id: ID of admin performing action (automatically provided)
    """
    from database import SessionLocal
    
    db = SessionLocal()
    try:
        # Verify caller is admin
        if not verify_admin(db, admin_id):
            return {"error": "Admin access required"}
        
        transactions = db.query(BookingPayments).all()
        result = []
        
        for t in transactions:
            user = db.query(Users).filter(Users.id == t.user_id).first()
            booking = db.query(Bookings).filter(Bookings.id == t.booking_id).first()
            event = db.query(Events).filter(Events.id == booking.event_id).first() if booking else None
            
            result.append({
                "transaction_id": t.id,
                "booking_id": t.booking_id,
                "user_id": t.user_id,
                "username": user.username if user else "Unknown",
                "event_title": event.title if event else "Unknown",
                "amount": t.amount,
                "status": t.status,
                "created_at": str(t.created_at)
            })
        
        return {
            "total_transactions": len(result),
            "transactions": result
        }
    finally:
        db.close()


@tool
def get_all_hosting_transactions(admin_id: int) -> dict:
    """
    Get all hosting fee transactions.
    Admin only.
    
    Args:
        admin_id: ID of admin performing action (automatically provided)
    """
    from database import SessionLocal
    
    db = SessionLocal()
    try:
        # Verify caller is admin
        if not verify_admin(db, admin_id):
            return {"error": "Admin access required"}
        
        transactions = db.query(HostingPayments).all()
        result = []
        
        for t in transactions:
            host = db.query(Hosts).filter(Hosts.id == t.host_id).first()
            user = db.query(Users).filter(Users.id == host.user_id).first() if host else None
            
            result.append({
                "transaction_id": t.id,
                "host_id": t.host_id,
                "company_name": host.company_name if host else "Unknown",
                "username": user.username if user else "Unknown",
                "amount": t.amount,
                "status": t.status,
                "created_at": str(t.created_at)
            })
        
        return {
            "total_transactions": len(result),
            "transactions": result
        }
    finally:
        db.close()

@tool
def get_system_stats(admin_id: int) -> dict:
    """
    [ADMIN ONLY] Get basic system statistics.
    
    Returns ONLY these exact metrics:
    - total_users: Number of regular users
    - total_hosts: Number of hosts
    - total_events: Number of events
    - total_bookings: Number of bookings
    - total_wallets: Number of wallets
    
    Args:
        admin_id: Your admin ID (automatically provided)
    
    Returns:
        Dictionary with exactly these 5 metrics
    """
    db = SessionLocal()
    try:
        # Verify admin
        admin = db.query(Users).filter(
            Users.id == admin_id, 
            Users.role == "admin"
        ).first()
        
        if not admin:
            return {"error": "Admin access required"}
        
        # Get only the stats that exist in database
        stats = {
            "total_users": db.query(Users).filter(Users.role == "user").count(),
            "total_hosts": db.query(Hosts).count(),
            "total_events": db.query(Events).count(),
            "total_bookings": db.query(Bookings).count(),
            "total_wallets": db.query(Wallets).count()
        }
        
        return stats
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()

# ==================================================
# TOOLKIT LIST FOR AGENT
# ==================================================

admin_tools = [
    promote_to_admin,
    get_all_users,
    get_all_hosts,
    delete_event_by_id,
    delete_booking_by_id,
    demote_host_by_id,
    get_all_events,
    get_all_bookings,
    get_all_wallets,
    get_all_promotions,
    get_all_booking_transactions,
    get_all_hosting_transactions,
    get_system_stats
]