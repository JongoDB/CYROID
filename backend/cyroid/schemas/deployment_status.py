# backend/cyroid/schemas/deployment_status.py
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


def to_camel(string: str) -> str:
    """Convert snake_case to camelCase."""
    components = string.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


class CamelModel(BaseModel):
    """Base model that converts snake_case to camelCase in JSON output."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class ResourceStatus(CamelModel):
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


class DeploymentSummary(CamelModel):
    total: int
    completed: int
    in_progress: int
    failed: int
    pending: int


class DeploymentStatusResponse(CamelModel):
    status: str
    elapsed_seconds: int
    started_at: Optional[str] = None
    current_step: Optional[str] = None  # Latest deployment step message (e.g., image transfer progress)
    current_stage: Optional[int] = None  # Current deployment stage (1-4)
    total_stages: Optional[int] = None  # Total number of stages
    stage_name: Optional[str] = None  # Human-readable stage name
    summary: DeploymentSummary
    router: Optional[ResourceStatus] = None
    networks: List[NetworkStatus]
    vms: List[VMStatus]
