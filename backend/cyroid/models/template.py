# backend/cyroid/models/template.py
from enum import Enum
from typing import Optional, List
from uuid import UUID
from sqlalchemy import String, Integer, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class OSType(str, Enum):
    WINDOWS = "windows"
    LINUX = "linux"
    NETWORK = "network"  # For network devices (VyOS, OPNsense, pfSense, etc.)
    CUSTOM = "custom"  # For custom ISOs


class VMType(str, Enum):
    """Type of VM/container implementation."""
    CONTAINER = "container"      # Basic Docker container (lightweight Linux)
    LINUX_VM = "linux_vm"        # Full Linux VM via qemus/qemu
    WINDOWS_VM = "windows_vm"    # Full Windows VM via dockur/windows


class LinuxDistro(str, Enum):
    """Supported Linux distributions for qemus/qemu VMs.

    These are auto-downloaded by qemus/qemu when specified in the BOOT env var.
    See: https://github.com/qemus/qemu
    """
    # Popular desktop distributions
    UBUNTU = "ubuntu"            # ~2.5 GB
    DEBIAN = "debian"            # ~600 MB
    FEDORA = "fedora"            # ~2.0 GB
    ALPINE = "alpine"            # ~60 MB (minimal)
    ARCH = "arch"                # ~800 MB
    MANJARO = "manjaro"          # ~2.5 GB
    OPENSUSE = "opensuse"        # ~800 MB
    MINT = "mint"                # ~2.5 GB
    ZORIN = "zorin"              # ~4.5 GB
    ELEMENTARY = "elementary"    # ~2.5 GB
    POPOS = "popos"              # ~2.5 GB

    # Security-focused distributions (for cyber range training)
    KALI = "kali"                # ~3.5 GB - Penetration testing
    PARROT = "parrot"            # ~5.0 GB - Security/forensics
    TAILS = "tails"              # ~1.3 GB - Privacy-focused

    # Enterprise/server distributions
    ROCKY = "rocky"              # ~1.5 GB - RHEL compatible
    ALMA = "alma"                # ~1.5 GB - RHEL compatible

    # Custom ISO (use iso_url instead)
    CUSTOM = "custom"


class VMTemplate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "vm_templates"

    name: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    os_type: Mapped[OSType]
    os_variant: Mapped[str] = mapped_column(String(100))  # e.g., "Ubuntu 22.04", "Windows Server 2022"
    base_image: Mapped[str] = mapped_column(String(255))  # Docker image, linux distro, or windows version

    # VM implementation type
    vm_type: Mapped[VMType] = mapped_column(default=VMType.CONTAINER)  # container, linux_vm, or windows_vm

    # Linux VM-specific (for qemus/qemu)
    linux_distro: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # ubuntu, kali, etc.
    boot_mode: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, default="uefi")
    disk_type: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, default="scsi")

    # Default specs
    default_cpu: Mapped[int] = mapped_column(Integer, default=2)
    default_ram_mb: Mapped[int] = mapped_column(Integer, default=4096)
    default_disk_gb: Mapped[int] = mapped_column(Integer, default=40)

    # Configuration
    config_script: Mapped[Optional[str]] = mapped_column(Text)  # bash or PowerShell
    tags: Mapped[List[str]] = mapped_column(JSON, default=list)

    # Cached image support
    golden_image_path: Mapped[Optional[str]] = mapped_column(String(500))  # Path to golden image for Windows
    cached_iso_path: Mapped[Optional[str]] = mapped_column(String(500))  # Path to cached ISO
    is_cached: Mapped[bool] = mapped_column(default=False)  # Whether this template uses cached images

    # Multi-architecture support
    iso_url_x86: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    iso_url_arm64: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    native_arch: Mapped[str] = mapped_column(String(20), default='x86_64')  # 'x86_64', 'arm64', or 'both'

    # Built-in template identification
    is_seed: Mapped[bool] = mapped_column(default=False)  # True for templates shipped with CYROID
    seed_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True)  # e.g., "kali-attack"

    # Ownership
    created_by: Mapped[Optional[UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)  # Nullable for seed templates
    created_by_user = relationship("User", back_populates="templates")

    # Relationships
    vms = relationship("VM", back_populates="template")
