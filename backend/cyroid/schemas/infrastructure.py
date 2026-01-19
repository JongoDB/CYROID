# backend/cyroid/schemas/infrastructure.py
"""Pydantic schemas for infrastructure observability."""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# Service Health Models
class ServiceHealth(BaseModel):
    """Health status for a single service."""
    name: str
    display_name: str
    status: Literal["healthy", "unhealthy", "degraded", "unknown"]
    container_id: Optional[str] = None
    container_status: Optional[str] = None
    uptime_seconds: Optional[int] = None
    uptime_human: Optional[str] = None
    cpu_percent: Optional[float] = None
    memory_mb: Optional[float] = None
    memory_limit_mb: Optional[float] = None
    memory_percent: Optional[float] = None
    ports: List[str] = Field(default_factory=list)
    health_check_output: Optional[str] = None
    last_checked: datetime


class InfrastructureServicesResponse(BaseModel):
    """Response for service health endpoint."""
    services: List[ServiceHealth]
    overall_status: Literal["healthy", "degraded", "unhealthy"]
    checked_at: datetime


# Log Models
class LogEntry(BaseModel):
    """A single log entry."""
    timestamp: Optional[datetime] = None
    level: Optional[str] = None
    message: str
    raw: str


class ServiceLogsResponse(BaseModel):
    """Response for logs endpoint."""
    service: str
    logs: List[LogEntry]
    total_lines: int
    has_more: bool
    filters_applied: Dict[str, Any] = Field(default_factory=dict)


# Docker Overview Models
class DockerContainerOverview(BaseModel):
    """Overview of a Docker container."""
    id: str
    name: str
    image: str
    status: str
    state: str
    created: Optional[datetime] = None
    ports: List[str] = Field(default_factory=list)
    labels: Dict[str, str] = Field(default_factory=dict)
    is_cyroid_infra: bool = False
    is_cyroid_vm: bool = False


class DockerNetworkOverview(BaseModel):
    """Overview of a Docker network."""
    id: str
    name: str
    driver: str
    scope: str
    internal: bool = False
    subnet: Optional[str] = None
    gateway: Optional[str] = None
    container_count: int = 0
    is_cyroid_range: bool = False


class DockerVolumeOverview(BaseModel):
    """Overview of a Docker volume."""
    name: str
    driver: str
    mountpoint: str
    created: Optional[datetime] = None
    size_bytes: Optional[int] = None
    labels: Dict[str, str] = Field(default_factory=dict)


class DockerImageOverview(BaseModel):
    """Overview of a Docker image."""
    id: str
    tags: List[str] = Field(default_factory=list)
    size_bytes: int
    size_human: str
    created: Optional[datetime] = None
    is_cyroid_related: bool = False


class DockerSummary(BaseModel):
    """Summary counts for Docker resources."""
    total_containers: int = 0
    running_containers: int = 0
    stopped_containers: int = 0
    cyroid_vms: int = 0
    cyroid_infra: int = 0
    total_networks: int = 0
    cyroid_networks: int = 0
    total_volumes: int = 0
    total_images: int = 0


class DockerOverviewResponse(BaseModel):
    """Response for Docker overview endpoint."""
    containers: List[DockerContainerOverview]
    networks: List[DockerNetworkOverview]
    volumes: List[DockerVolumeOverview]
    images: List[DockerImageOverview]
    summary: DockerSummary


# Resource Metrics Models
class HostMetrics(BaseModel):
    """Host system metrics."""
    cpu_count: int
    cpu_percent: float
    memory_total_mb: float
    memory_used_mb: float
    memory_available_mb: float
    memory_percent: float
    disk_total_gb: float
    disk_used_gb: float
    disk_free_gb: float
    disk_percent: float
    load_average: Optional[List[float]] = None  # 1, 5, 15 min


class DatabaseMetrics(BaseModel):
    """PostgreSQL database metrics."""
    connection_count: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    database_size_mb: float = 0.0
    database_size_human: str = "0 MB"
    table_count: int = 0
    largest_tables: List[Dict[str, Any]] = Field(default_factory=list)


class TaskQueueMetrics(BaseModel):
    """Dramatiq task queue metrics."""
    queue_length: int = 0
    workers_active: int = 0
    messages_total: int = 0
    delayed_messages: int = 0


class StorageMetrics(BaseModel):
    """Storage utilization metrics."""
    minio_bucket_count: int = 0
    minio_total_objects: int = 0
    minio_total_size_mb: float = 0.0
    iso_cache_size_mb: float = 0.0
    iso_cache_files: int = 0
    template_storage_size_mb: float = 0.0
    template_storage_files: int = 0
    vm_storage_size_mb: float = 0.0
    vm_storage_dirs: int = 0


class InfrastructureMetricsResponse(BaseModel):
    """Response for metrics endpoint."""
    host: HostMetrics
    database: DatabaseMetrics
    task_queue: TaskQueueMetrics
    storage: StorageMetrics
    collected_at: datetime


# System Info Models
class MigrationInfo(BaseModel):
    """Information about a database migration."""
    revision: str
    description: str
    applied: bool = True


class ConfigItem(BaseModel):
    """A configuration item (non-sensitive)."""
    key: str
    value: str
    source: str = "default"  # "default", "env", "file"


class SystemInfoResponse(BaseModel):
    """Response for system info endpoint."""
    version: str
    commit: str
    build_date: str
    app_name: str
    python_version: str
    docker_version: Optional[str] = None
    architecture: str
    is_arm: bool
    database_revision: Optional[str] = None
    migrations: List[MigrationInfo] = Field(default_factory=list)
    config: List[ConfigItem] = Field(default_factory=list)
