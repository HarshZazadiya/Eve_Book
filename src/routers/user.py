from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated
from sqlalchemy.orm import Session
from database import SessionLocal
from routers.auth import get_current_user
from model import Users

# Import AI tools
from AI.tools.user_tools import (
    get_user_profile,
    get_all_available_events,
    get_user_bookings,
    promote_user_to_host,
    book_event_for_user,
    cancel_user_booking,
    user_tools
)

router = APIRouter(prefix="/user", tags=["User"])

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
user_dependency = Annotated[Users, Depends(get_current_user)]

# --------------------------------------------------
# USER INFO
# --------------------------------------------------
@router.get("/")
async def get_user_info(user: user_dependency):
    """Get current user information"""
    result = get_user_profile.invoke({
        "user_id": user.id
    })
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result

# --------------------------------------------------
# GET ALL EVENTS
# --------------------------------------------------
@router.get("/events")
async def get_all_events(user: user_dependency):
    """Get all available events"""
    result = get_all_available_events.invoke({})
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result

# --------------------------------------------------
# GET MY BOOKINGS
# --------------------------------------------------
@router.get("/myEvents")
async def get_my_events(user: user_dependency):
    """Get current user's bookings"""
    result = get_user_bookings.invoke({
        "user_id": user.id
    })
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result

# --------------------------------------------------
# PROMOTE TO HOST
# --------------------------------------------------
@router.post("/promote-to-host")
async def promote_to_host(user: user_dependency):
    """Promote current user to host (costs ₹10,000)"""
    result = promote_user_to_host.invoke({
        "user_id": user.id
    })
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result

# --------------------------------------------------
# BOOK EVENT
# --------------------------------------------------
@router.post("/event/{event_id}")
async def book_event(event_id: int, user: user_dependency):
    """Book a ticket for an event"""
    result = book_event_for_user.invoke({
        "user_id": user.id,
        "event_id": event_id
    })
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result

# --------------------------------------------------
# CANCEL BOOKING
# --------------------------------------------------
@router.delete("/booking/{booking_id}")
async def cancel_booking(booking_id: int, user: user_dependency):
    """Cancel a booking and get refund"""
    result = cancel_user_booking.invoke({
        "user_id": user.id,
        "booking_id": booking_id
    })
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result

# --------------------------------------------------
# TOOLKIT ENDPOINT (for agent)
# --------------------------------------------------
@router.get("/tools")
async def get_tools():
    """Return list of available user tools"""
    return [tool.name for tool in user_tools]