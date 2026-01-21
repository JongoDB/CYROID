# backend/cyroid/api/vms.py
import asyncio
import ipaddress
from typing import List, Optional, Tuple
from uuid import UUID
import logging

from fastapi import APIRouter, HTTPException, status, Request, Query
from sqlalchemy.orm import joinedload, Session
from sqlalchemy.orm.attributes import flag_modified

from cyroid.api.deps import DBSession, CurrentUser
from cyroid.models.vm import VM, VMStatus
from cyroid.models.range import Range, RangeStatus
from cyroid.models.network import Network
from cyroid.models.template import OSType, VMType
from cyroid.models.snapshot import Snapshot
from cyroid.models.base_image import BaseImage
from cyroid.models.golden_image import GoldenImage
from cyroid.models.event_log import EventType
from cyroid.schemas.vm import VMCreate, VMUpdate, VMResponse
from cyroid.services.event_service import EventService
from cyroid.config import get_settings
from cyroid.utils.arch import IS_ARM
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vms", tags=["VMs"])

# Linux distros that have native ARM64 support
ARM64_NATIVE_DISTROS = {'ubuntu', 'debian', 'fedora', 'alpine', 'rocky', 'alma', 'kali'}


def get_next_available_ip(network: Network, db: Session, skip_gateway: bool = True) -> Optional[str]:
    """
    Calculate the next available IP address in a network subnet.

    Args:
        network: The network model with subnet info
        db: Database session for querying existing VMs
        skip_gateway: Whether to skip the gateway IP (default: True)

    Returns:
        The next available IP address as a string, or None if all IPs are taken
    """
    try:
        net = ipaddress.ip_network(network.subnet, strict=False)
    except ValueError:
        logger.warning(f"Invalid subnet format: {network.subnet}")
        return None

    # Get all existing IPs in this network
    existing_ips = db.query(VM.ip_address).filter(VM.network_id == network.id).all()
    used_ips = {ip[0] for ip in existing_ips}

    # Also exclude the gateway
    if skip_gateway and network.gateway:
        used_ips.add(network.gateway)

    # Iterate through hosts in the subnet, starting from .10 to leave room for infrastructure
    # Skip network address (.0) and broadcast address (.255 for /24)
    start_offset = 10  # Start from .10 for user VMs
    for host in net.hosts():
        host_str = str(host)
        # Check if this is at least .10 in the last octet
        last_octet = int(host_str.split('.')[-1])
        if last_octet < start_offset:
            continue
        if host_str not in used_ips:
            return host_str

    return None


def get_available_ips_in_range(network: Network, db: Session, limit: int = 20) -> List[str]:
    """
    Get a list of available IP addresses in a network subnet.

    Args:
        network: The network model with subnet info
        db: Database session for querying existing VMs
        limit: Maximum number of IPs to return

    Returns:
        List of available IP addresses
    """
    try:
        net = ipaddress.ip_network(network.subnet, strict=False)
    except ValueError:
        return []

    # Get all existing IPs in this network
    existing_ips = db.query(VM.ip_address).filter(VM.network_id == network.id).all()
    used_ips = {ip[0] for ip in existing_ips}

    # Also exclude the gateway
    if network.gateway:
        used_ips.add(network.gateway)

    available = []
    start_offset = 10  # Start from .10 for user VMs
    for host in net.hosts():
        host_str = str(host)
        last_octet = int(host_str.split('.')[-1])
        if last_octet < start_offset:
            continue
        if host_str not in used_ips:
            available.append(host_str)
            if len(available) >= limit:
                break

    return available


def compute_emulation_status(
    vm: VM,
    base_image: Optional[BaseImage] = None,
    golden_image: Optional[GoldenImage] = None,
    snapshot: Optional[Snapshot] = None
) -> Tuple[bool, Optional[str]]:
    """
    Determine if a VM will run via emulation on this host.

    Args:
        vm: The VM model instance
        base_image: The VM's base image (optional)
        golden_image: The VM's golden image (optional)
        snapshot: The VM's source snapshot (optional)

    Returns:
        Tuple of (is_emulated, warning_message)
    """
    # If VM has explicit architecture set, check against host
    if vm.arch:
        from cyroid.utils.arch import requires_emulation
        if requires_emulation(vm.arch):
            arch_display = "ARM64" if vm.arch == "arm64" else "x86_64"
            host_display = "ARM64" if IS_ARM else "x86_64"
            return True, f"VM targets {arch_display} but host is {host_display}. Performance will be reduced (10-20x slower)."
        return False, None

    if not IS_ARM:
        # x86 hosts run everything natively
        return False, None

    # Get VM type and OS type from base_image, golden_image, or snapshot
    vm_type = None
    os_type = None
    native_arch = 'x86_64'

    if base_image:
        vm_type = VMType(base_image.vm_type) if base_image.vm_type else None
        os_type = OSType(base_image.os_type) if base_image.os_type else None
        native_arch = base_image.native_arch or 'x86_64'
    elif golden_image:
        vm_type = VMType(golden_image.vm_type) if golden_image.vm_type else None
        os_type = OSType(golden_image.os_type) if golden_image.os_type else None
        native_arch = golden_image.native_arch or 'x86_64'
    elif snapshot:
        vm_type = VMType(snapshot.vm_type) if snapshot.vm_type else None
        os_type = OSType(snapshot.os_type) if snapshot.os_type else None

    # Windows VMs - now support ARM64 with dockur/windows-arm
    # When vm.arch is NULL (host default), docker_service selects the native image:
    # - ARM host → dockur/windows-arm (native)
    # - x86 host → dockur/windows (native)
    # So no emulation warning needed when vm.arch is NULL
    if vm_type == VMType.WINDOWS_VM or os_type == OSType.WINDOWS:
        # If we got here, vm.arch is NULL and we're on ARM host
        # docker_service will use dockur/windows-arm → native, no emulation
        return False, None

    # macOS VMs - only supported on x86_64 hosts (no ARM support via dockur/macos)
    if vm_type == VMType.MACOS_VM or os_type == OSType.MACOS:
        from cyroid.utils.arch import HOST_ARCH
        if HOST_ARCH == "arm64":
            return True, "macOS VMs are only supported on x86_64 hosts. Not available on ARM."
        return False, None

    # Linux VMs - check if distro has ARM64 support
    if vm_type == VMType.LINUX_VM:
        linux_distro = vm.linux_distro
        if linux_distro and linux_distro.lower() in ARM64_NATIVE_DISTROS:
            return False, None
        # Unknown or unsupported distro on ARM
        return True, f"This Linux VM may run via x86 emulation. Performance may be reduced."

    # Custom ISOs - check native_arch
    if os_type == OSType.CUSTOM:
        if native_arch == 'arm64' or native_arch == 'both':
            return False, None
        return True, "Custom ISO runs via x86 emulation on ARM hosts. Performance may be reduced."

    # Containers - most are multi-arch, assume native
    # Default: assume native for containers and snapshot-based VMs
    return False, None


def vm_to_response(
    vm: VM,
    base_image: Optional[BaseImage] = None,
    golden_image: Optional[GoldenImage] = None,
    snapshot: Optional[Snapshot] = None
) -> dict:
    """
    Convert VM model to response dict with emulation status.

    Args:
        vm: The VM model instance
        base_image: The VM's base image (optional)
        golden_image: The VM's golden image (optional)
        snapshot: The VM's source snapshot (optional)

    Returns:
        Dictionary for VMResponse
    """
    emulated, warning = compute_emulation_status(vm, base_image, golden_image, snapshot)
    response = {
        "id": vm.id,
        "range_id": vm.range_id,
        "network_id": vm.network_id,
        "base_image_id": vm.base_image_id,
        "golden_image_id": vm.golden_image_id,
        "snapshot_id": vm.snapshot_id,
        "hostname": vm.hostname,
        "ip_address": vm.ip_address,
        "cpu": vm.cpu,
        "ram_mb": vm.ram_mb,
        "disk_gb": vm.disk_gb,
        "position_x": vm.position_x,
        "position_y": vm.position_y,
        "status": vm.status,
        "container_id": vm.container_id,
        "windows_version": vm.windows_version,
        "windows_username": vm.windows_username,
        "iso_url": vm.iso_url,
        "iso_path": vm.iso_path,
        "display_type": vm.display_type or "desktop",
        "use_dhcp": vm.use_dhcp,
        "gateway": vm.gateway,
        "dns_servers": vm.dns_servers,
        "disk2_gb": vm.disk2_gb,
        "disk3_gb": vm.disk3_gb,
        "enable_shared_folder": vm.enable_shared_folder,
        "enable_global_shared": vm.enable_global_shared,
        "language": vm.language,
        "keyboard": vm.keyboard,
        "region": vm.region,
        "manual_install": vm.manual_install,
        "linux_username": vm.linux_username,
        "linux_user_sudo": vm.linux_user_sudo,
        "boot_source": vm.boot_source,
        "arch": vm.arch,
        "error_message": vm.error_message,
        "created_at": vm.created_at,
        "updated_at": vm.updated_at,
        "emulated": emulated,
        "emulation_warning": warning,
    }
    return response


def get_docker_service():
    """Lazy import to avoid Docker connection issues during testing."""
    from cyroid.services.docker_service import get_docker_service as _get_docker_service
    return _get_docker_service()


def load_vm_source(db: Session, vm: VM) -> Tuple[Optional[BaseImage], Optional[GoldenImage], Optional[Snapshot]]:
    """
    Load VM's image source (base_image, golden_image, or snapshot).

    Args:
        db: Database session
        vm: The VM model instance

    Returns:
        Tuple of (base_image, golden_image, snapshot) - two will be None
    """
    base_image = None
    golden_image = None
    snapshot = None
    if vm.base_image_id:
        base_image = db.query(BaseImage).filter(BaseImage.id == vm.base_image_id).first()
    elif vm.golden_image_id:
        golden_image = db.query(GoldenImage).filter(GoldenImage.id == vm.golden_image_id).first()
    elif vm.snapshot_id:
        snapshot = db.query(Snapshot).filter(Snapshot.id == vm.snapshot_id).first()
    return base_image, golden_image, snapshot


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

    # Use eager loading to avoid N+1 query problem
    vms = db.query(VM).options(
        joinedload(VM.base_image),
        joinedload(VM.golden_image),
        joinedload(VM.source_snapshot)
    ).filter(VM.range_id == range_id).all()

    # Build responses with emulation status (relationships already loaded)
    responses = []
    for vm in vms:
        base_image = vm.base_image  # Already loaded via joinedload
        golden_image = vm.golden_image  # Already loaded via joinedload
        snapshot = vm.source_snapshot  # Already loaded via joinedload
        responses.append(vm_to_response(vm, base_image, golden_image, snapshot))
    return responses


@router.post("", response_model=VMResponse, status_code=status.HTTP_201_CREATED)
def create_vm(vm_data: VMCreate, db: DBSession, current_user: CurrentUser):
    # Verify range exists
    range_obj = db.query(Range).filter(Range.id == vm_data.range_id).first()
    if not range_obj:
        logger.warning(f"VM creation failed: Range not found (id={vm_data.range_id})")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Range not found: {vm_data.range_id}",
        )

    # Verify network exists and belongs to the range
    network = db.query(Network).filter(Network.id == vm_data.network_id).first()
    if not network:
        logger.warning(f"VM creation failed: Network not found (id={vm_data.network_id})")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Network not found: {vm_data.network_id}",
        )
    if network.range_id != vm_data.range_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Network does not belong to this range",
        )

    # Auto-fill IP address if not provided
    if vm_data.ip_address is None:
        next_ip = get_next_available_ip(network, db)
        if next_ip is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No available IP addresses in this network",
            )
        vm_data.ip_address = next_ip
        logger.info(f"Auto-assigned IP {next_ip} to VM {vm_data.hostname}")

    # Validate source (base_image, golden_image, OR snapshot)
    base_image = None
    golden_image = None
    snapshot = None

    if vm_data.base_image_id:
        base_image = db.query(BaseImage).filter(BaseImage.id == vm_data.base_image_id).first()
        if not base_image:
            logger.warning(f"VM creation failed: Base image not found (id={vm_data.base_image_id})")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Base image not found: {vm_data.base_image_id}",
            )
    elif vm_data.golden_image_id:
        golden_image = db.query(GoldenImage).filter(GoldenImage.id == vm_data.golden_image_id).first()
        if not golden_image:
            logger.warning(f"VM creation failed: Golden image not found (id={vm_data.golden_image_id})")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Golden image not found: {vm_data.golden_image_id}",
            )
    elif vm_data.snapshot_id:
        snapshot = db.query(Snapshot).filter(Snapshot.id == vm_data.snapshot_id).first()
        if not snapshot:
            logger.warning(f"VM creation failed: Snapshot not found (id={vm_data.snapshot_id})")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Snapshot not found: {vm_data.snapshot_id}",
            )
        if not snapshot.docker_image_id and not snapshot.docker_image_tag:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Snapshot has no Docker image",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VM must have a base_image_id, golden_image_id, or snapshot_id",
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
    return vm_to_response(vm, base_image, golden_image, snapshot)


@router.get("/{vm_id}", response_model=VMResponse)
def get_vm(vm_id: UUID, db: DBSession, current_user: CurrentUser):
    vm = db.query(VM).filter(VM.id == vm_id).first()
    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found",
        )
    base_image, golden_image, snapshot = load_vm_source(db, vm)
    return vm_to_response(vm, base_image, golden_image, snapshot)


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
    base_image, golden_image, snapshot = load_vm_source(db, vm)
    return vm_to_response(vm, base_image, golden_image, snapshot)


@router.delete("/{vm_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vm(vm_id: UUID, db: DBSession, current_user: CurrentUser):
    vm = db.query(VM).filter(VM.id == vm_id).first()
    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found",
        )

    # Get range for DinD mode check
    range_obj = db.query(Range).filter(Range.id == vm.range_id).first()
    use_dind = bool(range_obj and range_obj.dind_docker_url)

    # Try to recover DinD info if missing (ensures VNC cleanup works)
    if range_obj and not use_dind:
        from cyroid.services.dind_service import get_dind_service
        dind_service = get_dind_service()
        dind_info = asyncio.run(dind_service.get_container_info(str(range_obj.id)))
        if dind_info and dind_info.get("docker_url"):
            logger.info(f"Auto-recovering DinD info for range {range_obj.id} during VM delete")
            range_obj.dind_container_id = dind_info["container_id"]
            range_obj.dind_container_name = dind_info["container_name"]
            range_obj.dind_mgmt_ip = dind_info["mgmt_ip"]
            range_obj.dind_docker_url = dind_info["docker_url"]
            db.commit()
            use_dind = True

    # Remove VNC port forwarding for DinD ranges
    if use_dind and range_obj.vnc_proxy_mappings:
        vm_id_str = str(vm_id)
        proxy_info = range_obj.vnc_proxy_mappings.get(vm_id_str)
        if proxy_info:
            try:
                from cyroid.services.dind_service import get_dind_service
                from cyroid.services.traefik_route_service import get_traefik_route_service

                dind_service = get_dind_service()
                traefik_service = get_traefik_route_service()

                # Remove iptables DNAT rule
                asyncio.run(dind_service.remove_vnc_port_forwarding(
                    range_id=str(vm.range_id),
                    vm_id=vm_id_str,
                    proxy_info=proxy_info,
                ))

                # Update database - remove this VM's mapping
                updated_mappings = {k: v for k, v in range_obj.vnc_proxy_mappings.items() if k != vm_id_str}
                range_obj.vnc_proxy_mappings = updated_mappings if updated_mappings else None
                db.commit()

                # Regenerate Traefik routes without this VM
                if updated_mappings:
                    traefik_service.generate_vnc_routes(str(vm.range_id), updated_mappings)
                else:
                    traefik_service.remove_vnc_routes(str(vm.range_id))

                logger.info(f"Removed VNC forwarding for VM {vm.hostname}")
            except Exception as e:
                logger.warning(f"Failed to remove VNC forwarding for VM {vm_id}: {e}")

    # Remove container if it exists
    if vm.container_id:
        try:
            docker = get_docker_service()

            if use_dind:
                asyncio.run(docker.remove_range_container_dind(
                    range_id=str(vm.range_id),
                    docker_url=range_obj.dind_docker_url,
                    container_id=vm.container_id,
                ))
            else:
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

        # Get network info
        network = db.query(Network).filter(Network.id == vm.network_id).first()

        if not network:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Network not found",
            )

        # Get range to check for DinD mode
        range_obj = db.query(Range).filter(Range.id == vm.range_id).first()
        use_dind = bool(range_obj and range_obj.dind_docker_url)

        # Try to recover DinD info if missing but container might exist
        if range_obj and not use_dind:
            from cyroid.services.dind_service import get_dind_service
            dind_service = get_dind_service()
            dind_info = asyncio.run(dind_service.get_container_info(str(range_obj.id)))
            if dind_info and dind_info.get("docker_url"):
                # Found a DinD container - recover the info
                logger.info(f"Auto-recovering DinD info for range {range_obj.id} during VM start")
                range_obj.dind_container_id = dind_info["container_id"]
                range_obj.dind_container_name = dind_info["container_name"]
                range_obj.dind_mgmt_ip = dind_info["mgmt_ip"]
                range_obj.dind_docker_url = dind_info["docker_url"]
                db.commit()
                use_dind = True

        # Validate network is provisioned
        if not use_dind and not network.docker_network_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Network not provisioned",
            )

        # Get source configuration (base_image, golden_image, or snapshot)
        snapshot = None
        base_image_record = None
        golden_image_record = None
        image_ref = None  # Docker image name or ISO reference
        os_type = None
        vm_type = None

        if vm.base_image_id:
            # Base Image (container or ISO)
            base_image_record = db.query(BaseImage).filter(BaseImage.id == vm.base_image_id).first()
            if not base_image_record:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="VM's base image not found",
                )
            # For containers, use docker_image_tag; for ISOs, use iso_path
            if base_image_record.image_type == "container":
                image_ref = base_image_record.docker_image_tag or base_image_record.docker_image_id
            else:
                # ISO-based VM
                image_ref = f"iso:{base_image_record.iso_path}"
            os_type = OSType(base_image_record.os_type) if base_image_record.os_type else OSType.LINUX
            vm_type = VMType(base_image_record.vm_type) if base_image_record.vm_type else VMType.CONTAINER
        elif vm.golden_image_id:
            # Golden Image (pre-configured snapshot or import)
            golden_image_record = db.query(GoldenImage).filter(GoldenImage.id == vm.golden_image_id).first()
            if not golden_image_record:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="VM's golden image not found",
                )
            # Use docker_image_tag if available, otherwise docker_image_id or disk_image_path
            image_ref = golden_image_record.docker_image_tag or golden_image_record.docker_image_id
            if not image_ref and golden_image_record.disk_image_path:
                image_ref = f"disk:{golden_image_record.disk_image_path}"
            if not image_ref:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Golden image has no Docker image or disk reference",
                )
            os_type = OSType(golden_image_record.os_type) if golden_image_record.os_type else OSType.LINUX
            vm_type = VMType(golden_image_record.vm_type) if golden_image_record.vm_type else VMType.CONTAINER
        elif vm.snapshot_id:
            # Snapshot (point-in-time fork)
            snapshot = db.query(Snapshot).filter(Snapshot.id == vm.snapshot_id).first()
            if not snapshot:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="VM's snapshot not found",
                )
            # Use docker_image_tag if available, otherwise docker_image_id
            image_ref = snapshot.docker_image_tag or snapshot.docker_image_id
            if not image_ref:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Snapshot has no Docker image reference",
                )
            os_type = OSType(snapshot.os_type) if snapshot.os_type else OSType.LINUX
            vm_type = VMType(snapshot.vm_type) if snapshot.vm_type else VMType.CONTAINER
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="VM has no image source (base_image_id, golden_image_id, or snapshot_id)",
            )

        # Container already exists - just start it
        container_id = vm.container_id  # Track for VNC setup
        if vm.container_id:
            if use_dind:
                # Start container inside DinD
                asyncio.run(docker.start_range_container_dind(
                    range_id=str(vm.range_id),
                    docker_url=range_obj.dind_docker_url,
                    container_id=vm.container_id,
                ))
            else:
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
                image_for_check = image_ref or ""
                is_linuxserver = "linuxserver/" in image_for_check or "lscr.io/linuxserver" in image_for_check
                is_kasmweb = "kasmweb/" in image_for_check

                # For snapshots, use the snapshot's VNC port if specified
                if snapshot and snapshot.vnc_port:
                    vnc_port = str(snapshot.vnc_port)
                    vnc_scheme = "http"
                    needs_auth = False
                elif image_for_check.startswith("iso:") or os_type == OSType.WINDOWS or os_type == OSType.CUSTOM:
                    # qemux/qemu and dockur/windows use port 8006 over HTTP
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

                # Use range network for routing (traefik connects to range networks, not VMs to traefik-routing)
                # This ensures VMs cannot access the management network
                range_network_name = f"cyroid-{network.name}-{str(network.id)[:8]}"

                labels.update({
                    "traefik.enable": "true",
                    "traefik.docker.network": range_network_name,  # Use range network for routing
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
                    # Use hardcoded VNC credentials for seamless console auto-login
                    auth_string = base64.b64encode(b"kasm_user:vncpassword").decode()
                    auth_middleware = f"vnc-auth-{vm_id_short}"
                    labels[f"traefik.http.middlewares.{auth_middleware}.headers.customrequestheaders.Authorization"] = f"Basic {auth_string}"
                    middlewares.append(auth_middleware)

                # Set all middlewares (for both HTTP and HTTPS routers)
                labels[f"traefik.http.routers.{router_name}.middlewares"] = ",".join(middlewares)
                labels[f"traefik.http.routers.{router_name}-secure.middlewares"] = ",".join(middlewares)

            if os_type == OSType.WINDOWS:
                settings = get_settings()

                # Setup VM-specific storage path
                vm_storage_path = os.path.join(
                    settings.vm_storage_dir,
                    str(vm.range_id),
                    str(vm.id),
                    "storage"
                )

                # Determine Windows version (VM setting takes priority)
                # Version codes: 11, 11l, 11e, 10, 10l, 10e, 8e, 7u, vu, xp, 2k, 2025, 2022, 2019, 2016, 2012, 2008, 2003
                windows_version = vm.windows_version or "11"

                # Check architecture compatibility
                # dockur/windows and dockur/windows-arm both use KVM (no cross-arch emulation)
                from cyroid.utils.arch import HOST_ARCH
                # Only Windows 11 has ARM64 support (Win10 ARM requires UUP build - not supported)
                WINDOWS_ARM64_VERSIONS = {"11", "11e", "11l"}

                target_arch = vm.arch or HOST_ARCH

                # Block x86 Windows on ARM hosts
                if HOST_ARCH == "arm64" and target_arch == "x86_64":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="x86 Windows emulation on ARM hosts is not supported. "
                               "Please use Windows 11 ARM64, or run on an x86 host."
                    )

                # Block non-Win11 versions on ARM hosts
                if HOST_ARCH == "arm64" and windows_version not in WINDOWS_ARM64_VERSIONS:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Windows version '{windows_version}' is not available for ARM64. "
                               f"Only Windows 11 (11, 11e, 11l) supports ARM64 hosts. "
                               f"All other versions require an x86 host."
                    )

                # Block ARM64 Windows on x86 hosts
                if HOST_ARCH == "x86_64" and target_arch == "arm64":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="ARM64 Windows emulation on x86 hosts is not supported. "
                               "Please use x86 Windows, or run on an ARM host."
                    )

                # Determine ISO path from VM or base_image
                iso_path = vm.iso_path
                if not iso_path and base_image_record and base_image_record.iso_path:
                    iso_path = base_image_record.iso_path

                # Get golden image path for cloning if using golden_image
                clone_from = None
                if golden_image_record and golden_image_record.disk_image_path:
                    clone_from = golden_image_record.disk_image_path

                # Setup per-VM shared folder path
                shared_folder_path = None
                if vm.enable_shared_folder:
                    shared_folder_path = os.path.join(
                        settings.vm_storage_dir,
                        str(vm.range_id),
                        str(vm.id),
                        "shared"
                    )

                if use_dind:
                    # Create Windows VM inside DinD with dockur/windows
                    windows_env = {
                        "VERSION": windows_version,
                        "DISK_SIZE": f"{vm.disk_gb or 64}G",
                        "CPU_CORES": str(vm.cpu or 4),
                        "RAM_SIZE": f"{vm.ram_mb or 8192}M",
                        "DISPLAY": "web" if (vm.display_type or "desktop") == "desktop" else "none",
                        "KVM": "N",  # DinD typically doesn't have KVM access
                    }
                    if vm.windows_username:
                        windows_env["USERNAME"] = vm.windows_username
                    if vm.windows_password:
                        windows_env["PASSWORD"] = vm.windows_password
                    if vm.use_dhcp:
                        windows_env["DHCP"] = "Y"
                    else:
                        if vm.gateway:
                            windows_env["GATEWAY"] = vm.gateway
                        if vm.dns_servers:
                            windows_env["DNS"] = vm.dns_servers

                    # Volume mounts for ISO
                    volumes = {}

                    # Priority: local ISO path > ISO URL > version (auto-download)
                    if iso_path and os.path.exists(iso_path):
                        # Mount the cached ISO into the container
                        volumes[iso_path] = {"bind": "/boot.iso", "mode": "ro"}
                        windows_env["BOOT"] = "/boot.iso"
                        logger.info(f"Using cached ISO for VM {vm.hostname}: {iso_path}")
                    elif vm.iso_url:
                        windows_env["BOOT"] = vm.iso_url
                    # If no ISO specified, dockur/windows will auto-download based on VERSION

                    container_id = asyncio.run(docker.create_range_container_dind(
                        range_id=str(vm.range_id),
                        docker_url=range_obj.dind_docker_url,
                        name=vm.hostname,
                        image="dockurr/windows",
                        network_name=network.name,
                        ip_address=vm.ip_address,
                        cpu_limit=vm.cpu or 4,
                        memory_limit_mb=vm.ram_mb or 8192,
                        hostname=vm.hostname,
                        labels=labels,
                        environment=windows_env,
                        volumes=volumes if volumes else None,
                        privileged=True,
                        dns_servers=network.dns_servers,
                        dns_search=network.dns_search,
                    ))
                else:
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
                        # Architecture selection
                        arch=vm.arch,
                    )
            elif os_type == OSType.CUSTOM:
                # Custom ISO VMs use qemux/qemu with the custom ISO
                settings = get_settings()

                # Setup VM-specific storage path
                vm_storage_path = os.path.join(
                    settings.vm_storage_dir,
                    str(vm.range_id),
                    str(vm.id),
                    "storage"
                )

                # Get custom ISO path from VM or base_image
                iso_path = vm.iso_path
                if not iso_path and base_image_record and base_image_record.iso_path:
                    iso_path = base_image_record.iso_path

                if use_dind:
                    # Create custom ISO VM inside DinD with qemux/qemu
                    custom_env = {
                        "DISK_SIZE": f"{vm.disk_gb or 40}G",
                        "CPU_CORES": str(vm.cpu or 2),
                        "RAM_SIZE": f"{vm.ram_mb or 4096}M",
                        "KVM": "N",  # DinD typically doesn't have KVM access
                    }

                    # Volume mounts for ISO
                    volumes = {}

                    # Priority: local ISO path > ISO URL
                    # DinD container has ISO cache mounted, so local paths are accessible
                    if iso_path and os.path.exists(iso_path):
                        # Mount the cached ISO into the container at /boot.iso
                        volumes[iso_path] = {"bind": "/boot.iso", "mode": "ro"}
                        custom_env["BOOT"] = "/boot.iso"
                        logger.info(f"Using cached ISO for custom VM {vm.hostname}: {iso_path}")
                    elif vm.iso_url:
                        custom_env["BOOT"] = vm.iso_url

                    container_id = asyncio.run(docker.create_range_container_dind(
                        range_id=str(vm.range_id),
                        docker_url=range_obj.dind_docker_url,
                        name=vm.hostname,
                        image="qemux/qemu",
                        network_name=network.name,
                        ip_address=vm.ip_address,
                        cpu_limit=vm.cpu or 2,
                        memory_limit_mb=vm.ram_mb or 4096,
                        hostname=vm.hostname,
                        labels=labels,
                        environment=custom_env,
                        volumes=volumes if volumes else None,
                        privileged=True,
                        dns_servers=network.dns_servers,
                        dns_search=network.dns_search,
                    ))
                else:
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
                        # Linux user configuration (cloud-init)
                        linux_username=vm.linux_username,
                        linux_password=vm.linux_password,
                        linux_user_sudo=vm.linux_user_sudo if vm.linux_user_sudo is not None else True,
                        # Network DNS configuration
                        gateway=network.gateway,
                        dns_servers=network.dns_servers,
                        dns_search=network.dns_search,
                        # Architecture selection
                        arch=vm.arch,
                    )
            elif os_type == OSType.MACOS:
                # macOS VM using dockur/macos
                settings = get_settings()

                # Setup VM-specific storage path
                vm_storage_path = os.path.join(
                    settings.vm_storage_dir,
                    str(vm.range_id),
                    str(vm.id),
                    "storage"
                )

                # Determine macOS version (VM setting takes priority)
                # Version codes: sequoia, sonoma, ventura, monterey, big-sur, catalina, mojave, high-sierra
                macos_version = vm.macos_version or "sequoia"

                # Check architecture compatibility
                # dockur/macos requires KVM and runs on x86_64 hosts
                # ARM (Apple Silicon) macOS is not supported via dockur/macos
                from cyroid.utils.arch import HOST_ARCH
                if HOST_ARCH == "arm64":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="macOS VMs are only supported on x86_64 hosts due to KVM requirements. "
                               "ARM hosts cannot run macOS VMs via dockur/macos."
                    )

                if use_dind:
                    # Create macOS VM inside DinD with dockur/macos
                    macos_env = {
                        "VERSION": macos_version,
                        "DISK_SIZE": f"{vm.disk_gb or 64}G",
                        "CPU_CORES": str(vm.cpu or 4),
                        "RAM_SIZE": f"{vm.ram_mb or 8192}M",
                        "DISPLAY": "web",  # macOS uses web VNC display
                        "KVM": "N",  # DinD typically doesn't have KVM access
                    }

                    container_id = asyncio.run(docker.create_range_container_dind(
                        range_id=str(vm.range_id),
                        docker_url=range_obj.dind_docker_url,
                        name=vm.hostname,
                        image="dockurr/macos",
                        network_name=network.name,
                        ip_address=vm.ip_address,
                        cpu_limit=vm.cpu or 4,
                        memory_limit_mb=vm.ram_mb or 8192,
                        hostname=vm.hostname,
                        labels=labels,
                        environment=macos_env,
                        privileged=True,
                        dns_servers=network.dns_servers,
                        dns_search=network.dns_search,
                    ))
                else:
                    container_id = docker.create_macos_container(
                        name=f"cyroid-{vm.hostname}-{str(vm.id)[:8]}",
                        network_id=network.docker_network_id,
                        ip_address=vm.ip_address,
                        cpu_limit=vm.cpu,
                        memory_limit_mb=vm.ram_mb,
                        disk_size_gb=vm.disk_gb,
                        macos_version=macos_version,
                        labels=labels,
                        storage_path=vm_storage_path,
                        display_type=vm.display_type or "desktop",
                    )
            elif vm_type == VMType.LINUX_VM:
                # Linux VM using qemux/qemu (ISO-based Linux installation)
                settings = get_settings()

                # Setup VM-specific storage path
                vm_storage_path = os.path.join(
                    settings.vm_storage_dir,
                    str(vm.range_id),
                    str(vm.id),
                    "storage"
                )

                # Get ISO path from VM or base_image
                iso_path = vm.iso_path
                if not iso_path and base_image_record and base_image_record.iso_path:
                    iso_path = base_image_record.iso_path

                # Get linux distro for auto-download (e.g., "kali", "ubuntu", "debian")
                # Valid qemux/qemu BOOT values: ubuntu, debian, fedora, kali, alpine, etc.
                VALID_QEMU_DISTROS = {"ubuntu", "debian", "fedora", "kali", "alpine", "mint", "centos", "rocky", "alma", "arch", "manjaro", "opensuse", "suse", "oracle", "rhel", "tinycore"}

                linux_distro = vm.linux_distro
                if not linux_distro and base_image_record:
                    # Try to extract distro from ISO path first (more reliable)
                    if base_image_record.iso_path:
                        # Extract distro name from path like "/data/cyroid/iso-cache/linux-isos/linux-kali.iso"
                        iso_filename = os.path.basename(base_image_record.iso_path)
                        if iso_filename.startswith("linux-"):
                            linux_distro = iso_filename.replace("linux-", "").replace(".iso", "")
                    # Fall back to iso_source only if it's a valid distro name
                    if not linux_distro and base_image_record.iso_source and base_image_record.iso_source.lower() in VALID_QEMU_DISTROS:
                        linux_distro = base_image_record.iso_source

                if use_dind:
                    # Create Linux VM inside DinD with qemux/qemu
                    linux_env = {
                        "DISK_SIZE": f"{vm.disk_gb or 40}G",
                        "CPU_CORES": str(vm.cpu or 2),
                        "RAM_SIZE": f"{vm.ram_mb or 4096}M",
                        "KVM": "N",  # DinD typically doesn't have KVM access
                    }

                    # Volume mounts for ISO
                    volumes = {}

                    # Priority: local ISO path > ISO URL > distro name (auto-download)
                    if iso_path and os.path.exists(iso_path):
                        # Mount the cached ISO into the container at /boot.iso
                        # DinD container has the ISO cache mounted, so path is accessible
                        volumes[iso_path] = {"bind": "/boot.iso", "mode": "ro"}
                        linux_env["BOOT"] = "/boot.iso"
                        logger.info(f"Using cached ISO for VM {vm.hostname}: {iso_path}")
                    elif vm.iso_url:
                        linux_env["BOOT"] = vm.iso_url
                    elif linux_distro:
                        linux_env["BOOT"] = linux_distro

                    container_id = asyncio.run(docker.create_range_container_dind(
                        range_id=str(vm.range_id),
                        docker_url=range_obj.dind_docker_url,
                        name=vm.hostname,
                        image="qemux/qemu",
                        network_name=network.name,
                        ip_address=vm.ip_address,
                        cpu_limit=vm.cpu or 2,
                        memory_limit_mb=vm.ram_mb or 4096,
                        hostname=vm.hostname,
                        labels=labels,
                        environment=linux_env,
                        volumes=volumes if volumes else None,
                        privileged=True,
                        dns_servers=network.dns_servers,
                        dns_search=network.dns_search,
                    ))
                else:
                    container_id = docker.create_linux_vm_container(
                        name=f"cyroid-{vm.hostname}-{str(vm.id)[:8]}",
                        network_id=network.docker_network_id,
                        ip_address=vm.ip_address,
                        cpu_limit=vm.cpu,
                        memory_limit_mb=vm.ram_mb,
                        disk_size_gb=vm.disk_gb,
                        linux_distro=linux_distro or "custom",
                        labels=labels,
                        iso_path=iso_path,
                        storage_path=vm_storage_path,
                        display_type=vm.display_type or "desktop",
                        # Extended configuration
                        disk2_gb=vm.disk2_gb,
                        disk3_gb=vm.disk3_gb,
                        # Linux user configuration (cloud-init)
                        linux_username=vm.linux_username,
                        linux_password=vm.linux_password,
                        linux_user_sudo=vm.linux_user_sudo if vm.linux_user_sudo is not None else True,
                        # Network DNS configuration
                        gateway=network.gateway,
                        dns_servers=network.dns_servers,
                        dns_search=network.dns_search,
                        # Architecture selection
                        arch=vm.arch,
                    )
            else:
                # Container (standard Docker container) or snapshot-based VM
                if use_dind:
                    # Build environment for LinuxServer/KasmVNC containers
                    environment = {}

                    # KasmVNC containers use VNC_PW for auto-auth
                    if "kasmweb/" in (image_ref or ""):
                        environment["VNC_PW"] = "vncpassword"

                    # LinuxServer containers use CUSTOM_USER, PASSWORD, SUDO_ACCESS
                    if "linuxserver/" in (image_ref or "") or "lscr.io/linuxserver" in (image_ref or ""):
                        if vm.linux_username:
                            environment["CUSTOM_USER"] = vm.linux_username
                            environment["PUID"] = "1000"
                            environment["PGID"] = "1000"
                        if vm.linux_password:
                            environment["PASSWORD"] = vm.linux_password
                        if vm.linux_user_sudo:
                            environment["SUDO_ACCESS"] = "true"

                    container_id = asyncio.run(docker.create_range_container_dind(
                        range_id=str(vm.range_id),
                        docker_url=range_obj.dind_docker_url,
                        name=vm.hostname,
                        image=image_ref,
                        network_name=network.name,
                        ip_address=vm.ip_address,
                        cpu_limit=vm.cpu or 2,
                        memory_limit_mb=vm.ram_mb or 2048,
                        hostname=vm.hostname,
                        labels=labels,
                        environment=environment if environment else None,
                        dns_servers=network.dns_servers,
                        dns_search=network.dns_search,
                    ))
                else:
                    container_id = docker.create_container(
                        name=f"cyroid-{vm.hostname}-{str(vm.id)[:8]}",
                        image=image_ref,
                        network_id=network.docker_network_id,
                        ip_address=vm.ip_address,
                        cpu_limit=vm.cpu,
                        memory_limit_mb=vm.ram_mb,
                        hostname=vm.hostname,
                        labels=labels,
                        # Linux user configuration (KasmVNC/LinuxServer env vars)
                        linux_username=vm.linux_username,
                        linux_password=vm.linux_password,
                        linux_user_sudo=vm.linux_user_sudo if vm.linux_user_sudo is not None else True,
                        # Network DNS configuration
                        dns_servers=network.dns_servers,
                        dns_search=network.dns_search,
                    )

            vm.container_id = container_id
            if use_dind:
                asyncio.run(docker.start_range_container_dind(
                    range_id=str(vm.range_id),
                    docker_url=range_obj.dind_docker_url,
                    container_id=container_id,
                ))
            else:
                docker.start_container(container_id)

            # Configure Linux user for KasmVNC and LinuxServer containers
            image_for_check = image_ref or ""
            if "kasmweb/" in image_for_check:
                # KasmVNC uses 'kasm-user' as the default user
                username = vm.linux_username or "kasm-user"
                if vm.linux_password:
                    if use_dind:
                        docker.set_linux_user_password_dind(
                            str(vm.range_id), range_obj.dind_docker_url,
                            container_id, username, vm.linux_password
                        )
                    else:
                        docker.set_linux_user_password(container_id, username, vm.linux_password)
                if vm.linux_user_sudo:
                    if use_dind:
                        docker.grant_sudo_privileges_dind(
                            str(vm.range_id), range_obj.dind_docker_url,
                            container_id, username
                        )
                    else:
                        docker.grant_sudo_privileges(container_id, username)
            elif "linuxserver/" in image_for_check or "lscr.io/linuxserver" in image_for_check:
                # LinuxServer containers use 'abc' as default user (or CUSTOM_USER from env)
                username = vm.linux_username or "abc"
                if vm.linux_password:
                    if use_dind:
                        docker.set_linux_user_password_dind(
                            str(vm.range_id), range_obj.dind_docker_url,
                            container_id, username, vm.linux_password
                        )
                    else:
                        docker.set_linux_user_password(container_id, username, vm.linux_password)
                if vm.linux_user_sudo:
                    if use_dind:
                        docker.grant_sudo_privileges_dind(
                            str(vm.range_id), range_obj.dind_docker_url,
                            container_id, username
                        )
                    else:
                        docker.grant_sudo_privileges(container_id, username)

        vm.status = VMStatus.RUNNING
        db.commit()
        db.refresh(vm)

        # Set up VNC port forwarding for DinD ranges (for VMs created after deployment or missing VNC)
        logger.info(f"VNC check: use_dind={use_dind}, container_id={vm.container_id}, ip={vm.ip_address}, vm_type={vm_type}")
        if use_dind and vm.container_id and vm.ip_address:
            # Check if this VM already has VNC mapping
            existing_mappings = range_obj.vnc_proxy_mappings or {}
            vm_id_str = str(vm.id)
            logger.info(f"VNC check for VM {vm_id_str}: existing mappings={list(existing_mappings.keys())}")

            if vm_id_str not in existing_mappings:
                logger.info(f"VNC mapping missing for VM {vm_id_str}, setting up...")
                # VNC mapping missing - set it up
                try:
                    from cyroid.services.dind_service import get_dind_service
                    from cyroid.services.traefik_route_service import get_traefik_route_service

                    dind_service = get_dind_service()
                    traefik_service = get_traefik_route_service()

                    # Determine VNC port based on VM type and image
                    # QEMU VMs (LINUX_VM, WINDOWS_VM) use port 8006 (noVNC)
                    # Containers use image-specific ports
                    vnc_port = 8006  # Default for QEMU VMs
                    if vm_type == VMType.CONTAINER:
                        # Container VMs have image-specific VNC ports
                        if "kasmweb" in (image_ref or ""):
                            vnc_port = 6901  # KasmVNC (HTTPS)
                        elif "linuxserver/" in (image_ref or "") or "lscr.io/linuxserver" in (image_ref or ""):
                            vnc_port = 3000  # LinuxServer webtop (HTTP)
                        else:
                            vnc_port = 3000  # Default for other containers
                    # LINUX_VM and WINDOWS_VM keep default 8006

                    vm_ports = [{
                        "vm_id": vm_id_str,
                        "hostname": vm.hostname,
                        "vnc_port": vnc_port,
                        "ip_address": vm.ip_address,
                    }]
                    logger.info(f"VNC setup: calling setup_vnc_port_forwarding for {vm_id_str} with port {vnc_port}")

                    # Log VNC setup event for frontend visibility
                    event_service = EventService(db)
                    event_service.log_event(
                        range_id=vm.range_id,
                        vm_id=vm.id,
                        event_type=EventType.VM_STARTED,
                        message=f"Setting up VNC port forwarding for {vm.hostname} (port {vnc_port})"
                    )

                    port_mappings = asyncio.run(dind_service.setup_vnc_port_forwarding(
                        range_id=str(vm.range_id),
                        vm_ports=vm_ports,
                        existing_mappings=existing_mappings,
                    ))
                    logger.info(f"VNC setup: port_mappings returned: {port_mappings}")

                    if port_mappings and vm_id_str in port_mappings:
                        # Merge new port mappings with existing ones - create new dict to trigger SQLAlchemy change detection
                        updated_mappings = dict(existing_mappings)
                        updated_mappings.update(port_mappings)
                        range_obj.vnc_proxy_mappings = updated_mappings
                        flag_modified(range_obj, "vnc_proxy_mappings")
                        db.commit()
                        db.refresh(range_obj)
                        logger.info(f"VNC setup: database updated with mappings for {vm_id_str}")

                        # Verify the update persisted
                        verified_mappings = range_obj.vnc_proxy_mappings or {}
                        if vm_id_str in verified_mappings:
                            logger.info(f"VNC setup: verified {vm_id_str} in database mappings")
                            mapping_info = verified_mappings[vm_id_str]
                            event_service.log_event(
                                range_id=vm.range_id,
                                vm_id=vm.id,
                                event_type=EventType.VM_STARTED,
                                message=f"VNC ready for {vm.hostname} at proxy port {mapping_info.get('proxy_port')}"
                            )
                        else:
                            logger.error(f"VNC setup: FAILED to persist {vm_id_str} to database!")
                            event_service.log_event(
                                range_id=vm.range_id,
                                vm_id=vm.id,
                                event_type=EventType.ERROR,
                                message=f"VNC database persistence failed for {vm.hostname}"
                            )

                        # Generate Traefik routes for VNC console access
                        route_file = traefik_service.generate_vnc_routes(str(vm.range_id), updated_mappings)
                        if route_file:
                            logger.info(f"VNC setup: Traefik routes generated at {route_file}")
                            event_service.log_event(
                                range_id=vm.range_id,
                                vm_id=vm.id,
                                event_type=EventType.VM_STARTED,
                                message=f"VNC routes configured for {vm.hostname}"
                            )
                        else:
                            logger.warning(f"VNC setup: Failed to generate Traefik routes for {vm.hostname}")
                            event_service.log_event(
                                range_id=vm.range_id,
                                vm_id=vm.id,
                                event_type=EventType.ERROR,
                                message=f"VNC route generation failed for {vm.hostname}"
                            )
                    else:
                        logger.error(f"VNC setup: No port mapping returned for {vm_id_str}")
                        event_service.log_event(
                            range_id=vm.range_id,
                            vm_id=vm.id,
                            event_type=EventType.ERROR,
                            message=f"VNC port forwarding failed for {vm.hostname} - no mapping returned"
                        )

                except Exception as e:
                    logger.error(f"VNC setup: Failed for {vm.hostname}: {e}", exc_info=True)
                    # Log error event for frontend visibility
                    try:
                        event_service = EventService(db)
                        event_service.log_event(
                            range_id=vm.range_id,
                            vm_id=vm.id,
                            event_type=EventType.ERROR,
                            message=f"VNC setup error for {vm.hostname}: {str(e)[:200]}"
                        )
                    except:
                        pass
                    # Don't fail the VM start if VNC forwarding fails

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
        if not range_obj:
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
        vm.error_message = str(e)[:1000]
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

    return vm_to_response(vm, base_image_record, golden_image_record, snapshot)


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
            # Check for DinD mode
            range_obj = db.query(Range).filter(Range.id == vm.range_id).first()
            use_dind = bool(range_obj and range_obj.dind_docker_url)

            if use_dind:
                asyncio.run(docker.stop_range_container_dind(
                    range_id=str(vm.range_id),
                    docker_url=range_obj.dind_docker_url,
                    container_id=vm.container_id,
                ))
            else:
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
        if not range_obj:
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

    base_image, golden_image, snapshot = load_vm_source(db, vm)
    return vm_to_response(vm, base_image, golden_image, snapshot)


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
        # Check if range uses DinD isolation with VNC proxy
        range_obj = db.query(Range).filter(Range.id == vm.range_id).first()

        # Check if this is a DinD range by looking for dind_container_id
        use_dind = range_obj and range_obj.dind_container_id is not None if range_obj else False

        if use_dind:
            # DinD range - VNC must be set up through proxy mappings
            proxy_mapping = None
            if range_obj.vnc_proxy_mappings:
                proxy_mapping = range_obj.vnc_proxy_mappings.get(str(vm.id))

            if proxy_mapping:
                # VNC proxy is configured - return connection info
                return {
                    "vm_id": str(vm.id),
                    "hostname": vm.hostname,
                    "path": f"/vnc/{vm.id}",
                    "websocket_path": f"vnc/{vm.id}",  # KasmVNC builds WS URL as host + path (Issue #77)
                    "proxy_host": proxy_mapping.get("proxy_host"),
                    "proxy_port": proxy_mapping.get("proxy_port"),
                    "method": "dind_proxy",
                }

            # VNC not configured for this VM in DinD range - try to set it up on-demand
            if vm.ip_address:
                try:
                    from cyroid.services.dind_service import get_dind_service
                    from cyroid.services.traefik_route_service import get_traefik_route_service

                    dind_service = get_dind_service()
                    traefik_service = get_traefik_route_service()

                    # Determine VNC port based on VM type and image
                    vnc_port = 8006  # Default for QEMU VMs (linux_vm, windows_vm)
                    if vm.base_image:
                        # Check vm_type first
                        if vm.base_image.vm_type == "container":
                            vnc_port = 3000  # Default for containers
                            # Check docker_image_tag for specific images
                            image_tag = vm.base_image.docker_image_tag or ""
                            if "kasmweb" in image_tag.lower():
                                vnc_port = 6901
                            elif "linuxserver/" in image_tag.lower() or "lscr.io/linuxserver" in image_tag.lower():
                                vnc_port = 3000

                    vm_ports = [{
                        "vm_id": str(vm.id),
                        "hostname": vm.hostname,
                        "vnc_port": vnc_port,
                        "ip_address": vm.ip_address,
                    }]

                    existing_mappings = range_obj.vnc_proxy_mappings or {}

                    port_mappings = asyncio.run(dind_service.setup_vnc_port_forwarding(
                        range_id=str(vm.range_id),
                        vm_ports=vm_ports,
                        existing_mappings=existing_mappings,
                    ))

                    existing_mappings.update(port_mappings)
                    range_obj.vnc_proxy_mappings = existing_mappings
                    db.commit()

                    # Generate Traefik routes
                    traefik_service.generate_vnc_routes(str(vm.range_id), existing_mappings)

                    proxy_mapping = port_mappings.get(str(vm.id))
                    if proxy_mapping:
                        logger.info(f"Set up VNC routing on-demand for VM {vm.hostname}")
                        return {
                            "vm_id": str(vm.id),
                            "hostname": vm.hostname,
                            "path": f"/vnc/{vm.id}",
                            "websocket_path": f"vnc/{vm.id}",  # KasmVNC builds WS URL as host + path (Issue #77)
                            "proxy_host": proxy_mapping.get("proxy_host"),
                            "proxy_port": proxy_mapping.get("proxy_port"),
                            "method": "dind_proxy",
                        }
                except Exception as e:
                    logger.warning(f"Failed to set up VNC routing on-demand for VM {vm.hostname}: {e}")

            # VNC routing failed for DinD range
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="VNC console not available - routing not configured for this VM",
            )

        # Standard (non-DinD) deployment - VNC is proxied through traefik at /vnc/{vm_id}
        vnc_path = f"/vnc/{vm.id}"

        # KasmVNC builds WebSocket URL as host + path, so use full vnc path (Issue #77)
        websocket_path = f"vnc/{vm.id}"

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


@router.get("/network/{network_id}/available-ips")
def get_network_available_ips(
    network_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100, description="Max IPs to return"),
):
    """
    Get a list of available IP addresses in a network subnet.

    Returns the next available IPs starting from .10 in the subnet,
    excluding the gateway and any IPs already assigned to VMs.
    """
    network = db.query(Network).filter(Network.id == network_id).first()
    if not network:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Network not found",
        )

    available_ips = get_available_ips_in_range(network, db, limit=limit)

    return {
        "network_id": str(network_id),
        "network_name": network.name,
        "subnet": network.subnet,
        "gateway": network.gateway,
        "available_ips": available_ips,
        "count": len(available_ips),
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
            # Check for DinD mode
            range_obj = db.query(Range).filter(Range.id == vm.range_id).first()
            use_dind = bool(range_obj and range_obj.dind_docker_url)

            if use_dind:
                # Restart via stop + start for DinD
                asyncio.run(docker.stop_range_container_dind(
                    range_id=str(vm.range_id),
                    docker_url=range_obj.dind_docker_url,
                    container_id=vm.container_id,
                ))
                asyncio.run(docker.start_range_container_dind(
                    range_id=str(vm.range_id),
                    docker_url=range_obj.dind_docker_url,
                    container_id=vm.container_id,
                ))
            else:
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
        vm.error_message = str(e)[:1000]
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

    base_image, golden_image, snapshot = load_vm_source(db, vm)
    return vm_to_response(vm, base_image, golden_image, snapshot)


@router.get("/{vm_id}/logs")
def get_vm_logs(
    vm_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    tail: int = Query(100, ge=10, le=1000, description="Number of log lines to retrieve"),
):
    """
    Fetch container logs for a VM.

    Returns the last N lines of the container's stdout/stderr with timestamps.
    For QEMU/Windows VMs, this shows hypervisor output, not guest OS logs.
    """
    vm = db.query(VM).filter(VM.id == vm_id).first()
    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found",
        )

    range_obj = db.query(Range).filter(Range.id == vm.range_id).first()
    if not range_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Range not found",
        )
    if range_obj.created_by != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )

    if not vm.container_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM has no container - it may not be deployed yet",
        )

    docker = get_docker_service()
    lines = docker.get_container_logs(vm.container_id, tail=tail)

    return {
        "vm_id": str(vm_id),
        "hostname": vm.hostname,
        "container_id": vm.container_id[:12],
        "tail": tail,
        "lines": lines,
        "note": "For QEMU/Windows VMs, these are hypervisor logs. Use the console for guest OS access.",
    }
