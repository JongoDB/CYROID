# backend/cyroid/schemas/network.py
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class NetworkBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    subnet: str = Field(..., pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$")  # CIDR notation
    gateway: str = Field(..., pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    dns_servers: Optional[str] = "8.8.8.8,8.8.4.4"  # Comma-separated DNS servers
    dns_search: Optional[str] = None  # Search domain (e.g., "corp.local")
    is_isolated: bool = True  # Isolated by default for security
    internet_enabled: bool = False  # Internet access via VyOS NAT
    dhcp_enabled: bool = False  # VyOS DHCP server for this network


class NetworkCreate(NetworkBase):
    range_id: UUID


class NetworkUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    dns_servers: Optional[str] = None
    dns_search: Optional[str] = None
    is_isolated: Optional[bool] = None
    internet_enabled: Optional[bool] = None
    dhcp_enabled: Optional[bool] = None


class NetworkResponse(NetworkBase):
    id: UUID
    range_id: UUID
    docker_network_id: Optional[str] = None
    vyos_interface: Optional[str] = None  # eth1, eth2, etc.
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
