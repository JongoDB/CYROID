# backend/cyroid/models/inject.py
from enum import Enum
from typing import Optional, List, Any, TYPE_CHECKING
from datetime import datetime
from uuid import UUID
from sqlalchemy import String, Text, Integer, ForeignKey, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from cyroid.models.msel import MSEL


class InjectStatus(str, Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Inject(Base, UUIDMixin, TimestampMixin):
    """Individual inject/event within an MSEL timeline."""
    __tablename__ = "injects"

    msel_id: Mapped[UUID] = mapped_column(
        ForeignKey("msels.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    inject_time_minutes: Mapped[int] = mapped_column(Integer, nullable=False)  # Minutes from exercise start
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_vm_ids: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list)  # List of VM UUIDs
    actions: Mapped[Optional[List[Any]]] = mapped_column(JSON, default=list)  # List of {action_type, parameters}
    status: Mapped[InjectStatus] = mapped_column(default=InjectStatus.PENDING, index=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_log: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    msel: Mapped["MSEL"] = relationship("MSEL", back_populates="injects")
