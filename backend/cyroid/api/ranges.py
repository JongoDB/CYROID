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
from cyroid.services.event_service import EventService
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


def get_vyos_service():
    """Lazy import for VyOS service."""
    from cyroid.services.vyos_service import VyOSService
    return VyOSService()


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

    # Initialize event service for progress logging
    event_service = EventService(db)
    networks = db.query(Network).filter(Network.range_id == range_id).all()
    vms = db.query(VM).filter(VM.range_id == range_id).all()

    # Log deployment start
    event_service.log_event(
        range_id=range_id,
        event_type=EventType.DEPLOYMENT_STARTED,
        message=f"Starting deployment of range '{range_obj.name}'",
        extra_data=json.dumps({
            "total_networks": len(networks),
            "total_vms": len(vms),
        })
    )

    try:
        docker = get_docker_service()
        vyos = get_vyos_service()

        # Step 0: Create VyOS router for this range
        range_router = db.query(RangeRouter).filter(RangeRouter.range_id == range_id).first()
        if not range_router:
            # Create router record
            management_ip = vyos.allocate_management_ip()
            range_router = RangeRouter(
                range_id=range_id,
                management_ip=management_ip,
                status=RouterStatus.CREATING
            )
            db.add(range_router)
            db.commit()

        # Create and start the router container if needed
        if not range_router.container_id:
            try:
                range_router.status = RouterStatus.CREATING
                db.commit()

                event_service.log_event(
                    range_id=range_id,
                    event_type=EventType.ROUTER_CREATING,
                    message=f"Creating VyOS router (management IP: {range_router.management_ip})"
                )

                container_id = vyos.create_router_container(
                    range_id=str(range_id),
                    management_ip=range_router.management_ip
                )
                range_router.container_id = container_id
                vyos.start_router(container_id)

                # Wait for router to be ready
                import time
                time.sleep(3)  # VyOS needs time to initialize

                range_router.status = RouterStatus.RUNNING
                db.commit()

                event_service.log_event(
                    range_id=range_id,
                    event_type=EventType.ROUTER_CREATED,
                    message="VyOS router created and running"
                )
                logger.info(f"VyOS router created for range {range_id}")
            except Exception as e:
                logger.error(f"Failed to create VyOS router: {e}")
                range_router.status = RouterStatus.ERROR
                range_router.error_message = str(e)[:500]
                db.commit()
                raise

        # Step 1: Provision all networks
        event_service.log_event(
            range_id=range_id,
            event_type=EventType.DEPLOYMENT_STEP,
            message=f"Provisioning {len(networks)} network(s)"
        )
        interface_num = 1  # eth0 is management, start from eth1
        for idx, network in enumerate(networks):
            if not network.docker_network_id:
                event_service.log_event(
                    range_id=range_id,
                    event_type=EventType.NETWORK_CREATING,
                    message=f"Creating network '{network.name}' ({idx + 1}/{len(networks)})",
                    extra_data=json.dumps({"subnet": network.subnet, "gateway": network.gateway})
                )
                docker_network_id = docker.create_network(
                    name=f"cyroid-{network.name}-{str(network.id)[:8]}",
                    subnet=network.subnet,
                    gateway=network.gateway,
                    internal=network.is_isolated,
                    labels={
                        "cyroid.range_id": str(range_id),
                        "cyroid.network_id": str(network.id),
                    }
                )
                network.docker_network_id = docker_network_id

                # Connect traefik to this network for VNC/web console routing
                docker.connect_traefik_to_network(docker_network_id)

                # Apply iptables isolation if network is isolated
                if network.is_isolated:
                    docker.setup_network_isolation(docker_network_id, network.subnet)

                db.commit()

                event_service.log_event(
                    range_id=range_id,
                    event_type=EventType.NETWORK_CREATED,
                    message=f"Network '{network.name}' created ({network.subnet})"
                )

            # Connect VyOS router to this network as the gateway
            if range_router.container_id and range_router.status == RouterStatus.RUNNING:
                try:
                    import ipaddress
                    interface_name = f"eth{interface_num}"
                    network.vyos_interface = interface_name

                    # VyOS gets the gateway IP (.1) - Docker bridge no longer claims it
                    vyos_ip = network.gateway
                    subnet_obj = ipaddress.ip_network(network.subnet, strict=False)

                    # Connect router to network with gateway IP
                    vyos.connect_to_network(
                        container_id=range_router.container_id,
                        network_id=network.docker_network_id,
                        interface_ip=vyos_ip
                    )

                    # Configure interface in VyOS (need CIDR notation)
                    ip_with_cidr = f"{vyos_ip}/{subnet_obj.prefixlen}"
                    vyos.configure_interface(
                        container_id=range_router.container_id,
                        interface=interface_name,
                        ip_address=ip_with_cidr,
                        description=network.name
                    )

                    # Configure NAT if internet is enabled
                    if network.internet_enabled:
                        vyos.configure_nat_outbound(
                            container_id=range_router.container_id,
                            rule_number=interface_num * 10,
                            source_network=network.subnet
                        )

                    interface_num += 1
                    db.commit()
                    logger.info(f"Connected VyOS router as gateway for {network.name} at {vyos_ip}")
                except Exception as e:
                    logger.warning(f"Failed to connect VyOS to network {network.name}: {e}")

        # Step 2: Create and start all VMs
        event_service.log_event(
            range_id=range_id,
            event_type=EventType.DEPLOYMENT_STEP,
            message=f"Starting {len(vms)} VM(s)"
        )
        for vm_idx, vm in enumerate(vms):
            if vm.container_id:
                # Container exists, just start it
                event_service.log_event(
                    range_id=range_id,
                    event_type=EventType.VM_CREATING,
                    message=f"Starting existing VM '{vm.hostname}' ({vm_idx + 1}/{len(vms)})",
                    vm_id=vm.id
                )
                docker.start_container(vm.container_id)
            else:
                # Create new container
                network = db.query(Network).filter(Network.id == vm.network_id).first()
                template = db.query(VMTemplate).filter(VMTemplate.id == vm.template_id).first()

                if not network or not network.docker_network_id:
                    logger.warning(f"Skipping VM {vm.id}: network not provisioned")
                    continue

                # Determine VM type for logging
                vm_type = "container"
                if template.os_type == OSType.WINDOWS:
                    vm_type = "Windows VM"
                elif template.os_type == OSType.CUSTOM or (template.base_image and template.base_image.startswith("iso:")):
                    vm_type = "Linux VM (QEMU)"

                event_service.log_event(
                    range_id=range_id,
                    event_type=EventType.VM_CREATING,
                    message=f"Creating {vm_type} '{vm.hostname}' ({vm_idx + 1}/{len(vms)})",
                    vm_id=vm.id,
                    extra_data=json.dumps({
                        "image": template.base_image,
                        "ip_address": vm.ip_address,
                        "cpu": vm.cpu,
                        "ram_mb": vm.ram_mb
                    })
                )

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
                        gateway=network.gateway,
                        dns_servers=network.dns_servers,
                        dns_search=network.dns_search,
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
                        gateway=network.gateway,
                        dns_servers=network.dns_servers,
                        dns_search=network.dns_search,
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
                        gateway=network.gateway,
                        dns_servers=network.dns_servers,
                        dns_search=network.dns_search,
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
                        dns_servers=network.dns_servers,
                        dns_search=network.dns_search,
                    )

                vm.container_id = container_id
                docker.start_container(container_id)

                # Configure default route for Docker containers (VyOS is the gateway)
                # Windows/Linux VMs (QEMU-based) handle their own routing internally
                base_image = template.base_image or ""
                is_docker_container = (
                    template.os_type != OSType.WINDOWS and
                    template.os_type != OSType.CUSTOM and
                    not base_image.startswith("iso:")
                )
                if is_docker_container and network.gateway:
                    try:
                        # Give container a moment to initialize networking
                        import time
                        time.sleep(1)
                        docker.configure_default_route(container_id, network.gateway)
                    except Exception as e:
                        logger.warning(f"Failed to configure default route for VM {vm.id}: {e}")

                # Configure Linux user for KasmVNC containers
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

            event_service.log_event(
                range_id=range_id,
                event_type=EventType.VM_STARTED,
                message=f"VM '{vm.hostname}' is now running",
                vm_id=vm.id
            )

        range_obj.status = RangeStatus.RUNNING
        db.commit()

        # Log deployment completion
        event_service.log_event(
            range_id=range_id,
            event_type=EventType.DEPLOYMENT_COMPLETED,
            message=f"Range '{range_obj.name}' deployed successfully",
            extra_data=json.dumps({
                "networks_deployed": len(networks),
                "vms_deployed": len(vms)
            })
        )
        db.refresh(range_obj)

    except Exception as e:
        logger.error(f"Failed to deploy range {range_id}: {e}")
        range_obj.status = RangeStatus.ERROR
        range_obj.error_message = str(e)[:1000]
        db.commit()

        # Log deployment failure
        event_service.log_event(
            range_id=range_id,
            event_type=EventType.DEPLOYMENT_FAILED,
            message=f"Deployment failed: {str(e)[:200]}",
            extra_data=json.dumps({"error": str(e)})
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deploy range: {str(e)}",
        )

    return range_obj


@router.post("/{range_id}/start", response_model=RangeResponse)
def start_range(range_id: UUID, db: DBSession, current_user: CurrentUser):
    """Start all VMs and router in a stopped range."""
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
    """Stop all VMs and router in a running range.

    This stops all containers but preserves networks for quick restart.
    Use teardown to fully clean up resources.
    """
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
