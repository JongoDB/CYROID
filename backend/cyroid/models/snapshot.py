# backend/cyroid/models/snapshot.py
from typing import Optional, List
from uuid import UUID
from sqlalchemy import String, Text, ForeignKey, Integer, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class Snapshot(Base, UUIDMixin, TimestampMixin):
    """Snapshot model - represents a committed Docker image from a VM state.

    Snapshots can be used as sources for creating new VMs (VM Library feature).
    When is_global=True, the snapshot is visible to all users for VM creation.
    """
    __tablename__ = "snapshots"

    # Source VM (optional - snapshots can exist independently for imported images)
    vm_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("vms.id", ondelete="SET NULL"), nullable=True
    )

    # Basic info
    name: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Docker image reference
    docker_image_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)  # sha256:hash
    docker_image_tag: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # e.g., cyroid-snapshot:dc01-v1

    # VM metadata (copied from source VM/template for use in VM Library)
    os_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # windows, linux, network, custom
    vm_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # container, linux_vm, windows_vm

    # Default specs for VMs created from this snapshot
    default_cpu: Mapped[int] = mapped_column(Integer, default=2)
    default_ram_mb: Mapped[int] = mapped_column(Integer, default=4096)
    default_disk_gb: Mapped[int] = mapped_column(Integer, default=40)

    # Display configuration
    display_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # desktop, headless
    vnc_port: Mapped[int] = mapped_column(Integer, default=8006)

    # Visibility
    is_global: Mapped[bool] = mapped_column(Boolean, default=True)  # Visible to all users

    # Categorization
    tags: Mapped[List[str]] = mapped_column(JSON, default=list)

    # Relationships
    # VM this snapshot was taken from (Snapshot.vm_id -> VM.id)
    vm = relationship("VM", back_populates="snapshots", foreign_keys=[vm_id])
    # VMs created from this snapshot (VM.snapshot_id -> Snapshot.id)
    created_vms = relationship(
        "VM",
        back_populates="source_snapshot",
        foreign_keys="VM.snapshot_id"
    )
