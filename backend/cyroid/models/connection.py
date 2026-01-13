# backend/cyroid/models/connection.py
from enum import Enum
from typing import Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy import String, Integer, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class ConnectionProtocol(str, Enum):
    TCP = "tcp"
    UDP = "udp"
    ICMP = "icmp"


class ConnectionState(str, Enum):
    ESTABLISHED = "established"
    CLOSED = "closed"
    TIMEOUT = "timeout"
    RESET = "reset"


class Connection(Base, UUIDMixin, TimestampMixin):
    """Tracks network connections between VMs in a range."""
    __tablename__ = "connections"

    range_id: Mapped[UUID] = mapped_column(ForeignKey("ranges.id", ondelete="CASCADE"), index=True)

    # Source
    src_vm_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("vms.id", ondelete="SET NULL"), nullable=True, index=True)
    src_ip: Mapped[str] = mapped_column(String(45))
    src_port: Mapped[int] = mapped_column(Integer)

    # Destination
    dst_vm_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("vms.id", ondelete="SET NULL"), nullable=True, index=True)
    dst_ip: Mapped[str] = mapped_column(String(45))
    dst_port: Mapped[int] = mapped_column(Integer)

    # Connection details
    protocol: Mapped[ConnectionProtocol] = mapped_column(default=ConnectionProtocol.TCP)
    state: Mapped[ConnectionState] = mapped_column(default=ConnectionState.ESTABLISHED, index=True)
    bytes_sent: Mapped[int] = mapped_column(Integer, default=0)
    bytes_received: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    range = relationship("Range", back_populates="connections")
    src_vm = relationship("VM", foreign_keys=[src_vm_id], back_populates="outgoing_connections")
    dst_vm = relationship("VM", foreign_keys=[dst_vm_id], back_populates="incoming_connections")
