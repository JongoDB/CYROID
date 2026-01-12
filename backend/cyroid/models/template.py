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


class VMTemplate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "vm_templates"

    name: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    os_type: Mapped[OSType]
    os_variant: Mapped[str] = mapped_column(String(100))  # e.g., "Ubuntu 22.04", "Windows Server 2022"
    base_image: Mapped[str] = mapped_column(String(255))  # Docker image or dockur config

    # Default specs
    default_cpu: Mapped[int] = mapped_column(Integer, default=2)
    default_ram_mb: Mapped[int] = mapped_column(Integer, default=4096)
    default_disk_gb: Mapped[int] = mapped_column(Integer, default=40)

    # Configuration
    config_script: Mapped[Optional[str]] = mapped_column(Text)  # bash or PowerShell
    tags: Mapped[List[str]] = mapped_column(JSON, default=list)

    # Ownership
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_by_user = relationship("User", back_populates="templates")

    # Relationships
    vms = relationship("VM", back_populates="template")
