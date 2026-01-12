# backend/cyroid/api/vms.py
from typing import List
from uuid import UUID
import logging

from fastapi import APIRouter, HTTPException, status

from cyroid.api.deps import DBSession, CurrentUser
from cyroid.models.vm import VM, VMStatus
from cyroid.models.range import Range
from cyroid.models.network import Network
from cyroid.models.template import VMTemplate
from cyroid.schemas.vm import VMCreate, VMUpdate, VMResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vms", tags=["VMs"])


def get_docker_service():
    """Lazy import to avoid Docker connection issues during testing."""
    from cyroid.services.docker_service import get_docker_service as _get_docker_service
    return _get_docker_service()


@router.get("", response_model=List[VMResponse])
def list_vms(range_id: UUID, db: DBSession, current_user: CurrentUser):
    """List all VMs in a range"""
    # Verify range exists
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Range not found",
        )

    vms = db.query(VM).filter(VM.range_id == range_id).all()
    return vms


@router.post("", response_model=VMResponse, status_code=status.HTTP_201_CREATED)
def create_vm(vm_data: VMCreate, db: DBSession, current_user: CurrentUser):
    # Verify range exists
    range_obj = db.query(Range).filter(Range.id == vm_data.range_id).first()
    if not range_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Range not found",
        )

    # Verify network exists and belongs to the range
    network = db.query(Network).filter(Network.id == vm_data.network_id).first()
    if not network:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Network not found",
        )
    if network.range_id != vm_data.range_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Network does not belong to this range",
        )

    # Verify template exists
    template = db.query(VMTemplate).filter(VMTemplate.id == vm_data.template_id).first()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    # Check for duplicate hostname in the range
    existing = db.query(VM).filter(
        VM.range_id == vm_data.range_id,
        VM.hostname == vm_data.hostname
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hostname already exists in this range",
        )

    # Check for duplicate IP in the network
    existing_ip = db.query(VM).filter(
        VM.network_id == vm_data.network_id,
        VM.ip_address == vm_data.ip_address
    ).first()
    if existing_ip:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="IP address already exists in this network",
        )

    vm = VM(**vm_data.model_dump())
    db.add(vm)
    db.commit()
    db.refresh(vm)
    return vm


@router.get("/{vm_id}", response_model=VMResponse)
def get_vm(vm_id: UUID, db: DBSession, current_user: CurrentUser):
    vm = db.query(VM).filter(VM.id == vm_id).first()
    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found",
        )
    return vm


@router.put("/{vm_id}", response_model=VMResponse)
def update_vm(
    vm_id: UUID,
    vm_data: VMUpdate,
    db: DBSession,
    current_user: CurrentUser,
):
    vm = db.query(VM).filter(VM.id == vm_id).first()
    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found",
        )

    update_data = vm_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(vm, field, value)

    db.commit()
    db.refresh(vm)
    return vm


@router.delete("/{vm_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vm(vm_id: UUID, db: DBSession, current_user: CurrentUser):
    vm = db.query(VM).filter(VM.id == vm_id).first()
    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found",
        )

    # Remove container if it exists
    if vm.container_id:
        try:
            docker = get_docker_service()
            docker.remove_container(vm.container_id, force=True)
        except Exception as e:
            logger.warning(f"Failed to remove container for VM {vm_id}: {e}")

    db.delete(vm)
    db.commit()


@router.post("/{vm_id}/start", response_model=VMResponse)
def start_vm(vm_id: UUID, db: DBSession, current_user: CurrentUser):
    """Start a stopped VM"""
    vm = db.query(VM).filter(VM.id == vm_id).first()
    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found",
        )

    if vm.status not in [VMStatus.STOPPED, VMStatus.PENDING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot start VM in {vm.status} status",
        )

    vm.status = VMStatus.CREATING
    db.commit()

    try:
        docker = get_docker_service()

        # Get network and template info
        network = db.query(Network).filter(Network.id == vm.network_id).first()
        template = db.query(VMTemplate).filter(VMTemplate.id == vm.template_id).first()

        if not network or not network.docker_network_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Network not provisioned",
            )

        # Container already exists - just start it
        if vm.container_id:
            docker.start_container(vm.container_id)
        else:
            # Create new container
            labels = {
                "cyroid.range_id": str(vm.range_id),
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
                    logger.warning(f"Config script failed for VM {vm_id}: {e}")

        vm.status = VMStatus.RUNNING
        db.commit()
        db.refresh(vm)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start VM {vm_id}: {e}")
        vm.status = VMStatus.ERROR
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start VM: {str(e)}",
        )

    return vm


@router.post("/{vm_id}/stop", response_model=VMResponse)
def stop_vm(vm_id: UUID, db: DBSession, current_user: CurrentUser):
    """Stop a running VM"""
    vm = db.query(VM).filter(VM.id == vm_id).first()
    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found",
        )

    if vm.status != VMStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot stop VM in {vm.status} status",
        )

    try:
        if vm.container_id:
            docker = get_docker_service()
            docker.stop_container(vm.container_id)

        vm.status = VMStatus.STOPPED
        db.commit()
        db.refresh(vm)

    except Exception as e:
        logger.error(f"Failed to stop VM {vm_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop VM: {str(e)}",
        )

    return vm


@router.post("/{vm_id}/restart", response_model=VMResponse)
def restart_vm(vm_id: UUID, db: DBSession, current_user: CurrentUser):
    """Restart a running VM"""
    vm = db.query(VM).filter(VM.id == vm_id).first()
    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found",
        )

    if vm.status != VMStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot restart VM in {vm.status} status",
        )

    try:
        if vm.container_id:
            docker = get_docker_service()
            docker.restart_container(vm.container_id)

        vm.status = VMStatus.RUNNING
        db.commit()
        db.refresh(vm)

    except Exception as e:
        logger.error(f"Failed to restart VM {vm_id}: {e}")
        vm.status = VMStatus.ERROR
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restart VM: {str(e)}",
        )

    return vm
