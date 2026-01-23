# backend/cyroid/schemas/range.py
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from uuid import UUID
from pydantic import BaseModel, Field, field_serializer

from cyroid.models.range import RangeStatus
from cyroid.models.router import RouterStatus

if TYPE_CHECKING:
    from cyroid.schemas.network import NetworkResponse
    from cyroid.schemas.vm import VMResponse


class RouterResponse(BaseModel):
    """VyOS router status for a range."""
    id: UUID
    container_id: Optional[str] = None
    management_ip: Optional[str] = None
    status: RouterStatus
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @field_serializer('status')
    def serialize_status(self, status: RouterStatus) -> str:
        """Return lowercase status for frontend compatibility."""
        return status.value.lower()


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
    error_message: Optional[str] = None
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    deployed_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    network_count: int = 0
    vm_count: int = 0
    # Training content link
    student_guide_id: Optional[UUID] = None

    class Config:
        from_attributes = True

    @field_serializer('status')
    def serialize_status(self, status: RangeStatus) -> str:
        """Return lowercase status for frontend compatibility."""
        return status.value.lower()

    @classmethod
    def from_orm_with_counts(cls, range_obj):
        """Create response with network and VM counts."""
        return cls(
            id=range_obj.id,
            name=range_obj.name,
            description=range_obj.description,
            status=range_obj.status,
            error_message=range_obj.error_message,
            created_by=range_obj.created_by,
            created_at=range_obj.created_at,
            updated_at=range_obj.updated_at,
            deployed_at=range_obj.deployed_at,
            started_at=range_obj.started_at,
            stopped_at=range_obj.stopped_at,
            network_count=len(range_obj.networks) if range_obj.networks else 0,
            vm_count=len(range_obj.vms) if range_obj.vms else 0,
            student_guide_id=range_obj.student_guide_id,
        )


class RangeDetailResponse(RangeResponse):
    """Range with nested networks, VMs, and router status"""
    networks: List["NetworkResponse"] = []
    vms: List["VMResponse"] = []
    router: Optional[RouterResponse] = None


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
    is_isolated: bool = True


class VMTemplateData(BaseModel):
    """VM data for range template."""
    hostname: str
    ip_address: str
    network_name: str  # Reference to network by name
    # Image Library sources (at least one required)
    base_image_id: Optional[str] = None
    golden_image_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    # Legacy (for backwards compatibility with old exports)
    template_name: Optional[str] = None
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
