# cyroid/schemas/snapshot.py
"""Pydantic schemas for Snapshot model (forks in the Image Library)."""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from uuid import UUID


class SnapshotBase(BaseModel):
    """Base schema with common fields."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None


class SnapshotCreate(SnapshotBase):
    """Schema for creating a Snapshot."""
    vm_id: UUID


class SnapshotUpdate(BaseModel):
    """Schema for updating a Snapshot."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_global: Optional[bool] = None
    tags: Optional[List[str]] = None


class SnapshotResponse(SnapshotBase):
    """Schema for Snapshot response."""
    id: UUID
    vm_id: Optional[UUID] = None
    # Lineage tracking
    golden_image_id: Optional[UUID] = None
    parent_snapshot_id: Optional[UUID] = None
    # Docker image info
    docker_image_id: Optional[str] = None
    docker_image_tag: Optional[str] = None
    # Metadata
    os_type: Optional[str] = None
    vm_type: Optional[str] = None
    # Resource defaults
    default_cpu: int = 2
    default_ram_mb: int = 4096
    default_disk_gb: int = 40
    # Display
    display_type: Optional[str] = None
    vnc_port: int = 8006
    # Visibility
    is_global: bool = True
    tags: List[str] = []
    # Timestamps
    created_at: datetime

    class Config:
        from_attributes = True


class SnapshotBrief(BaseModel):
    """Brief schema for Snapshot (used in listings/dropdowns)."""
    id: UUID
    name: str
    os_type: Optional[str] = None
    vm_type: Optional[str] = None
    default_cpu: int = 2
    default_ram_mb: int = 4096
    default_disk_gb: int = 40
    # Lineage display
    golden_image_name: Optional[str] = None

    class Config:
        from_attributes = True
