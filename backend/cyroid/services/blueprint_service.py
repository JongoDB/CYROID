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
            name=f"{range_obj.name} Scenario",
            content=config.msel.content,
        )
        db.add(msel)

    db.flush()
    return range_obj
