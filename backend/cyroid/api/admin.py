# backend/cyroid/api/admin.py
"""
Administrative API endpoints.

These endpoints require admin privileges and provide system-wide operations
like cleanup, diagnostics, and maintenance.
"""
import logging
import os
import platform
import re
import sys
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Optional

import psutil
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from cyroid.api.deps import get_current_user, require_admin, get_db
from cyroid.config import get_settings
from cyroid.models.user import User
from cyroid.models.range import Range, RangeStatus
from cyroid.models.vm import VM, VMStatus
from cyroid.models.network import Network
from cyroid.models.blueprint import RangeInstance
from cyroid.services.docker_service import get_docker_service
from cyroid.services.dind_service import get_dind_service
from cyroid.schemas.infrastructure import (
    ServiceHealth,
    InfrastructureServicesResponse,
    LogEntry,
    ServiceLogsResponse,
    DockerContainerOverview,
    DockerNetworkOverview,
    DockerVolumeOverview,
    DockerImageOverview,
    DockerSummary,
    DockerOverviewResponse,
    HostMetrics,
    DatabaseMetrics,
    TaskQueueMetrics,
    StorageMetrics,
    InfrastructureMetricsResponse,
    MigrationInfo,
    ConfigItem,
    SystemInfoResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

# Type aliases
DBSession = Annotated[Session, Depends(get_db)]
AdminUser = Annotated[User, Depends(require_admin())]


class CleanupResult(BaseModel):
    """Result of a cleanup operation."""
    ranges_cleaned: int
    dind_containers_removed: int
    containers_removed: int
    networks_removed: int
    database_records_updated: int
    database_records_deleted: int
    errors: List[str]
    orphaned_resources_cleaned: int


class CleanupMode(str):
    """Cleanup operation mode."""
    RESET_TO_DRAFT = "reset_to_draft"  # Stop DinD containers, reset DB to draft state
    PURGE_RANGES = "purge_ranges"  # Delete DinD containers AND DB records


class CleanupRequest(BaseModel):
    """Options for cleanup operation."""
    mode: str = CleanupMode.RESET_TO_DRAFT  # "reset_to_draft" or "purge_ranges"
    # Legacy fields for backwards compatibility
    clean_database: bool = True
    delete_database_records: bool = False
    force: bool = False


@router.post("/cleanup-all", response_model=CleanupResult)
def cleanup_all_resources(
    db: DBSession,
    admin_user: AdminUser,
    options: Optional[CleanupRequest] = None,
):
    """
    Cleanup CYROID range resources with two modes:

    **reset_to_draft**: Stop all DinD containers, reset ranges to draft state (keeps range definitions)
    **purge_ranges**: Delete all DinD containers AND range records from database (keeps templates, ISOs)

    **Requires admin privileges.**
    """
    import asyncio

    if options is None:
        options = CleanupRequest()

    # Handle legacy options
    if options.delete_database_records:
        options.mode = CleanupMode.PURGE_RANGES
    elif options.clean_database:
        options.mode = CleanupMode.RESET_TO_DRAFT

    docker = get_docker_service()
    dind = get_dind_service()
    result = CleanupResult(
        ranges_cleaned=0,
        dind_containers_removed=0,
        containers_removed=0,
        networks_removed=0,
        database_records_updated=0,
        database_records_deleted=0,
        errors=[],
        orphaned_resources_cleaned=0,
    )

    logger.info(f"Admin cleanup initiated by user {admin_user.email}, mode={options.mode}")

    # Step 1: Get all ranges from database
    ranges = db.query(Range).all()

    for range_obj in ranges:
        try:
            range_id = str(range_obj.id)

            # Delete DinD container if exists (this cleans up all VMs/networks inside)
            if range_obj.dind_container_id or range_obj.dind_container_name:
                try:
                    # Run async delete synchronously
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(dind.delete_range_container(range_id))
                        result.dind_containers_removed += 1
                    finally:
                        loop.close()
                except Exception as e:
                    logger.warning(f"Could not delete DinD container for range {range_id}: {e}")

            # Also try legacy cleanup (for any pre-DinD containers/networks)
            try:
                cleanup_result = docker.cleanup_range(range_id)
                result.containers_removed += cleanup_result.get("containers", 0)
                result.networks_removed += cleanup_result.get("networks", 0)
            except Exception as e:
                logger.debug(f"Legacy cleanup for range {range_id}: {e}")

            result.ranges_cleaned += 1

            if options.mode == CleanupMode.PURGE_RANGES:
                # Delete all range data from database
                # First delete range_instances that reference this range
                range_instances = db.query(RangeInstance).filter(
                    RangeInstance.range_id == range_obj.id
                ).all()
                for instance in range_instances:
                    db.delete(instance)
                    result.database_records_deleted += 1

                # Delete VMs
                for vm in range_obj.vms:
                    db.delete(vm)
                    result.database_records_deleted += 1

                # Delete networks
                for network in range_obj.networks:
                    db.delete(network)
                    result.database_records_deleted += 1

                # Delete router if exists
                if range_obj.router:
                    db.delete(range_obj.router)
                    result.database_records_deleted += 1

                # Delete range
                db.delete(range_obj)
                result.database_records_deleted += 1

            else:  # RESET_TO_DRAFT
                # Reset range to draft state
                range_obj.status = RangeStatus.DRAFT
                range_obj.error_message = None
                range_obj.dind_container_id = None
                range_obj.dind_container_name = None
                range_obj.dind_mgmt_ip = None
                range_obj.dind_docker_url = None
                range_obj.deployed_at = None
                range_obj.started_at = None
                range_obj.stopped_at = None
                result.database_records_updated += 1

                # Reset all VMs
                for vm in range_obj.vms:
                    vm.status = VMStatus.PENDING
                    vm.container_id = None
                    vm.error_message = None
                    result.database_records_updated += 1

                # Reset networks
                for network in range_obj.networks:
                    network.docker_network_id = None
                    result.database_records_updated += 1

                # Reset router if exists
                if range_obj.router:
                    range_obj.router.container_id = None
                    range_obj.router.status = "pending"
                    result.database_records_updated += 1

        except Exception as e:
            error_msg = f"Failed to cleanup range {range_obj.name}: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)

    # Step 2: Clean up orphaned DinD containers (not tracked in database)
    logger.info("Cleaning up orphaned DinD containers...")
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            orphan_containers = loop.run_until_complete(dind.list_range_containers())
            for container in orphan_containers:
                try:
                    container_name = container.get("container_name", "")
                    # Force remove orphaned container
                    host_container = dind.host_client.containers.get(container_name)
                    host_container.stop(timeout=5)
                    host_container.remove(force=True)
                    result.orphaned_resources_cleaned += 1
                    logger.info(f"Removed orphaned DinD container: {container_name}")
                except Exception as e:
                    logger.warning(f"Could not remove orphan container: {e}")
        finally:
            loop.close()
    except Exception as e:
        error_msg = f"Failed orphan DinD cleanup: {e}"
        logger.warning(error_msg)

    # Step 3: Clean up any orphaned legacy Docker resources
    logger.info("Cleaning up orphaned legacy Docker resources...")
    try:
        orphan_cleanup = docker.cleanup_all_cyroid_resources()
        result.orphaned_resources_cleaned += (
            orphan_cleanup.get("containers_removed", 0) +
            orphan_cleanup.get("networks_removed", 0)
        )
        result.errors.extend(orphan_cleanup.get("errors", []))
    except Exception as e:
        logger.debug(f"Legacy orphan cleanup: {e}")

    # Commit database changes
    try:
        db.commit()
    except Exception as e:
        error_msg = f"Failed to commit database changes: {e}"
        logger.error(error_msg)
        result.errors.append(error_msg)
        db.rollback()

    logger.info(f"Admin cleanup complete: {result.ranges_cleaned} ranges, "
               f"{result.dind_containers_removed} DinD containers, "
               f"{result.containers_removed} legacy containers, "
               f"{result.networks_removed} networks")

    return result


@router.get("/docker-status")
def get_docker_status(admin_user: AdminUser):
    """
    Get current Docker resource status for CYROID.

    Returns counts of containers, networks, and volumes managed by CYROID.
    **Requires admin privileges.**
    """
    docker = get_docker_service()

    # Count CYROID resources
    containers = []
    networks = []

    try:
        all_containers = docker.client.containers.list(all=True)
        for c in all_containers:
            labels = c.labels or {}
            if labels.get("cyroid.range_id") or labels.get("cyroid.vm_id"):
                containers.append({
                    "name": c.name,
                    "status": c.status,
                    "range_id": labels.get("cyroid.range_id"),
                    "vm_id": labels.get("cyroid.vm_id"),
                })
    except Exception as e:
        logger.error(f"Failed to list containers: {e}")

    try:
        all_networks = docker.client.networks.list()
        for n in all_networks:
            if n.name.startswith("cyroid-") and n.name not in ["cyroid-management", "cyroid_default"]:
                networks.append({
                    "name": n.name,
                    "id": n.id[:12],
                })
    except Exception as e:
        logger.error(f"Failed to list networks: {e}")

    return {
        "containers": containers,
        "container_count": len(containers),
        "networks": networks,
        "network_count": len(networks),
        "system_info": docker.get_system_info(),
    }


# =============================================================================
# Infrastructure Observability Endpoints
# =============================================================================

# Infrastructure service names and display names
INFRASTRUCTURE_SERVICES = {
    "api": "API Server",
    "worker": "Task Worker",
    "db": "PostgreSQL",
    "redis": "Redis",
    "minio": "MinIO",
    "traefik": "Traefik",
    "frontend": "Frontend",
}


def _format_uptime(seconds: int) -> str:
    """Convert seconds to human-readable uptime string."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}m"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        return f"{days}d {hours}h"


def _find_container_by_service(docker, service_name: str):
    """Find a container by service name pattern."""
    try:
        containers = docker.client.containers.list(all=True)
        patterns = [
            f"cyroid-{service_name}-1",
            f"cyroid_{service_name}_1",
            f"cyroid-{service_name}",
            f"cyroid_{service_name}",
            service_name,
        ]
        for container in containers:
            for pattern in patterns:
                if container.name == pattern or container.name.endswith(f"-{service_name}-1"):
                    return container
        return None
    except Exception as e:
        logger.error(f"Error finding container for {service_name}: {e}")
        return None


def _get_service_health(docker, service_name: str, display_name: str) -> ServiceHealth:
    """Get health status for a service."""
    now = datetime.now(timezone.utc)
    container = _find_container_by_service(docker, service_name)

    if not container:
        return ServiceHealth(
            name=service_name,
            display_name=display_name,
            status="unknown",
            last_checked=now,
        )

    # Get container status
    container_status = container.status
    health_status = "unknown"

    if container_status == "running":
        # Check if container has health check
        health = container.attrs.get("State", {}).get("Health", {})
        if health:
            health_state = health.get("Status", "")
            if health_state == "healthy":
                health_status = "healthy"
            elif health_state == "unhealthy":
                health_status = "unhealthy"
            else:
                health_status = "degraded"
        else:
            # No health check, assume healthy if running
            health_status = "healthy"
    elif container_status in ["exited", "dead"]:
        health_status = "unhealthy"
    else:
        health_status = "degraded"

    # Calculate uptime
    started_at = container.attrs.get("State", {}).get("StartedAt", "")
    uptime_seconds = None
    uptime_human = None
    if started_at and container_status == "running":
        try:
            # Parse Docker timestamp
            start_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            uptime_seconds = int((now - start_time).total_seconds())
            uptime_human = _format_uptime(uptime_seconds)
        except Exception:
            pass

    # Get resource stats
    cpu_percent = None
    memory_mb = None
    memory_limit_mb = None
    memory_percent = None

    if container_status == "running":
        try:
            stats = docker.get_container_stats(container.id)
            if stats:
                cpu_percent = stats.get("cpu_percent", 0.0)
                memory_mb = stats.get("memory_mb", 0.0)
                memory_limit_mb = stats.get("memory_limit_mb", 0.0)
                if memory_limit_mb and memory_limit_mb > 0:
                    memory_percent = (memory_mb / memory_limit_mb) * 100
        except Exception as e:
            logger.debug(f"Could not get stats for {service_name}: {e}")

    # Get ports
    ports = []
    try:
        port_bindings = container.attrs.get("NetworkSettings", {}).get("Ports", {})
        for container_port, host_bindings in port_bindings.items():
            if host_bindings:
                for binding in host_bindings:
                    host_port = binding.get("HostPort", "")
                    if host_port:
                        ports.append(f"{host_port}->{container_port}")
    except Exception:
        pass

    # Get health check output
    health_output = None
    health = container.attrs.get("State", {}).get("Health", {})
    if health:
        log = health.get("Log", [])
        if log:
            last_check = log[-1]
            health_output = last_check.get("Output", "")[:200]  # Truncate

    return ServiceHealth(
        name=service_name,
        display_name=display_name,
        status=health_status,
        container_id=container.id[:12],
        container_status=container_status,
        uptime_seconds=uptime_seconds,
        uptime_human=uptime_human,
        cpu_percent=round(cpu_percent, 2) if cpu_percent is not None else None,
        memory_mb=round(memory_mb, 2) if memory_mb is not None else None,
        memory_limit_mb=round(memory_limit_mb, 2) if memory_limit_mb is not None else None,
        memory_percent=round(memory_percent, 2) if memory_percent is not None else None,
        ports=ports,
        health_check_output=health_output,
        last_checked=now,
    )


@router.get("/infrastructure/services", response_model=InfrastructureServicesResponse)
def get_infrastructure_services(admin_user: AdminUser):
    """
    Get health status of all CYROID infrastructure services.

    Returns status, uptime, and resource usage for API, Worker, DB, Redis, MinIO, Traefik, and Frontend.
    **Requires admin privileges.**
    """
    docker = get_docker_service()
    services = []

    for service_name, display_name in INFRASTRUCTURE_SERVICES.items():
        service_health = _get_service_health(docker, service_name, display_name)
        services.append(service_health)

    # Determine overall status
    statuses = [s.status for s in services]
    if all(s == "healthy" for s in statuses):
        overall_status = "healthy"
    elif any(s == "unhealthy" for s in statuses):
        overall_status = "unhealthy"
    else:
        overall_status = "degraded"

    return InfrastructureServicesResponse(
        services=services,
        overall_status=overall_status,
        checked_at=datetime.now(timezone.utc),
    )


@router.get("/infrastructure/logs", response_model=ServiceLogsResponse)
def get_infrastructure_logs(
    admin_user: AdminUser,
    service: str = Query(..., description="Service name (api, worker, db, redis, minio, traefik, frontend)"),
    level: Optional[str] = Query(None, description="Log level filter (error, warning, info, debug)"),
    search: Optional[str] = Query(None, description="Search text in logs"),
    since: Optional[str] = Query(None, description="Start time (ISO format)"),
    until: Optional[str] = Query(None, description="End time (ISO format)"),
    limit: int = Query(100, ge=1, le=1000, description="Number of log lines"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    Get logs for a CYROID infrastructure service.

    Supports filtering by log level, text search, and time range.
    **Requires admin privileges.**
    """
    if service not in INFRASTRUCTURE_SERVICES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid service. Must be one of: {', '.join(INFRASTRUCTURE_SERVICES.keys())}",
        )

    docker = get_docker_service()
    container = _find_container_by_service(docker, service)

    if not container:
        return ServiceLogsResponse(
            service=service,
            logs=[],
            total_lines=0,
            has_more=False,
            filters_applied={"error": "Container not found"},
        )

    # Get logs from container
    try:
        # Calculate tail count (we need extra for filtering)
        tail_count = (offset + limit) * 3 if (level or search) else (offset + limit + 100)
        tail_count = min(tail_count, 5000)  # Cap at 5000 lines

        since_dt = None
        until_dt = None
        if since:
            try:
                since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            except ValueError:
                pass
        if until:
            try:
                until_dt = datetime.fromisoformat(until.replace("Z", "+00:00"))
            except ValueError:
                pass

        raw_logs = container.logs(
            tail=tail_count,
            timestamps=True,
            since=since_dt,
            until=until_dt,
        ).decode("utf-8", errors="replace")

        lines = raw_logs.strip().split("\n") if raw_logs.strip() else []

        # Parse and filter logs
        log_entries = []
        level_pattern = re.compile(r"\b(ERROR|WARN(?:ING)?|INFO|DEBUG)\b", re.IGNORECASE)

        for line in lines:
            if not line.strip():
                continue

            # Parse timestamp (Docker format: 2024-01-18T14:32:01.123456789Z)
            timestamp = None
            message = line
            try:
                if len(line) > 30 and line[4] == "-" and line[10] == "T":
                    ts_str = line[:30].split()[0]
                    timestamp = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    message = line[31:].strip() if len(line) > 31 else line
            except Exception:
                pass

            # Detect log level
            detected_level = None
            level_match = level_pattern.search(message[:100])
            if level_match:
                detected_level = level_match.group(1).upper()
                if detected_level == "WARNING":
                    detected_level = "WARN"

            # Apply level filter
            if level:
                level_upper = level.upper()
                if level_upper == "ERROR" and detected_level != "ERROR":
                    continue
                elif level_upper == "WARNING" and detected_level not in ["ERROR", "WARN"]:
                    continue
                elif level_upper == "INFO" and detected_level not in ["ERROR", "WARN", "INFO"]:
                    continue
                # DEBUG includes all

            # Apply search filter
            if search and search.lower() not in message.lower():
                continue

            log_entries.append(LogEntry(
                timestamp=timestamp,
                level=detected_level,
                message=message,
                raw=line,
            ))

        total_lines = len(log_entries)
        # Apply pagination
        paginated_entries = log_entries[offset:offset + limit]
        has_more = (offset + limit) < total_lines

        return ServiceLogsResponse(
            service=service,
            logs=paginated_entries,
            total_lines=total_lines,
            has_more=has_more,
            filters_applied={
                "level": level,
                "search": search,
                "since": since,
                "until": until,
                "limit": limit,
                "offset": offset,
            },
        )

    except Exception as e:
        logger.error(f"Error getting logs for {service}: {e}")
        return ServiceLogsResponse(
            service=service,
            logs=[],
            total_lines=0,
            has_more=False,
            filters_applied={"error": str(e)},
        )


@router.get("/infrastructure/docker", response_model=DockerOverviewResponse)
def get_docker_overview(admin_user: AdminUser):
    """
    Get comprehensive Docker resource overview.

    Returns containers, networks, volumes, and images with CYROID-specific annotations.
    **Requires admin privileges.**
    """
    docker = get_docker_service()
    now = datetime.now(timezone.utc)

    # Get containers
    containers = []
    cyroid_vms = 0
    cyroid_infra = 0
    running_count = 0
    stopped_count = 0

    try:
        all_containers = docker.client.containers.list(all=True)
        for c in all_containers:
            labels = c.labels or {}
            is_vm = bool(labels.get("cyroid.vm_id"))
            is_infra = c.name.startswith("cyroid-") or c.name.startswith("cyroid_")

            if is_vm:
                cyroid_vms += 1
            if is_infra and not is_vm:
                cyroid_infra += 1

            if c.status == "running":
                running_count += 1
            else:
                stopped_count += 1

            # Get ports
            ports = []
            try:
                port_bindings = c.attrs.get("NetworkSettings", {}).get("Ports", {})
                for container_port, host_bindings in (port_bindings or {}).items():
                    if host_bindings:
                        for binding in host_bindings:
                            host_port = binding.get("HostPort", "")
                            if host_port:
                                ports.append(f"{host_port}->{container_port}")
            except Exception:
                pass

            # Parse created time
            created = None
            try:
                created_str = c.attrs.get("Created", "")
                if created_str:
                    created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            except Exception:
                pass

            containers.append(DockerContainerOverview(
                id=c.id[:12],
                name=c.name,
                image=c.image.tags[0] if c.image.tags else c.image.id[:12],
                status=c.status,
                state=c.attrs.get("State", {}).get("Status", "unknown"),
                created=created,
                ports=ports,
                labels=labels,
                is_cyroid_infra=is_infra and not is_vm,
                is_cyroid_vm=is_vm,
            ))
    except Exception as e:
        logger.error(f"Error listing containers: {e}")

    # Get networks
    networks = []
    cyroid_networks = 0

    try:
        all_networks = docker.client.networks.list()
        for n in all_networks:
            is_cyroid = n.name.startswith("cyroid-")

            if is_cyroid:
                cyroid_networks += 1

            # Get IPAM config
            subnet = None
            gateway = None
            try:
                ipam = n.attrs.get("IPAM", {}).get("Config", [])
                if ipam:
                    subnet = ipam[0].get("Subnet")
                    gateway = ipam[0].get("Gateway")
            except Exception:
                pass

            # Count connected containers
            container_count = len(n.attrs.get("Containers", {}) or {})

            networks.append(DockerNetworkOverview(
                id=n.id[:12],
                name=n.name,
                driver=n.attrs.get("Driver", "unknown"),
                scope=n.attrs.get("Scope", "local"),
                internal=n.attrs.get("Internal", False),
                subnet=subnet,
                gateway=gateway,
                container_count=container_count,
                is_cyroid_range=is_cyroid and n.name not in ["cyroid-management", "cyroid_default"],
            ))
    except Exception as e:
        logger.error(f"Error listing networks: {e}")

    # Get volumes
    volumes = []
    try:
        all_volumes = docker.client.volumes.list()
        for v in all_volumes:
            # Parse created time
            created = None
            try:
                created_str = v.attrs.get("CreatedAt", "")
                if created_str:
                    created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            except Exception:
                pass

            volumes.append(DockerVolumeOverview(
                name=v.name,
                driver=v.attrs.get("Driver", "local"),
                mountpoint=v.attrs.get("Mountpoint", ""),
                created=created,
                labels=v.attrs.get("Labels", {}) or {},
            ))
    except Exception as e:
        logger.error(f"Error listing volumes: {e}")

    # Get images
    images = []
    try:
        all_images = docker.client.images.list()
        for img in all_images:
            # Check if CYROID-related
            tags = img.tags or []
            is_cyroid = any(
                "cyroid" in t.lower() or
                "qemu" in t.lower() or
                "dockur" in t.lower() or
                "kasmweb" in t.lower() or
                "linuxserver" in t.lower() or
                "vyos" in t.lower()
                for t in tags
            )

            size_bytes = img.attrs.get("Size", 0)
            size_human = _format_size(size_bytes)

            # Parse created time
            created = None
            try:
                created_str = img.attrs.get("Created", "")
                if created_str:
                    created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            except Exception:
                pass

            images.append(DockerImageOverview(
                id=img.id.split(":")[1][:12] if ":" in img.id else img.id[:12],
                tags=tags,
                size_bytes=size_bytes,
                size_human=size_human,
                created=created,
                is_cyroid_related=is_cyroid,
            ))
    except Exception as e:
        logger.error(f"Error listing images: {e}")

    return DockerOverviewResponse(
        containers=containers,
        networks=networks,
        volumes=volumes,
        images=images,
        summary=DockerSummary(
            total_containers=len(containers),
            running_containers=running_count,
            stopped_containers=stopped_count,
            cyroid_vms=cyroid_vms,
            cyroid_infra=cyroid_infra,
            total_networks=len(networks),
            cyroid_networks=cyroid_networks,
            total_volumes=len(volumes),
            total_images=len(images),
        ),
    )


def _format_size(size_bytes: int) -> str:
    """Format bytes to human-readable size."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def _get_directory_size(path: str) -> tuple[float, int]:
    """Get directory size in MB and file count."""
    total_size = 0
    file_count = 0
    try:
        if os.path.exists(path):
            for dirpath, dirnames, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        total_size += os.path.getsize(fp)
                        file_count += 1
                    except (OSError, IOError):
                        pass
    except Exception:
        pass
    return total_size / (1024 * 1024), file_count


@router.get("/infrastructure/metrics", response_model=InfrastructureMetricsResponse)
def get_infrastructure_metrics(admin_user: AdminUser, db: DBSession):
    """
    Get resource metrics for host, database, task queue, and storage.

    **Requires admin privileges.**
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)

    # Host metrics
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    load_avg = None
    try:
        load_avg = list(os.getloadavg())
    except (OSError, AttributeError):
        pass  # Windows doesn't have getloadavg

    host_metrics = HostMetrics(
        cpu_count=psutil.cpu_count() or 1,
        cpu_percent=cpu_percent,
        memory_total_mb=memory.total / (1024 * 1024),
        memory_used_mb=memory.used / (1024 * 1024),
        memory_available_mb=memory.available / (1024 * 1024),
        memory_percent=memory.percent,
        disk_total_gb=disk.total / (1024 * 1024 * 1024),
        disk_used_gb=disk.used / (1024 * 1024 * 1024),
        disk_free_gb=disk.free / (1024 * 1024 * 1024),
        disk_percent=disk.percent,
        load_average=load_avg,
    )

    # Database metrics
    db_metrics = DatabaseMetrics()
    try:
        # Connection count
        result = db.execute(text(
            "SELECT count(*) as total, "
            "count(*) FILTER (WHERE state = 'active') as active, "
            "count(*) FILTER (WHERE state = 'idle') as idle "
            "FROM pg_stat_activity WHERE datname = current_database()"
        ))
        row = result.fetchone()
        if row:
            db_metrics.connection_count = row[0] or 0
            db_metrics.active_connections = row[1] or 0
            db_metrics.idle_connections = row[2] or 0

        # Database size
        result = db.execute(text(
            "SELECT pg_database_size(current_database())"
        ))
        row = result.fetchone()
        if row and row[0]:
            size_bytes = row[0]
            db_metrics.database_size_mb = size_bytes / (1024 * 1024)
            db_metrics.database_size_human = _format_size(size_bytes)

        # Table count
        result = db.execute(text(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = 'public'"
        ))
        row = result.fetchone()
        if row:
            db_metrics.table_count = row[0] or 0

        # Largest tables
        result = db.execute(text(
            "SELECT relname as table_name, "
            "pg_total_relation_size(c.oid) as size "
            "FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relkind = 'r' "
            "ORDER BY pg_total_relation_size(c.oid) DESC "
            "LIMIT 5"
        ))
        largest = []
        for row in result:
            largest.append({
                "name": row[0],
                "size_bytes": row[1],
                "size_human": _format_size(row[1]),
            })
        db_metrics.largest_tables = largest

    except Exception as e:
        logger.error(f"Error getting database metrics: {e}")

    # Task queue metrics (Redis/Dramatiq)
    queue_metrics = TaskQueueMetrics()
    try:
        import redis
        redis_client = redis.from_url(settings.redis_url)

        # Get Dramatiq queue lengths
        # Default queue is 'default'
        queue_length = redis_client.llen("dramatiq:default")
        delayed_length = redis_client.zcard("dramatiq:default.DQ")

        queue_metrics.queue_length = queue_length or 0
        queue_metrics.delayed_messages = delayed_length or 0

        # Count total messages (approximation)
        total_keys = 0
        for key in redis_client.scan_iter("dramatiq:*"):
            total_keys += 1
        queue_metrics.messages_total = total_keys

    except Exception as e:
        logger.debug(f"Error getting task queue metrics: {e}")

    # Storage metrics
    storage_metrics = StorageMetrics()

    # ISO cache
    iso_size, iso_count = _get_directory_size(settings.iso_cache_dir)
    storage_metrics.iso_cache_size_mb = round(iso_size, 2)
    storage_metrics.iso_cache_files = iso_count

    # Template storage
    template_size, template_count = _get_directory_size(settings.template_storage_dir)
    storage_metrics.template_storage_size_mb = round(template_size, 2)
    storage_metrics.template_storage_files = template_count

    # VM storage
    vm_size, _ = _get_directory_size(settings.vm_storage_dir)
    storage_metrics.vm_storage_size_mb = round(vm_size, 2)
    # Count directories (each VM gets a directory)
    try:
        if os.path.exists(settings.vm_storage_dir):
            storage_metrics.vm_storage_dirs = len([
                d for d in os.listdir(settings.vm_storage_dir)
                if os.path.isdir(os.path.join(settings.vm_storage_dir, d))
            ])
    except Exception:
        pass

    # MinIO metrics
    try:
        from minio import Minio
        minio_client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        buckets = list(minio_client.list_buckets())
        storage_metrics.minio_bucket_count = len(buckets)

        total_objects = 0
        total_size = 0
        for bucket in buckets:
            try:
                for obj in minio_client.list_objects(bucket.name, recursive=True):
                    total_objects += 1
                    total_size += obj.size or 0
            except Exception:
                pass
        storage_metrics.minio_total_objects = total_objects
        storage_metrics.minio_total_size_mb = round(total_size / (1024 * 1024), 2)
    except Exception as e:
        logger.debug(f"Error getting MinIO metrics: {e}")

    return InfrastructureMetricsResponse(
        host=host_metrics,
        database=db_metrics,
        task_queue=queue_metrics,
        storage=storage_metrics,
        collected_at=now,
    )


@router.get("/infrastructure/system", response_model=SystemInfoResponse)
def get_system_info(admin_user: AdminUser, db: DBSession):
    """
    Get system information including version, migrations, and configuration.

    **Requires admin privileges.**
    """
    settings = get_settings()
    docker = get_docker_service()

    # Get Docker version
    docker_version = None
    try:
        docker_info = docker.client.version()
        docker_version = docker_info.get("Version", "unknown")
    except Exception:
        pass

    # Get architecture
    arch = platform.machine()
    is_arm = arch in ["arm64", "aarch64"]

    # Get current migration revision
    db_revision = None
    migrations = []
    try:
        result = db.execute(text("SELECT version_num FROM alembic_version"))
        row = result.fetchone()
        if row:
            db_revision = row[0]
    except Exception as e:
        logger.debug(f"Could not get migration revision: {e}")

    # Get migration history from alembic
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        # Find alembic.ini
        alembic_ini = os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic.ini")
        if os.path.exists(alembic_ini):
            config = Config(alembic_ini)
            script = ScriptDirectory.from_config(config)

            for rev in script.walk_revisions():
                migrations.append(MigrationInfo(
                    revision=rev.revision[:12],
                    description=rev.doc or "No description",
                    applied=db_revision is not None and script.get_revision(db_revision) is not None,
                ))
            # Limit to last 10
            migrations = migrations[:10]
    except Exception as e:
        logger.debug(f"Could not load migration history: {e}")

    # Non-sensitive config items
    config_items = [
        ConfigItem(key="app_name", value=settings.app_name, source="config"),
        ConfigItem(key="debug", value=str(settings.debug), source="config"),
        ConfigItem(key="iso_cache_dir", value=settings.iso_cache_dir, source="config"),
        ConfigItem(key="template_storage_dir", value=settings.template_storage_dir, source="config"),
        ConfigItem(key="vm_storage_dir", value=settings.vm_storage_dir, source="config"),
        ConfigItem(key="vyos_image", value=settings.vyos_image, source="config"),
        ConfigItem(key="management_network", value=settings.management_network_name, source="config"),
    ]

    return SystemInfoResponse(
        version=settings.app_version,
        commit=settings.git_commit,
        build_date=settings.build_date,
        app_name=settings.app_name,
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        docker_version=docker_version,
        architecture=arch,
        is_arm=is_arm,
        database_revision=db_revision,
        migrations=migrations,
        config=config_items,
    )
