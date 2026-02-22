# backend/cyroid/schemas/blueprint.py
from typing import Optional, List, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


# ============ Config Sub-schemas ============

class NetworkConfig(BaseModel):
    name: str
    subnet: str
    gateway: str
    is_isolated: bool = False
    internet_enabled: bool = False
    dhcp_enabled: bool = False


class NetworkInterfaceConfig(BaseModel):
    """Network interface configuration for multi-NIC VMs in blueprints."""
    network_name: str
    ip_address: Optional[str] = None  # None = auto-assign on import
    is_primary: bool = False


class VMConfig(BaseModel):
    hostname: str
    # Legacy fields (kept for backward compatibility with older blueprints)
    ip_address: Optional[str] = None
    network_name: Optional[str] = None
    # Multi-NIC support: list of network interfaces
    # If present, takes precedence over legacy ip_address/network_name
    network_interfaces: Optional[List[NetworkInterfaceConfig]] = None
    # Image Library sources - exactly one required
    base_image_id: Optional[str] = None
    golden_image_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    # Fallback fields for cross-environment portability (Issue #80)
    base_image_name: Optional[str] = None
    base_image_tag: Optional[str] = None
    # Deprecated: kept for backward compatibility with older blueprints
    template_name: Optional[str] = None
    cpu: int = 1
    ram_mb: int = 1024
    disk_gb: int = 20
    position_x: Optional[int] = None
    position_y: Optional[int] = None
    # Windows version code for dockur/windows VMs (e.g., "11", "10", "2022")
    windows_version: Optional[str] = None
    # Environment variables passed to the container at runtime
    environment: Optional[dict[str, str]] = None


class RouterConfig(BaseModel):
    enabled: bool = True
    dhcp_enabled: bool = False


class MSELConfig(BaseModel):
    content: Optional[str] = None
    format: str = "yaml"
    walkthrough: Optional[dict] = None  # Structured walkthrough/guide content


class BlueprintConfig(BaseModel):
    networks: List[NetworkConfig]
    vms: List[VMConfig]
    router: Optional[RouterConfig] = None
    msel: Optional[MSELConfig] = None
    content_ids: Optional[List[str]] = None  # Linked content IDs for static reference


# ============ Blueprint Schemas ============

class BlueprintCreate(BaseModel):
    range_id: UUID
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    # DEPRECATED: No longer used with DinD isolation - kept for backward compatibility
    base_subnet_prefix: Optional[str] = Field(default=None, pattern=r"^\d{1,3}\.\d{1,3}(\.\d{1,3}\.\d{1,3}/\d{1,2})?$")


class BlueprintUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    content_ids: Optional[List[str]] = None  # Linked content for training events
    config: Optional[BlueprintConfig] = None  # Direct config update (increments version)


class BlueprintResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    version: int
    # DEPRECATED: No longer used with DinD isolation - kept for backward compatibility
    base_subnet_prefix: Optional[str] = None
    next_offset: Optional[int] = 0
    content_ids: List[str] = []  # Linked content for training events
    created_by: Optional[UUID] = None  # Nullable for seed blueprints
    created_at: datetime
    updated_at: datetime
    network_count: int = 0
    vm_count: int = 0
    instance_count: int = 0
    is_seed: bool = False  # True for built-in blueprints

    class Config:
        from_attributes = True


class BlueprintDetailResponse(BlueprintResponse):
    config: BlueprintConfig
    created_by_username: Optional[str] = None


# ============ Instance Schemas ============

class InstanceDeploy(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    auto_deploy: bool = True


class InstanceResponse(BaseModel):
    id: UUID
    name: str
    blueprint_id: UUID
    blueprint_version: int
    subnet_offset: int
    instructor_id: UUID
    range_id: UUID
    created_at: datetime
    # Denormalized fields for convenience
    range_name: Optional[str] = None
    range_status: Optional[str] = None
    instructor_username: Optional[str] = None

    class Config:
        from_attributes = True
