# backend/cyroid/models/msel.py
from typing import Optional, List, TYPE_CHECKING
from uuid import UUID
from sqlalchemy import String, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from cyroid.models.range import Range
    from cyroid.models.inject import Inject


class MSEL(Base, UUIDMixin, TimestampMixin):
    """Master Scenario Events List - defines the scenario timeline for a range."""
    __tablename__ = "msels"

    range_id: Mapped[UUID] = mapped_column(
        ForeignKey("ranges.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # Raw markdown
    walkthrough: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    range: Mapped["Range"] = relationship("Range", back_populates="msel")
    injects: Mapped[List["Inject"]] = relationship(
        "Inject", back_populates="msel", cascade="all, delete-orphan"
    )
