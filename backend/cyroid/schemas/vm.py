# backend/cyroid/schemas/vm.py
from datetime import datetime
from typing import Optional, Literal
from uuid import UUID
from pydantic import BaseModel, Field, computed_field, field_serializer, model_validator

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

    # Image Library sources (new - preferred)
    base_image_id: Optional[UUID] = None
    golden_image_id: Optional[UUID] = None
    snapshot_id: Optional[UUID] = None
    # Deprecated (kept for backward compatibility)
    template_id: Optional[UUID] = None

    @model_validator(mode='after')
    def check_source(self) -> 'VMCreate':
        """Ensure exactly one image source is provided."""
        sources = [
            self.base_image_id,
            self.golden_image_id,
            self.snapshot_id,
            self.template_id,
        ]
        set_count = sum(1 for s in sources if s is not None)

        if set_count == 0:
            raise ValueError(
                "Must provide exactly one of: base_image_id, golden_image_id, "
                "snapshot_id, or template_id (deprecated)"
            )
        if set_count > 1:
            raise ValueError(
                "Cannot specify multiple image sources. "
                "Provide exactly one of: base_image_id, golden_image_id, "
                "snapshot_id, or template_id"
            )

        return self

    # Windows-specific settings (for dockur/windows VMs)
    # Version codes: 11, 11l, 11e, 10, 10l, 10e, 8e, 7u, vu, xp, 2k, 2025, 2022, 2019, 2016, 2012, 2008, 2003
    windows_version: Optional[str] = Field(None, max_length=10, description="Windows version code for dockur/windows")
    windows_username: Optional[str] = Field(None, max_length=64, description="Windows username (default: Docker)")
    windows_password: Optional[str] = Field(None, max_length=128, description="Windows password (default: empty)")
    iso_url: Optional[str] = Field(None, max_length=512, description="Custom ISO download URL")
    iso_path: Optional[str] = Field(None, max_length=512, description="Local ISO path for bind mount")
    display_type: Optional[str] = Field("desktop", description="Display type: 'desktop' (VNC/web console) or 'server' (RDP only)")

    # Network configuration
    use_dhcp: bool = Field(default=False, description="Use DHCP instead of static IP assignment")
    gateway: Optional[str] = Field(None, pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", description="Gateway IP address")
    dns_servers: Optional[str] = Field(None, max_length=100, description="DNS servers (comma-separated)")

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

    # Linux user configuration (for cloud-init in qemux/qemu, env vars in KasmVNC/LinuxServer)
    linux_username: Optional[str] = Field(None, max_length=64, description="Linux username")
    linux_password: Optional[str] = Field(None, max_length=128, description="Linux password")
    linux_user_sudo: bool = Field(default=True, description="Grant sudo/admin privileges to the user")

    # Boot source for QEMU-based VMs (Windows via dockur, Linux via qemux)
    # golden_image = boot from pre-configured snapshot (fast)
    # fresh_install = boot from cached ISO (requires install)
    boot_source: Optional[Literal["golden_image", "fresh_install"]] = Field(
        None,
        description="Boot source for QEMU VMs: 'golden_image' (pre-configured) or 'fresh_install' (from ISO)"
    )


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
    # Network configuration
    use_dhcp: Optional[bool] = None
    gateway: Optional[str] = Field(None, pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    dns_servers: Optional[str] = Field(None, max_length=100)
    # Extended configuration
    disk2_gb: Optional[int] = Field(None, ge=1, le=1000)
    disk3_gb: Optional[int] = Field(None, ge=1, le=1000)
    enable_shared_folder: Optional[bool] = None
    enable_global_shared: Optional[bool] = None
    language: Optional[str] = Field(None, max_length=50)
    keyboard: Optional[str] = Field(None, max_length=20)
    region: Optional[str] = Field(None, max_length=20)
    manual_install: Optional[bool] = None
    # Linux user configuration
    linux_username: Optional[str] = Field(None, max_length=64)
    linux_password: Optional[str] = Field(None, max_length=128)
    linux_user_sudo: Optional[bool] = None
    # Boot source for QEMU VMs
    boot_source: Optional[Literal["golden_image", "fresh_install"]] = None


class VMResponse(VMBase):
    id: UUID
    range_id: UUID
    network_id: UUID
    # Image Library sources (new)
    base_image_id: Optional[UUID] = None
    golden_image_id: Optional[UUID] = None
    snapshot_id: Optional[UUID] = None
    # Deprecated template reference
    template_id: Optional[UUID] = None
    status: VMStatus
    error_message: Optional[str] = None
    container_id: Optional[str] = None
    # Windows-specific fields
    windows_version: Optional[str] = None
    windows_username: Optional[str] = None
    # Note: windows_password not included in response for security
    iso_url: Optional[str] = None
    iso_path: Optional[str] = None
    display_type: Optional[str] = "desktop"
    # Network configuration
    use_dhcp: bool = False
    gateway: Optional[str] = None
    dns_servers: Optional[str] = None
    # Extended configuration
    disk2_gb: Optional[int] = None
    disk3_gb: Optional[int] = None
    enable_shared_folder: bool = False
    enable_global_shared: bool = False
    language: Optional[str] = None
    keyboard: Optional[str] = None
    region: Optional[str] = None
    manual_install: bool = False
    # Linux user configuration (password excluded for security)
    linux_username: Optional[str] = None
    linux_user_sudo: bool = True
    # Boot source for QEMU VMs
    boot_source: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Multi-architecture support - computed by API
    emulated: bool = False
    emulation_warning: Optional[str] = None

    class Config:
        from_attributes = True

    @field_serializer('status')
    def serialize_status(self, status: VMStatus) -> str:
        """Return lowercase status for frontend compatibility."""
        return status.value.lower()
