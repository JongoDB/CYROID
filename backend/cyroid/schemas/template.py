# backend/cyroid/schemas/template.py
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field

from cyroid.models.template import OSType


class VMTemplateBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    os_type: OSType
    os_variant: str = Field(..., min_length=1, max_length=100)
    base_image: str = Field(..., min_length=1, max_length=255)
    default_cpu: int = Field(default=2, ge=1, le=32)
    default_ram_mb: int = Field(default=4096, ge=512, le=131072)
    default_disk_gb: int = Field(default=40, ge=10, le=1000)
    config_script: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    # Cached image support
    golden_image_path: Optional[str] = Field(None, max_length=500)
    cached_iso_path: Optional[str] = Field(None, max_length=500)
    is_cached: bool = Field(default=False)


class VMTemplateCreate(VMTemplateBase):
    pass


class VMTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    os_variant: Optional[str] = Field(None, min_length=1, max_length=100)
    base_image: Optional[str] = Field(None, min_length=1, max_length=255)
    default_cpu: Optional[int] = Field(None, ge=1, le=32)
    default_ram_mb: Optional[int] = Field(None, ge=512, le=131072)
    default_disk_gb: Optional[int] = Field(None, ge=10, le=1000)
    config_script: Optional[str] = None
    tags: Optional[List[str]] = None
    # Cached image support
    golden_image_path: Optional[str] = Field(None, max_length=500)
    cached_iso_path: Optional[str] = Field(None, max_length=500)
    is_cached: Optional[bool] = None


class VMTemplateResponse(VMTemplateBase):
    id: UUID
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
