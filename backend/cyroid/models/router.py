# backend/cyroid/models/router.py
"""Range router model for VyOS containers."""
from enum import Enum
from typing import Optional
from uuid import UUID
from sqlalchemy import String, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class RouterStatus(str, Enum):
    """Status of a range router."""
    PENDING = "pending"
    CREATING = "creating"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class RangeRouter(Base, UUIDMixin, TimestampMixin):
    """
    VyOS router container for a range.

    Each range gets one VyOS router that:
    - Connects to the management network (eth0) for CYROID control
    - Has LAN interfaces (eth1, eth2, ...) for each network in the range
    - Handles NAT for internet-enabled networks
    - Enforces isolation via firewall rules
    """
    __tablename__ = "range_routers"

    # One router per range
    range_id: Mapped[UUID] = mapped_column(
        ForeignKey("ranges.id", ondelete="CASCADE"),
        unique=True
    )

    # Docker container ID (set after creation)
    container_id: Mapped[Optional[str]] = mapped_column(String(64))

    # Management network IP (10.10.0.X)
    management_ip: Mapped[Optional[str]] = mapped_column(String(15))

    # Router status - use SAEnum to ensure proper value serialization
    status: Mapped[RouterStatus] = mapped_column(
        SAEnum(RouterStatus, values_callable=lambda x: [e.value for e in x], native_enum=True, name='routerstatus', create_constraint=False),
        default=RouterStatus.PENDING
    )

    # Error message if status is ERROR
    error_message: Mapped[Optional[str]] = mapped_column(String(500))

    # Relationship back to range
    range = relationship("Range", back_populates="router")
