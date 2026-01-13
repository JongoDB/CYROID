# backend/cyroid/schemas/vm.py
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

from cyroid.models.vm import VMStatus


class VMBase(BaseModel):
    hostname: str = Field(..., min_length=1, max_length=63)
    ip_address: str = Field(..., pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    cpu: int = Field(ge=1, le=32)
    ram_mb: int = Field(ge=512, le=131072)
    disk_gb: int = Field(ge=10, le=1000)
    position_x: int = Field(default=0)
    position_y: int = Field(default=0)


class VMCreate(VMBase):
    range_id: UUID
    network_id: UUID
    template_id: UUID
    # Windows-specific settings (for dockur/windows VMs)
    # Version codes: 11, 11l, 11e, 10, 10l, 10e, 8e, 7u, vu, xp, 2k, 2025, 2022, 2019, 2016, 2012, 2008, 2003
    windows_version: Optional[str] = Field(None, max_length=10, description="Windows version code for dockur/windows")
    windows_username: Optional[str] = Field(None, max_length=64, description="Windows username (default: Docker)")
    windows_password: Optional[str] = Field(None, max_length=128, description="Windows password (default: empty)")
    iso_url: Optional[str] = Field(None, max_length=512, description="Custom ISO download URL")
    iso_path: Optional[str] = Field(None, max_length=512, description="Local ISO path for bind mount")
    display_type: Optional[str] = Field("desktop", description="Display type: 'desktop' (VNC/web console) or 'server' (RDP only)")


class VMUpdate(BaseModel):
    hostname: Optional[str] = Field(None, min_length=1, max_length=63)
    ip_address: Optional[str] = Field(None, pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    cpu: Optional[int] = Field(None, ge=1, le=32)
    ram_mb: Optional[int] = Field(None, ge=512, le=131072)
    disk_gb: Optional[int] = Field(None, ge=10, le=1000)
    position_x: Optional[int] = None
    position_y: Optional[int] = None
    # Windows settings can be updated
    windows_version: Optional[str] = Field(None, max_length=10)
    windows_username: Optional[str] = Field(None, max_length=64)
    windows_password: Optional[str] = Field(None, max_length=128)
    iso_url: Optional[str] = Field(None, max_length=512)
    iso_path: Optional[str] = Field(None, max_length=512)
    display_type: Optional[str] = Field(None, max_length=20)


class VMResponse(VMBase):
    id: UUID
    range_id: UUID
    network_id: UUID
    template_id: UUID
    status: VMStatus
    container_id: Optional[str] = None
    # Windows-specific fields
    windows_version: Optional[str] = None
    windows_username: Optional[str] = None
    # Note: windows_password not included in response for security
    iso_url: Optional[str] = None
    iso_path: Optional[str] = None
    display_type: Optional[str] = "desktop"
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
