# cyroid/api/snapshots.py
"""API endpoints for VM snapshot management.

Implements the three-tier Image Library logic:
- First snapshot of a VM → creates GoldenImage (with lineage to BaseImage)
- Follow-on snapshots → creates Snapshot (fork, with lineage to GoldenImage)
"""
from typing import List, Union
from uuid import UUID
import logging

from fastapi import APIRouter, HTTPException, status

from cyroid.api.deps import DBSession, CurrentUser
from cyroid.models.snapshot import Snapshot
from cyroid.models.golden_image import GoldenImage
from cyroid.models.vm import VM, VMStatus
from cyroid.schemas.snapshot import SnapshotCreate, SnapshotResponse
from cyroid.schemas.golden_image import GoldenImageResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/snapshots", tags=["Snapshots"])


def get_docker_service():
    """Lazy import docker service."""
    from cyroid.services.docker_service import get_docker_service as _get_docker
    return _get_docker()


@router.post("", response_model=Union[GoldenImageResponse, SnapshotResponse], status_code=status.HTTP_201_CREATED)
def create_snapshot(
    snapshot_data: SnapshotCreate,
    db: DBSession,
    current_user: CurrentUser,
):
    """Create a snapshot of a VM.

    Implements Image Library logic:
    - First snapshot → creates GoldenImage (linked to VM's base_image_id if set)
    - Follow-on snapshots → creates Snapshot fork (linked to the GoldenImage)

    Returns either GoldenImageResponse or SnapshotResponse depending on which was created.
    """
    vm = db.query(VM).filter(VM.id == snapshot_data.vm_id).first()
    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found",
        )

    if not vm.container_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VM has no running container",
        )

    docker = get_docker_service()

    # Check if this VM already has a GoldenImage
    existing_golden = db.query(GoldenImage).filter(
        GoldenImage.source_vm_id == vm.id
    ).first()

    if existing_golden is None:
        # First snapshot → create GoldenImage
        image_name = f"cyroid-golden-{vm.id}-{snapshot_data.name}".lower().replace(" ", "-")

        try:
            image_id = docker.create_snapshot(vm.container_id, image_name)
        except Exception as e:
            logger.error(f"Failed to create golden image snapshot: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create snapshot: {str(e)}",
            )

        # Determine OS and VM type from Image Library sources
        os_type = "linux"
        vm_type = "container"
        if vm.base_image:
            os_type = vm.base_image.os_type
            vm_type = vm.base_image.vm_type

        golden = GoldenImage(
            name=snapshot_data.name,
            description=snapshot_data.description,
            source="snapshot",
            base_image_id=vm.base_image_id,  # Link to base image if set
            source_vm_id=vm.id,
            docker_image_id=image_id,
            docker_image_tag=image_name,
            os_type=os_type,
            vm_type=vm_type,
            default_cpu=vm.cpu,
            default_ram_mb=vm.ram_mb,
            default_disk_gb=vm.disk_gb,
            is_global=True,
            created_by=current_user.id,
        )
        db.add(golden)
        db.commit()
        db.refresh(golden)

        logger.info(f"Created GoldenImage '{golden.name}' from VM {vm.hostname}")
        return golden

    else:
        # Follow-on snapshot → create Snapshot (fork)
        image_name = f"cyroid-snapshot-{vm.id}-{snapshot_data.name}".lower().replace(" ", "-")

        try:
            image_id = docker.create_snapshot(vm.container_id, image_name)
        except Exception as e:
            logger.error(f"Failed to create snapshot: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create snapshot: {str(e)}",
            )

        snapshot = Snapshot(
            vm_id=snapshot_data.vm_id,
            name=snapshot_data.name,
            description=snapshot_data.description,
            docker_image_id=image_id,
            docker_image_tag=image_name,
            golden_image_id=existing_golden.id,  # Link to parent golden image
            os_type=existing_golden.os_type,
            vm_type=existing_golden.vm_type,
            default_cpu=vm.cpu,
            default_ram_mb=vm.ram_mb,
            default_disk_gb=vm.disk_gb,
            is_global=True,
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)

        logger.info(f"Created Snapshot fork '{snapshot.name}' linked to GoldenImage '{existing_golden.name}'")
        return snapshot


@router.get("", response_model=List[SnapshotResponse])
def list_snapshots(
    vm_id: UUID = None,
    db: DBSession = None,
    current_user: CurrentUser = None,
):
    """List snapshots, optionally filtered by VM."""
    query = db.query(Snapshot)
    if vm_id:
        query = query.filter(Snapshot.vm_id == vm_id)
    return query.order_by(Snapshot.created_at.desc()).all()


@router.get("/{snapshot_id}", response_model=SnapshotResponse)
def get_snapshot(
    snapshot_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    """Get snapshot details."""
    snapshot = db.query(Snapshot).filter(Snapshot.id == snapshot_id).first()
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Snapshot not found",
        )
    return snapshot


@router.post("/{snapshot_id}/restore", response_model=SnapshotResponse)
def restore_snapshot(
    snapshot_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    """Restore a VM to a snapshot state."""
    snapshot = db.query(Snapshot).filter(Snapshot.id == snapshot_id).first()
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Snapshot not found",
        )

    if not snapshot.docker_image_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Snapshot has no associated Docker image",
        )

    vm = db.query(VM).filter(VM.id == snapshot.vm_id).first()
    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found",
        )

    docker = get_docker_service()

    try:
        # Stop and remove current container if exists
        if vm.container_id:
            try:
                docker.stop_container(vm.container_id)
                docker.remove_container(vm.container_id, force=True)
            except Exception as e:
                logger.warning(f"Failed to remove old container: {e}")

        # Create new container from snapshot image
        from cyroid.models.network import Network
        network = db.query(Network).filter(Network.id == vm.network_id).first()

        if not network or not network.docker_network_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Network not provisioned",
            )

        labels = {
            "cyroid.range_id": str(vm.range_id),
            "cyroid.vm_id": str(vm.id),
            "cyroid.hostname": vm.hostname,
            "cyroid.restored_from": str(snapshot.id),
        }

        container_id = docker.create_container(
            name=f"cyroid-{vm.hostname}-{str(vm.id)[:8]}",
            image=snapshot.docker_image_id,
            network_id=network.docker_network_id,
            ip_address=vm.ip_address,
            cpu_limit=vm.cpu,
            memory_limit_mb=vm.ram_mb,
            hostname=vm.hostname,
            labels=labels,
        )

        docker.start_container(container_id)

        vm.container_id = container_id
        vm.status = VMStatus.RUNNING
        db.commit()

        logger.info(f"Restored VM {vm.hostname} from snapshot {snapshot.name}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to restore snapshot: {e}")
        vm.status = VMStatus.ERROR
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restore snapshot: {str(e)}",
        )

    return snapshot


@router.delete("/{snapshot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_snapshot(
    snapshot_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    """Delete a snapshot."""
    snapshot = db.query(Snapshot).filter(Snapshot.id == snapshot_id).first()
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Snapshot not found",
        )

    # Delete Docker image if exists
    if snapshot.docker_image_id:
        try:
            docker = get_docker_service()
            docker.client.images.remove(snapshot.docker_image_id, force=True)
        except Exception as e:
            logger.warning(f"Failed to remove snapshot image: {e}")

    db.delete(snapshot)
    db.commit()
