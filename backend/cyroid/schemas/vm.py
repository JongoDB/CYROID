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


class VMUpdate(BaseModel):
    hostname: Optional[str] = Field(None, min_length=1, max_length=63)
    ip_address: Optional[str] = Field(None, pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    cpu: Optional[int] = Field(None, ge=1, le=32)
    ram_mb: Optional[int] = Field(None, ge=512, le=131072)
    disk_gb: Optional[int] = Field(None, ge=10, le=1000)
    position_x: Optional[int] = None
    position_y: Optional[int] = None


class VMResponse(VMBase):
    id: UUID
    range_id: UUID
    network_id: UUID
    template_id: UUID
    status: VMStatus
    container_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
