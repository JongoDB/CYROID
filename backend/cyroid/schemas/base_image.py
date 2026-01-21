# backend/cyroid/schemas/base_image.py
"""Pydantic schemas for BaseImage model."""
from datetime import datetime
from typing import Optional, List, Literal
from uuid import UUID
from pydantic import BaseModel, Field


class BaseImageBase(BaseModel):
    """Base schema with common fields."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    image_type: Literal["container", "iso"]
    os_type: Literal["windows", "linux", "macos", "network", "custom"]
    vm_type: Literal["container", "linux_vm", "windows_vm", "macos_vm"]
    native_arch: str = Field(default="x86_64", max_length=20)
    default_cpu: int = Field(default=2, ge=1, le=32)
    default_ram_mb: int = Field(default=4096, ge=512, le=131072)
    default_disk_gb: int = Field(default=40, ge=10, le=1000)
    tags: List[str] = Field(default_factory=list)


class BaseImageCreate(BaseImageBase):
    """Schema for creating a BaseImage."""
    # Container-specific fields
    docker_image_tag: Optional[str] = Field(None, max_length=255)
    docker_image_id: Optional[str] = Field(None, max_length=128)
    # ISO-specific fields
    iso_path: Optional[str] = Field(None, max_length=500)
    iso_source: Optional[str] = Field(None, max_length=50)  # windows, linux, custom
    iso_version: Optional[str] = Field(None, max_length=50)
    # Size
    size_bytes: Optional[int] = None


class BaseImageUpdate(BaseModel):
    """Schema for updating a BaseImage."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    os_type: Optional[Literal["windows", "linux", "macos", "network", "custom"]] = None
    native_arch: Optional[str] = Field(None, max_length=20)
    default_cpu: Optional[int] = Field(None, ge=1, le=32)
    default_ram_mb: Optional[int] = Field(None, ge=512, le=131072)
    default_disk_gb: Optional[int] = Field(None, ge=10, le=1000)
    tags: Optional[List[str]] = None
    is_global: Optional[bool] = None


class BaseImageResponse(BaseImageBase):
    """Schema for BaseImage response."""
    id: UUID
    docker_image_id: Optional[str] = None
    docker_image_tag: Optional[str] = None
    iso_path: Optional[str] = None
    iso_source: Optional[str] = None
    iso_version: Optional[str] = None
    size_bytes: Optional[int] = None
    is_global: bool
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BaseImageBrief(BaseModel):
    """Brief schema for BaseImage (used in listings/dropdowns)."""
    id: UUID
    name: str
    image_type: str
    os_type: str
    vm_type: str
    native_arch: str
    default_cpu: int
    default_ram_mb: int
    default_disk_gb: int
    size_bytes: Optional[int] = None

    class Config:
        from_attributes = True
