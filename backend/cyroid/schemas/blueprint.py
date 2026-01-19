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


class VMConfig(BaseModel):
    hostname: str
    ip_address: str
    network_name: str
    template_name: str
    cpu: int = 1
    ram_mb: int = 1024
    disk_gb: int = 20
    position_x: Optional[int] = None
    position_y: Optional[int] = None


class RouterConfig(BaseModel):
    enabled: bool = True
    dhcp_enabled: bool = False


class MSELConfig(BaseModel):
    content: Optional[str] = None
    format: str = "yaml"


class BlueprintConfig(BaseModel):
    networks: List[NetworkConfig]
    vms: List[VMConfig]
    router: Optional[RouterConfig] = None
    msel: Optional[MSELConfig] = None


# ============ Blueprint Schemas ============

class BlueprintCreate(BaseModel):
    range_id: UUID
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    base_subnet_prefix: str = Field(..., pattern=r"^\d{1,3}\.\d{1,3}$")  # e.g., "10.100"


class BlueprintUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None


class BlueprintResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    version: int
    base_subnet_prefix: str
    next_offset: int
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
