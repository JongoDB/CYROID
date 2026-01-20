# backend/cyroid/models/vm.py
from enum import Enum
from typing import Optional, List
from uuid import UUID
from sqlalchemy import String, Integer, ForeignKey, JSON, Boolean
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

    # Source: either template OR snapshot (mutually exclusive)
    template_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("vm_templates.id"), nullable=True
    )
    snapshot_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("snapshots.id"), nullable=True
    )

    hostname: Mapped[str] = mapped_column(String(63))
    ip_address: Mapped[str] = mapped_column(String(15))

    # Specs (can override template defaults)
    cpu: Mapped[int] = mapped_column(Integer)
    ram_mb: Mapped[int] = mapped_column(Integer)
    disk_gb: Mapped[int] = mapped_column(Integer)

    status: Mapped[VMStatus] = mapped_column(default=VMStatus.PENDING)

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    # Docker container ID (set after creation)
    container_id: Mapped[Optional[str]] = mapped_column(String(64))

    # Windows-specific settings (for dockur/windows VMs)
    # Version codes: 11, 11l, 11e, 10, 10l, 10e, 8e, 7u, vu, xp, 2k, 2025, 2022, 2019, 2016, 2012, 2008, 2003
    windows_version: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    windows_username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    windows_password: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    iso_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    iso_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # Display type for Windows VMs: desktop (VNC/web console) or server (RDP only)
    display_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, default="desktop")

    # Network configuration
    use_dhcp: Mapped[bool] = mapped_column(Boolean, default=False)  # DHCP vs static IP
    gateway: Mapped[Optional[str]] = mapped_column(String(15), nullable=True)  # Gateway IP
    dns_servers: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Comma-separated DNS

    # Additional storage (shows as D:, E: drives in Windows)
    disk2_gb: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    disk3_gb: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Shared folders (bind mounts)
    enable_shared_folder: Mapped[bool] = mapped_column(Boolean, default=False)  # Per-VM /shared
    enable_global_shared: Mapped[bool] = mapped_column(Boolean, default=False)  # Global /global (read-only)

    # Localization
    language: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g., "French", "German"
    keyboard: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # e.g., "en-US", "de-DE"
    region: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)    # e.g., "en-US", "fr-FR"

    # Installation mode
    manual_install: Mapped[bool] = mapped_column(Boolean, default=False)  # Interactive install mode

    # Linux VM-specific settings (for qemux/qemu VMs)
    # Distro codes: ubuntu, debian, fedora, alpine, arch, manjaro, opensuse, mint,
    #               zorin, elementary, popos, kali, parrot, tails, rocky, alma
    linux_distro: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    boot_mode: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, default="uefi")  # uefi or legacy
    disk_type: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, default="scsi")  # scsi, blk, or ide

    # Linux user configuration (for cloud-init in qemux/qemu, env vars in KasmVNC/LinuxServer)
    linux_username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    linux_password: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    linux_user_sudo: Mapped[bool] = mapped_column(Boolean, default=True)

    # Position in visual builder (for UI)
    position_x: Mapped[int] = mapped_column(Integer, default=0)
    position_y: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    range = relationship("Range", back_populates="vms")
    network = relationship("Network", back_populates="vms")
    template = relationship("VMTemplate", back_populates="vms")
    snapshots: Mapped[List["Snapshot"]] = relationship(
        "Snapshot", back_populates="vm", foreign_keys="[Snapshot.vm_id]"
    )
    source_snapshot: Mapped[Optional["Snapshot"]] = relationship(
        "Snapshot",
        back_populates="created_vms",
        foreign_keys="[VM.snapshot_id]"
    )
    artifact_placements: Mapped[List["ArtifactPlacement"]] = relationship(
        "ArtifactPlacement", back_populates="vm", cascade="all, delete-orphan"
    )
    event_logs: Mapped[List["EventLog"]] = relationship(
        "EventLog", back_populates="vm", cascade="all, delete-orphan"
    )
    outgoing_connections: Mapped[List["Connection"]] = relationship(
        "Connection", foreign_keys="Connection.src_vm_id", back_populates="src_vm"
    )
    incoming_connections: Mapped[List["Connection"]] = relationship(
        "Connection", foreign_keys="Connection.dst_vm_id", back_populates="dst_vm"
    )
