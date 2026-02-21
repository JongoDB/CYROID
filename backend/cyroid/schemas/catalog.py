# backend/cyroid/schemas/catalog.py
"""Pydantic schemas for Catalog API."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from cyroid.models.catalog import CatalogItemType, CatalogSourceType, CatalogSyncStatus


# ============ Catalog Source Schemas ============

class CatalogSourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    source_type: CatalogSourceType = CatalogSourceType.GIT
    url: str = Field(..., min_length=1, max_length=500)
    branch: str = Field(default="main", max_length=100)
    enabled: bool = True


class CatalogSourceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    url: Optional[str] = Field(None, min_length=1, max_length=500)
    branch: Optional[str] = Field(None, max_length=100)
    enabled: Optional[bool] = None


class CatalogSourceResponse(BaseModel):
    id: UUID
    name: str
    source_type: CatalogSourceType
    url: str
    branch: str
    enabled: bool
    sync_status: CatalogSyncStatus
    error_message: Optional[str] = None
    item_count: int = 0
    last_synced: Optional[datetime] = None
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============ Catalog Item Schemas (from index.json) ============

class CatalogItemSummary(BaseModel):
    """An item from the catalog index."""
    id: str
    type: CatalogItemType
    name: str
    description: str = ""
    tags: List[str] = []
    version: str = "1.0"
    path: str = ""
    checksum: str = ""
    # Blueprint-specific
    requires_images: List[str] = []
    requires_base_images: List[str] = []
    includes_msel: bool = False
    includes_content: bool = False
    # Image-specific
    arch: Optional[str] = None
    docker_tag: Optional[str] = None
    # Install status (populated at query time)
    installed: bool = False
    installed_version: Optional[str] = None
    update_available: bool = False


class CatalogItemDetail(CatalogItemSummary):
    """Full item detail including README content."""
    readme: Optional[str] = None
    source_id: Optional[UUID] = None


# ============ Installed Item Schemas ============

class CatalogInstalledItemResponse(BaseModel):
    id: UUID
    catalog_source_id: UUID
    catalog_item_id: str
    item_type: CatalogItemType
    item_name: str
    installed_version: str
    installed_checksum: Optional[str] = None
    local_resource_id: Optional[UUID] = None
    installed_by: Optional[UUID] = None
    installed_at: datetime
    update_available: bool = False

    class Config:
        from_attributes = True


# ============ Install Request ============

class CatalogInstallRequest(BaseModel):
    source_id: UUID
    build_images: bool = False


# ============ Catalog Index (from index.json) ============

class CatalogIndex(BaseModel):
    catalog: dict = {}
    items: List[CatalogItemSummary] = []
