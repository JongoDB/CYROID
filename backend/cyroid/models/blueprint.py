# backend/cyroid/models/blueprint.py
from typing import Optional, List
from uuid import UUID
from sqlalchemy import String, Text, ForeignKey, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class RangeBlueprint(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "range_blueprints"

    name: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    config: Mapped[dict] = mapped_column(JSON)  # networks, VMs, MSEL, router

    # DEPRECATED: No longer used with DinD isolation - kept for backward compatibility
    base_subnet_prefix: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, default="10.0.0.0/8")
    next_offset: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)

    # Linked content for training events (auto-selected when blueprint chosen)
    content_ids: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list)

    # Built-in blueprint identification (like templates)
    is_seed: Mapped[bool] = mapped_column(default=False)  # True for blueprints shipped with CYROID
    seed_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True)  # e.g., "red-team-training-lab"

    # Ownership (nullable for seed blueprints)
    created_by: Mapped[Optional[UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by_user = relationship("User", foreign_keys=[created_by])

    # Relationships
    instances: Mapped[List["RangeInstance"]] = relationship(
        "RangeInstance", back_populates="blueprint", cascade="all, delete-orphan"
    )


class RangeInstance(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "range_instances"

    name: Mapped[str] = mapped_column(String(100))
    blueprint_id: Mapped[UUID] = mapped_column(ForeignKey("range_blueprints.id"))
    blueprint_version: Mapped[int] = mapped_column(Integer)
    subnet_offset: Mapped[int] = mapped_column(Integer)

    # Ownership
    instructor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    instructor = relationship("User", foreign_keys=[instructor_id])

    # Link to actual range
    range_id: Mapped[UUID] = mapped_column(ForeignKey("ranges.id"))
    range = relationship("Range")

    # Parent blueprint
    blueprint = relationship("RangeBlueprint", back_populates="instances")
