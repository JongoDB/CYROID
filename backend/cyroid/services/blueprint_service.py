# backend/cyroid/services/blueprint_service.py
"""
Blueprint service for creating ranges from blueprint configurations.

All ranges use DinD (Docker-in-Docker) isolation, so IP offset logic is not
needed. Each range runs in its own isolated network namespace inside a DinD
container, allowing multiple ranges to use identical IP spaces.
"""
import re
from typing import Dict, Any, List
from uuid import UUID
from sqlalchemy.orm import Session

from cyroid.models import Range, Network, VM, MSEL, RangeRouter
from cyroid.models.base_image import BaseImage
from cyroid.models.vm_network import VMNetwork
from cyroid.schemas.blueprint import BlueprintConfig, NetworkConfig, VMConfig, RouterConfig, MSELConfig, NetworkInterfaceConfig


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
        # Get fallback identifiers for cross-environment portability (Issue #80)
        base_image_name = None
        base_image_tag = None
        if vm.base_image_id:
            base_image = db.query(BaseImage).filter(BaseImage.id == vm.base_image_id).first()
            if base_image:
                base_image_name = base_image.name
                base_image_tag = base_image.docker_image_tag

        # Check for multi-NIC configuration (VMNetwork records)
        vm_networks = db.query(VMNetwork).filter(VMNetwork.vm_id == vm.id).order_by(
            VMNetwork.is_primary.desc()  # Primary first
        ).all()

        if vm_networks:
            # Multi-NIC path: export all network interfaces
            network_interfaces = [
                NetworkInterfaceConfig(
                    network_name=network_lookup.get(vn.network_id, "unknown"),
                    ip_address=vn.ip_address,
                    is_primary=vn.is_primary,
                )
                for vn in vm_networks
            ]
            # Primary interface also populates legacy fields for backward compatibility
            primary = vm_networks[0]
            ip_address = primary.ip_address
            network_name = network_lookup.get(primary.network_id, "unknown")
        else:
            # Legacy single-NIC path (VMs created before multi-NIC support)
            network_interfaces = None
            ip_address = vm.ip_address
            network_name = network_lookup.get(vm.network_id, "unknown")

        vm_configs.append(
            VMConfig(
                hostname=vm.hostname,
                ip_address=ip_address,
                network_name=network_name,
                network_interfaces=network_interfaces,
                base_image_id=str(vm.base_image_id) if vm.base_image_id else None,
                golden_image_id=str(vm.golden_image_id) if vm.golden_image_id else None,
                snapshot_id=str(vm.snapshot_id) if vm.snapshot_id else None,
                base_image_name=base_image_name,
                base_image_tag=base_image_tag,
                cpu=vm.cpu,
                ram_mb=vm.ram_mb,
                disk_gb=vm.disk_gb,
                position_x=vm.position_x,
                position_y=vm.position_y,
                environment=vm.environment,
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
    Create a new Range from blueprint config with exact blueprint IPs.

    All ranges use DinD isolation, so no IP translation is needed.
    The offset parameter is kept for API compatibility but is ignored.

    Args:
        db: Database session
        config: Blueprint configuration
        range_name: Name for the new range
        base_prefix: Base subnet prefix (kept for API compatibility)
        offset: Subnet offset (ignored - DinD provides isolation)
        created_by: User ID of creator

    Returns:
        Created Range object (not yet deployed)
    """
    from cyroid.models import Range, Network, VM, MSEL, RangeRouter, RangeStatus
    from cyroid.models.base_image import BaseImage

    # Create range
    range_obj = Range(
        name=range_name,
        description=f"Instance from blueprint (DinD isolated)",
        created_by=created_by,
        status=RangeStatus.DRAFT,
    )
    db.add(range_obj)
    db.flush()

    # Create networks with exact blueprint IPs
    network_lookup: Dict[str, UUID] = {}
    for net_config in config.networks:
        network = Network(
            range_id=range_obj.id,
            name=net_config.name,
            subnet=net_config.subnet,
            gateway=net_config.gateway,
            is_isolated=net_config.is_isolated,
        )
        db.add(network)
        db.flush()
        network_lookup[net_config.name] = network.id

    # Create VMs with exact blueprint IPs
    for vm_config in config.vms:
        # Determine primary network assignment
        if vm_config.network_interfaces:
            # Multi-NIC path: find primary interface
            primary_iface = next(
                (i for i in vm_config.network_interfaces if i.is_primary),
                vm_config.network_interfaces[0]  # Default to first if no primary marked
            )
            network_id = network_lookup.get(primary_iface.network_name)
            ip_address = primary_iface.ip_address
        else:
            # Legacy single-NIC path
            network_id = network_lookup.get(vm_config.network_name)
            ip_address = vm_config.ip_address

        if not network_id:
            continue  # Skip VMs with missing networks

        # Resolve image source from vm_config with fallback chain (Issue #80)
        from uuid import UUID as UUID_type
        base_image_id = None
        golden_image_id = None
        snapshot_id = None

        # Try base_image_id first
        if vm_config.base_image_id:
            try:
                candidate_id = UUID_type(vm_config.base_image_id)
                # Check if UUID exists in database
                if db.query(BaseImage).filter(BaseImage.id == candidate_id).first():
                    base_image_id = candidate_id
            except (ValueError, TypeError):
                pass

        # Fallback: lookup by name if UUID didn't work (Issue #80)
        if not base_image_id and hasattr(vm_config, 'base_image_name') and vm_config.base_image_name:
            fallback_image = db.query(BaseImage).filter(BaseImage.name == vm_config.base_image_name).first()
            if fallback_image:
                base_image_id = fallback_image.id

        # Fallback: lookup by docker image tag if name didn't work (Issue #80)
        if not base_image_id and hasattr(vm_config, 'base_image_tag') and vm_config.base_image_tag:
            tag = vm_config.base_image_tag
            # Try exact match first
            fallback_image = db.query(BaseImage).filter(BaseImage.docker_image_tag == tag).first()
            # If no match and tag has registry prefix, try without it (e.g., 127.0.0.1:5000/cyroid/kali -> cyroid/kali)
            if not fallback_image and '/' in tag:
                # Strip registry prefix (anything before first slash that contains a dot or colon)
                parts = tag.split('/', 1)
                if len(parts) == 2 and ('.' in parts[0] or ':' in parts[0]):
                    tag_without_registry = parts[1]
                    fallback_image = db.query(BaseImage).filter(BaseImage.docker_image_tag == tag_without_registry).first()
            if fallback_image:
                base_image_id = fallback_image.id

        # Fallback: lookup by template_name (for seed blueprints and backward compatibility)
        if not base_image_id and hasattr(vm_config, 'template_name') and vm_config.template_name:
            fallback_image = db.query(BaseImage).filter(BaseImage.name == vm_config.template_name).first()
            if fallback_image:
                base_image_id = fallback_image.id

        # Try golden_image_id (no fallback chain yet)
        if vm_config.golden_image_id:
            try:
                golden_image_id = UUID_type(vm_config.golden_image_id)
            except (ValueError, TypeError):
                pass

        # Try snapshot_id (no fallback chain yet)
        if vm_config.snapshot_id:
            try:
                snapshot_id = UUID_type(vm_config.snapshot_id)
            except (ValueError, TypeError):
                pass

        if not base_image_id and not golden_image_id and not snapshot_id:
            continue  # Skip VMs with no resolvable image source

        vm = VM(
            range_id=range_obj.id,
            network_id=network_id,
            base_image_id=base_image_id,
            golden_image_id=golden_image_id,
            snapshot_id=snapshot_id,
            hostname=vm_config.hostname,
            ip_address=ip_address,
            cpu=vm_config.cpu,
            ram_mb=vm_config.ram_mb,
            disk_gb=vm_config.disk_gb,
            position_x=vm_config.position_x,
            position_y=vm_config.position_y,
            windows_version=vm_config.windows_version,
            environment=vm_config.environment,
        )
        db.add(vm)
        db.flush()  # Get VM ID for VMNetwork records

        # Create VMNetwork records for multi-NIC VMs
        if vm_config.network_interfaces:
            # Track which networks we've already added to prevent duplicates
            seen_network_ids = set()
            for idx, iface in enumerate(vm_config.network_interfaces):
                iface_network_id = network_lookup.get(iface.network_name)
                if not iface_network_id:
                    continue  # Skip interfaces with missing networks

                # Skip duplicate network assignments (same network can only be connected once per VM)
                if iface_network_id in seen_network_ids:
                    continue
                seen_network_ids.add(iface_network_id)

                # Determine if this is the primary interface
                is_primary = iface.is_primary or (idx == 0 and not any(i.is_primary for i in vm_config.network_interfaces))

                vm_network = VMNetwork(
                    vm_id=vm.id,
                    network_id=iface_network_id,
                    ip_address=iface.ip_address,  # May be None for auto-assign on deploy
                    is_primary=is_primary,
                )
                db.add(vm_network)

    # Create MSEL if present
    if config.msel and (config.msel.content or config.msel.walkthrough):
        msel = MSEL(
            range_id=range_obj.id,
            name=f"{range_obj.name} Scenario",
            content=config.msel.content or "",
            walkthrough=config.msel.walkthrough,
        )
        db.add(msel)

    # Link student guide from blueprint's content_ids (static reference, not duplicated)
    # Content is created during blueprint import and shared across all range instances
    # Run migration to populate content_ids for existing blueprints with MSEL walkthrough
    if config.content_ids:
        from uuid import UUID as UUID_type
        from cyroid.models.content import Content

        # Use first content_id as student guide (typically the walkthrough)
        for cid in config.content_ids:
            try:
                content_uuid = UUID_type(cid)
                if db.query(Content).filter(Content.id == content_uuid).first():
                    range_obj.student_guide_id = content_uuid
                    break
            except (ValueError, TypeError):
                continue

    db.flush()
    return range_obj
