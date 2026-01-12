# backend/cyroid/api/vms.py
from typing import List
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from cyroid.api.deps import DBSession, CurrentUser
from cyroid.models.vm import VM, VMStatus
from cyroid.models.range import Range
from cyroid.models.network import Network
from cyroid.models.template import VMTemplate
from cyroid.schemas.vm import VMCreate, VMUpdate, VMResponse

router = APIRouter(prefix="/vms", tags=["VMs"])


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
    db.refresh(vm)

    # TODO: Trigger async start task via Dramatiq

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

    vm.status = VMStatus.STOPPED
    db.commit()
    db.refresh(vm)

    # TODO: Trigger async stop task via Dramatiq

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

    vm.status = VMStatus.CREATING
    db.commit()
    db.refresh(vm)

    # TODO: Trigger async restart task via Dramatiq

    return vm
