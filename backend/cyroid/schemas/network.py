# backend/cyroid/schemas/network.py
import ipaddress
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, model_validator


class NetworkBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    subnet: str = Field(..., pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$")  # CIDR notation
    gateway: Optional[str] = Field(None, pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")  # Auto-filled if not provided
    dns_servers: Optional[str] = "8.8.8.8,8.8.4.4"  # Comma-separated DNS servers
    dns_search: Optional[str] = None  # Search domain (e.g., "corp.local")
    is_isolated: bool = True  # Isolated by default for security
    internet_enabled: bool = False  # Internet access via VyOS NAT
    dhcp_enabled: bool = False  # VyOS DHCP server for this network

    @model_validator(mode='after')
    def auto_fill_gateway(self) -> 'NetworkBase':
        """Auto-fill gateway as first host IP in subnet if not provided."""
        if self.gateway is None and self.subnet:
            try:
                network = ipaddress.ip_network(self.subnet, strict=False)
                # Use .1 as the default gateway (first usable host)
                self.gateway = str(network.network_address + 1)
            except ValueError:
                pass  # Invalid subnet format, let validation catch it
        return self


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
