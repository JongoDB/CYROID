# backend/cyroid/api/ranges.py
from typing import List
from uuid import UUID
import logging

from fastapi import APIRouter, HTTPException, status

from cyroid.api.deps import DBSession, CurrentUser
from cyroid.models.range import Range, RangeStatus
from cyroid.models.network import Network, IsolationLevel
from cyroid.models.vm import VM, VMStatus
from cyroid.models.template import VMTemplate
from cyroid.schemas.range import RangeCreate, RangeUpdate, RangeResponse, RangeDetailResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ranges", tags=["Ranges"])


def get_docker_service():
    """Lazy import to avoid Docker connection issues during testing."""
    from cyroid.services.docker_service import get_docker_service as _get_docker_service
    return _get_docker_service()


@router.get("", response_model=List[RangeResponse])
def list_ranges(db: DBSession, current_user: CurrentUser):
    ranges = db.query(Range).filter(Range.created_by == current_user.id).all()
    return ranges


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
    range_obj = db.query(Range).filter(Range.id == range_id).first()
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
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Range not found",
        )

    # Cleanup Docker resources before deleting
    try:
        docker = get_docker_service()
        docker.cleanup_range(str(range_id))
    except Exception as e:
        logger.warning(f"Failed to cleanup Docker resources for range {range_id}: {e}")

    db.delete(range_obj)
    db.commit()


@router.post("/{range_id}/deploy", response_model=RangeResponse)
def deploy_range(range_id: UUID, db: DBSession, current_user: CurrentUser):
    """Deploy a range - creates Docker networks and starts all VMs"""
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
    db.commit()

    try:
        docker = get_docker_service()

        # Step 1: Provision all networks
        networks = db.query(Network).filter(Network.range_id == range_id).all()
        for network in networks:
            if not network.docker_network_id:
                internal = network.isolation_level in [IsolationLevel.COMPLETE, IsolationLevel.CONTROLLED]
                docker_network_id = docker.create_network(
                    name=f"cyroid-{network.name}-{str(network.id)[:8]}",
                    subnet=network.subnet,
                    gateway=network.gateway,
                    internal=internal,
                    labels={
                        "cyroid.range_id": str(range_id),
                        "cyroid.network_id": str(network.id),
                    }
                )
                network.docker_network_id = docker_network_id
                db.commit()

        # Step 2: Create and start all VMs
        vms = db.query(VM).filter(VM.range_id == range_id).all()
        for vm in vms:
            if vm.container_id:
                # Container exists, just start it
                docker.start_container(vm.container_id)
            else:
                # Create new container
                network = db.query(Network).filter(Network.id == vm.network_id).first()
                template = db.query(VMTemplate).filter(VMTemplate.id == vm.template_id).first()

                if not network or not network.docker_network_id:
                    logger.warning(f"Skipping VM {vm.id}: network not provisioned")
                    continue

                labels = {
                    "cyroid.range_id": str(range_id),
                    "cyroid.vm_id": str(vm.id),
                    "cyroid.hostname": vm.hostname,
                }

                if template.os_type == "windows":
                    container_id = docker.create_windows_container(
                        name=f"cyroid-{vm.hostname}-{str(vm.id)[:8]}",
                        network_id=network.docker_network_id,
                        ip_address=vm.ip_address,
                        cpu_limit=vm.cpu,
                        memory_limit_mb=vm.ram_mb,
                        disk_size_gb=vm.disk_gb,
                        labels=labels,
                    )
                else:
                    container_id = docker.create_container(
                        name=f"cyroid-{vm.hostname}-{str(vm.id)[:8]}",
                        image=template.base_image,
                        network_id=network.docker_network_id,
                        ip_address=vm.ip_address,
                        cpu_limit=vm.cpu,
                        memory_limit_mb=vm.ram_mb,
                        hostname=vm.hostname,
                        labels=labels,
                    )

                vm.container_id = container_id
                docker.start_container(container_id)

                # Run config script if present
                if template.config_script:
                    try:
                        docker.exec_command(container_id, template.config_script)
                    except Exception as e:
                        logger.warning(f"Config script failed for VM {vm.id}: {e}")

            vm.status = VMStatus.RUNNING
            db.commit()

        range_obj.status = RangeStatus.RUNNING
        db.commit()
        db.refresh(range_obj)

    except Exception as e:
        logger.error(f"Failed to deploy range {range_id}: {e}")
        range_obj.status = RangeStatus.ERROR
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deploy range: {str(e)}",
        )

    return range_obj


@router.post("/{range_id}/start", response_model=RangeResponse)
def start_range(range_id: UUID, db: DBSession, current_user: CurrentUser):
    """Start all VMs in a stopped range"""
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

        vms = db.query(VM).filter(VM.range_id == range_id).all()
        for vm in vms:
            if vm.container_id:
                docker.start_container(vm.container_id)
                vm.status = VMStatus.RUNNING
                db.commit()

        range_obj.status = RangeStatus.RUNNING
        db.commit()
        db.refresh(range_obj)

    except Exception as e:
        logger.error(f"Failed to start range {range_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start range: {str(e)}",
        )

    return range_obj


@router.post("/{range_id}/stop", response_model=RangeResponse)
def stop_range(range_id: UUID, db: DBSession, current_user: CurrentUser):
    """Stop all VMs in a running range"""
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

        vms = db.query(VM).filter(VM.range_id == range_id).all()
        for vm in vms:
            if vm.container_id:
                docker.stop_container(vm.container_id)
                vm.status = VMStatus.STOPPED
                db.commit()

        range_obj.status = RangeStatus.STOPPED
        db.commit()
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

        # Step 1: Remove all VM containers
        vms = db.query(VM).filter(VM.range_id == range_id).all()
        for vm in vms:
            if vm.container_id:
                docker.remove_container(vm.container_id, force=True)
                vm.container_id = None
                vm.status = VMStatus.PENDING
                db.commit()

        # Step 2: Remove all Docker networks
        networks = db.query(Network).filter(Network.range_id == range_id).all()
        for network in networks:
            if network.docker_network_id:
                docker.delete_network(network.docker_network_id)
                network.docker_network_id = None
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
