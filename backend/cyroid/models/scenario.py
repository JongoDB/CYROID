# backend/cyroid/models/scenario.py
from typing import Optional, List
from sqlalchemy import String, Integer, Text, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class Scenario(Base, UUIDMixin, TimestampMixin):
    """Pre-built training scenario with event sequences."""
    __tablename__ = "scenarios"

    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # red-team, blue-team, insider-threat
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)  # beginner, intermediate, advanced
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False)
    required_roles: Mapped[List[str]] = mapped_column(JSON, default=list)  # ["domain-controller", "workstation"]
    events: Mapped[List[dict]] = mapped_column(JSON, default=list)  # Event definitions

    # Seed identification
    is_seed: Mapped[bool] = mapped_column(Boolean, default=True)
    seed_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True)
