# backend/cyroid/models/catalog.py
"""Catalog source and installed item models for the CYROID catalog system."""
from enum import Enum
from typing import Optional, List
from uuid import UUID

from sqlalchemy import String, Text, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class CatalogSourceType(str, Enum):
    """Types of catalog sources."""
    GIT = "git"
    HTTP = "http"
    LOCAL = "local"


class CatalogSyncStatus(str, Enum):
    """Sync status for a catalog source."""
    IDLE = "idle"
    SYNCING = "syncing"
    ERROR = "error"


class CatalogItemType(str, Enum):
    """Types of items that can be installed from a catalog."""
    BLUEPRINT = "blueprint"
    SCENARIO = "scenario"
    IMAGE = "image"
    TEMPLATE = "template"
    CONTENT = "content"


class CatalogSource(Base, UUIDMixin, TimestampMixin):
    """A catalog source repository that provides installable items."""
    __tablename__ = "catalog_sources"

    name: Mapped[str] = mapped_column(String(200), index=True)
    source_type: Mapped[CatalogSourceType] = mapped_column(default=CatalogSourceType.GIT)
    url: Mapped[str] = mapped_column(String(500))
    branch: Mapped[str] = mapped_column(String(100), default="main")
    enabled: Mapped[bool] = mapped_column(default=True)
    sync_status: Mapped[CatalogSyncStatus] = mapped_column(default=CatalogSyncStatus.IDLE)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    # Relationships
    installed_items: Mapped[List["CatalogInstalledItem"]] = relationship(
        "CatalogInstalledItem", back_populates="source", cascade="all, delete-orphan"
    )


class CatalogInstalledItem(Base, UUIDMixin, TimestampMixin):
    """An item installed from a catalog source into the local CYROID instance."""
    __tablename__ = "catalog_installed_items"

    catalog_source_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_sources.id", ondelete="CASCADE")
    )
    catalog_item_id: Mapped[str] = mapped_column(String(200), index=True)
    item_type: Mapped[CatalogItemType] = mapped_column(default=CatalogItemType.BLUEPRINT)
    item_name: Mapped[str] = mapped_column(String(200))
    installed_version: Mapped[str] = mapped_column(String(100))
    installed_checksum: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    local_resource_id: Mapped[Optional[UUID]] = mapped_column(nullable=True)
    installed_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    # Relationships
    source: Mapped["CatalogSource"] = relationship(
        "CatalogSource", back_populates="installed_items"
    )
