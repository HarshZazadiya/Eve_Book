from pydantic import BaseModel
from typing import Optional
from datetime import date

class EventQuery(BaseModel):
    host_name : Optional[str] = None
    event_name: Optional[str] = None
    date: Optional[str] = None
    venue: Optional[str] = None
    company: Optional[str] = None
    intent: Optional[str] = None