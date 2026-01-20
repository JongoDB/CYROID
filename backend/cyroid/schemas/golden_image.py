# backend/cyroid/schemas/golden_image.py
"""Pydantic schemas for GoldenImage model."""
from datetime import datetime
from typing import Optional, List, Literal
from uuid import UUID
from pydantic import BaseModel, Field

from cyroid.schemas.base_image import BaseImageBrief


class GoldenImageBase(BaseModel):
    """Base schema with common fields."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    os_type: Literal["windows", "linux", "network", "custom"]
    vm_type: Literal["container", "linux_vm", "windows_vm"]
    native_arch: str = Field(default="x86_64", max_length=20)
    default_cpu: int = Field(default=2, ge=1, le=32)
    default_ram_mb: int = Field(default=4096, ge=512, le=131072)
    default_disk_gb: int = Field(default=40, ge=10, le=1000)
    tags: List[str] = Field(default_factory=list)


class GoldenImageCreate(GoldenImageBase):
    """Schema for creating a GoldenImage (used for imports)."""
    source: Literal["snapshot", "import"]
    base_image_id: Optional[UUID] = None
    # Display settings
    display_type: Optional[str] = Field(None, max_length=20)
    vnc_port: int = Field(default=8006)


class GoldenImageUpdate(BaseModel):
    """Schema for updating a GoldenImage."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    os_type: Optional[Literal["windows", "linux", "network", "custom"]] = None
    native_arch: Optional[str] = Field(None, max_length=20)
    default_cpu: Optional[int] = Field(None, ge=1, le=32)
    default_ram_mb: Optional[int] = Field(None, ge=512, le=131072)
    default_disk_gb: Optional[int] = Field(None, ge=10, le=1000)
    tags: Optional[List[str]] = None
    is_global: Optional[bool] = None
    display_type: Optional[str] = Field(None, max_length=20)


class GoldenImageResponse(GoldenImageBase):
    """Schema for GoldenImage response."""
    id: UUID
    source: str
    base_image_id: Optional[UUID] = None
    source_vm_id: Optional[UUID] = None
    docker_image_id: Optional[str] = None
    docker_image_tag: Optional[str] = None
    disk_image_path: Optional[str] = None
    import_format: Optional[str] = None
    display_type: Optional[str] = None
    vnc_port: int
    size_bytes: Optional[int] = None
    is_global: bool
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    # Lineage info (populated when needed)
    base_image: Optional[BaseImageBrief] = None

    class Config:
        from_attributes = True


class GoldenImageBrief(BaseModel):
    """Brief schema for GoldenImage (used in listings/dropdowns)."""
    id: UUID
    name: str
    source: str
    os_type: str
    vm_type: str
    native_arch: str
    default_cpu: int
    default_ram_mb: int
    default_disk_gb: int
    size_bytes: Optional[int] = None
    # Lineage display
    base_image_name: Optional[str] = None

    class Config:
        from_attributes = True


class GoldenImageImportRequest(BaseModel):
    """Schema for importing an OVA/QCOW2/VMDK file as a GoldenImage."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    os_type: Literal["windows", "linux", "network", "custom"]
    vm_type: Literal["container", "linux_vm", "windows_vm"]
    native_arch: str = Field(default="x86_64", max_length=20)
    default_cpu: int = Field(default=2, ge=1, le=32)
    default_ram_mb: int = Field(default=4096, ge=512, le=131072)
    default_disk_gb: int = Field(default=40, ge=10, le=1000)
    tags: List[str] = Field(default_factory=list)
    display_type: Optional[str] = Field(None, max_length=20)
    vnc_port: int = Field(default=8006)
