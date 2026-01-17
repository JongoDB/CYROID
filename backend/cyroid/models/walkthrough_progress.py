# backend/cyroid/models/walkthrough_progress.py
from typing import Optional, List, TYPE_CHECKING
from uuid import UUID
from sqlalchemy import String, ForeignKey, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from cyroid.models.range import Range
    from cyroid.models.user import User


class WalkthroughProgress(Base, UUIDMixin, TimestampMixin):
    """Tracks student progress through a walkthrough."""
    __tablename__ = "walkthrough_progress"

    range_id: Mapped[UUID] = mapped_column(
        ForeignKey("ranges.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    completed_steps: Mapped[List[str]] = mapped_column(JSON, default=list)
    current_phase: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    current_step: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Relationships
    range: Mapped["Range"] = relationship("Range")
    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        UniqueConstraint('range_id', 'user_id', name='uq_walkthrough_progress_range_user'),
    )
