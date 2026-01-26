# backend/cyroid/models/notification.py
"""User-scoped notification model for targeted alerts."""
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy import String, Text, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class NotificationType(str, Enum):
    """Types of notifications."""
    # Range events
    RANGE_DEPLOYED = "range_deployed"
    RANGE_STARTED = "range_started"
    RANGE_STOPPED = "range_stopped"
    RANGE_DELETED = "range_deleted"

    # VM events
    VM_STARTED = "vm_started"
    VM_STOPPED = "vm_stopped"
    VM_ERROR = "vm_error"

    # Training event notifications
    EVENT_SCHEDULED = "event_scheduled"
    EVENT_STARTING = "event_starting"
    EVENT_STARTED = "event_started"
    EVENT_COMPLETED = "event_completed"
    EVENT_CANCELLED = "event_cancelled"

    # Inject notifications
    INJECT_AVAILABLE = "inject_available"
    INJECT_EXECUTED = "inject_executed"

    # Evidence/scoring
    EVIDENCE_SUBMITTED = "evidence_submitted"
    SCORE_UPDATED = "score_updated"

    # User/admin
    USER_CREATED = "user_created"
    USER_APPROVED = "user_approved"

    # System
    SYSTEM_ALERT = "system_alert"

    # General
    INFO = "info"


class NotificationSeverity(str, Enum):
    """Severity levels for notifications."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"


class Notification(Base, UUIDMixin, TimestampMixin):
    """User-scoped notification for targeted alerts.

    Notifications can be scoped to:
    - A specific user (user_id)
    - Users with a specific role (target_role)
    - Users with access to a specific resource (resource_type + resource_id)

    If multiple scoping fields are set, they act as OR conditions.
    """
    __tablename__ = "notifications"

    # Notification content
    notification_type: Mapped[NotificationType] = mapped_column(default=NotificationType.INFO)
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    severity: Mapped[NotificationSeverity] = mapped_column(default=NotificationSeverity.INFO)

    # Scoping - target specific user
    user_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True
    )

    # Scoping - target users with specific role
    target_role: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Scoping - target users with access to resource
    resource_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 'range', 'event', 'team'
    resource_id: Mapped[Optional[UUID]] = mapped_column(nullable=True)

    # Link to source event (if applicable)
    source_event_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("event_logs.id", ondelete="SET NULL"),
        nullable=True
    )

    # Read status per user - stored as JSON {user_id: read_at}
    # For single-user notifications, we just use read_at
    read_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index('ix_notifications_user_id', 'user_id'),
        Index('ix_notifications_target_role', 'target_role'),
        Index('ix_notifications_resource', 'resource_type', 'resource_id'),
        Index('ix_notifications_created_at', 'created_at'),
    )
