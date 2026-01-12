# backend/cyroid/models/vm.py
from enum import Enum
from typing import Optional, List
from uuid import UUID
from sqlalchemy import String, Integer, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class VMStatus(str, Enum):
    PENDING = "pending"
    CREATING = "creating"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class VM(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "vms"

    range_id: Mapped[UUID] = mapped_column(ForeignKey("ranges.id", ondelete="CASCADE"))
    network_id: Mapped[UUID] = mapped_column(ForeignKey("networks.id"))
    template_id: Mapped[UUID] = mapped_column(ForeignKey("vm_templates.id"))

    hostname: Mapped[str] = mapped_column(String(63))
    ip_address: Mapped[str] = mapped_column(String(15))

    # Specs (can override template defaults)
    cpu: Mapped[int] = mapped_column(Integer)
    ram_mb: Mapped[int] = mapped_column(Integer)
    disk_gb: Mapped[int] = mapped_column(Integer)

    status: Mapped[VMStatus] = mapped_column(default=VMStatus.PENDING)

    # Docker container ID (set after creation)
    container_id: Mapped[Optional[str]] = mapped_column(String(64))

    # Position in visual builder (for UI)
    position_x: Mapped[int] = mapped_column(Integer, default=0)
    position_y: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    range = relationship("Range", back_populates="vms")
    network = relationship("Network", back_populates="vms")
    template = relationship("VMTemplate", back_populates="vms")
    snapshots: Mapped[List["Snapshot"]] = relationship(
        "Snapshot", back_populates="vm", cascade="all, delete-orphan"
    )
    artifact_placements: Mapped[List["ArtifactPlacement"]] = relationship(
        "ArtifactPlacement", back_populates="vm", cascade="all, delete-orphan"
    )
