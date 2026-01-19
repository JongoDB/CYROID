# backend/cyroid/api/ranges.py
import json
from datetime import datetime
from typing import List
from uuid import UUID
import logging
import os

from fastapi import APIRouter, HTTPException, status

from cyroid.config import get_settings

from cyroid.api.deps import DBSession, CurrentUser, filter_by_visibility, check_resource_access
from cyroid.models.range import Range, RangeStatus
from cyroid.models.network import Network
from cyroid.models.vm import VM, VMStatus
from cyroid.models.template import VMTemplate, OSType
from cyroid.models.resource_tag import ResourceTag
from cyroid.models.user import User
from cyroid.models.router import RangeRouter, RouterStatus
from cyroid.models.event_log import EventType
from cyroid.models.msel import MSEL
from cyroid.services.scenario_filesystem import get_scenario
from cyroid.models.inject import Inject, InjectStatus
from cyroid.services.event_service import EventService
from cyroid.schemas.range import (
    RangeCreate, RangeUpdate, RangeResponse, RangeDetailResponse,
    RangeTemplateExport, RangeTemplateImport, NetworkTemplateData, VMTemplateData
)
from cyroid.schemas.deployment_status import (
    DeploymentStatusResponse, DeploymentSummary, ResourceStatus, NetworkStatus, VMStatus as VMStatusSchema
)
from cyroid.schemas.scenario import ApplyScenarioRequest, ApplyScenarioResponse
from sqlalchemy.orm import joinedload
from cyroid.schemas.user import ResourceTagCreate, ResourceTagsResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ranges", tags=["Ranges"])


def get_docker_service():
    """Lazy import to avoid Docker connection issues during testing."""
    from cyroid.services.docker_service import get_docker_service as _get_docker_service
    return _get_docker_service()


def get_vyos_service():
    """Lazy import for VyOS service."""
    from cyroid.services.vyos_service import VyOSService
    return VyOSService()


def get_dind_service():
    """Lazy import for DinD service."""
    from cyroid.services.dind_service import get_dind_service as _get_dind_service
    return _get_dind_service()


def compute_deployment_status(range_obj, events: list) -> DeploymentStatusResponse:
    """Compute per-resource deployment status from events."""
    from datetime import timezone
    from cyroid.models.event_log import EventLog

    # Find deployment start time
    started_at = None
    for event in events:
        if event.event_type == EventType.DEPLOYMENT_STARTED:
            started_at = event.created_at
            break

    # Track timestamps for duration calculation
    resource_start_times = {}

    # Initialize router status
    router_status = ResourceStatus(name="gateway", status="pending")

    # Initialize network statuses
    network_statuses = {}
    for n in range_obj.networks:
        network_statuses[n.id] = NetworkStatus(
            id=str(n.id), name=n.name, subnet=n.subnet, status="pending"
        )

    # Initialize VM statuses
    vm_statuses = {}
    for v in range_obj.vms:
        vm_statuses[v.id] = VMStatusSchema(
            id=str(v.id), name=v.hostname, hostname=v.hostname,
            ip=v.ip_address, status="pending"
        )

    # Process events chronologically
    for event in events:
        event_type = event.event_type

        # Router events
        if event_type == EventType.ROUTER_CREATING:
            router_status.status = "creating"
            router_status.status_detail = "Creating VyOS router..."
            resource_start_times["router"] = event.created_at
        elif event_type == EventType.ROUTER_CREATED:
            router_status.status = "running"
            router_status.status_detail = "Running"
            if "router" in resource_start_times:
                delta = event.created_at - resource_start_times["router"]
                router_status.duration_ms = int(delta.total_seconds() * 1000)

        # Network events
        elif event_type == EventType.NETWORK_CREATING:
            if event.network_id and event.network_id in network_statuses:
                network_statuses[event.network_id].status = "creating"
                network_statuses[event.network_id].status_detail = "Creating Docker network..."
                resource_start_times[f"network_{event.network_id}"] = event.created_at
        elif event_type == EventType.NETWORK_CREATED:
            if event.network_id and event.network_id in network_statuses:
                network_statuses[event.network_id].status = "created"
                network_statuses[event.network_id].status_detail = "Created"
                key = f"network_{event.network_id}"
                if key in resource_start_times:
                    delta = event.created_at - resource_start_times[key]
                    network_statuses[event.network_id].duration_ms = int(delta.total_seconds() * 1000)

        # VM events
        elif event_type == EventType.VM_CREATING:
            if event.vm_id and event.vm_id in vm_statuses:
                vm_statuses[event.vm_id].status = "creating"
                vm_statuses[event.vm_id].status_detail = "Creating container..."
                resource_start_times[f"vm_{event.vm_id}"] = event.created_at
        elif event_type == EventType.VM_STARTED:
            if event.vm_id and event.vm_id in vm_statuses:
                vm_statuses[event.vm_id].status = "running"
                vm_statuses[event.vm_id].status_detail = "Running"
                key = f"vm_{event.vm_id}"
                if key in resource_start_times:
                    delta = event.created_at - resource_start_times[key]
                    vm_statuses[event.vm_id].duration_ms = int(delta.total_seconds() * 1000)
        elif event_type == EventType.VM_ERROR:
            if event.vm_id and event.vm_id in vm_statuses:
                vm_statuses[event.vm_id].status = "failed"
                vm_statuses[event.vm_id].status_detail = event.message

        # Deployment failure
        elif event_type == EventType.DEPLOYMENT_FAILED:
            if router_status.status == "creating":
                router_status.status = "failed"
                router_status.status_detail = event.message

    # Build summary
    all_resources = [router_status] + list(network_statuses.values()) + list(vm_statuses.values())
    summary = DeploymentSummary(
        total=len(all_resources),
        completed=sum(1 for r in all_resources if r.status in ["running", "created"]),
        in_progress=sum(1 for r in all_resources if r.status in ["creating", "starting"]),
        failed=sum(1 for r in all_resources if r.status == "failed"),
        pending=sum(1 for r in all_resources if r.status == "pending")
    )

    # Calculate elapsed time
    elapsed_seconds = 0
    if started_at:
        from datetime import datetime
        now = datetime.now(timezone.utc) if started_at.tzinfo else datetime.utcnow()
        elapsed_seconds = int((now - started_at).total_seconds())

    return DeploymentStatusResponse(
        status=range_obj.status.value if hasattr(range_obj.status, 'value') else range_obj.status,
        elapsed_seconds=elapsed_seconds,
        started_at=started_at.isoformat() if started_at else None,
        summary=summary,
        router=router_status,
        networks=list(network_statuses.values()),
        vms=list(vm_statuses.values())
    )


@router.get("", response_model=List[RangeResponse])
def list_ranges(db: DBSession, current_user: CurrentUser):
    """
    List ranges visible to the current user.

    Visibility rules:
    - Admins see ALL ranges
    - Users see ranges they own
    - Users see ranges with matching tags (if they have tags)
    - Users see untagged ranges (public)
    """
    # Start with user's own ranges - eager load networks and vms for counts
    base_options = [joinedload(Range.networks), joinedload(Range.vms)]

    if current_user.is_admin:
        # Admins see all ranges
        query = db.query(Range).options(*base_options)
    else:
        # Non-admins: own ranges + visibility-filtered shared ranges
        from sqlalchemy import or_
        shared_query = db.query(Range).filter(Range.created_by != current_user.id)
        shared_query = filter_by_visibility(shared_query, 'range', current_user, db, Range)

        query = db.query(Range).options(*base_options).filter(
            or_(
                Range.created_by == current_user.id,
                Range.id.in_(shared_query.with_entities(Range.id).subquery())
            )
        )

    ranges = query.all()
    return [RangeResponse.from_orm_with_counts(r) for r in ranges]


@router.post("", response_model=RangeResponse, status_code=status.HTTP_201_CREATED)
def create_range(range_data: RangeCreate, db: DBSession, current_user: CurrentUser):
    range_obj = Range(
        **range_data.model_dump(),
        created_by=current_user.id,
    )
    db.add(range_obj)
    db.commit()
    db.refresh(range_obj)
    return range_obj


@router.get("/{range_id}", response_model=RangeDetailResponse)
def get_range(range_id: UUID, db: DBSession, current_user: CurrentUser):
    range_obj = db.query(Range).options(
        joinedload(Range.networks),
        joinedload(Range.vms),
        joinedload(Range.router)
    ).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Range not found",
        )
    return range_obj


@router.put("/{range_id}", response_model=RangeResponse)
def update_range(
    range_id: UUID,
    range_data: RangeUpdate,
    db: DBSession,
    current_user: CurrentUser,
):
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Range not found",
        )

    update_data = range_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(range_obj, field, value)

    db.commit()
    db.refresh(range_obj)
    return range_obj


@router.delete("/{range_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_range(range_id: UUID, db: DBSession, current_user: CurrentUser):
    """Delete a range and clean up all associated Docker resources.

    For DinD-based deployments:
    - Destroys the DinD container (which automatically cleans up all VMs/networks inside)
    - Clears Docker client cache for this range
    - Deletes database record

    For legacy deployments:
    - Cleans up containers and networks via labels
    - Deletes database record
    """
    import asyncio

    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Range not found",
        )

    # Cleanup Docker resources before deleting
    try:
        docker = get_docker_service()
        dind = get_dind_service()

        # Check if this is a DinD-based deployment
        if range_obj.dind_container_id:
            # DinD-based deployment: destroy the DinD container
            # This automatically cleans up all VMs and networks inside it
            logger.info(f"Deleting DinD container for range {range_id}")

            # Run async delete_range_container
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(dind.delete_range_container(str(range_id)))
                logger.info(f"Successfully deleted DinD container for range {range_id}")
            finally:
                loop.close()

            # Clear the Docker client cache for this range
            docker.dind_service.close_range_client(str(range_id))

        else:
            # Legacy non-DinD deployment: use label-based cleanup
            logger.info(f"Cleaning up legacy (non-DinD) range {range_id}")
            docker.cleanup_range(str(range_id))

    except Exception as e:
        logger.warning(f"Failed to cleanup Docker resources for range {range_id}: {e}")
        # Continue with database deletion even if Docker cleanup fails

    db.delete(range_obj)
    db.commit()


@router.get("/{range_id}/deployment-status", response_model=DeploymentStatusResponse)
def get_deployment_status(
    range_id: UUID,
    db: DBSession,
    current_user: CurrentUser
):
    """Get detailed per-resource deployment status."""
    from datetime import datetime, timedelta
    from cyroid.models.event_log import EventLog

    range_obj = db.query(Range).options(
        joinedload(Range.networks),
        joinedload(Range.vms)
    ).filter(Range.id == range_id).first()

    if not range_obj:
        raise HTTPException(status_code=404, detail="Range not found")

    # Get deployment events from last hour
    events = db.query(EventLog).filter(
        EventLog.range_id == range_id,
        EventLog.created_at > datetime.utcnow() - timedelta(hours=1)
    ).order_by(EventLog.created_at).all()

    return compute_deployment_status(range_obj, events)


@router.post("/{range_id}/deploy", response_model=RangeResponse)
def deploy_range(range_id: UUID, db: DBSession, current_user: CurrentUser):
    """Deploy a range using DinD isolation - creates isolated Docker environment with networks and VMs"""
    from cyroid.services.range_deployment_service import get_range_deployment_service
    import asyncio

    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Range not found",
        )

    if range_obj.status not in [RangeStatus.DRAFT, RangeStatus.STOPPED, RangeStatus.ERROR]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot deploy range in {range_obj.status} status",
        )

    range_obj.status = RangeStatus.DEPLOYING
    range_obj.error_message = None  # Clear any previous error
    db.commit()

    # Initialize event service for progress logging
    event_service = EventService(db)
    networks = db.query(Network).filter(Network.range_id == range_id).all()
    vms = db.query(VM).filter(VM.range_id == range_id).all()

    # Log deployment start
    event_service.log_event(
        range_id=range_id,
        event_type=EventType.DEPLOYMENT_STARTED,
        message=f"Starting DinD deployment of range '{range_obj.name}'",
        user_id=current_user.id,
        extra_data=json.dumps({
            "total_networks": len(networks),
            "total_vms": len(vms),
            "isolation": "dind"
        })
    )

    try:
        # Use the new DinD-based deployment service
        deployment_service = get_range_deployment_service()

        # Run async deployment synchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                deployment_service.deploy_range(db, range_id)
            )
            logger.info(f"DinD deployment completed for range {range_id}: {result}")
        finally:
            loop.close()

        # Refresh range object to get updated status
        db.refresh(range_obj)

        # Log deployment completion
        event_service.log_event(
            range_id=range_id,
            event_type=EventType.DEPLOYMENT_COMPLETED,
            message=f"Range '{range_obj.name}' deployed successfully with DinD isolation",
            user_id=current_user.id,
            extra_data=json.dumps({
                "networks_deployed": len(networks),
                "vms_deployed": len(vms),
                "dind_container_id": range_obj.dind_container_id
            })
        )

    except Exception as e:
        import traceback
        logger.error(f"Failed to deploy range {range_id}: {type(e).__name__}: {e}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        range_obj.status = RangeStatus.ERROR
        range_obj.error_message = str(e)[:1000]
        db.commit()

        # Log deployment failure
        event_service.log_event(
            range_id=range_id,
            event_type=EventType.DEPLOYMENT_FAILED,
            message=f"Deployment failed: {str(e)[:200]}",
            user_id=current_user.id,
            extra_data=json.dumps({"error": str(e)})
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deploy range: {str(e)}",
        )

    return range_obj


@router.post("/{range_id}/start", response_model=RangeResponse)
def start_range(range_id: UUID, db: DBSession, current_user: CurrentUser):
    """Start all VMs and router in a stopped range.

    For DinD-based deployments:
    - Ensures the DinD container itself is running (starts it if stopped)
    - Waits for Docker daemon inside DinD to be ready
    - Starts VyOS router container inside DinD first
    - Starts all VM containers inside DinD
    """
    import asyncio

    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Range not found",
        )

    if range_obj.status != RangeStatus.STOPPED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot start range in {range_obj.status} status",
        )

    try:
        docker = get_docker_service()
        dind = get_dind_service()

        # Check if this is a DinD-based deployment
        if range_obj.dind_container_id and range_obj.dind_docker_url:
            # DinD-based deployment
            logger.info(f"Starting DinD-based range {range_id}")

            # Step 0: Ensure the DinD container itself is running
            # Use asyncio to run the async start_range_container method
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                dind_info = loop.run_until_complete(
                    dind.start_range_container(str(range_id))
                )
                logger.info(f"DinD container started/confirmed running: {dind_info}")

                # Update docker_url in case IP changed after restart
                if dind_info.get("docker_url") and dind_info["docker_url"] != range_obj.dind_docker_url:
                    range_obj.dind_docker_url = dind_info["docker_url"]
                    range_obj.dind_mgmt_ip = dind_info.get("mgmt_ip")
                    db.commit()
                    logger.info(f"Updated DinD Docker URL to {dind_info['docker_url']}")
            finally:
                loop.close()

            # Get Docker client for the inner Docker daemon
            range_client = docker.get_range_client_sync(
                str(range_id),
                range_obj.dind_docker_url
            )

            # Step 1: Start VyOS router first (VMs need networking)
            range_router = db.query(RangeRouter).filter(RangeRouter.range_id == range_id).first()
            if range_router and range_router.container_id:
                try:
                    container = range_client.containers.get(range_router.container_id)
                    container.start()
                    range_router.status = RouterStatus.RUNNING
                    db.commit()
                    logger.info(f"Started VyOS router for range {range_id} inside DinD")
                except Exception as e:
                    logger.warning(f"Failed to start VyOS router: {e}")

            # Step 2: Start all VM containers inside DinD
            vms = db.query(VM).filter(VM.range_id == range_id).all()
            for vm in vms:
                if vm.container_id:
                    try:
                        container = range_client.containers.get(vm.container_id)
                        container.start()
                        vm.status = VMStatus.RUNNING
                        db.commit()
                        logger.info(f"Started VM {vm.hostname} inside DinD")
                    except Exception as e:
                        logger.warning(f"Failed to start VM {vm.hostname}: {e}")

        else:
            # Legacy non-DinD deployment (fallback)
            # Range must have been deployed with DinD to start - otherwise redeploy is required
            if not range_obj.dind_container_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Range has no DinD container. Please redeploy the range.",
                )

            logger.info(f"Starting legacy (non-DinD) range {range_id}")
            vyos = get_vyos_service()

            # Step 1: Start the router first (VMs need networking)
            range_router = db.query(RangeRouter).filter(RangeRouter.range_id == range_id).first()
            if range_router and range_router.container_id:
                try:
                    vyos.start_router(range_router.container_id)
                    range_router.status = RouterStatus.RUNNING
                    db.commit()
                    logger.info(f"Started VyOS router for range {range_id}")
                except Exception as e:
                    logger.warning(f"Failed to start VyOS router: {e}")

            # Step 2: Start all VM containers
            vms = db.query(VM).filter(VM.range_id == range_id).all()
            for vm in vms:
                if vm.container_id:
                    docker.start_container(vm.container_id)
                    vm.status = VMStatus.RUNNING
                    db.commit()
                    logger.info(f"Started VM {vm.hostname}")

        range_obj.status = RangeStatus.RUNNING
        # Set lifecycle timestamp
        from datetime import timezone
        range_obj.started_at = datetime.now(timezone.utc)
        db.commit()

        # Log the start event
        event_service = EventService(db)
        event_service.log_event(
            range_id=range_id,
            event_type=EventType.RANGE_STARTED,
            message=f"Range '{range_obj.name}' started",
            user_id=current_user.id
        )
        db.refresh(range_obj)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start range {range_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start range: {str(e)}",
        )

    return range_obj


@router.post("/{range_id}/stop", response_model=RangeResponse)
def stop_range(range_id: UUID, db: DBSession, current_user: CurrentUser):
    """Stop all VMs and router in a running range.

    This stops all containers but preserves networks for quick restart.
    Use teardown to fully clean up resources.

    For DinD-based deployments:
    - Gets Docker client connected to inner Docker daemon
    - Stops all VM containers inside the DinD container
    - Stops VyOS router container inside DinD
    - Does NOT stop the DinD container itself (preserves for restart)
    """
    import asyncio

    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Range not found",
        )

    if range_obj.status != RangeStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot stop range in {range_obj.status} status",
        )

    try:
        docker = get_docker_service()
        dind = get_dind_service()

        # Check if this is a DinD-based deployment
        if range_obj.dind_container_id and range_obj.dind_docker_url:
            # DinD-based deployment: operate on containers inside DinD
            logger.info(f"Stopping DinD-based range {range_id}")

            # Get Docker client for the inner Docker daemon
            range_client = docker.get_range_client_sync(
                str(range_id),
                range_obj.dind_docker_url
            )

            # Step 1: Stop all VM containers inside DinD
            vms = db.query(VM).filter(VM.range_id == range_id).all()
            for vm in vms:
                if vm.container_id:
                    try:
                        container = range_client.containers.get(vm.container_id)
                        container.stop(timeout=30)
                        vm.status = VMStatus.STOPPED
                        db.commit()
                        logger.info(f"Stopped VM {vm.hostname} inside DinD")
                    except Exception as e:
                        logger.warning(f"Failed to stop VM {vm.hostname}: {e}")

            # Step 2: Stop VyOS router container inside DinD
            range_router = db.query(RangeRouter).filter(RangeRouter.range_id == range_id).first()
            if range_router and range_router.container_id:
                try:
                    container = range_client.containers.get(range_router.container_id)
                    container.stop(timeout=30)
                    range_router.status = RouterStatus.STOPPED
                    db.commit()
                    logger.info(f"Stopped VyOS router for range {range_id} inside DinD")
                except Exception as e:
                    logger.warning(f"Failed to stop VyOS router: {e}")

            # Note: We do NOT stop the DinD container itself - this allows quick restart

        else:
            # Legacy non-DinD deployment (fallback)
            logger.info(f"Stopping legacy (non-DinD) range {range_id}")
            vyos = get_vyos_service()

            # Step 1: Stop all VM containers
            vms = db.query(VM).filter(VM.range_id == range_id).all()
            for vm in vms:
                if vm.container_id:
                    docker.stop_container(vm.container_id)
                    vm.status = VMStatus.STOPPED
                    db.commit()
                    logger.info(f"Stopped VM {vm.hostname}")

            # Step 2: Stop the router container
            range_router = db.query(RangeRouter).filter(RangeRouter.range_id == range_id).first()
            if range_router and range_router.container_id:
                try:
                    vyos.stop_router(range_router.container_id)
                    range_router.status = RouterStatus.STOPPED
                    db.commit()
                    logger.info(f"Stopped VyOS router for range {range_id}")
                except Exception as e:
                    logger.warning(f"Failed to stop VyOS router: {e}")

        range_obj.status = RangeStatus.STOPPED
        # Set lifecycle timestamp
        from datetime import timezone
        range_obj.stopped_at = datetime.now(timezone.utc)
        db.commit()

        # Log the stop event
        event_service = EventService(db)
        event_service.log_event(
            range_id=range_id,
            event_type=EventType.RANGE_STOPPED,
            message=f"Range '{range_obj.name}' stopped",
            user_id=current_user.id
        )
        db.refresh(range_obj)

    except Exception as e:
        logger.error(f"Failed to stop range {range_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop range: {str(e)}",
        )

    return range_obj


@router.post("/{range_id}/teardown", response_model=RangeResponse)
def teardown_range(range_id: UUID, db: DBSession, current_user: CurrentUser):
    """Tear down a range - destroy all VMs and networks"""
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Range not found",
        )

    if range_obj.status == RangeStatus.DEPLOYING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot teardown range while deploying",
        )

    try:
        docker = get_docker_service()
        vyos = get_vyos_service()

        # Step 1: Remove all VM containers
        vms = db.query(VM).filter(VM.range_id == range_id).all()
        for vm in vms:
            if vm.container_id:
                docker.remove_container(vm.container_id, force=True)
                vm.container_id = None
                vm.status = VMStatus.PENDING
                db.commit()

        # Step 2: Remove VyOS router
        range_router = db.query(RangeRouter).filter(RangeRouter.range_id == range_id).first()
        if range_router and range_router.container_id:
            try:
                vyos.remove_router(range_router.container_id)
                logger.info(f"Removed VyOS router for range {range_id}")
            except Exception as e:
                logger.warning(f"Failed to remove VyOS router: {e}")
            range_router.container_id = None
            range_router.status = RouterStatus.PENDING
            db.commit()

        # Step 3: Remove all Docker networks and reset VyOS interface assignments
        networks = db.query(Network).filter(Network.range_id == range_id).all()
        for network in networks:
            if network.docker_network_id:
                docker.delete_network(network.docker_network_id)
                network.docker_network_id = None
                network.vyos_interface = None
                db.commit()

        range_obj.status = RangeStatus.DRAFT
        db.commit()
        db.refresh(range_obj)

    except Exception as e:
        logger.error(f"Failed to teardown range {range_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to teardown range: {str(e)}",
        )

    return range_obj


@router.get("/{range_id}/export", response_model=RangeTemplateExport)
def export_range(range_id: UUID, db: DBSession, current_user: CurrentUser):
    """Export a range as a reusable template."""
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Range not found",
        )

    # Get networks
    networks = db.query(Network).filter(Network.range_id == range_id).all()
    network_data = [
        NetworkTemplateData(
            name=n.name,
            subnet=n.subnet,
            gateway=n.gateway,
            is_isolated=n.is_isolated,
        )
        for n in networks
    ]

    # Build network name lookup
    network_lookup = {n.id: n.name for n in networks}

    # Get VMs with their template names
    vms = db.query(VM).filter(VM.range_id == range_id).all()
    vm_data = []
    for vm in vms:
        template = db.query(VMTemplate).filter(VMTemplate.id == vm.template_id).first()
        vm_data.append(
            VMTemplateData(
                hostname=vm.hostname,
                ip_address=vm.ip_address,
                network_name=network_lookup.get(vm.network_id, "unknown"),
                template_name=template.name if template else "unknown",
                cpu=vm.cpu,
                ram_mb=vm.ram_mb,
                disk_gb=vm.disk_gb,
                position_x=vm.position_x,
                position_y=vm.position_y,
            )
        )

    return RangeTemplateExport(
        version="1.0",
        name=range_obj.name,
        description=range_obj.description,
        networks=network_data,
        vms=vm_data,
    )


@router.post("/import", response_model=RangeDetailResponse, status_code=status.HTTP_201_CREATED)
def import_range(
    import_data: RangeTemplateImport,
    db: DBSession,
    current_user: CurrentUser,
):
    """Import a range from a template."""
    template = import_data.template
    range_name = import_data.name_override or template.name

    # Create range
    range_obj = Range(
        name=range_name,
        description=template.description,
        created_by=current_user.id,
    )
    db.add(range_obj)
    db.commit()
    db.refresh(range_obj)

    # Create networks and build lookup
    network_lookup = {}
    for net_data in template.networks:
        network = Network(
            range_id=range_obj.id,
            name=net_data.name,
            subnet=net_data.subnet,
            gateway=net_data.gateway,
            is_isolated=net_data.is_isolated,
        )
        db.add(network)
        db.commit()
        db.refresh(network)
        network_lookup[net_data.name] = network.id

    # Create VMs
    for vm_data in template.vms:
        # Find network by name
        network_id = network_lookup.get(vm_data.network_name)
        if not network_id:
            logger.warning(f"Network '{vm_data.network_name}' not found for VM '{vm_data.hostname}'")
            continue

        # Find template by name
        vm_template = db.query(VMTemplate).filter(VMTemplate.name == vm_data.template_name).first()
        if not vm_template:
            logger.warning(f"VM template '{vm_data.template_name}' not found for VM '{vm_data.hostname}'")
            continue

        vm = VM(
            range_id=range_obj.id,
            network_id=network_id,
            template_id=vm_template.id,
            hostname=vm_data.hostname,
            ip_address=vm_data.ip_address,
            cpu=vm_data.cpu,
            ram_mb=vm_data.ram_mb,
            disk_gb=vm_data.disk_gb,
            position_x=vm_data.position_x,
            position_y=vm_data.position_y,
        )
        db.add(vm)
        db.commit()

    db.refresh(range_obj)
    return range_obj


@router.post("/{range_id}/clone", response_model=RangeDetailResponse, status_code=status.HTTP_201_CREATED)
def clone_range(
    range_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    new_name: str = None,
):
    """Clone a range with all its networks and VMs."""
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Range not found",
        )

    # Create cloned range
    cloned_range = Range(
        name=new_name or f"{range_obj.name} (Copy)",
        description=range_obj.description,
        created_by=current_user.id,
    )
    db.add(cloned_range)
    db.commit()
    db.refresh(cloned_range)

    # Clone networks and build ID mapping
    old_to_new_network = {}
    networks = db.query(Network).filter(Network.range_id == range_id).all()
    for network in networks:
        cloned_network = Network(
            range_id=cloned_range.id,
            name=network.name,
            subnet=network.subnet,
            gateway=network.gateway,
            is_isolated=network.is_isolated,
        )
        db.add(cloned_network)
        db.commit()
        db.refresh(cloned_network)
        old_to_new_network[network.id] = cloned_network.id

    # Clone VMs
    vms = db.query(VM).filter(VM.range_id == range_id).all()
    for vm in vms:
        cloned_vm = VM(
            range_id=cloned_range.id,
            network_id=old_to_new_network.get(vm.network_id),
            template_id=vm.template_id,
            hostname=vm.hostname,
            ip_address=vm.ip_address,
            cpu=vm.cpu,
            ram_mb=vm.ram_mb,
            disk_gb=vm.disk_gb,
            position_x=vm.position_x,
            position_y=vm.position_y,
        )
        db.add(cloned_vm)
        db.commit()

    db.refresh(cloned_range)
    return cloned_range


@router.post("/{range_id}/scenario", response_model=ApplyScenarioResponse)
def apply_scenario(
    range_id: UUID,
    request: ApplyScenarioRequest,
    db: DBSession,
    current_user: CurrentUser,
):
    """Apply a training scenario to a range, generating MSEL and injects."""
    # Get range
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(status_code=404, detail="Range not found")

    # Get scenario from filesystem
    scenario = get_scenario(str(request.scenario_id))
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    # Validate role mapping - all required roles must be mapped
    missing_roles = set(scenario.required_roles) - set(request.role_mapping.keys())
    if missing_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Missing role mappings: {', '.join(missing_roles)}"
        )

    # Validate VM IDs exist in this range
    vm_ids = set(request.role_mapping.values())
    existing_vms = db.query(VM).filter(
        VM.range_id == range_id,
        VM.id.in_([UUID(vid) for vid in vm_ids])
    ).all()
    existing_vm_ids = {str(vm.id) for vm in existing_vms}
    invalid_vms = vm_ids - existing_vm_ids
    if invalid_vms:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid VM IDs: {', '.join(invalid_vms)}"
        )

    # Delete existing MSEL if any
    existing_msel = db.query(MSEL).filter(MSEL.range_id == range_id).first()
    if existing_msel:
        db.delete(existing_msel)
        db.flush()

    # Create MSEL content from scenario
    msel_content = f"# {scenario.name}\n\n{scenario.description}\n\n"
    msel_content += "## Events\n\n"
    for event in scenario.events:
        msel_content += f"### T+{event['delay_minutes']}min: {event['title']}\n"
        msel_content += f"{event.get('description', '')}\n\n"

    # Create MSEL
    msel = MSEL(
        range_id=range_id,
        name=f"Scenario: {scenario.name}",
        content=msel_content,
    )
    db.add(msel)
    db.flush()

    # Create Injects from scenario events
    inject_count = 0
    for event in scenario.events:
        # Map target_role to actual VM ID
        target_role = event.get("target_role", "")
        target_vm_id = request.role_mapping.get(target_role)

        inject = Inject(
            msel_id=msel.id,
            sequence_number=event["sequence"],
            inject_time_minutes=event["delay_minutes"],
            title=event["title"],
            description=event.get("description"),
            target_vm_ids=[target_vm_id] if target_vm_id else [],
            actions=event.get("actions", []),
            status=InjectStatus.PENDING,
        )
        db.add(inject)
        inject_count += 1

    db.commit()

    return ApplyScenarioResponse(
        msel_id=msel.id,
        inject_count=inject_count,
        status="applied"
    )


# ============================================================================
# Comprehensive Export/Import Endpoints (v2.0)
# ============================================================================

from pathlib import Path
from typing import Union
from fastapi import UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
import tempfile
import redis
import json as json_module

from cyroid.schemas.export import (
    ExportRequest,
    ExportJobStatus,
    ImportValidationResult,
    ImportOptions,
    ImportResult,
    RangeExportFull,
)


def get_redis_client():
    """Get Redis client for job status tracking."""
    settings = get_settings()
    return redis.from_url(settings.redis_url)


@router.post("/{range_id}/export/full")
def export_range_full(
    range_id: UUID,
    options: ExportRequest,
    background_tasks: BackgroundTasks,
    db: DBSession,
    current_user: CurrentUser,
):
    """
    Export range with full configuration (all VM settings, templates, MSEL, artifacts).

    For online exports (include_docker_images=False): Returns file directly.
    For offline exports (include_docker_images=True): Starts background job and returns job ID.
    """
    from cyroid.services.export_service import get_export_service

    # Verify range exists and user has access
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(status_code=404, detail="Range not found")

    check_resource_access('range', range_id, current_user, db, range_obj.created_by)

    export_service = get_export_service()

    if options.include_docker_images:
        # Offline export - run as background task
        import uuid
        job_id = str(uuid.uuid4())

        # Store initial job status in Redis
        redis_client = get_redis_client()
        job_status = ExportJobStatus(
            job_id=job_id,
            status="pending",
            progress_percent=0,
            current_step="Initializing...",
            created_at=datetime.utcnow(),
        )
        redis_client.setex(
            f"export_job:{job_id}",
            3600 * 24,  # 24 hour TTL
            job_status.model_dump_json()
        )

        # Schedule background task
        background_tasks.add_task(
            _run_offline_export,
            range_id=range_id,
            job_id=job_id,
            options=options,
            user_id=current_user.id,
        )

        return job_status

    else:
        # Online export - return file directly
        try:
            archive_path, filename = export_service.export_range_online(
                range_id=range_id,
                options=options,
                user=current_user,
                db=db,
            )
            return FileResponse(
                path=str(archive_path),
                filename=filename,
                media_type="application/zip",
                background=BackgroundTasks()  # Cleanup after response
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.exception("Export failed")
            raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


def _run_offline_export(range_id: UUID, job_id: str, options: ExportRequest, user_id: UUID):
    """Background task for offline export with Docker images."""
    from cyroid.services.export_service import get_export_service
    from cyroid.database import SessionLocal

    redis_client = get_redis_client()

    def update_progress(percent: int, step: str):
        job_data = redis_client.get(f"export_job:{job_id}")
        if job_data:
            job_status = ExportJobStatus.model_validate_json(job_data)
            job_status.status = "in_progress"
            job_status.progress_percent = percent
            job_status.current_step = step
            redis_client.setex(
                f"export_job:{job_id}",
                3600 * 24,
                job_status.model_dump_json()
            )

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        export_service = get_export_service()
        archive_path, filename = export_service.export_range_offline(
            range_id=range_id,
            options=options,
            user=user,
            db=db,
            progress_callback=update_progress,
        )

        # Update job with download info
        file_size = os.path.getsize(archive_path)
        job_status = ExportJobStatus(
            job_id=job_id,
            status="completed",
            progress_percent=100,
            current_step="Export complete",
            download_url=f"/ranges/export/jobs/{job_id}/download",
            file_size_bytes=file_size,
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        # Store the archive path for download
        redis_client.setex(f"export_job:{job_id}:path", 3600 * 24, str(archive_path))
        redis_client.setex(f"export_job:{job_id}:filename", 3600 * 24, filename)
        redis_client.setex(f"export_job:{job_id}", 3600 * 24, job_status.model_dump_json())

    except Exception as e:
        logger.exception(f"Offline export failed for job {job_id}")
        job_status = ExportJobStatus(
            job_id=job_id,
            status="failed",
            progress_percent=0,
            current_step="Export failed",
            error_message=str(e),
            created_at=datetime.utcnow(),
        )
        redis_client.setex(f"export_job:{job_id}", 3600 * 24, job_status.model_dump_json())
    finally:
        db.close()


@router.get("/export/jobs/{job_id}", response_model=ExportJobStatus)
def get_export_job_status(job_id: str, current_user: CurrentUser):
    """Get status of a background export job."""
    redis_client = get_redis_client()
    job_data = redis_client.get(f"export_job:{job_id}")

    if not job_data:
        raise HTTPException(status_code=404, detail="Export job not found")

    return ExportJobStatus.model_validate_json(job_data)


@router.get("/export/jobs/{job_id}/download")
def download_export(job_id: str, current_user: CurrentUser):
    """Download a completed export archive."""
    redis_client = get_redis_client()

    # Check job status
    job_data = redis_client.get(f"export_job:{job_id}")
    if not job_data:
        raise HTTPException(status_code=404, detail="Export job not found")

    job_status = ExportJobStatus.model_validate_json(job_data)
    if job_status.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Export not ready. Status: {job_status.status}"
        )

    # Get archive path
    archive_path = redis_client.get(f"export_job:{job_id}:path")
    filename = redis_client.get(f"export_job:{job_id}:filename")

    if not archive_path or not filename:
        raise HTTPException(status_code=404, detail="Export file not found")

    archive_path = archive_path.decode() if isinstance(archive_path, bytes) else archive_path
    filename = filename.decode() if isinstance(filename, bytes) else filename

    if not os.path.exists(archive_path):
        raise HTTPException(status_code=404, detail="Export file has been deleted")

    return FileResponse(
        path=archive_path,
        filename=filename,
        media_type="application/gzip",
    )


@router.post("/import/validate", response_model=ImportValidationResult)
async def validate_import(
    file: UploadFile = File(...),
    db: DBSession = None,
    current_user: CurrentUser = None,
):
    """
    Validate an import archive and preview conflicts.

    Upload a .zip or .tar.gz export archive to validate before importing.
    Returns validation results including any conflicts with existing templates or networks.
    """
    from cyroid.services.export_service import get_export_service

    # Save uploaded file to temp location
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file.filename)
    try:
        content = await file.read()
        temp_file.write(content)
        temp_file.close()

        export_service = get_export_service()
        result = export_service.validate_import(Path(temp_file.name), db)
        return result

    finally:
        # Cleanup temp file
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)


@router.post("/import/execute", response_model=ImportResult)
async def execute_import(
    file: UploadFile = File(...),
    name_override: str = None,
    template_conflict_action: str = "use_existing",
    skip_artifacts: bool = False,
    skip_msel: bool = False,
    db: DBSession = None,
    current_user: CurrentUser = None,
):
    """
    Execute a range import from an archive.

    Upload a .zip or .tar.gz export archive to import.

    Options:
    - name_override: Override the range name (required if name conflicts)
    - template_conflict_action: "use_existing", "create_new", or "skip"
    - skip_artifacts: Don't import artifacts
    - skip_msel: Don't import MSEL/injects
    """
    from cyroid.services.export_service import get_export_service

    # Save uploaded file to temp location
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file.filename)
    try:
        content = await file.read()
        temp_file.write(content)
        temp_file.close()

        options = ImportOptions(
            name_override=name_override,
            template_conflict_action=template_conflict_action,
            skip_artifacts=skip_artifacts,
            skip_msel=skip_msel,
        )

        export_service = get_export_service()
        result = export_service.import_range(
            archive_path=Path(temp_file.name),
            options=options,
            user=current_user,
            db=db,
        )
        return result

    finally:
        # Cleanup temp file
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)


@router.post("/import/load-images")
async def load_docker_images(
    file: UploadFile = File(...),
    current_user: CurrentUser = None,
):
    """
    Load Docker images from an offline export archive.

    Use this endpoint to pre-load Docker images before importing a range
    on an air-gapped system.
    """
    from cyroid.services.export_service import get_export_service

    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    # Save uploaded file to temp location
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file.filename)
    try:
        content = await file.read()
        temp_file.write(content)
        temp_file.close()

        export_service = get_export_service()
        loaded_images = export_service.load_docker_images(Path(temp_file.name))

        return {
            "success": True,
            "images_loaded": loaded_images,
            "count": len(loaded_images),
        }

    except Exception as e:
        logger.exception("Failed to load Docker images")
        raise HTTPException(status_code=500, detail=f"Failed to load images: {str(e)}")

    finally:
        # Cleanup temp file
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)


# ============================================================================
# Resource Tag Endpoints (ABAC Visibility Control)
# ============================================================================

@router.get("/{range_id}/tags", response_model=ResourceTagsResponse)
def get_range_tags(range_id: UUID, db: DBSession, current_user: CurrentUser):
    """Get visibility tags for a range."""
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(status_code=404, detail="Range not found")

    # Check access
    check_resource_access('range', range_id, current_user, db, range_obj.created_by)

    tags = db.query(ResourceTag.tag).filter(
        ResourceTag.resource_type == 'range',
        ResourceTag.resource_id == range_id
    ).all()

    return ResourceTagsResponse(
        resource_type='range',
        resource_id=range_id,
        tags=[t[0] for t in tags]
    )


@router.post("/{range_id}/tags", status_code=status.HTTP_201_CREATED)
def add_range_tag(range_id: UUID, tag_data: ResourceTagCreate, db: DBSession, current_user: CurrentUser):
    """
    Add a visibility tag to a range.
    Only the owner or an admin can add tags.
    """
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(status_code=404, detail="Range not found")

    # Only owner or admin can add tags
    if range_obj.created_by != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only the owner or admin can add tags")

    # Check if tag already exists
    existing = db.query(ResourceTag).filter(
        ResourceTag.resource_type == 'range',
        ResourceTag.resource_id == range_id,
        ResourceTag.tag == tag_data.tag
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Tag already exists on this range")

    tag = ResourceTag(
        resource_type='range',
        resource_id=range_id,
        tag=tag_data.tag
    )
    db.add(tag)
    db.commit()

    return {"message": f"Tag '{tag_data.tag}' added to range"}


@router.delete("/{range_id}/tags/{tag}")
def remove_range_tag(range_id: UUID, tag: str, db: DBSession, current_user: CurrentUser):
    """
    Remove a visibility tag from a range.
    Only the owner or an admin can remove tags.
    """
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(status_code=404, detail="Range not found")

    # Only owner or admin can remove tags
    if range_obj.created_by != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only the owner or admin can remove tags")

    tag_obj = db.query(ResourceTag).filter(
        ResourceTag.resource_type == 'range',
        ResourceTag.resource_id == range_id,
        ResourceTag.tag == tag
    ).first()
    if not tag_obj:
        raise HTTPException(status_code=404, detail="Tag not found on this range")

    db.delete(tag_obj)
    db.commit()

    return {"message": f"Tag '{tag}' removed from range"}
