# backend/cyroid/api/admin.py
"""
Administrative API endpoints.

These endpoints require admin privileges and provide system-wide operations
like cleanup, diagnostics, and maintenance.
"""
import logging
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from cyroid.api.deps import get_current_user, require_admin, get_db
from cyroid.models.user import User
from cyroid.models.range import Range, RangeStatus
from cyroid.models.vm import VM, VMStatus
from cyroid.models.network import Network
from cyroid.services.docker_service import get_docker_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

# Type aliases
DBSession = Annotated[Session, Depends(get_db)]
AdminUser = Annotated[User, Depends(require_admin())]


class CleanupResult(BaseModel):
    """Result of a cleanup operation."""
    ranges_cleaned: int
    containers_removed: int
    networks_removed: int
    database_records_updated: int
    errors: List[str]
    orphaned_resources_cleaned: int


class CleanupRequest(BaseModel):
    """Options for cleanup operation."""
    clean_database: bool = True  # Also reset database records
    force: bool = False  # Force cleanup even if ranges appear active


@router.post("/cleanup-all", response_model=CleanupResult)
def cleanup_all_resources(
    db: DBSession,
    admin_user: AdminUser,
    options: Optional[CleanupRequest] = None,
):
    """
    Nuclear cleanup: Remove ALL CYROID range resources.

    This will:
    1. Stop and remove all VM containers (not CYROID infrastructure)
    2. Remove all range networks (not management network)
    3. Optionally reset database records to reflect cleanup

    **Requires admin privileges.**

    Use this when:
    - Starting fresh after testing
    - Recovering from inconsistent state
    - Preparing for a clean deployment
    """
    if options is None:
        options = CleanupRequest()

    docker = get_docker_service()
    result = CleanupResult(
        ranges_cleaned=0,
        containers_removed=0,
        networks_removed=0,
        database_records_updated=0,
        errors=[],
        orphaned_resources_cleaned=0,
    )

    # Step 1: Get all ranges from database and clean them up properly
    logger.info(f"Admin cleanup initiated by user {admin_user.email}")
    ranges = db.query(Range).all()

    for range_obj in ranges:
        try:
            # Use the proper cleanup method for each range
            cleanup_result = docker.cleanup_range(str(range_obj.id))
            result.containers_removed += cleanup_result.get("containers", 0)
            result.networks_removed += cleanup_result.get("networks", 0)
            result.ranges_cleaned += 1

            # Update database if requested
            if options.clean_database:
                # Reset range status
                range_obj.status = RangeStatus.DRAFT
                range_obj.error_message = None

                # Reset all VMs in this range
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

                result.database_records_updated += 1  # For the range itself

        except Exception as e:
            error_msg = f"Failed to cleanup range {range_obj.name}: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)

    # Step 2: Clean up any orphaned Docker resources (not in database)
    logger.info("Cleaning up orphaned Docker resources...")
    try:
        orphan_cleanup = docker.cleanup_all_cyroid_resources()
        result.orphaned_resources_cleaned = (
            orphan_cleanup.get("containers_removed", 0) +
            orphan_cleanup.get("networks_removed", 0)
        )
        result.errors.extend(orphan_cleanup.get("errors", []))
    except Exception as e:
        error_msg = f"Failed orphan cleanup: {e}"
        logger.error(error_msg)
        result.errors.append(error_msg)

    # Commit database changes
    if options.clean_database:
        try:
            db.commit()
        except Exception as e:
            error_msg = f"Failed to commit database changes: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)
            db.rollback()

    logger.info(f"Admin cleanup complete: {result.ranges_cleaned} ranges, "
               f"{result.containers_removed} containers, "
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
