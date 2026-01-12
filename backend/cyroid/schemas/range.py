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

    class Config:
        from_attributes = True


class RangeDetailResponse(RangeResponse):
    """Range with nested networks and VMs"""
    networks: List["NetworkResponse"] = []
    vms: List["VMResponse"] = []


# Import and rebuild for forward references
from cyroid.schemas.network import NetworkResponse
from cyroid.schemas.vm import VMResponse

RangeDetailResponse.model_rebuild()
