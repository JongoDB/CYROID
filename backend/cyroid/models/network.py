# backend/cyroid/models/network.py
from typing import Optional, List
from uuid import UUID
from sqlalchemy import String, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class Network(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "networks"

    range_id: Mapped[UUID] = mapped_column(ForeignKey("ranges.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    subnet: Mapped[str] = mapped_column(String(18))  # CIDR notation
    gateway: Mapped[str] = mapped_column(String(15))
    dns_servers: Mapped[Optional[str]] = mapped_column(String(255))  # Comma-separated

    # Docker network ID (set after creation)
    docker_network_id: Mapped[Optional[str]] = mapped_column(String(64))

    # Network isolation - when True:
    # - Docker network is internal (no external routing)
    # - iptables rules block access to host/infrastructure
    is_isolated: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    range = relationship("Range", back_populates="networks")
    vms: Mapped[List["VM"]] = relationship("VM", back_populates="network")
