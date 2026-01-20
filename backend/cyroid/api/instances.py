# backend/cyroid/api/instances.py
from uuid import UUID
from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from cyroid.api.deps import DBSession, CurrentUser
from cyroid.models import Range, RangeBlueprint, RangeInstance
from cyroid.schemas.blueprint import InstanceResponse, BlueprintConfig
from cyroid.services.blueprint_service import create_range_from_blueprint
from cyroid.tasks.deployment import deploy_range_task, teardown_range_task

router = APIRouter(prefix="/instances", tags=["instances"])


@router.get("/{instance_id}", response_model=InstanceResponse)
def get_instance(instance_id: UUID, db: DBSession, current_user: CurrentUser):
    """Get instance details."""
    instance = db.query(RangeInstance).filter(RangeInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")

    return _instance_to_response(instance, db)


@router.post("/{instance_id}/reset", response_model=InstanceResponse)
def reset_instance(instance_id: UUID, db: DBSession, current_user: CurrentUser):
    """Reset instance to initial state (same blueprint version)."""
    instance = db.query(RangeInstance).filter(RangeInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")

    blueprint = instance.blueprint
    range_obj = instance.range

    # Teardown current range resources (async task)
    teardown_range_task.send(str(range_obj.id))

    # Redeploy from same config
    config = BlueprintConfig.model_validate(blueprint.config)

    # Delete VMs and networks from range
    from cyroid.models import VM, Network
    db.query(VM).filter(VM.range_id == range_obj.id).delete()
    db.query(Network).filter(Network.range_id == range_obj.id).delete()
    db.flush()

    # Recreate from config
    _recreate_range_contents(
        db, range_obj, config, blueprint.base_subnet_prefix, instance.subnet_offset
    )

    # Redeploy (queue async task)
    db.commit()
    deploy_range_task.send(str(range_obj.id))
    db.refresh(instance)

    return _instance_to_response(instance, db)


@router.post("/{instance_id}/redeploy", response_model=InstanceResponse)
def redeploy_instance(instance_id: UUID, db: DBSession, current_user: CurrentUser):
    """Redeploy instance from latest blueprint version."""
    instance = db.query(RangeInstance).filter(RangeInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")

    blueprint = instance.blueprint
    range_obj = instance.range

    # Teardown first (sync for now to ensure cleanup before recreate)
    teardown_range_task.send(str(range_obj.id))

    # Get LATEST config from blueprint
    config = BlueprintConfig.model_validate(blueprint.config)

    # Delete VMs and networks from range
    from cyroid.models import VM, Network
    db.query(VM).filter(VM.range_id == range_obj.id).delete()
    db.query(Network).filter(Network.range_id == range_obj.id).delete()
    db.flush()

    # Recreate from latest config
    _recreate_range_contents(
        db, range_obj, config, blueprint.base_subnet_prefix, instance.subnet_offset
    )

    # Update instance to latest version
    instance.blueprint_version = blueprint.version

    # Redeploy (queue async task)
    db.commit()
    deploy_range_task.send(str(range_obj.id))
    db.refresh(instance)

    return _instance_to_response(instance, db)


@router.post("/{instance_id}/clone", response_model=InstanceResponse, status_code=status.HTTP_201_CREATED)
def clone_instance(instance_id: UUID, db: DBSession, current_user: CurrentUser):
    """Clone an instance (create new instance with next offset)."""
    instance = db.query(RangeInstance).filter(RangeInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")

    blueprint = instance.blueprint
    config = BlueprintConfig.model_validate(blueprint.config)

    # Get next offset
    offset = blueprint.next_offset
    blueprint.next_offset += 1

    # Create new range
    new_range = create_range_from_blueprint(
        db=db,
        config=config,
        range_name=f"{instance.name} (Clone)",
        base_prefix=blueprint.base_subnet_prefix,
        offset=offset,
        created_by=current_user.id,
    )

    # Create new instance record
    new_instance = RangeInstance(
        name=f"{instance.name} (Clone)",
        blueprint_id=blueprint.id,
        blueprint_version=blueprint.version,
        subnet_offset=offset,
        instructor_id=current_user.id,
        range_id=new_range.id,
    )
    db.add(new_instance)
    db.commit()
    db.refresh(new_instance)

    return _instance_to_response(new_instance, db)


@router.delete("/{instance_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_instance(instance_id: UUID, db: DBSession, current_user: CurrentUser):
    """Delete an instance and its range."""
    instance = db.query(RangeInstance).filter(RangeInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")

    range_obj = instance.range

    # Teardown range resources (async task)
    teardown_range_task.send(str(range_obj.id))

    # Delete range (cascades to VMs, networks)
    db.delete(range_obj)

    # Delete instance
    db.delete(instance)
    db.commit()


# ============ Helper Functions ============

def _recreate_range_contents(
    db: Session, range_obj: Range, config: BlueprintConfig, base_prefix: str, offset: int
):
    """Recreate networks and VMs in an existing range."""
    from cyroid.models import Network, VM
    from cyroid.models.base_image import BaseImage
    from cyroid.models.golden_image import GoldenImage
    from cyroid.models.snapshot import Snapshot
    from cyroid.services.blueprint_service import apply_subnet_offset

    # Create networks
    network_lookup = {}
    for net_config in config.networks:
        adjusted_subnet = apply_subnet_offset(net_config.subnet, base_prefix, offset)
        adjusted_gateway = apply_subnet_offset(net_config.gateway, base_prefix, offset)

        network = Network(
            range_id=range_obj.id,
            name=net_config.name,
            subnet=adjusted_subnet,
            gateway=adjusted_gateway,
            is_isolated=net_config.is_isolated,
        )
        db.add(network)
        db.flush()
        network_lookup[net_config.name] = network.id

    # Create VMs
    for vm_config in config.vms:
        network_id = network_lookup.get(vm_config.network_name)
        if not network_id:
            continue

        # Resolve image source from vm_config
        base_image_id = None
        golden_image_id = None
        snapshot_id = None

        if hasattr(vm_config, 'base_image_id') and vm_config.base_image_id:
            base_image_id = vm_config.base_image_id
        elif hasattr(vm_config, 'golden_image_id') and vm_config.golden_image_id:
            golden_image_id = vm_config.golden_image_id
        elif hasattr(vm_config, 'snapshot_id') and vm_config.snapshot_id:
            snapshot_id = vm_config.snapshot_id
        else:
            # No image source found, skip this VM
            continue

        adjusted_ip = apply_subnet_offset(vm_config.ip_address, base_prefix, offset)

        vm = VM(
            range_id=range_obj.id,
            network_id=network_id,
            base_image_id=base_image_id,
            golden_image_id=golden_image_id,
            snapshot_id=snapshot_id,
            hostname=vm_config.hostname,
            ip_address=adjusted_ip,
            cpu=vm_config.cpu,
            ram_mb=vm_config.ram_mb,
            disk_gb=vm_config.disk_gb,
            position_x=vm_config.position_x,
            position_y=vm_config.position_y,
        )
        db.add(vm)

    db.flush()


def _instance_to_response(instance: RangeInstance, db: Session) -> InstanceResponse:
    from cyroid.models import User

    range_obj = instance.range
    instructor = db.query(User).filter(User.id == instance.instructor_id).first()

    return InstanceResponse(
        id=instance.id,
        name=instance.name,
        blueprint_id=instance.blueprint_id,
        blueprint_version=instance.blueprint_version,
        subnet_offset=instance.subnet_offset,
        instructor_id=instance.instructor_id,
        range_id=instance.range_id,
        created_at=instance.created_at,
        range_name=range_obj.name if range_obj else None,
        range_status=range_obj.status.value if range_obj else None,
        instructor_username=instructor.username if instructor else None,
    )
