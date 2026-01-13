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

    # Extended dockur/windows configuration
    # Network mode
    use_dhcp: bool = Field(default=False, description="Use DHCP instead of static IP assignment")

    # Additional storage (appears as D:, E: drives in Windows)
    disk2_gb: Optional[int] = Field(None, ge=1, le=1000, description="Second disk size in GB")
    disk3_gb: Optional[int] = Field(None, ge=1, le=1000, description="Third disk size in GB")

    # Shared folders
    enable_shared_folder: bool = Field(default=False, description="Enable per-VM shared folder (/shared)")
    enable_global_shared: bool = Field(default=False, description="Mount global shared folder (/global, read-only)")

    # Localization
    language: Optional[str] = Field(None, max_length=50, description="Windows language (e.g., French, German)")
    keyboard: Optional[str] = Field(None, max_length=20, description="Keyboard layout (e.g., en-US, de-DE)")
    region: Optional[str] = Field(None, max_length=20, description="Regional settings (e.g., en-US, fr-FR)")

    # Installation mode
    manual_install: bool = Field(default=False, description="Enable manual/interactive installation mode")


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
    # Extended dockur/windows configuration
    use_dhcp: Optional[bool] = None
    disk2_gb: Optional[int] = Field(None, ge=1, le=1000)
    disk3_gb: Optional[int] = Field(None, ge=1, le=1000)
    enable_shared_folder: Optional[bool] = None
    enable_global_shared: Optional[bool] = None
    language: Optional[str] = Field(None, max_length=50)
    keyboard: Optional[str] = Field(None, max_length=20)
    region: Optional[str] = Field(None, max_length=20)
    manual_install: Optional[bool] = None


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
    # Extended dockur/windows configuration
    use_dhcp: bool = False
    disk2_gb: Optional[int] = None
    disk3_gb: Optional[int] = None
    enable_shared_folder: bool = False
    enable_global_shared: bool = False
    language: Optional[str] = None
    keyboard: Optional[str] = None
    region: Optional[str] = None
    manual_install: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
