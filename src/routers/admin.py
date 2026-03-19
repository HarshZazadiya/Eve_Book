from jose import jwt
from model import Users
from typing import Annotated
from database import SessionLocal
from sqlalchemy.orm import Session
from AI.tools.admin_tools import (
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
)
from model import Events, Users, Hosts, Bookings, Wallets
from fastapi import APIRouter, Depends, HTTPException, Body
from routers.auth import oauth2_bearer, SECRET_KEY, ALGORITHM

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
async def get_current_admin(token: Annotated[str, Depends(oauth2_bearer)], db: db_dependency):
    """
    Verify that the current user is an admin
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Check if role is admin
        if payload.get("role") != "admin":
            raise HTTPException(status_code = 403, detail = "Admin access required")

        # Get admin from database
        admin = db.query(Users).filter(Users.id == payload.get("id")).first()

        if not admin:
            raise HTTPException(status_code = 401, detail = "Admin not found")

        if admin.role != "admin":
            raise HTTPException(status_code = 403, detail = "User is no longer admin")

        return admin
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code = 401, detail = "Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code = 401, detail = "Invalid token")
    except Exception as e:
        raise HTTPException(status_code = 401, detail = f"Authentication error : {str(e)}")

admin_dependency = Annotated[Users, Depends(get_current_admin)]

# ============================
# ADMIN ROUTES
# ============================

@router.post("/create-admin")
async def create_admin(email: str = Body(...), setup_key: str = Body(...)):
    """
    Promote a user to admin.
    This endpoint does NOT require admin authentication (uses setup key).
    """
    
    result = promote_to_admin.invoke({
        "email" : email,
        "setup_key" : setup_key,
        "admin_id" : 0  # Special case - setup key used instead of admin auth
    })
    
    if "error" in result:
        raise HTTPException(status_code = 400, detail = result["error"])
    
    return result


@router.get("/users")
async def get_users(admin: admin_dependency):
    """
    Get all regular users in the system.
    Admin only.
    """
    result = get_all_users.invoke({
        "admin_id" : admin.id
    })
    
    if "error" in result:
        raise HTTPException(status_code = 403, detail = result["error"])
    
    return result


@router.get("/hosts")
async def get_hosts(admin : admin_dependency):
    """
    Get all hosts in the system.
    Admin only.
    """
    result = get_all_hosts.invoke({
        "admin_id" : admin.id
    })
    
    if "error" in result:
        raise HTTPException(status_code = 403, detail = result["error"])
    
    return result


@router.delete("/event/{event_id}")
async def delete_event(event_id : int,  admin : admin_dependency):
    """
    Delete an event by ID and process refunds.
    Admin only.
    """
    result = delete_event_by_id.invoke({
        "event_id" : event_id,
        "admin_id" : admin.id
    })
    
    if "error" in result:
        raise HTTPException(status_code = 404, detail = result["error"])
    
    return result


@router.delete("/booking/{booking_id}")
async def delete_booking(booking_id: int,  admin: admin_dependency):
    """
    Delete a booking by ID and process refund.
    Admin only.
    """
    result = delete_booking_by_id.invoke({
        "booking_id" : booking_id,
        "admin_id" : admin.id
    })
    
    if "error" in result:
        raise HTTPException(status_code = 404, detail = result["error"])
    
    return result


@router.post("/demote-host/{host_id}")
async def demote_host(host_id : int,  admin : admin_dependency):
    """
    Demote a host back to regular user.
    Admin only.
    """
    result = demote_host_by_id.invoke({
        "host_id" : host_id,
        "admin_id" : admin.id
    })
    
    if "error" in result:
        raise HTTPException(status_code = 400, detail = result["error"])
    
    return result


@router.get("/events")
async def get_events(admin: admin_dependency):
    """
    Get all events in the system with host details.
    Admin only.
    """
    result = get_all_events.invoke({
        "admin_id" : admin.id
    })
    
    if "error" in result:
        raise HTTPException(status_code = 403, detail = result["error"])
    
    return result


@router.get("/bookings")
async def get_bookings(admin: admin_dependency):
    """
    Get all bookings in the system.
    Admin only.
    """
    result = get_all_bookings.invoke({
        "admin_id" : admin.id
    })
    
    if "error" in result:
        raise HTTPException(status_code = 403, detail = result["error"])
    
    return result


@router.get("/wallets")
async def get_wallets(admin : admin_dependency):
    """
    Get all wallets in the system.
    Admin only.
    """
    result = get_all_wallets.invoke({
        "admin_id" : admin.id
    })
    
    if "error" in result:
        raise HTTPException(status_code = 403, detail = result["error"])
    
    return result


@router.get("/promotions")
async def get_promotions(admin : admin_dependency):
    """
    Get all host promotion records.
    Admin only.
    """
    result = get_all_promotions.invoke({
        "admin_id" : admin.id
    })
    
    if "error" in result:
        raise HTTPException(status_code = 403, detail = result["error"])
    
    return result


@router.get("/booking-transactions")
async def get_booking_transactions(admin : admin_dependency):
    """
    Get all booking payment transactions.
    Admin only.
    """
    result = get_all_booking_transactions.invoke({
        "admin_id" : admin.id
    })
    
    if "error" in result:
        raise HTTPException(status_code = 403, detail = result["error"])
    
    return result


@router.get("/hosting-transactions")
async def get_hosting_transactions(admin : admin_dependency):
    """
    Get all hosting fee transactions.
    Admin only.
    """
    result = get_all_hosting_transactions.invoke({
        "admin_id" : admin.id
    })
    
    if "error" in result:
        raise HTTPException(status_code = 403, detail = result["error"])
    
    return result


# ============================
# DEBUG/HEALTH ENDPOINTS
# ============================

@router.get("/check-auth")
async def check_admin_auth(admin : admin_dependency):
    """
    Check if current user is authenticated as admin.
    Useful for debugging.
    """
    return {
        "id" : admin.id,
        "username" : admin.username,
        "email" : admin.email,
        "role" : admin.role,
        "is_admin" : True
    }

@router.get("/stats")
async def get_stats(admin: admin_dependency):
    """Get system statistics - returns ONLY real data"""
    result = get_system_stats.invoke({
        "admin_id": admin.id
    })
    
    if "error" in result:
        raise HTTPException(status_code=403, detail=result["error"])
    
    return result