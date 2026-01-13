# backend/cyroid/schemas/event_log.py
from datetime import datetime
from uuid import UUID
from typing import Optional, List
from pydantic import BaseModel
from cyroid.models.event_log import EventType


class EventLogBase(BaseModel):
    event_type: EventType
    message: str
    extra_data: Optional[str] = None


class EventLogCreate(EventLogBase):
    range_id: UUID
    vm_id: Optional[UUID] = None


class EventLogResponse(EventLogBase):
    id: UUID
    range_id: UUID
    vm_id: Optional[UUID]
    created_at: datetime

    class Config:
        from_attributes = True


class EventLogList(BaseModel):
    events: List[EventLogResponse]
    total: int
