# Range Blueprints Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable instructors to save ranges as reusable blueprints and deploy multiple isolated instances with auto-allocated subnets.

**Architecture:** Two new database models (RangeBlueprint, RangeInstance) with JSON config storage. Blueprint API extracts range configuration; Instance API creates ranges with offset-adjusted subnets. Frontend adds Blueprints page with card grid, detail page with instances tab, and modals for save/deploy workflows.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, React, TypeScript, Tailwind CSS

---

## Task 1: Create Database Models

**Files:**
- Create: `backend/cyroid/models/blueprint.py`
- Modify: `backend/cyroid/models/__init__.py`

**Step 1: Create the blueprint models file**

```python
# backend/cyroid/models/blueprint.py
from typing import Optional, List
from uuid import UUID
from sqlalchemy import String, Text, ForeignKey, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class RangeBlueprint(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "range_blueprints"

    name: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    config: Mapped[dict] = mapped_column(JSON)  # networks, VMs, MSEL, router
    base_subnet_prefix: Mapped[str] = mapped_column(String(20))  # e.g., "10.100"
    next_offset: Mapped[int] = mapped_column(Integer, default=0)

    # Ownership
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_by_user = relationship("User", foreign_keys=[created_by])

    # Relationships
    instances: Mapped[List["RangeInstance"]] = relationship(
        "RangeInstance", back_populates="blueprint", cascade="all, delete-orphan"
    )


class RangeInstance(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "range_instances"

    name: Mapped[str] = mapped_column(String(100))
    blueprint_id: Mapped[UUID] = mapped_column(ForeignKey("range_blueprints.id"))
    blueprint_version: Mapped[int] = mapped_column(Integer)
    subnet_offset: Mapped[int] = mapped_column(Integer)

    # Ownership
    instructor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    instructor = relationship("User", foreign_keys=[instructor_id])

    # Link to actual range
    range_id: Mapped[UUID] = mapped_column(ForeignKey("ranges.id"))
    range = relationship("Range")

    # Parent blueprint
    blueprint = relationship("RangeBlueprint", back_populates="instances")
```

**Step 2: Update models __init__.py**

Add to `backend/cyroid/models/__init__.py`:

```python
from cyroid.models.blueprint import RangeBlueprint, RangeInstance
```

And add to `__all__`:

```python
"RangeBlueprint", "RangeInstance",
```

**Step 3: Commit**

```bash
git add backend/cyroid/models/blueprint.py backend/cyroid/models/__init__.py
git commit -m "feat(blueprints): add RangeBlueprint and RangeInstance models"
```

---

## Task 2: Create Database Migration

**Files:**
- Create: `backend/alembic/versions/xxxx_add_blueprints.py` (auto-generated)

**Step 1: Generate migration**

```bash
cd /Users/JonWFH/jondev/CYROID
docker-compose exec api alembic revision --autogenerate -m "add_range_blueprints"
```

**Step 2: Apply migration**

```bash
docker-compose exec api alembic upgrade head
```

**Step 3: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat(blueprints): add database migration for blueprints"
```

---

## Task 3: Create Pydantic Schemas

**Files:**
- Create: `backend/cyroid/schemas/blueprint.py`
- Modify: `backend/cyroid/schemas/__init__.py`

**Step 1: Create schemas file**

```python
# backend/cyroid/schemas/blueprint.py
from typing import Optional, List, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


# ============ Config Sub-schemas ============

class NetworkConfig(BaseModel):
    name: str
    subnet: str
    gateway: str
    is_isolated: bool = False


class VMConfig(BaseModel):
    hostname: str
    ip_address: str
    network_name: str
    template_name: str
    cpu: int = 1
    ram_mb: int = 1024
    disk_gb: int = 20
    position_x: Optional[int] = None
    position_y: Optional[int] = None


class RouterConfig(BaseModel):
    enabled: bool = True
    dhcp_enabled: bool = False


class MSELConfig(BaseModel):
    content: Optional[str] = None
    format: str = "yaml"


class BlueprintConfig(BaseModel):
    networks: List[NetworkConfig]
    vms: List[VMConfig]
    router: Optional[RouterConfig] = None
    msel: Optional[MSELConfig] = None


# ============ Blueprint Schemas ============

class BlueprintCreate(BaseModel):
    range_id: UUID
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    base_subnet_prefix: str = Field(..., pattern=r"^\d{1,3}\.\d{1,3}$")  # e.g., "10.100"


class BlueprintUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None


class BlueprintResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    version: int
    base_subnet_prefix: str
    next_offset: int
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    network_count: int = 0
    vm_count: int = 0
    instance_count: int = 0

    class Config:
        from_attributes = True


class BlueprintDetailResponse(BlueprintResponse):
    config: BlueprintConfig
    created_by_username: Optional[str] = None


# ============ Instance Schemas ============

class InstanceDeploy(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    auto_deploy: bool = True


class InstanceResponse(BaseModel):
    id: UUID
    name: str
    blueprint_id: UUID
    blueprint_version: int
    subnet_offset: int
    instructor_id: UUID
    range_id: UUID
    created_at: datetime
    # Denormalized fields for convenience
    range_name: Optional[str] = None
    range_status: Optional[str] = None
    instructor_username: Optional[str] = None

    class Config:
        from_attributes = True
```

**Step 2: Update schemas __init__.py**

Add to `backend/cyroid/schemas/__init__.py`:

```python
from cyroid.schemas.blueprint import (
    BlueprintCreate, BlueprintUpdate, BlueprintResponse, BlueprintDetailResponse,
    InstanceDeploy, InstanceResponse, BlueprintConfig, NetworkConfig, VMConfig
)
```

**Step 3: Commit**

```bash
git add backend/cyroid/schemas/blueprint.py backend/cyroid/schemas/__init__.py
git commit -m "feat(blueprints): add Pydantic schemas for blueprints and instances"
```

---

## Task 4: Create Blueprint Service

**Files:**
- Create: `backend/cyroid/services/blueprint_service.py`

**Step 1: Create the service file**

```python
# backend/cyroid/services/blueprint_service.py
import re
from typing import Dict, Any, List
from uuid import UUID
from sqlalchemy.orm import Session

from cyroid.models import Range, Network, VM, VMTemplate, MSEL, RangeRouter
from cyroid.schemas.blueprint import BlueprintConfig, NetworkConfig, VMConfig, RouterConfig, MSELConfig


def extract_config_from_range(db: Session, range_id: UUID) -> BlueprintConfig:
    """Extract configuration from an existing range to create a blueprint."""
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise ValueError(f"Range {range_id} not found")

    # Extract networks
    networks = db.query(Network).filter(Network.range_id == range_id).all()
    network_configs = [
        NetworkConfig(
            name=n.name,
            subnet=n.subnet,
            gateway=n.gateway,
            is_isolated=n.is_isolated,
        )
        for n in networks
    ]

    # Build network ID to name lookup
    network_lookup = {n.id: n.name for n in networks}

    # Extract VMs
    vms = db.query(VM).filter(VM.range_id == range_id).all()
    vm_configs = []
    for vm in vms:
        template = db.query(VMTemplate).filter(VMTemplate.id == vm.template_id).first()
        vm_configs.append(
            VMConfig(
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

    # Extract router config
    router = db.query(RangeRouter).filter(RangeRouter.range_id == range_id).first()
    router_config = None
    if router:
        router_config = RouterConfig(
            enabled=True,
            dhcp_enabled=router.dhcp_enabled if hasattr(router, 'dhcp_enabled') else False,
        )

    # Extract MSEL
    msel = db.query(MSEL).filter(MSEL.range_id == range_id).first()
    msel_config = None
    if msel:
        msel_config = MSELConfig(
            content=msel.content,
            format=msel.format if hasattr(msel, 'format') else "yaml",
        )

    return BlueprintConfig(
        networks=network_configs,
        vms=vm_configs,
        router=router_config,
        msel=msel_config,
    )


def extract_subnet_prefix(subnet: str) -> str:
    """Extract the first two octets from a subnet (e.g., '10.100.0.0/24' -> '10.100')."""
    match = re.match(r"(\d{1,3})\.(\d{1,3})\.", subnet)
    if match:
        return f"{match.group(1)}.{match.group(2)}"
    return "10.100"  # Default fallback


def apply_subnet_offset(ip_or_subnet: str, base_prefix: str, offset: int) -> str:
    """
    Apply subnet offset to an IP or subnet.

    Example:
        apply_subnet_offset("10.100.0.10", "10.100", 2) -> "10.102.0.10"
        apply_subnet_offset("10.100.1.0/24", "10.100", 2) -> "10.102.1.0/24"
    """
    # Parse base prefix
    base_match = re.match(r"(\d{1,3})\.(\d{1,3})", base_prefix)
    if not base_match:
        return ip_or_subnet

    base_second_octet = int(base_match.group(2))
    new_second_octet = base_second_octet + offset

    if new_second_octet > 255:
        raise ValueError(f"Offset {offset} would exceed valid IP range")

    # Replace second octet in the IP/subnet
    pattern = rf"({base_match.group(1)})\.{base_second_octet}\."
    replacement = rf"\g<1>.{new_second_octet}."

    return re.sub(pattern, replacement, ip_or_subnet)


def create_range_from_blueprint(
    db: Session,
    config: BlueprintConfig,
    range_name: str,
    base_prefix: str,
    offset: int,
    created_by: UUID,
) -> Range:
    """
    Create a new Range from blueprint config with offset-adjusted subnets.
    Returns the created Range object (not yet deployed).
    """
    from cyroid.models import Range, Network, VM, VMTemplate, MSEL, RangeRouter, RangeStatus

    # Create range
    range_obj = Range(
        name=range_name,
        description=f"Instance from blueprint (offset {offset})",
        created_by=created_by,
        status=RangeStatus.DRAFT,
    )
    db.add(range_obj)
    db.flush()

    # Create networks with offset
    network_lookup: Dict[str, UUID] = {}
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

    # Create VMs with offset IPs
    for vm_config in config.vms:
        # Find template by name
        template = db.query(VMTemplate).filter(VMTemplate.name == vm_config.template_name).first()
        if not template:
            continue  # Skip VMs with missing templates

        network_id = network_lookup.get(vm_config.network_name)
        if not network_id:
            continue  # Skip VMs with missing networks

        adjusted_ip = apply_subnet_offset(vm_config.ip_address, base_prefix, offset)

        vm = VM(
            range_id=range_obj.id,
            network_id=network_id,
            template_id=template.id,
            hostname=vm_config.hostname,
            ip_address=adjusted_ip,
            cpu=vm_config.cpu,
            ram_mb=vm_config.ram_mb,
            disk_gb=vm_config.disk_gb,
            position_x=vm_config.position_x,
            position_y=vm_config.position_y,
        )
        db.add(vm)

    # Create MSEL if present
    if config.msel and config.msel.content:
        msel = MSEL(
            range_id=range_obj.id,
            content=config.msel.content,
        )
        db.add(msel)

    db.flush()
    return range_obj
```

**Step 2: Commit**

```bash
git add backend/cyroid/services/blueprint_service.py
git commit -m "feat(blueprints): add blueprint service for config extraction and offset calculation"
```

---

## Task 5: Create Blueprints API

**Files:**
- Create: `backend/cyroid/api/blueprints.py`
- Modify: `backend/cyroid/main.py`

**Step 1: Create the blueprints API file**

```python
# backend/cyroid/api/blueprints.py
from typing import List
from uuid import UUID
from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from cyroid.api.deps import DBSession, CurrentUser
from cyroid.models import Range, RangeBlueprint, RangeInstance
from cyroid.schemas.blueprint import (
    BlueprintCreate, BlueprintUpdate, BlueprintResponse, BlueprintDetailResponse,
    InstanceDeploy, InstanceResponse, BlueprintConfig
)
from cyroid.services.blueprint_service import (
    extract_config_from_range, extract_subnet_prefix, create_range_from_blueprint
)
from cyroid.services.docker_service import DockerService

router = APIRouter(prefix="/blueprints", tags=["blueprints"])


@router.post("", response_model=BlueprintDetailResponse, status_code=status.HTTP_201_CREATED)
def create_blueprint(data: BlueprintCreate, db: DBSession, current_user: CurrentUser):
    """Create a new blueprint from an existing range."""
    # Verify range exists
    range_obj = db.query(Range).filter(Range.id == data.range_id).first()
    if not range_obj:
        raise HTTPException(status_code=404, detail="Range not found")

    # Extract config from range
    config = extract_config_from_range(db, data.range_id)

    # Create blueprint
    blueprint = RangeBlueprint(
        name=data.name,
        description=data.description,
        config=config.model_dump(),
        base_subnet_prefix=data.base_subnet_prefix,
        created_by=current_user.id,
        version=1,
        next_offset=0,
    )
    db.add(blueprint)
    db.commit()
    db.refresh(blueprint)

    return _blueprint_to_detail_response(blueprint, config, current_user.username)


@router.get("", response_model=List[BlueprintResponse])
def list_blueprints(db: DBSession, current_user: CurrentUser):
    """List all blueprints."""
    blueprints = db.query(RangeBlueprint).all()
    return [_blueprint_to_response(b, db) for b in blueprints]


@router.get("/{blueprint_id}", response_model=BlueprintDetailResponse)
def get_blueprint(blueprint_id: UUID, db: DBSession, current_user: CurrentUser):
    """Get blueprint details."""
    blueprint = db.query(RangeBlueprint).filter(RangeBlueprint.id == blueprint_id).first()
    if not blueprint:
        raise HTTPException(status_code=404, detail="Blueprint not found")

    config = BlueprintConfig.model_validate(blueprint.config)

    # Get creator username
    from cyroid.models import User
    creator = db.query(User).filter(User.id == blueprint.created_by).first()
    username = creator.username if creator else None

    return _blueprint_to_detail_response(blueprint, config, username)


@router.put("/{blueprint_id}", response_model=BlueprintDetailResponse)
def update_blueprint(
    blueprint_id: UUID, data: BlueprintUpdate, db: DBSession, current_user: CurrentUser
):
    """Update blueprint metadata. Increments version if config changes."""
    blueprint = db.query(RangeBlueprint).filter(RangeBlueprint.id == blueprint_id).first()
    if not blueprint:
        raise HTTPException(status_code=404, detail="Blueprint not found")

    if data.name is not None:
        blueprint.name = data.name
    if data.description is not None:
        blueprint.description = data.description

    db.commit()
    db.refresh(blueprint)

    config = BlueprintConfig.model_validate(blueprint.config)
    return _blueprint_to_detail_response(blueprint, config, current_user.username)


@router.delete("/{blueprint_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_blueprint(blueprint_id: UUID, db: DBSession, current_user: CurrentUser):
    """Delete a blueprint. Fails if instances exist."""
    blueprint = db.query(RangeBlueprint).filter(RangeBlueprint.id == blueprint_id).first()
    if not blueprint:
        raise HTTPException(status_code=404, detail="Blueprint not found")

    # Check for instances
    instance_count = db.query(RangeInstance).filter(
        RangeInstance.blueprint_id == blueprint_id
    ).count()
    if instance_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete blueprint with {instance_count} active instances"
        )

    db.delete(blueprint)
    db.commit()


@router.post("/{blueprint_id}/deploy", response_model=InstanceResponse, status_code=status.HTTP_201_CREATED)
def deploy_instance(
    blueprint_id: UUID, data: InstanceDeploy, db: DBSession, current_user: CurrentUser
):
    """Deploy a new instance from a blueprint."""
    blueprint = db.query(RangeBlueprint).filter(RangeBlueprint.id == blueprint_id).first()
    if not blueprint:
        raise HTTPException(status_code=404, detail="Blueprint not found")

    config = BlueprintConfig.model_validate(blueprint.config)

    # Get next offset and increment
    offset = blueprint.next_offset
    blueprint.next_offset += 1

    # Create range from blueprint with offset
    range_obj = create_range_from_blueprint(
        db=db,
        config=config,
        range_name=data.name,
        base_prefix=blueprint.base_subnet_prefix,
        offset=offset,
        created_by=current_user.id,
    )

    # Create instance record
    instance = RangeInstance(
        name=data.name,
        blueprint_id=blueprint.id,
        blueprint_version=blueprint.version,
        subnet_offset=offset,
        instructor_id=current_user.id,
        range_id=range_obj.id,
    )
    db.add(instance)
    db.commit()
    db.refresh(instance)

    # Auto-deploy if requested
    if data.auto_deploy:
        try:
            docker_service = DockerService()
            docker_service.deploy_range(db, range_obj.id)
        except Exception as e:
            # Don't fail the whole operation, just log
            print(f"Auto-deploy failed: {e}")

    return _instance_to_response(instance, db)


@router.get("/{blueprint_id}/instances", response_model=List[InstanceResponse])
def list_instances(blueprint_id: UUID, db: DBSession, current_user: CurrentUser):
    """List all instances of a blueprint."""
    blueprint = db.query(RangeBlueprint).filter(RangeBlueprint.id == blueprint_id).first()
    if not blueprint:
        raise HTTPException(status_code=404, detail="Blueprint not found")

    instances = db.query(RangeInstance).filter(
        RangeInstance.blueprint_id == blueprint_id
    ).all()

    return [_instance_to_response(i, db) for i in instances]


# ============ Helper Functions ============

def _blueprint_to_response(blueprint: RangeBlueprint, db: Session) -> BlueprintResponse:
    config = blueprint.config
    return BlueprintResponse(
        id=blueprint.id,
        name=blueprint.name,
        description=blueprint.description,
        version=blueprint.version,
        base_subnet_prefix=blueprint.base_subnet_prefix,
        next_offset=blueprint.next_offset,
        created_by=blueprint.created_by,
        created_at=blueprint.created_at,
        updated_at=blueprint.updated_at,
        network_count=len(config.get("networks", [])),
        vm_count=len(config.get("vms", [])),
        instance_count=len(blueprint.instances),
    )


def _blueprint_to_detail_response(
    blueprint: RangeBlueprint, config: BlueprintConfig, username: str = None
) -> BlueprintDetailResponse:
    return BlueprintDetailResponse(
        id=blueprint.id,
        name=blueprint.name,
        description=blueprint.description,
        version=blueprint.version,
        base_subnet_prefix=blueprint.base_subnet_prefix,
        next_offset=blueprint.next_offset,
        created_by=blueprint.created_by,
        created_at=blueprint.created_at,
        updated_at=blueprint.updated_at,
        network_count=len(config.networks),
        vm_count=len(config.vms),
        instance_count=len(blueprint.instances) if hasattr(blueprint, 'instances') else 0,
        config=config,
        created_by_username=username,
    )


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
```

**Step 2: Register router in main.py**

Add to `backend/cyroid/main.py` imports:

```python
from cyroid.api.blueprints import router as blueprints_router
```

Add to router includes (around line 130):

```python
app.include_router(blueprints_router, prefix="/api/v1")
```

**Step 3: Commit**

```bash
git add backend/cyroid/api/blueprints.py backend/cyroid/main.py
git commit -m "feat(blueprints): add blueprints API endpoints"
```

---

## Task 6: Create Instances API

**Files:**
- Create: `backend/cyroid/api/instances.py`
- Modify: `backend/cyroid/main.py`

**Step 1: Create the instances API file**

```python
# backend/cyroid/api/instances.py
from uuid import UUID
from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from cyroid.api.deps import DBSession, CurrentUser
from cyroid.models import Range, RangeBlueprint, RangeInstance
from cyroid.schemas.blueprint import InstanceResponse, BlueprintConfig
from cyroid.services.blueprint_service import create_range_from_blueprint
from cyroid.services.docker_service import DockerService

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

    # Stop and delete current range resources
    docker_service = DockerService()
    try:
        docker_service.stop_range(db, range_obj.id)
        docker_service.cleanup_range(db, range_obj.id)
    except Exception as e:
        print(f"Cleanup warning: {e}")

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

    # Redeploy
    docker_service.deploy_range(db, range_obj.id)

    db.commit()
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

    # Stop and cleanup
    docker_service = DockerService()
    try:
        docker_service.stop_range(db, range_obj.id)
        docker_service.cleanup_range(db, range_obj.id)
    except Exception as e:
        print(f"Cleanup warning: {e}")

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

    # Redeploy
    docker_service.deploy_range(db, range_obj.id)

    db.commit()
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

    # Stop and cleanup range
    docker_service = DockerService()
    try:
        docker_service.stop_range(db, range_obj.id)
        docker_service.cleanup_range(db, range_obj.id)
    except Exception as e:
        print(f"Cleanup warning: {e}")

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
    from cyroid.models import Network, VM, VMTemplate
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
        template = db.query(VMTemplate).filter(VMTemplate.name == vm_config.template_name).first()
        if not template:
            continue

        network_id = network_lookup.get(vm_config.network_name)
        if not network_id:
            continue

        adjusted_ip = apply_subnet_offset(vm_config.ip_address, base_prefix, offset)

        vm = VM(
            range_id=range_obj.id,
            network_id=network_id,
            template_id=template.id,
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
```

**Step 2: Register router in main.py**

Add to `backend/cyroid/main.py` imports:

```python
from cyroid.api.instances import router as instances_router
```

Add to router includes:

```python
app.include_router(instances_router, prefix="/api/v1")
```

**Step 3: Commit**

```bash
git add backend/cyroid/api/instances.py backend/cyroid/main.py
git commit -m "feat(blueprints): add instances API for reset, redeploy, clone, delete"
```

---

## Task 7: Add Frontend API Client

**Files:**
- Modify: `frontend/src/services/api.ts`

**Step 1: Add blueprint types and API methods**

Add to `frontend/src/services/api.ts`:

```typescript
// ============ Blueprint Types ============

export interface NetworkConfig {
  name: string;
  subnet: string;
  gateway: string;
  is_isolated: boolean;
}

export interface VMConfig {
  hostname: string;
  ip_address: string;
  network_name: string;
  template_name: string;
  cpu: number;
  ram_mb: number;
  disk_gb: number;
  position_x?: number;
  position_y?: number;
}

export interface BlueprintConfig {
  networks: NetworkConfig[];
  vms: VMConfig[];
  router?: { enabled: boolean; dhcp_enabled: boolean };
  msel?: { content?: string; format: string };
}

export interface Blueprint {
  id: string;
  name: string;
  description?: string;
  version: number;
  base_subnet_prefix: string;
  next_offset: number;
  created_by: string;
  created_at: string;
  updated_at: string;
  network_count: number;
  vm_count: number;
  instance_count: number;
}

export interface BlueprintDetail extends Blueprint {
  config: BlueprintConfig;
  created_by_username?: string;
}

export interface BlueprintCreate {
  range_id: string;
  name: string;
  description?: string;
  base_subnet_prefix: string;
}

export interface Instance {
  id: string;
  name: string;
  blueprint_id: string;
  blueprint_version: number;
  subnet_offset: number;
  instructor_id: string;
  range_id: string;
  created_at: string;
  range_name?: string;
  range_status?: string;
  instructor_username?: string;
}

export interface InstanceDeploy {
  name: string;
  auto_deploy?: boolean;
}

// ============ Blueprint API ============

export const blueprintsApi = {
  list: () => api.get<Blueprint[]>('/blueprints'),
  get: (id: string) => api.get<BlueprintDetail>(`/blueprints/${id}`),
  create: (data: BlueprintCreate) => api.post<BlueprintDetail>('/blueprints', data),
  update: (id: string, data: { name?: string; description?: string }) =>
    api.put<BlueprintDetail>(`/blueprints/${id}`, data),
  delete: (id: string) => api.delete(`/blueprints/${id}`),
  deploy: (id: string, data: InstanceDeploy) =>
    api.post<Instance>(`/blueprints/${id}/deploy`, data),
  listInstances: (id: string) => api.get<Instance[]>(`/blueprints/${id}/instances`),
};

export const instancesApi = {
  get: (id: string) => api.get<Instance>(`/instances/${id}`),
  reset: (id: string) => api.post<Instance>(`/instances/${id}/reset`),
  redeploy: (id: string) => api.post<Instance>(`/instances/${id}/redeploy`),
  clone: (id: string) => api.post<Instance>(`/instances/${id}/clone`),
  delete: (id: string) => api.delete(`/instances/${id}`),
};
```

**Step 2: Commit**

```bash
git add frontend/src/services/api.ts
git commit -m "feat(blueprints): add frontend API client for blueprints and instances"
```

---

## Task 8: Create Blueprints Page

**Files:**
- Create: `frontend/src/pages/Blueprints.tsx`

**Step 1: Create the Blueprints page**

```typescript
// frontend/src/pages/Blueprints.tsx
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { blueprintsApi, Blueprint, InstanceDeploy } from '../services/api';
import {
  LayoutTemplate,
  Loader2,
  Plus,
  Rocket,
  Trash2,
  Network,
  Server,
  Users,
} from 'lucide-react';
import clsx from 'clsx';
import { ConfirmDialog } from '../components/common/ConfirmDialog';
import { toast } from '../stores/toastStore';
import DeployInstanceModal from '../components/blueprints/DeployInstanceModal';

export default function Blueprints() {
  const [blueprints, setBlueprints] = useState<Blueprint[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleteConfirm, setDeleteConfirm] = useState<{
    blueprint: Blueprint | null;
    isLoading: boolean;
  }>({ blueprint: null, isLoading: false });
  const [deployModal, setDeployModal] = useState<Blueprint | null>(null);

  const fetchBlueprints = async () => {
    try {
      const response = await blueprintsApi.list();
      setBlueprints(response.data);
    } catch (err) {
      console.error('Failed to fetch blueprints:', err);
      toast.error('Failed to load blueprints');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBlueprints();
  }, []);

  const handleDelete = (blueprint: Blueprint) => {
    setDeleteConfirm({ blueprint, isLoading: false });
  };

  const confirmDelete = async () => {
    if (!deleteConfirm.blueprint) return;
    setDeleteConfirm((prev) => ({ ...prev, isLoading: true }));
    try {
      await blueprintsApi.delete(deleteConfirm.blueprint.id);
      setDeleteConfirm({ blueprint: null, isLoading: false });
      fetchBlueprints();
      toast.success('Blueprint deleted');
    } catch (err: any) {
      setDeleteConfirm({ blueprint: null, isLoading: false });
      toast.error(err.response?.data?.detail || 'Failed to delete blueprint');
    }
  };

  const handleDeploy = async (data: InstanceDeploy) => {
    if (!deployModal) return;
    try {
      const response = await blueprintsApi.deploy(deployModal.id, data);
      toast.success(`Instance "${response.data.name}" created`);
      setDeployModal(null);
      fetchBlueprints();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to deploy instance');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    );
  }

  return (
    <div>
      <div className="sm:flex sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Blueprints</h1>
          <p className="mt-2 text-sm text-gray-700">
            Reusable range configurations for deploying multiple isolated instances
          </p>
        </div>
      </div>

      {blueprints.length === 0 ? (
        <div className="mt-8 text-center">
          <LayoutTemplate className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">No blueprints</h3>
          <p className="mt-1 text-sm text-gray-500">
            Create a range first, then save it as a blueprint from the range detail page.
          </p>
        </div>
      ) : (
        <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {blueprints.map((blueprint) => (
            <div
              key={blueprint.id}
              className="bg-white rounded-lg shadow overflow-hidden hover:shadow-md transition-shadow"
            >
              <div className="p-5">
                <div className="flex items-start justify-between">
                  <div className="flex items-center">
                    <div className="flex-shrink-0 bg-indigo-100 rounded-md p-2">
                      <LayoutTemplate className="h-6 w-6 text-indigo-600" />
                    </div>
                    <div className="ml-3">
                      <Link
                        to={`/blueprints/${blueprint.id}`}
                        className="text-sm font-medium text-gray-900 hover:text-indigo-600"
                      >
                        {blueprint.name}
                      </Link>
                      <p className="text-xs text-gray-500">v{blueprint.version}</p>
                    </div>
                  </div>
                </div>

                {blueprint.description && (
                  <p className="mt-3 text-sm text-gray-500 line-clamp-2">
                    {blueprint.description}
                  </p>
                )}

                <div className="mt-4 flex items-center text-xs text-gray-500 space-x-4">
                  <span className="flex items-center">
                    <Network className="h-3.5 w-3.5 mr-1" />
                    {blueprint.network_count} networks
                  </span>
                  <span className="flex items-center">
                    <Server className="h-3.5 w-3.5 mr-1" />
                    {blueprint.vm_count} VMs
                  </span>
                  <span className="flex items-center">
                    <Users className="h-3.5 w-3.5 mr-1" />
                    {blueprint.instance_count} instances
                  </span>
                </div>
              </div>

              <div className="bg-gray-50 px-5 py-3 flex justify-between items-center">
                <span className="text-xs text-gray-500">
                  Subnet: {blueprint.base_subnet_prefix}.x.x
                </span>
                <div className="flex space-x-2">
                  <button
                    onClick={() => setDeployModal(blueprint)}
                    className="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700"
                  >
                    <Rocket className="h-3.5 w-3.5 mr-1" />
                    Deploy
                  </button>
                  <button
                    onClick={() => handleDelete(blueprint)}
                    className="p-1.5 text-gray-400 hover:text-red-600"
                    title="Delete"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Delete Confirmation */}
      <ConfirmDialog
        isOpen={deleteConfirm.blueprint !== null}
        title="Delete Blueprint"
        message={`Are you sure you want to delete "${deleteConfirm.blueprint?.name}"? This cannot be undone.`}
        confirmLabel="Delete"
        variant="danger"
        onConfirm={confirmDelete}
        onCancel={() => setDeleteConfirm({ blueprint: null, isLoading: false })}
        isLoading={deleteConfirm.isLoading}
      />

      {/* Deploy Instance Modal */}
      {deployModal && (
        <DeployInstanceModal
          blueprint={deployModal}
          onClose={() => setDeployModal(null)}
          onDeploy={handleDeploy}
        />
      )}
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/pages/Blueprints.tsx
git commit -m "feat(blueprints): add Blueprints list page"
```

---

## Task 9: Create Blueprint Components

**Files:**
- Create: `frontend/src/components/blueprints/DeployInstanceModal.tsx`
- Create: `frontend/src/components/blueprints/SaveBlueprintModal.tsx`
- Create: `frontend/src/components/blueprints/InstanceInfoBanner.tsx`
- Create: `frontend/src/components/blueprints/index.ts`

**Step 1: Create DeployInstanceModal**

```typescript
// frontend/src/components/blueprints/DeployInstanceModal.tsx
import { useState } from 'react';
import { Blueprint, InstanceDeploy } from '../../services/api';
import { X, Rocket, Loader2 } from 'lucide-react';

interface Props {
  blueprint: Blueprint;
  onClose: () => void;
  onDeploy: (data: InstanceDeploy) => Promise<void>;
}

export default function DeployInstanceModal({ blueprint, onClose, onDeploy }: Props) {
  const [name, setName] = useState('');
  const [autoDeploy, setAutoDeploy] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const nextSubnet = `${blueprint.base_subnet_prefix.split('.')[0]}.${
    parseInt(blueprint.base_subnet_prefix.split('.')[1]) + blueprint.next_offset
  }`;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await onDeploy({ name, auto_deploy: autoDeploy });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4">
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={onClose} />

        <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full">
          <div className="flex items-center justify-between p-4 border-b">
            <div>
              <h3 className="text-lg font-medium text-gray-900">Deploy Instance</h3>
              <p className="text-sm text-gray-500">
                {blueprint.name} v{blueprint.version}
              </p>
            </div>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-500">
              <X className="h-5 w-5" />
            </button>
          </div>

          <form onSubmit={handleSubmit} className="p-4 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Instance Name
              </label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                placeholder="e.g., Texas Morning Class"
              />
            </div>

            <div className="flex items-center">
              <input
                type="checkbox"
                id="autoDeploy"
                checked={autoDeploy}
                onChange={(e) => setAutoDeploy(e.target.checked)}
                className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
              />
              <label htmlFor="autoDeploy" className="ml-2 block text-sm text-gray-700">
                Auto-deploy after creation
              </label>
            </div>

            <div className="bg-gray-50 rounded-md p-3">
              <p className="text-sm text-gray-600">
                <span className="font-medium">Subnet:</span> {nextSubnet}.x.x (auto-assigned)
              </p>
            </div>

            <div className="flex justify-end space-x-3 pt-4">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting || !name}
                className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50"
              >
                {submitting ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Rocket className="h-4 w-4 mr-2" />
                )}
                Deploy Instance
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
```

**Step 2: Create SaveBlueprintModal**

```typescript
// frontend/src/components/blueprints/SaveBlueprintModal.tsx
import { useState } from 'react';
import { blueprintsApi, BlueprintCreate } from '../../services/api';
import { X, LayoutTemplate, Loader2 } from 'lucide-react';
import { toast } from '../../stores/toastStore';

interface Props {
  rangeId: string;
  rangeName: string;
  suggestedPrefix: string;
  onClose: () => void;
  onSuccess: () => void;
}

export default function SaveBlueprintModal({
  rangeId,
  rangeName,
  suggestedPrefix,
  onClose,
  onSuccess,
}: Props) {
  const [name, setName] = useState(rangeName);
  const [description, setDescription] = useState('');
  const [baseSubnetPrefix, setBaseSubnetPrefix] = useState(suggestedPrefix);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);

    try {
      const data: BlueprintCreate = {
        range_id: rangeId,
        name,
        description: description || undefined,
        base_subnet_prefix: baseSubnetPrefix,
      };
      await blueprintsApi.create(data);
      toast.success('Blueprint created successfully');
      onSuccess();
      onClose();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to create blueprint');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4">
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={onClose} />

        <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full">
          <div className="flex items-center justify-between p-4 border-b">
            <h3 className="text-lg font-medium text-gray-900">Save as Blueprint</h3>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-500">
              <X className="h-5 w-5" />
            </button>
          </div>

          <form onSubmit={handleSubmit} className="p-4 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Blueprint Name
              </label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                placeholder="e.g., Red Team Training Lab"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">
                Description
              </label>
              <textarea
                rows={2}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                placeholder="Optional description..."
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">
                Base Subnet Prefix
              </label>
              <input
                type="text"
                required
                pattern="\d{1,3}\.\d{1,3}"
                value={baseSubnetPrefix}
                onChange={(e) => setBaseSubnetPrefix(e.target.value)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                placeholder="e.g., 10.100"
              />
              <p className="mt-1 text-xs text-gray-500">
                Each instance will get an incremented second octet (10.100 → 10.101 → 10.102)
              </p>
            </div>

            <div className="flex justify-end space-x-3 pt-4">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting || !name || !baseSubnetPrefix}
                className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50"
              >
                {submitting ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <LayoutTemplate className="h-4 w-4 mr-2" />
                )}
                Save Blueprint
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
```

**Step 3: Create InstanceInfoBanner**

```typescript
// frontend/src/components/blueprints/InstanceInfoBanner.tsx
import { Link } from 'react-router-dom';
import { Instance, Blueprint } from '../../services/api';
import { Info, ExternalLink, RefreshCw } from 'lucide-react';

interface Props {
  instance: Instance;
  blueprint: Blueprint;
  onRedeploy?: () => void;
}

export default function InstanceInfoBanner({ instance, blueprint, onRedeploy }: Props) {
  const isOutdated = instance.blueprint_version < blueprint.version;

  return (
    <div className="bg-blue-50 border border-blue-200 rounded-md p-4 mb-6">
      <div className="flex items-start">
        <Info className="h-5 w-5 text-blue-500 mt-0.5" />
        <div className="ml-3 flex-1">
          <p className="text-sm text-blue-700">
            This range is an instance of{' '}
            <Link
              to={`/blueprints/${blueprint.id}`}
              className="font-medium underline hover:text-blue-800"
            >
              {blueprint.name}
            </Link>{' '}
            (v{instance.blueprint_version})
            {isOutdated && (
              <span className="ml-2 text-amber-600">
                — Latest is v{blueprint.version}
              </span>
            )}
          </p>
          <div className="mt-2 flex space-x-3">
            <Link
              to={`/blueprints/${blueprint.id}`}
              className="inline-flex items-center text-sm text-blue-600 hover:text-blue-800"
            >
              <ExternalLink className="h-3.5 w-3.5 mr-1" />
              View Blueprint
            </Link>
            {isOutdated && onRedeploy && (
              <button
                onClick={onRedeploy}
                className="inline-flex items-center text-sm text-amber-600 hover:text-amber-800"
              >
                <RefreshCw className="h-3.5 w-3.5 mr-1" />
                Redeploy from v{blueprint.version}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
```

**Step 4: Create index.ts**

```typescript
// frontend/src/components/blueprints/index.ts
export { default as DeployInstanceModal } from './DeployInstanceModal';
export { default as SaveBlueprintModal } from './SaveBlueprintModal';
export { default as InstanceInfoBanner } from './InstanceInfoBanner';
```

**Step 5: Commit**

```bash
git add frontend/src/components/blueprints/
git commit -m "feat(blueprints): add blueprint UI components"
```

---

## Task 10: Create BlueprintDetail Page

**Files:**
- Create: `frontend/src/pages/BlueprintDetail.tsx`

**Step 1: Create BlueprintDetail page**

```typescript
// frontend/src/pages/BlueprintDetail.tsx
import { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  blueprintsApi,
  instancesApi,
  BlueprintDetail as BlueprintDetailType,
  Instance,
  InstanceDeploy,
} from '../services/api';
import {
  LayoutTemplate,
  Loader2,
  ArrowLeft,
  Rocket,
  Network,
  Server,
  Play,
  Square,
  RefreshCw,
  Copy,
  Trash2,
  ExternalLink,
} from 'lucide-react';
import clsx from 'clsx';
import { toast } from '../stores/toastStore';
import { ConfirmDialog } from '../components/common/ConfirmDialog';
import { DeployInstanceModal } from '../components/blueprints';

const statusColors: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-800',
  deploying: 'bg-yellow-100 text-yellow-800',
  running: 'bg-green-100 text-green-800',
  stopped: 'bg-gray-100 text-gray-800',
  error: 'bg-red-100 text-red-800',
};

export default function BlueprintDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [blueprint, setBlueprint] = useState<BlueprintDetailType | null>(null);
  const [instances, setInstances] = useState<Instance[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'instances'>('overview');
  const [showDeployModal, setShowDeployModal] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<{
    instance: Instance | null;
    isLoading: boolean;
  }>({ instance: null, isLoading: false });

  const fetchData = async () => {
    if (!id) return;
    try {
      const [bpRes, instRes] = await Promise.all([
        blueprintsApi.get(id),
        blueprintsApi.listInstances(id),
      ]);
      setBlueprint(bpRes.data);
      setInstances(instRes.data);
    } catch (err) {
      console.error('Failed to fetch blueprint:', err);
      toast.error('Failed to load blueprint');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [id]);

  const handleDeploy = async (data: InstanceDeploy) => {
    if (!id) return;
    try {
      await blueprintsApi.deploy(id, data);
      toast.success('Instance deployed');
      setShowDeployModal(false);
      fetchData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to deploy');
    }
  };

  const handleClone = async (instance: Instance) => {
    try {
      await instancesApi.clone(instance.id);
      toast.success('Instance cloned');
      fetchData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to clone');
    }
  };

  const handleDelete = async () => {
    if (!deleteConfirm.instance) return;
    setDeleteConfirm((prev) => ({ ...prev, isLoading: true }));
    try {
      await instancesApi.delete(deleteConfirm.instance.id);
      toast.success('Instance deleted');
      setDeleteConfirm({ instance: null, isLoading: false });
      fetchData();
    } catch (err: any) {
      setDeleteConfirm({ instance: null, isLoading: false });
      toast.error(err.response?.data?.detail || 'Failed to delete');
    }
  };

  if (loading || !blueprint) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <Link
          to="/blueprints"
          className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700 mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back to Blueprints
        </Link>
        <div className="flex items-center justify-between">
          <div className="flex items-center">
            <div className="bg-indigo-100 rounded-md p-3">
              <LayoutTemplate className="h-8 w-8 text-indigo-600" />
            </div>
            <div className="ml-4">
              <h1 className="text-2xl font-bold text-gray-900">{blueprint.name}</h1>
              <p className="text-sm text-gray-500">
                Version {blueprint.version} · Created by {blueprint.created_by_username}
              </p>
            </div>
          </div>
          <button
            onClick={() => setShowDeployModal(true)}
            className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700"
          >
            <Rocket className="h-4 w-4 mr-2" />
            Deploy Instance
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('overview')}
            className={clsx(
              'py-4 px-1 border-b-2 font-medium text-sm',
              activeTab === 'overview'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            )}
          >
            Overview
          </button>
          <button
            onClick={() => setActiveTab('instances')}
            className={clsx(
              'py-4 px-1 border-b-2 font-medium text-sm',
              activeTab === 'instances'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            )}
          >
            Instances ({instances.length})
          </button>
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' ? (
        <div className="bg-white shadow rounded-lg p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Configuration</h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Networks */}
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center">
                <Network className="h-4 w-4 mr-2" />
                Networks ({blueprint.config.networks.length})
              </h4>
              <ul className="space-y-2">
                {blueprint.config.networks.map((net, i) => (
                  <li key={i} className="bg-gray-50 rounded p-2 text-sm">
                    <span className="font-medium">{net.name}</span>
                    <span className="text-gray-500 ml-2">{net.subnet}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* VMs */}
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center">
                <Server className="h-4 w-4 mr-2" />
                VMs ({blueprint.config.vms.length})
              </h4>
              <ul className="space-y-2">
                {blueprint.config.vms.map((vm, i) => (
                  <li key={i} className="bg-gray-50 rounded p-2 text-sm">
                    <span className="font-medium">{vm.hostname}</span>
                    <span className="text-gray-500 ml-2">{vm.ip_address}</span>
                    <span className="text-gray-400 ml-2">({vm.template_name})</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-white shadow rounded-lg overflow-hidden">
          {instances.length === 0 ? (
            <div className="p-8 text-center">
              <Rocket className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-2 text-sm font-medium text-gray-900">No instances</h3>
              <p className="mt-1 text-sm text-gray-500">
                Deploy your first instance from this blueprint.
              </p>
              <button
                onClick={() => setShowDeployModal(true)}
                className="mt-4 inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700"
              >
                <Rocket className="h-4 w-4 mr-2" />
                Deploy Instance
              </button>
            </div>
          ) : (
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Instance
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Subnet
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Instructor
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {instances.map((instance) => (
                  <tr key={instance.id}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">
                        {instance.name}
                      </div>
                      <div className="text-xs text-gray-500">
                        v{instance.blueprint_version}
                        {instance.blueprint_version < blueprint.version && (
                          <span className="ml-1 text-amber-500">(outdated)</span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {blueprint.base_subnet_prefix.split('.')[0]}.
                      {parseInt(blueprint.base_subnet_prefix.split('.')[1]) +
                        instance.subnet_offset}
                      .x.x
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={clsx(
                          'px-2 py-1 text-xs font-medium rounded-full',
                          statusColors[instance.range_status || 'draft']
                        )}
                      >
                        {instance.range_status || 'unknown'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {instance.instructor_username}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-2">
                      <Link
                        to={`/ranges/${instance.range_id}`}
                        className="text-indigo-600 hover:text-indigo-900"
                        title="Open Range"
                      >
                        <ExternalLink className="h-4 w-4 inline" />
                      </Link>
                      <button
                        onClick={() => handleClone(instance)}
                        className="text-gray-400 hover:text-gray-600"
                        title="Clone"
                      >
                        <Copy className="h-4 w-4 inline" />
                      </button>
                      <button
                        onClick={() =>
                          setDeleteConfirm({ instance, isLoading: false })
                        }
                        className="text-gray-400 hover:text-red-600"
                        title="Delete"
                      >
                        <Trash2 className="h-4 w-4 inline" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Deploy Modal */}
      {showDeployModal && (
        <DeployInstanceModal
          blueprint={blueprint}
          onClose={() => setShowDeployModal(false)}
          onDeploy={handleDeploy}
        />
      )}

      {/* Delete Confirmation */}
      <ConfirmDialog
        isOpen={deleteConfirm.instance !== null}
        title="Delete Instance"
        message={`Are you sure you want to delete "${deleteConfirm.instance?.name}"? This will delete the range and all its VMs. This cannot be undone.`}
        confirmLabel="Delete"
        variant="danger"
        onConfirm={handleDelete}
        onCancel={() => setDeleteConfirm({ instance: null, isLoading: false })}
        isLoading={deleteConfirm.isLoading}
      />
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/pages/BlueprintDetail.tsx
git commit -m "feat(blueprints): add BlueprintDetail page with instances tab"
```

---

## Task 11: Add Routes and Navigation

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/layout/Layout.tsx`

**Step 1: Add routes to App.tsx**

Add import:
```typescript
import Blueprints from './pages/Blueprints'
import BlueprintDetail from './pages/BlueprintDetail'
```

Add routes inside the Layout Routes (after /ranges/:id):
```typescript
<Route path="/blueprints" element={<Blueprints />} />
<Route path="/blueprints/:id" element={<BlueprintDetail />} />
```

**Step 2: Add navigation to Layout.tsx**

Add import:
```typescript
import { LayoutTemplate } from 'lucide-react'
```

Update navigation array (add after Templates):
```typescript
{ name: 'Blueprints', href: '/blueprints', icon: LayoutTemplate },
```

**Step 3: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/layout/Layout.tsx
git commit -m "feat(blueprints): add routes and navigation for blueprints"
```

---

## Task 12: Add Save as Blueprint to RangeDetail

**Files:**
- Modify: `frontend/src/pages/RangeDetail.tsx`

**Step 1: Add SaveBlueprintModal integration**

Add import:
```typescript
import { SaveBlueprintModal } from '../components/blueprints'
```

Add state:
```typescript
const [showSaveBlueprintModal, setShowSaveBlueprintModal] = useState(false)
```

Add helper to extract subnet prefix from first network:
```typescript
const suggestedPrefix = range?.networks?.[0]?.subnet
  ? range.networks[0].subnet.split('.').slice(0, 2).join('.')
  : '10.100';
```

Add button to header actions (before or after existing buttons):
```typescript
<button
  onClick={() => setShowSaveBlueprintModal(true)}
  className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
>
  <LayoutTemplate className="h-4 w-4 mr-2" />
  Save as Blueprint
</button>
```

Add modal at end of component:
```typescript
{showSaveBlueprintModal && range && (
  <SaveBlueprintModal
    rangeId={range.id}
    rangeName={range.name}
    suggestedPrefix={suggestedPrefix}
    onClose={() => setShowSaveBlueprintModal(false)}
    onSuccess={() => {}}
  />
)}
```

**Step 2: Commit**

```bash
git add frontend/src/pages/RangeDetail.tsx
git commit -m "feat(blueprints): add Save as Blueprint button to RangeDetail"
```

---

## Task 13: Final Testing and Version Bump

**Files:**
- Modify: `backend/cyroid/config.py`
- Modify: `CHANGELOG.md`

**Step 1: Update version to 0.6.0**

In `backend/cyroid/config.py`:
```python
app_version: str = "0.6.0"
```

**Step 2: Update CHANGELOG.md**

Add at top after header:
```markdown
## [0.6.0] - 2026-01-17

### Added

- **Range Blueprints** ([#18](../../issues/18)): Save ranges as reusable blueprints and deploy multiple isolated instances with auto-allocated subnets.
  - Save any range as a blueprint with "Save as Blueprint" button
  - Deploy instances from blueprints with automatic subnet offset (10.100 → 10.101 → 10.102)
  - Instance actions: reset (same version), redeploy (latest version), clone
  - Blueprints page with card grid showing all blueprints
  - Blueprint detail page with instances tab
  - Instance info banner on RangeDetail for blueprint-deployed ranges
  - New API endpoints: /blueprints, /instances
  - RangeBlueprint and RangeInstance database models
```

**Step 3: Commit and tag**

```bash
git add backend/cyroid/config.py CHANGELOG.md
git commit -m "chore: release v0.6.0 - Range Blueprints"
git tag -a v0.6.0 -m "v0.6.0 - Range Blueprints"
```

**Step 4: Push**

```bash
git push origin master
git push origin v0.6.0
```

**Step 5: Create GitHub release**

```bash
gh release create v0.6.0 --title "v0.6.0 - Range Blueprints" --notes "..."
```

**Step 6: Close issue**

```bash
gh issue close 18 --comment "Implemented in v0.6.0"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Create database models | blueprint.py, __init__.py |
| 2 | Create migration | alembic |
| 3 | Create Pydantic schemas | blueprint.py, __init__.py |
| 4 | Create blueprint service | blueprint_service.py |
| 5 | Create blueprints API | blueprints.py, main.py |
| 6 | Create instances API | instances.py, main.py |
| 7 | Add frontend API client | api.ts |
| 8 | Create Blueprints page | Blueprints.tsx |
| 9 | Create blueprint components | blueprints/*.tsx |
| 10 | Create BlueprintDetail page | BlueprintDetail.tsx |
| 11 | Add routes and navigation | App.tsx, Layout.tsx |
| 12 | Add Save as Blueprint | RangeDetail.tsx |
| 13 | Version bump and release | config.py, CHANGELOG.md |
