# backend/cyroid/models/base_image.py
"""BaseImage model - represents container images and cached ISOs in the Image Library.

BaseImages are the foundation of the three-tier image system:
- Base Images: Pulled container images or cached ISOs (this model)
- Golden Images: First snapshots or imported VMs
- Snapshots: Follow-on snapshots (forks)
"""
from enum import Enum
from typing import Optional, List, TYPE_CHECKING
from uuid import UUID
from sqlalchemy import String, Integer, BigInteger, Text, ForeignKey, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from cyroid.models.golden_image import GoldenImage
    from cyroid.models.vm import VM
    from cyroid.models.user import User


class ImageType(str, Enum):
    """Type of base image."""
    CONTAINER = "container"  # Docker container image (pulled from registry)
    ISO = "iso"              # ISO file (Windows/Linux cached)


class BaseImage(Base, UUIDMixin, TimestampMixin):
    """Base image in the Image Library.

    Base images are created automatically when:
    - A container image is pulled via Image Cache
    - An ISO is downloaded/cached

    Users create VMs directly from base images for fresh installs.
    """
    __tablename__ = "base_images"

    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_type: Mapped[str] = mapped_column(String(20), nullable=False)  # container or iso

    # Container-specific fields
    docker_image_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)  # sha256:hash
    docker_image_tag: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)  # e.g., kasmweb/ubuntu-jammy-desktop:1.14.0
    image_project_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)  # Links to /data/images/{project_name}/

    # ISO-specific fields
    iso_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, unique=True)  # Path to cached ISO file
    iso_source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # windows, linux, custom
    iso_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g., "22H2", "22.04"

    # Metadata
    os_type: Mapped[str] = mapped_column(String(20), nullable=False)  # windows, linux, network, custom
    vm_type: Mapped[str] = mapped_column(String(20), nullable=False)  # container, linux_vm, windows_vm
    native_arch: Mapped[str] = mapped_column(String(20), default="x86_64")  # x86_64, arm64, both

    # Resource defaults (user configures when pulling/uploading)
    default_cpu: Mapped[int] = mapped_column(Integer, default=2)
    default_ram_mb: Mapped[int] = mapped_column(Integer, default=4096)
    default_disk_gb: Mapped[int] = mapped_column(Integer, default=40)

    # Size tracking
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Visibility and ownership
    is_global: Mapped[bool] = mapped_column(Boolean, default=True)  # Visible to all users
    created_by: Mapped[Optional[UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Categorization
    tags: Mapped[List[str]] = mapped_column(JSON, default=list)

    # Container runtime configuration (capabilities, devices, security options)
    # See: https://docs.docker.com/engine/reference/run/
    container_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    golden_images: Mapped[List["GoldenImage"]] = relationship(
        "GoldenImage", back_populates="base_image"
    )
    vms: Mapped[List["VM"]] = relationship(
        "VM", back_populates="base_image"
    )
    created_by_user: Mapped[Optional["User"]] = relationship(
        "User", back_populates="base_images"
    )
