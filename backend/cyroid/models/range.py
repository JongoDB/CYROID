# backend/cyroid/models/range.py
from enum import Enum
from typing import Optional, List
from uuid import UUID
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class RangeStatus(str, Enum):
    DRAFT = "draft"
    DEPLOYING = "deploying"
    RUNNING = "running"
    STOPPED = "stopped"
    ARCHIVED = "archived"
    ERROR = "error"


class Range(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ranges"

    name: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[RangeStatus] = mapped_column(default=RangeStatus.DRAFT)

    # Ownership
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_by_user = relationship("User", back_populates="ranges")

    # Relationships
    networks: Mapped[List["Network"]] = relationship(
        "Network", back_populates="range", cascade="all, delete-orphan"
    )
    vms: Mapped[List["VM"]] = relationship(
        "VM", back_populates="range", cascade="all, delete-orphan"
    )
    event_logs: Mapped[List["EventLog"]] = relationship(
        "EventLog", back_populates="range", cascade="all, delete-orphan"
    )
    connections: Mapped[List["Connection"]] = relationship(
        "Connection", back_populates="range", cascade="all, delete-orphan"
    )
    msel: Mapped[Optional["MSEL"]] = relationship(
        "MSEL", back_populates="range", uselist=False, cascade="all, delete-orphan"
    )
