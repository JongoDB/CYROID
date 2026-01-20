# backend/cyroid/models/snapshot.py
"""Snapshot model - represents point-in-time forks in the Image Library.

In the three-tier image system:
- Base Images: Pulled container images or cached ISOs
- Golden Images: First snapshots or imported VMs
- Snapshots: Follow-on snapshots (forks) - this model

Snapshots track lineage to their parent GoldenImage.
"""
from typing import Optional, List, TYPE_CHECKING
from uuid import UUID
from sqlalchemy import String, Text, ForeignKey, Integer, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from cyroid.models.golden_image import GoldenImage


class Snapshot(Base, UUIDMixin, TimestampMixin):
    """Snapshot (fork) in the Image Library.

    Snapshots are created after a VM already has a GoldenImage. They represent
    point-in-time forks that can be used to create new VMs.

    Tracks lineage to the parent GoldenImage and optionally to a parent Snapshot
    for fork chains.
    """
    __tablename__ = "snapshots"

    # Source VM (optional - snapshots can exist independently for imported images)
    vm_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("vms.id", ondelete="SET NULL"), nullable=True
    )

    # Lineage tracking - link to parent golden image
    golden_image_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("golden_images.id", ondelete="SET NULL"), nullable=True
    )

    # Fork chain - link to parent snapshot (for nested forks)
    parent_snapshot_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("snapshots.id", ondelete="SET NULL"), nullable=True
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
        foreign_keys="[VM.snapshot_id]"
    )
    # Lineage relationship to parent golden image
    golden_image: Mapped[Optional["GoldenImage"]] = relationship(
        "GoldenImage", back_populates="snapshots"
    )
    # Self-referential relationship for fork chains
    parent_snapshot: Mapped[Optional["Snapshot"]] = relationship(
        "Snapshot", remote_side="Snapshot.id", backref="child_snapshots"
    )
