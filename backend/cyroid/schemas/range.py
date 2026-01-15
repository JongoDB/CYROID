# backend/cyroid/schemas/range.py
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from uuid import UUID
from pydantic import BaseModel, Field

from cyroid.models.range import RangeStatus

if TYPE_CHECKING:
    from cyroid.schemas.network import NetworkResponse
    from cyroid.schemas.vm import VMResponse


class RangeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None


class RangeCreate(RangeBase):
    pass


class RangeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None


class RangeResponse(RangeBase):
    id: UUID
    status: RangeStatus
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    network_count: int = 0
    vm_count: int = 0

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_with_counts(cls, range_obj):
        """Create response with network and VM counts."""
        return cls(
            id=range_obj.id,
            name=range_obj.name,
            description=range_obj.description,
            status=range_obj.status,
            created_by=range_obj.created_by,
            created_at=range_obj.created_at,
            updated_at=range_obj.updated_at,
            network_count=len(range_obj.networks) if range_obj.networks else 0,
            vm_count=len(range_obj.vms) if range_obj.vms else 0,
        )


class RangeDetailResponse(RangeResponse):
    """Range with nested networks and VMs"""
    networks: List["NetworkResponse"] = []
    vms: List["VMResponse"] = []


# Import and rebuild for forward references
from cyroid.schemas.network import NetworkResponse
from cyroid.schemas.vm import VMResponse

RangeDetailResponse.model_rebuild()


# Range Template Export/Import schemas
class NetworkTemplateData(BaseModel):
    """Network data for range template."""
    name: str
    subnet: str
    gateway: Optional[str] = None
    isolation_level: str = "complete"


class VMTemplateData(BaseModel):
    """VM data for range template."""
    hostname: str
    ip_address: str
    network_name: str  # Reference to network by name
    template_name: str  # Reference to VM template by name
    cpu: int
    ram_mb: int
    disk_gb: int
    position_x: int = 0
    position_y: int = 0


class RangeTemplateExport(BaseModel):
    """Full range template for export/import."""
    version: str = "1.0"
    name: str
    description: Optional[str] = None
    networks: List[NetworkTemplateData] = []
    vms: List[VMTemplateData] = []


class RangeTemplateImport(BaseModel):
    """Import a range from template."""
    template: RangeTemplateExport
    name_override: Optional[str] = None  # Override range name
