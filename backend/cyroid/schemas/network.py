# backend/cyroid/schemas/network.py
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

from cyroid.models.network import IsolationLevel


class NetworkBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    subnet: str = Field(..., pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$")  # CIDR notation
    gateway: str = Field(..., pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    dns_servers: Optional[str] = None
    isolation_level: IsolationLevel = IsolationLevel.COMPLETE


class NetworkCreate(NetworkBase):
    range_id: UUID


class NetworkUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    dns_servers: Optional[str] = None
    isolation_level: Optional[IsolationLevel] = None


class NetworkResponse(NetworkBase):
    id: UUID
    range_id: UUID
    docker_network_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
