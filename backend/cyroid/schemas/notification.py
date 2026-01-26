# backend/cyroid/schemas/notification.py
"""Schemas for user notifications."""
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel

from cyroid.models.notification import NotificationType, NotificationSeverity


class NotificationCreate(BaseModel):
    """Schema for creating a notification."""
    notification_type: NotificationType = NotificationType.INFO
    title: str
    message: str
    severity: NotificationSeverity = NotificationSeverity.INFO

    # Scoping - at least one should be set
    user_id: Optional[UUID] = None
    target_role: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[UUID] = None

    # Optional link to source event
    source_event_id: Optional[UUID] = None


class NotificationResponse(BaseModel):
    """Schema for notification response."""
    id: UUID
    notification_type: NotificationType
    title: str
    message: str
    severity: NotificationSeverity
    user_id: Optional[UUID] = None
    target_role: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[UUID] = None
    read_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationList(BaseModel):
    """Paginated list of notifications."""
    notifications: List[NotificationResponse]
    total: int
    unread_count: int


class NotificationMarkRead(BaseModel):
    """Schema for marking notifications as read."""
    notification_ids: List[UUID]
