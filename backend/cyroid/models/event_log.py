# backend/cyroid/models/event_log.py
from enum import Enum
from typing import Optional
from uuid import UUID
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class EventType(str, Enum):
    RANGE_DEPLOYED = "range_deployed"
    RANGE_STARTED = "range_started"
    RANGE_STOPPED = "range_stopped"
    RANGE_TEARDOWN = "range_teardown"
    VM_CREATED = "vm_created"
    VM_STARTED = "vm_started"
    VM_STOPPED = "vm_stopped"
    VM_RESTARTED = "vm_restarted"
    VM_ERROR = "vm_error"
    SNAPSHOT_CREATED = "snapshot_created"
    SNAPSHOT_RESTORED = "snapshot_restored"
    ARTIFACT_PLACED = "artifact_placed"
    INJECT_EXECUTED = "inject_executed"
    INJECT_FAILED = "inject_failed"
    CONNECTION_ESTABLISHED = "connection_established"
    CONNECTION_CLOSED = "connection_closed"


class EventLog(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "event_logs"

    range_id: Mapped[UUID] = mapped_column(ForeignKey("ranges.id", ondelete="CASCADE"), index=True)
    vm_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("vms.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type: Mapped[EventType] = mapped_column(index=True)
    message: Mapped[str] = mapped_column(Text)
    extra_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string for extra data

    range = relationship("Range", back_populates="event_logs")
    vm = relationship("VM", back_populates="event_logs")
