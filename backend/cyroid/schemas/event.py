# backend/cyroid/schemas/event.py
"""Pydantic schemas for Training Events API."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from cyroid.models.event import EventStatus


# ============ Event Participant Schemas ============

class EventParticipantBase(BaseModel):
    user_id: UUID
    role: str = "student"


class EventParticipantCreate(EventParticipantBase):
    pass


class EventParticipantResponse(EventParticipantBase):
    id: UUID
    event_id: UUID
    is_confirmed: bool
    created_at: datetime
    username: Optional[str] = None
    # Per-student range assignment
    range_id: Optional[UUID] = None
    range_status: Optional[str] = None
    range_name: Optional[str] = None
    # VM visibility control
    hidden_vm_ids: List[UUID] = Field(default_factory=list)

    class Config:
        from_attributes = True


# ============ Event Schemas ============

class EventBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    start_datetime: datetime
    end_datetime: Optional[datetime] = None
    is_all_day: bool = False
    timezone: str = "UTC"
    organization: Optional[str] = None
    location: Optional[str] = None


class EventCreate(EventBase):
    blueprint_id: Optional[UUID] = None
    content_ids: List[str] = Field(default_factory=list)
    allowed_roles: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class EventUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    is_all_day: Optional[bool] = None
    timezone: Optional[str] = None
    organization: Optional[str] = None
    location: Optional[str] = None
    blueprint_id: Optional[UUID] = None
    content_ids: Optional[List[str]] = None
    allowed_roles: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    status: Optional[EventStatus] = None


class EventResponse(EventBase):
    id: UUID
    blueprint_id: Optional[UUID] = None
    content_ids: List[str]
    status: EventStatus
    allowed_roles: List[str]
    tags: List[str]
    created_by_id: UUID
    range_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    participant_count: int = 0
    blueprint_name: Optional[str] = None
    created_by_username: Optional[str] = None

    class Config:
        from_attributes = True


class EventListResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    start_datetime: datetime
    end_datetime: Optional[datetime] = None
    is_all_day: bool
    timezone: str
    organization: Optional[str] = None
    location: Optional[str] = None
    status: EventStatus
    tags: List[str]
    allowed_roles: List[str]
    participant_count: int = 0
    student_count: int = 0
    has_blueprint: bool = False
    created_by_id: UUID
    created_at: datetime
    # For my-events endpoint: the range assigned to the current user
    my_range_id: Optional[UUID] = None

    class Config:
        from_attributes = True


class EventDetailResponse(EventResponse):
    """Full event details including related data."""
    participants: List[EventParticipantResponse] = Field(default_factory=list)


# ============ Event Content Delivery ============

class EventContentItem(BaseModel):
    """Content item visible to the user based on their role."""
    id: UUID
    title: str
    description: Optional[str] = None
    content_type: str
    body_html: Optional[str] = None
    version: str


class EventBriefingResponse(BaseModel):
    """Briefing materials for an event, role-filtered."""
    event_id: UUID
    event_name: str
    user_role: str  # Their role in this event
    content_items: List[EventContentItem]
    range_id: Optional[UUID] = None
    range_status: Optional[str] = None


# ============ VM Visibility Control ============

class VMVisibilityVM(BaseModel):
    """VM info for visibility control."""
    id: UUID
    hostname: str
    status: str
    is_hidden: bool = False


class VMVisibilityUpdate(BaseModel):
    """Update VM visibility for a participant."""
    hidden_vm_ids: List[UUID]


class VMVisibilityResponse(BaseModel):
    """VM visibility settings for a participant."""
    participant_id: UUID
    user_id: UUID
    username: str
    range_id: Optional[UUID] = None
    hidden_vm_ids: List[UUID] = Field(default_factory=list)
    vms: List[VMVisibilityVM] = Field(default_factory=list)


class BulkVMVisibilityUpdate(BaseModel):
    """Bulk update VM visibility for all participants."""
    vm_id: UUID
    is_hidden: bool
