# backend/cyroid/schemas/network.py
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class NetworkBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    subnet: str = Field(..., pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$")  # CIDR notation
    gateway: str = Field(..., pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    dns_servers: Optional[str] = None
    is_isolated: bool = True  # Isolated by default for security


class NetworkCreate(NetworkBase):
    range_id: UUID


class NetworkUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    dns_servers: Optional[str] = None
    is_isolated: Optional[bool] = None


class NetworkResponse(NetworkBase):
    id: UUID
    range_id: UUID
    docker_network_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
