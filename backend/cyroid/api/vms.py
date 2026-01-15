# backend/cyroid/api/vms.py
from typing import List
from uuid import UUID
import logging

from fastapi import APIRouter, HTTPException, status, Request

from cyroid.api.deps import DBSession, CurrentUser
from cyroid.models.vm import VM, VMStatus
from cyroid.models.range import Range, RangeStatus
from cyroid.models.network import Network
from cyroid.models.template import VMTemplate, OSType
from cyroid.models.event_log import EventType
from cyroid.schemas.vm import VMCreate, VMUpdate, VMResponse
from cyroid.services.event_service import EventService
from cyroid.config import get_settings
import os

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
            vm_id_short = str(vm.id)[:8]
            labels = {
                "cyroid.range_id": str(vm.range_id),
                "cyroid.vm_id": str(vm.id),
                "cyroid.hostname": vm.hostname,
            }

            # Add traefik labels for VNC web console routing
            # This allows accessing VNC at /vnc/{vm_id} through traefik
            display_type = vm.display_type or "desktop"
            if display_type == "desktop":
                # Determine VNC port and scheme based on image type
                base_image = template.base_image or ""
                is_linuxserver = "linuxserver/" in base_image or "lscr.io/linuxserver" in base_image
                is_kasmweb = "kasmweb/" in base_image

                if base_image.startswith("iso:") or template.os_type == OSType.WINDOWS or template.os_type == OSType.CUSTOM:
                    # qemus/qemu and dockur/windows use port 8006 over HTTP
                    vnc_port = "8006"
                    vnc_scheme = "http"
                    needs_auth = False
                elif is_linuxserver:
                    # LinuxServer containers (webtop, etc.) use port 3000 over HTTP, no auth by default
                    vnc_port = "3000"
                    vnc_scheme = "http"
                    needs_auth = False
                elif is_kasmweb:
                    # Official KasmVNC containers use port 6901 over HTTPS with auth
                    vnc_port = "6901"
                    vnc_scheme = "https"
                    needs_auth = True
                else:
                    # Default to 6901/HTTPS for other desktop containers
                    vnc_port = "6901"
                    vnc_scheme = "https"
                    needs_auth = False

                router_name = f"vnc-{vm_id_short}"
                middlewares = [f"vnc-strip-{vm_id_short}"]

                labels.update({
                    "traefik.enable": "true",
                    "traefik.docker.network": "traefik-routing",  # Use traefik-routing network
                    # Service (shared by both routers)
                    f"traefik.http.services.{router_name}.loadbalancer.server.port": vnc_port,
                    f"traefik.http.services.{router_name}.loadbalancer.server.scheme": vnc_scheme,
                    # HTTP router (priority=100 to take precedence over frontend catch-all)
                    f"traefik.http.routers.{router_name}.rule": f"PathPrefix(`/vnc/{vm.id}`)",
                    f"traefik.http.routers.{router_name}.entrypoints": "web",
                    f"traefik.http.routers.{router_name}.service": router_name,
                    f"traefik.http.routers.{router_name}.priority": "100",
                    # HTTPS router (priority=100 to take precedence over frontend catch-all)
                    f"traefik.http.routers.{router_name}-secure.rule": f"PathPrefix(`/vnc/{vm.id}`)",
                    f"traefik.http.routers.{router_name}-secure.entrypoints": "websecure",
                    f"traefik.http.routers.{router_name}-secure.tls": "true",
                    f"traefik.http.routers.{router_name}-secure.service": router_name,
                    f"traefik.http.routers.{router_name}-secure.priority": "100",
                    # Middleware
                    f"traefik.http.middlewares.vnc-strip-{vm_id_short}.stripprefix.prefixes": f"/vnc/{vm.id}",
                })

                # Use insecure transport for HTTPS backends (self-signed certs)
                if vnc_scheme == "https":
                    labels[f"traefik.http.services.{router_name}.loadbalancer.serversTransport"] = "insecure-transport@file"

                # For official KasmVNC containers, inject Basic Auth header to auto-login
                if needs_auth:
                    import base64
                    # Default KasmVNC credentials
                    auth_string = base64.b64encode(b"kasm_user:vncpassword").decode()
                    auth_middleware = f"vnc-auth-{vm_id_short}"
                    labels[f"traefik.http.middlewares.{auth_middleware}.headers.customrequestheaders.Authorization"] = f"Basic {auth_string}"
                    middlewares.append(auth_middleware)

                # Set all middlewares (for both HTTP and HTTPS routers)
                labels[f"traefik.http.routers.{router_name}.middlewares"] = ",".join(middlewares)
                labels[f"traefik.http.routers.{router_name}-secure.middlewares"] = ",".join(middlewares)

            if template.os_type == OSType.WINDOWS:
                settings = get_settings()

                # Setup VM-specific storage path
                vm_storage_path = os.path.join(
                    settings.vm_storage_dir,
                    str(vm.range_id),
                    str(vm.id),
                    "storage"
                )

                # Determine Windows version (VM setting takes priority over template)
                # Version codes: 11, 11l, 11e, 10, 10l, 10e, 8e, 7u, vu, xp, 2k, 2025, 2022, 2019, 2016, 2012, 2008, 2003
                windows_version = vm.windows_version or template.os_variant or "11"

                # Determine ISO path (VM setting takes priority)
                iso_path = vm.iso_path or (template.cached_iso_path if hasattr(template, 'cached_iso_path') and template.cached_iso_path else None)
                clone_from = template.golden_image_path if hasattr(template, 'golden_image_path') and template.golden_image_path else None

                # Setup per-VM shared folder path
                shared_folder_path = None
                if vm.enable_shared_folder:
                    shared_folder_path = os.path.join(
                        settings.vm_storage_dir,
                        str(vm.range_id),
                        str(vm.id),
                        "shared"
                    )

                # Setup OEM directory for post-install script (from template config_script)
                oem_script_path = None
                if template.config_script:
                    oem_dir = os.path.join(
                        settings.vm_storage_dir,
                        str(vm.range_id),
                        str(vm.id),
                        "oem"
                    )
                    os.makedirs(oem_dir, exist_ok=True)
                    install_bat = os.path.join(oem_dir, "install.bat")
                    with open(install_bat, "w") as f:
                        f.write(template.config_script)
                    oem_script_path = oem_dir
                    logger.info(f"Created OEM install.bat for VM {vm.id}")

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
                    iso_url=vm.iso_url,
                    storage_path=vm_storage_path,
                    clone_from=clone_from,
                    username=vm.windows_username,
                    password=vm.windows_password,
                    display_type=vm.display_type or "desktop",
                    # Network configuration
                    use_dhcp=vm.use_dhcp,
                    gateway=vm.gateway,
                    dns_servers=vm.dns_servers,
                    # Extended dockur/windows configuration
                    disk2_gb=vm.disk2_gb,
                    disk3_gb=vm.disk3_gb,
                    enable_shared_folder=vm.enable_shared_folder,
                    shared_folder_path=shared_folder_path,
                    enable_global_shared=vm.enable_global_shared,
                    global_shared_path=settings.global_shared_dir,
                    language=vm.language,
                    keyboard=vm.keyboard,
                    region=vm.region,
                    manual_install=vm.manual_install,
                    oem_script_path=oem_script_path,
                )
            elif template.os_type == OSType.CUSTOM:
                # Custom ISO VMs use qemux/qemu with the custom ISO
                settings = get_settings()

                # Setup VM-specific storage path
                vm_storage_path = os.path.join(
                    settings.vm_storage_dir,
                    str(vm.range_id),
                    str(vm.id),
                    "storage"
                )

                # Get custom ISO path from template
                iso_path = template.cached_iso_path if hasattr(template, 'cached_iso_path') and template.cached_iso_path else None

                container_id = docker.create_linux_vm_container(
                    name=f"cyroid-{vm.hostname}-{str(vm.id)[:8]}",
                    network_id=network.docker_network_id,
                    ip_address=vm.ip_address,
                    cpu_limit=vm.cpu,
                    memory_limit_mb=vm.ram_mb,
                    disk_size_gb=vm.disk_gb,
                    linux_distro="custom",  # Will be overridden by iso_path
                    labels=labels,
                    iso_path=iso_path,
                    storage_path=vm_storage_path,
                    display_type=vm.display_type or "desktop",
                    # Extended configuration
                    disk2_gb=vm.disk2_gb,
                    disk3_gb=vm.disk3_gb,
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

        # Log event
        event_service = EventService(db)
        event_service.log_event(
            range_id=vm.range_id,
            vm_id=vm.id,
            event_type=EventType.VM_STARTED,
            message=f"VM {vm.hostname} started"
        )

        # Update range status to RUNNING if any VM is running
        # This makes the execution console accessible
        range_obj = db.query(Range).filter(Range.id == vm.range_id).first()
        if range_obj and range_obj.status in (RangeStatus.STOPPED, RangeStatus.DRAFT):
            range_obj.status = RangeStatus.RUNNING
            db.commit()
            logger.info(f"Range {range_obj.id} status updated to RUNNING")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start VM {vm_id}: {e}")
        vm.status = VMStatus.ERROR
        db.commit()

        # Log error event
        event_service = EventService(db)
        event_service.log_event(
            range_id=vm.range_id,
            vm_id=vm.id,
            event_type=EventType.VM_ERROR,
            message=f"VM {vm.hostname} failed to start: {str(e)}"
        )

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

        # Log event
        event_service = EventService(db)
        event_service.log_event(
            range_id=vm.range_id,
            vm_id=vm.id,
            event_type=EventType.VM_STOPPED,
            message=f"VM {vm.hostname} stopped"
        )

        # Update range status to STOPPED if all VMs are stopped
        range_obj = db.query(Range).filter(Range.id == vm.range_id).first()
        if range_obj and range_obj.status == RangeStatus.RUNNING:
            all_vms = db.query(VM).filter(VM.range_id == vm.range_id).all()
            all_stopped = all(v.status == VMStatus.STOPPED for v in all_vms)
            if all_stopped:
                range_obj.status = RangeStatus.STOPPED
                db.commit()
                logger.info(f"Range {range_obj.id} status updated to STOPPED (all VMs stopped)")

    except Exception as e:
        logger.error(f"Failed to stop VM {vm_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop VM: {str(e)}",
        )

    return vm


@router.get("/{vm_id}/stats")
def get_vm_stats(vm_id: UUID, db: DBSession, current_user: CurrentUser):
    """Get real-time resource statistics for a VM"""
    vm = db.query(VM).filter(VM.id == vm_id).first()
    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found",
        )

    if vm.status != VMStatus.RUNNING:
        return {"vm_id": str(vm.id), "status": vm.status.value, "stats": None}

    if not vm.container_id:
        return {"vm_id": str(vm.id), "status": vm.status.value, "stats": None}

    try:
        docker = get_docker_service()
        stats = docker.get_container_stats(vm.container_id)
        return {
            "vm_id": str(vm.id),
            "hostname": vm.hostname,
            "status": vm.status.value,
            "stats": stats
        }
    except Exception as e:
        logger.warning(f"Failed to get stats for VM {vm_id}: {e}")
        return {"vm_id": str(vm.id), "status": vm.status.value, "stats": None}


@router.get("/{vm_id}/vnc-info")
def get_vm_vnc_info(vm_id: UUID, db: DBSession, current_user: CurrentUser, request: Request):
    """Get VNC console connection info for a VM"""
    vm = db.query(VM).filter(VM.id == vm_id).first()
    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found",
        )

    if vm.status != VMStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"VM is not running (status: {vm.status.value})",
        )

    if not vm.container_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VM has no running container",
        )

    # Check if display_type supports VNC console
    display_type = vm.display_type or "desktop"
    if display_type != "desktop":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VM is in server mode (no VNC console available)",
        )

    try:
        # VNC is proxied through traefik at /vnc/{vm_id}
        vnc_path = f"/vnc/{vm.id}"

        # Determine WebSocket path based on container type
        # - KasmVNC containers (kasmweb/*): use empty path (root /)
        # - qemu/dockur containers: use "websockify" path
        template = db.query(VMTemplate).filter(VMTemplate.id == vm.template_id).first()
        base_image = template.base_image if template else ""
        is_kasmweb = "kasmweb/" in base_image or "lscr.io/linuxserver" in base_image

        # KasmVNC handles WebSocket on root path, noVNC/websockify uses /websockify
        websocket_path = "" if is_kasmweb else "websockify"

        # Return the path - frontend will construct full URL using browser hostname
        # This avoids issues with Docker internal hostnames in the Host header
        return {
            "vm_id": str(vm.id),
            "hostname": vm.hostname,
            "path": vnc_path,
            "websocket_path": websocket_path,
            "traefik_port": 80,
            "method": "traefik_proxy",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get VNC info for VM {vm_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get VNC info: {str(e)}",
        )


@router.get("/{vm_id}/networks")
def get_vm_networks(vm_id: UUID, db: DBSession, current_user: CurrentUser):
    """Get all network interfaces for a VM from Docker"""
    vm = db.query(VM).filter(VM.id == vm_id).first()
    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found",
        )

    if not vm.container_id:
        return {
            "vm_id": str(vm.id),
            "hostname": vm.hostname,
            "status": vm.status.value,
            "interfaces": []
        }

    try:
        docker = get_docker_service()
        interfaces = docker.get_container_networks(vm.container_id)

        # Enrich with cyroid network info
        if interfaces:
            for iface in interfaces:
                # Try to match with cyroid networks by docker_network_id
                network = db.query(Network).filter(
                    Network.docker_network_id == iface.get("network_id")
                ).first()
                if network:
                    iface["cyroid_network_id"] = str(network.id)
                    iface["cyroid_network_name"] = network.name
                    iface["subnet"] = network.subnet

        return {
            "vm_id": str(vm.id),
            "hostname": vm.hostname,
            "status": vm.status.value,
            "interfaces": interfaces or []
        }
    except Exception as e:
        logger.warning(f"Failed to get network interfaces for VM {vm_id}: {e}")
        return {
            "vm_id": str(vm.id),
            "hostname": vm.hostname,
            "status": vm.status.value,
            "interfaces": []
        }


@router.get("/range/{range_id}/networks")
def get_range_vm_networks(range_id: UUID, db: DBSession, current_user: CurrentUser):
    """Get all network interfaces for all VMs in a range"""
    # Verify range exists
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Range not found",
        )

    # Get all VMs in the range
    vms = db.query(VM).filter(VM.range_id == range_id).all()

    docker = None
    try:
        docker = get_docker_service()
    except Exception as e:
        logger.warning(f"Could not connect to Docker: {e}")

    # Get networks for the range for matching
    networks = db.query(Network).filter(Network.range_id == range_id).all()
    network_map = {n.docker_network_id: n for n in networks if n.docker_network_id}

    result = []
    for vm in vms:
        vm_data = {
            "vm_id": str(vm.id),
            "hostname": vm.hostname,
            "status": vm.status.value,
            "interfaces": []
        }

        if vm.container_id and docker:
            try:
                interfaces = docker.get_container_networks(vm.container_id)
                if interfaces:
                    for iface in interfaces:
                        # Match with cyroid networks
                        docker_net_id = iface.get("network_id")
                        if docker_net_id in network_map:
                            network = network_map[docker_net_id]
                            iface["cyroid_network_id"] = str(network.id)
                            iface["cyroid_network_name"] = network.name
                            iface["subnet"] = network.subnet
                    vm_data["interfaces"] = interfaces
            except Exception as e:
                logger.warning(f"Failed to get networks for VM {vm.id}: {e}")

        result.append(vm_data)

    return {"vms": result, "range_id": str(range_id)}


@router.post("/{vm_id}/networks/{network_id}")
def add_vm_network(
    vm_id: UUID,
    network_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    ip_address: str = None
):
    """Add a network interface to a running VM"""
    vm = db.query(VM).filter(VM.id == vm_id).first()
    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found",
        )

    if vm.status != VMStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VM must be running to add network interfaces",
        )

    if not vm.container_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VM has no container",
        )

    # Get the network
    network = db.query(Network).filter(Network.id == network_id).first()
    if not network:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Network not found",
        )

    if not network.docker_network_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Network is not provisioned",
        )

    try:
        docker = get_docker_service()
        docker.connect_container_to_network(
            vm.container_id,
            network.docker_network_id,
            ip_address=ip_address
        )

        # Get updated interfaces
        interfaces = docker.get_container_networks(vm.container_id)

        return {
            "success": True,
            "message": f"Added network {network.name} to VM {vm.hostname}",
            "interfaces": interfaces or []
        }
    except Exception as e:
        logger.error(f"Failed to add network to VM: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add network: {str(e)}",
        )


@router.delete("/{vm_id}/networks/{network_id}")
def remove_vm_network(
    vm_id: UUID,
    network_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    """Remove a network interface from a running VM"""
    vm = db.query(VM).filter(VM.id == vm_id).first()
    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found",
        )

    if vm.status != VMStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VM must be running to remove network interfaces",
        )

    if not vm.container_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VM has no container",
        )

    # Get the network
    network = db.query(Network).filter(Network.id == network_id).first()
    if not network:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Network not found",
        )

    if not network.docker_network_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Network is not provisioned",
        )

    # Don't allow removing the primary network
    if str(network.id) == str(vm.network_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the primary network interface",
        )

    try:
        docker = get_docker_service()
        docker.disconnect_container_from_network(
            vm.container_id,
            network.docker_network_id
        )

        # Get updated interfaces
        interfaces = docker.get_container_networks(vm.container_id)

        return {
            "success": True,
            "message": f"Removed network {network.name} from VM {vm.hostname}",
            "interfaces": interfaces or []
        }
    except Exception as e:
        logger.error(f"Failed to remove network from VM: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove network: {str(e)}",
        )


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

        # Log event
        event_service = EventService(db)
        event_service.log_event(
            range_id=vm.range_id,
            vm_id=vm.id,
            event_type=EventType.VM_RESTARTED,
            message=f"VM {vm.hostname} restarted"
        )

    except Exception as e:
        logger.error(f"Failed to restart VM {vm_id}: {e}")
        vm.status = VMStatus.ERROR
        db.commit()

        # Log error event
        event_service = EventService(db)
        event_service.log_event(
            range_id=vm.range_id,
            vm_id=vm.id,
            event_type=EventType.VM_ERROR,
            message=f"VM {vm.hostname} failed to restart: {str(e)}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restart VM: {str(e)}",
        )

    return vm
