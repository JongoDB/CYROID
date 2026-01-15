# backend/cyroid/api/ranges.py
from typing import List
from uuid import UUID
import logging
import os

from fastapi import APIRouter, HTTPException, status

from cyroid.config import get_settings

from cyroid.api.deps import DBSession, CurrentUser, filter_by_visibility, check_resource_access
from cyroid.models.range import Range, RangeStatus
from cyroid.models.network import Network, IsolationLevel
from cyroid.models.vm import VM, VMStatus
from cyroid.models.template import VMTemplate, OSType
from cyroid.models.resource_tag import ResourceTag
from cyroid.schemas.range import (
    RangeCreate, RangeUpdate, RangeResponse, RangeDetailResponse,
    RangeTemplateExport, RangeTemplateImport, NetworkTemplateData, VMTemplateData
)
from sqlalchemy.orm import joinedload
from cyroid.schemas.user import ResourceTagCreate, ResourceTagsResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ranges", tags=["Ranges"])


def get_docker_service():
    """Lazy import to avoid Docker connection issues during testing."""
    from cyroid.services.docker_service import get_docker_service as _get_docker_service
    return _get_docker_service()


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

                vm_id_short = str(vm.id)[:8]
                labels = {
                    "cyroid.range_id": str(range_id),
                    "cyroid.vm_id": str(vm.id),
                    "cyroid.hostname": vm.hostname,
                }

                # Add traefik labels for VNC web console routing
                display_type = vm.display_type or "desktop"
                if display_type == "desktop":
                    base_image = template.base_image or ""
                    is_linuxserver = "linuxserver/" in base_image or "lscr.io/linuxserver" in base_image
                    is_kasmweb = "kasmweb/" in base_image

                    if base_image.startswith("iso:") or template.os_type == OSType.WINDOWS or template.os_type == OSType.CUSTOM:
                        vnc_port = "8006"
                        vnc_scheme = "http"
                        needs_auth = False
                    elif is_linuxserver:
                        vnc_port = "3000"
                        vnc_scheme = "http"
                        needs_auth = False
                    elif is_kasmweb:
                        vnc_port = "6901"
                        vnc_scheme = "https"
                        needs_auth = True
                    else:
                        vnc_port = "6901"
                        vnc_scheme = "https"
                        needs_auth = False

                    router_name = f"vnc-{vm_id_short}"
                    middlewares = [f"vnc-strip-{vm_id_short}"]

                    # Use range network for routing (traefik connects to range networks, not VMs to traefik-routing)
                    range_network_name = f"cyroid-{network.name}-{str(network.id)[:8]}"

                    labels.update({
                        "traefik.enable": "true",
                        "traefik.docker.network": range_network_name,  # Use range network for routing
                        f"traefik.http.services.{router_name}.loadbalancer.server.port": vnc_port,
                        f"traefik.http.services.{router_name}.loadbalancer.server.scheme": vnc_scheme,
                        f"traefik.http.routers.{router_name}.rule": f"PathPrefix(`/vnc/{vm.id}`)",
                        f"traefik.http.routers.{router_name}.entrypoints": "web",
                        f"traefik.http.routers.{router_name}.service": router_name,
                        f"traefik.http.routers.{router_name}.priority": "100",
                        f"traefik.http.routers.{router_name}-secure.rule": f"PathPrefix(`/vnc/{vm.id}`)",
                        f"traefik.http.routers.{router_name}-secure.entrypoints": "websecure",
                        f"traefik.http.routers.{router_name}-secure.tls": "true",
                        f"traefik.http.routers.{router_name}-secure.service": router_name,
                        f"traefik.http.routers.{router_name}-secure.priority": "100",
                        f"traefik.http.middlewares.vnc-strip-{vm_id_short}.stripprefix.prefixes": f"/vnc/{vm.id}",
                    })

                    if vnc_scheme == "https":
                        labels[f"traefik.http.services.{router_name}.loadbalancer.serversTransport"] = "insecure-transport@file"

                    if needs_auth:
                        import base64
                        # Use hardcoded VNC credentials for seamless console auto-login
                        auth_string = base64.b64encode(b"kasm_user:vncpassword").decode()
                        auth_middleware = f"vnc-auth-{vm_id_short}"
                        labels[f"traefik.http.middlewares.{auth_middleware}.headers.customrequestheaders.Authorization"] = f"Basic {auth_string}"
                        middlewares.append(auth_middleware)

                    labels[f"traefik.http.routers.{router_name}.middlewares"] = ",".join(middlewares)
                    labels[f"traefik.http.routers.{router_name}-secure.middlewares"] = ",".join(middlewares)

                if template.os_type == OSType.WINDOWS:
                    settings = get_settings()
                    vm_storage_path = os.path.join(
                        settings.vm_storage_dir,
                        str(vm.range_id),
                        str(vm.id),
                        "storage"
                    )
                    windows_version = vm.windows_version or template.os_variant or "11"
                    iso_path = vm.iso_path or (template.cached_iso_path if hasattr(template, 'cached_iso_path') and template.cached_iso_path else None)

                    container_id = docker.create_windows_container(
                        name=f"cyroid-{vm.hostname}-{str(vm.id)[:8]}",
                        network_id=network.docker_network_id,
                        ip_address=vm.ip_address,
                        cpu_limit=vm.cpu,
                        memory_limit_mb=vm.ram_mb,
                        disk_size_gb=vm.disk_gb,
                        windows_version=windows_version,
                        labels=labels,
                        iso_path=iso_path,
                        storage_path=vm_storage_path,
                        display_type=vm.display_type or "desktop",
                    )
                elif template.os_type == OSType.CUSTOM:
                    # Custom ISO VMs use qemux/qemu
                    settings = get_settings()
                    vm_storage_path = os.path.join(
                        settings.vm_storage_dir,
                        str(vm.range_id),
                        str(vm.id),
                        "storage"
                    )
                    iso_path = template.cached_iso_path if hasattr(template, 'cached_iso_path') and template.cached_iso_path else None

                    container_id = docker.create_linux_vm_container(
                        name=f"cyroid-{vm.hostname}-{str(vm.id)[:8]}",
                        network_id=network.docker_network_id,
                        ip_address=vm.ip_address,
                        cpu_limit=vm.cpu,
                        memory_limit_mb=vm.ram_mb,
                        disk_size_gb=vm.disk_gb,
                        linux_distro="custom",
                        labels=labels,
                        iso_path=iso_path,
                        storage_path=vm_storage_path,
                        display_type=vm.display_type or "desktop",
                    )
                elif template.base_image.startswith("iso:"):
                    # Linux ISO VMs use qemux/qemu
                    settings = get_settings()
                    vm_storage_path = os.path.join(
                        settings.vm_storage_dir,
                        str(vm.range_id),
                        str(vm.id),
                        "storage"
                    )
                    linux_distro = template.base_image.replace("iso:", "")

                    container_id = docker.create_linux_vm_container(
                        name=f"cyroid-{vm.hostname}-{str(vm.id)[:8]}",
                        network_id=network.docker_network_id,
                        ip_address=vm.ip_address,
                        cpu_limit=vm.cpu,
                        memory_limit_mb=vm.ram_mb,
                        disk_size_gb=vm.disk_gb,
                        linux_distro=linux_distro,
                        labels=labels,
                        storage_path=vm_storage_path,
                        display_type=vm.display_type or "desktop",
                    )
                else:
                    # Docker container
                    container_id = docker.create_container(
                        name=f"cyroid-{vm.hostname}-{str(vm.id)[:8]}",
                        image=template.base_image,
                        network_id=network.docker_network_id,
                        ip_address=vm.ip_address,
                        cpu_limit=vm.cpu,
                        memory_limit_mb=vm.ram_mb,
                        hostname=vm.hostname,
                        labels=labels,
                        linux_username=vm.linux_username,
                        linux_password=vm.linux_password,
                        linux_user_sudo=vm.linux_user_sudo,
                    )

                vm.container_id = container_id
                docker.start_container(container_id)

                # Configure Linux user for KasmVNC containers
                base_image = template.base_image or ""
                if "kasmweb/" in base_image:
                    # KasmVNC uses 'kasm-user' as the default user
                    username = vm.linux_username or "kasm-user"
                    if vm.linux_password:
                        docker.set_linux_user_password(container_id, username, vm.linux_password)
                    if vm.linux_user_sudo:
                        docker.grant_sudo_privileges(container_id, username)

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
            isolation_level=n.isolation_level.value,
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
            isolation_level=IsolationLevel(net_data.isolation_level),
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
            isolation_level=network.isolation_level,
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
