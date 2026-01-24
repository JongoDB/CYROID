# backend/cyroid/schemas/deployment_status.py
from typing import Optional, List
from pydantic import BaseModel


class ResourceStatus(BaseModel):
    id: Optional[str] = None
    name: str
    status: str  # pending, creating, starting, running, created, stopped, failed
    status_detail: Optional[str] = None
    duration_ms: Optional[int] = None


class NetworkStatus(ResourceStatus):
    subnet: str


class VMStatus(ResourceStatus):
    hostname: str
    ip: Optional[str] = None


class DeploymentSummary(BaseModel):
    total: int
    completed: int
    in_progress: int
    failed: int
    pending: int


class DeploymentStatusResponse(BaseModel):
    status: str
    elapsed_seconds: int
    started_at: Optional[str] = None
    current_step: Optional[str] = None  # Latest deployment step message (e.g., image transfer progress)
    summary: DeploymentSummary
    router: Optional[ResourceStatus] = None
    networks: List[NetworkStatus]
    vms: List[VMStatus]
