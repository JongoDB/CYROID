# backend/cyroid/models/event.py
"""Training event models for scheduling and role-based content delivery."""
from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from sqlalchemy import String, Text, Boolean, ForeignKey, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class EventStatus(str, Enum):
    """Training event lifecycle status."""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TrainingEvent(Base, UUIDMixin, TimestampMixin):
    """Training event for scheduling exercises and content delivery."""
    __tablename__ = "training_events"

    # Basic info
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Scheduling
    start_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_datetime: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")

    # Links to other entities
    blueprint_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("range_blueprints.id"), nullable=True)
    content_ids: Mapped[List[str]] = mapped_column(JSON, default=list)  # List of content UUIDs

    # Organization
    organization: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Ownership
    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))

    # Status
    status: Mapped[EventStatus] = mapped_column(default=EventStatus.DRAFT)

    # Role-based visibility (e.g., ["student", "instructor"] or specific cohorts)
    allowed_roles: Mapped[List[str]] = mapped_column(JSON, default=list)
    tags: Mapped[List[str]] = mapped_column(JSON, default=list)

    # Associated range instance (created when event starts)
    range_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("ranges.id"), nullable=True)

    # Relationships
    created_by_user = relationship("User", foreign_keys=[created_by_id])
    blueprint = relationship("RangeBlueprint", foreign_keys=[blueprint_id])
    range = relationship("Range", foreign_keys=[range_id])
    participants = relationship("EventParticipant", back_populates="event", cascade="all, delete-orphan")


class EventParticipant(Base, UUIDMixin, TimestampMixin):
    """Participant registration for a training event."""
    __tablename__ = "event_participants"

    event_id: Mapped[UUID] = mapped_column(ForeignKey("training_events.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))

    # Role in this specific event (can be different from user's global role)
    role: Mapped[str] = mapped_column(String(50), default="student")  # student, instructor, evaluator, observer

    # Status
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    event = relationship("TrainingEvent", back_populates="participants")
    user = relationship("User")
