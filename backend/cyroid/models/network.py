# backend/cyroid/models/network.py
from enum import Enum
from typing import Optional, List
from uuid import UUID
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class IsolationLevel(str, Enum):
    COMPLETE = "complete"
    CONTROLLED = "controlled"
    OPEN = "open"


class Network(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "networks"

    range_id: Mapped[UUID] = mapped_column(ForeignKey("ranges.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    subnet: Mapped[str] = mapped_column(String(18))  # CIDR notation
    gateway: Mapped[str] = mapped_column(String(15))
    dns_servers: Mapped[Optional[str]] = mapped_column(String(255))  # Comma-separated
    isolation_level: Mapped[IsolationLevel] = mapped_column(default=IsolationLevel.COMPLETE)

    # Docker network ID (set after creation)
    docker_network_id: Mapped[Optional[str]] = mapped_column(String(64))

    # Relationships
    range = relationship("Range", back_populates="networks")
    vms: Mapped[List["VM"]] = relationship("VM", back_populates="network")
