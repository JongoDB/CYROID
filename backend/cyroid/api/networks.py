# backend/cyroid/api/networks.py
from typing import List
from uuid import UUID
import logging

from fastapi import APIRouter, HTTPException, status

from cyroid.api.deps import DBSession, CurrentUser
from cyroid.models.network import Network
from cyroid.models.range import Range
from cyroid.schemas.network import NetworkCreate, NetworkUpdate, NetworkResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/networks", tags=["Networks"])


def get_docker_service():
    """Lazy import to avoid Docker connection issues during testing."""
    from cyroid.services.docker_service import get_docker_service as _get_docker_service
    return _get_docker_service()


@router.get("", response_model=List[NetworkResponse])
def list_networks(range_id: UUID, db: DBSession, current_user: CurrentUser):
    """List all networks in a range"""
    # Verify range exists and user has access
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Range not found",
        )

    networks = db.query(Network).filter(Network.range_id == range_id).all()
    return networks


@router.post("", response_model=NetworkResponse, status_code=status.HTTP_201_CREATED)
def create_network(network_data: NetworkCreate, db: DBSession, current_user: CurrentUser):
    # Verify range exists
    range_obj = db.query(Range).filter(Range.id == network_data.range_id).first()
    if not range_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Range not found",
        )

    # Check for duplicate subnet in the same range
    existing = db.query(Network).filter(
        Network.range_id == network_data.range_id,
        Network.subnet == network_data.subnet
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subnet already exists in this range",
        )

    network = Network(**network_data.model_dump())
    db.add(network)
    db.commit()
    db.refresh(network)
    return network


@router.get("/{network_id}", response_model=NetworkResponse)
def get_network(network_id: UUID, db: DBSession, current_user: CurrentUser):
    network = db.query(Network).filter(Network.id == network_id).first()
    if not network:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Network not found",
        )
    return network


@router.put("/{network_id}", response_model=NetworkResponse)
def update_network(
    network_id: UUID,
    network_data: NetworkUpdate,
    db: DBSession,
    current_user: CurrentUser,
):
    network = db.query(Network).filter(Network.id == network_id).first()
    if not network:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Network not found",
        )

    update_data = network_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(network, field, value)

    db.commit()
    db.refresh(network)
    return network


@router.delete("/{network_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_network(network_id: UUID, db: DBSession, current_user: CurrentUser):
    network = db.query(Network).filter(Network.id == network_id).first()
    if not network:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Network not found",
        )

    # Check if network has VMs attached
    if network.vms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete network with attached VMs",
        )

    # Remove Docker network if it exists
    if network.docker_network_id:
        try:
            docker = get_docker_service()
            docker.delete_network(network.docker_network_id)
        except Exception as e:
            logger.warning(f"Failed to delete Docker network: {e}")

    db.delete(network)
    db.commit()


@router.post("/{network_id}/provision", response_model=NetworkResponse)
def provision_network(network_id: UUID, db: DBSession, current_user: CurrentUser):
    """Provision a Docker network for this network configuration."""
    network = db.query(Network).filter(Network.id == network_id).first()
    if not network:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Network not found",
        )

    if network.docker_network_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Network already provisioned",
        )

    try:
        docker = get_docker_service()

        # Create Docker network
        # internal=False: VyOS router handles isolation via firewall rules,
        # not Docker's internal network flag (which blocks all external traffic)
        docker_network_id = docker.create_network(
            name=f"cyroid-{network.name}-{str(network.id)[:8]}",
            subnet=network.subnet,
            gateway=network.gateway,
            internal=False,
            labels={
                "cyroid.range_id": str(network.range_id),
                "cyroid.network_id": str(network.id),
                "cyroid.network_name": network.name,
            }
        )

        network.docker_network_id = docker_network_id
        db.commit()
        db.refresh(network)

        # Connect traefik to this network for VNC/web console routing
        docker.connect_traefik_to_network(docker_network_id)

        # If isolated, set up iptables rules to block access to host/infrastructure
        if network.is_isolated:
            docker.setup_network_isolation(docker_network_id, network.subnet)

        logger.info(f"Provisioned network {network.name} (isolated={network.is_isolated})")

    except Exception as e:
        logger.error(f"Failed to provision network {network_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to provision network: {str(e)}",
        )

    return network


@router.post("/{network_id}/toggle-isolation", response_model=NetworkResponse)
def toggle_network_isolation(network_id: UUID, db: DBSession, current_user: CurrentUser):
    """Toggle network isolation on/off for a provisioned network."""
    network = db.query(Network).filter(Network.id == network_id).first()
    if not network:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Network not found",
        )

    if not network.docker_network_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Network not provisioned",
        )

    try:
        docker = get_docker_service()

        if network.is_isolated:
            # Remove isolation
            docker.teardown_network_isolation(network.docker_network_id, network.subnet)
            network.is_isolated = False
            logger.info(f"Removed isolation from network {network.name}")
        else:
            # Apply isolation
            docker.connect_traefik_to_network(network.docker_network_id)
            docker.setup_network_isolation(network.docker_network_id, network.subnet)
            network.is_isolated = True
            logger.info(f"Applied isolation to network {network.name}")

        db.commit()
        db.refresh(network)

    except Exception as e:
        logger.error(f"Failed to toggle isolation for network {network_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle isolation: {str(e)}",
        )

    return network


@router.post("/{network_id}/toggle-internet", response_model=NetworkResponse)
def toggle_network_internet(network_id: UUID, db: DBSession, current_user: CurrentUser):
    """
    Toggle internet access on/off for a provisioned network.

    When enabled, VyOS router provides NAT masquerade for this network via eth0
    (management interface). Traffic flows: VM → VyOS NAT → Docker bridge NAT → Internet.

    This leverages Docker's native NAT on the management bridge for internet access,
    eliminating the need for complex macvlan configurations.
    """
    from cyroid.models.router import RangeRouter, RouterStatus

    network = db.query(Network).filter(Network.id == network_id).first()
    if not network:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Network not found",
        )

    if not network.docker_network_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Network not provisioned. Deploy the range first.",
        )

    # Get the VyOS router for this range
    router = db.query(RangeRouter).filter(RangeRouter.range_id == network.range_id).first()
    if not router or not router.container_id or router.status != RouterStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VyOS router not available. Deploy the range first.",
        )

    if not network.vyos_interface:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Network not connected to VyOS router",
        )

    try:
        from cyroid.services.vyos_service import get_vyos_service
        vyos = get_vyos_service()

        # Use eth0 (management interface) for outbound NAT
        # Docker's NAT on the management bridge will forward traffic to the internet
        outbound_interface = "eth0"

        if network.internet_enabled:
            # Disable internet access - remove NAT rule
            vyos.remove_internet_nat(router.container_id, network.subnet, outbound_interface)
            network.internet_enabled = False
            logger.info(f"Disabled internet for network {network.name}")
        else:
            # Enable internet access - add NAT masquerade rule via eth0
            if not vyos.configure_internet_nat(
                router.container_id,
                network.subnet,
                outbound_interface
            ):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to configure NAT for internet access",
                )
            network.internet_enabled = True
            logger.info(f"Enabled internet for network {network.name} via Docker bridge NAT")

        db.commit()
        db.refresh(network)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle internet for network {network_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle internet: {str(e)}",
        )

    return network


@router.post("/{network_id}/toggle-dhcp", response_model=NetworkResponse)
def toggle_network_dhcp(network_id: UUID, db: DBSession, current_user: CurrentUser):
    """
    Toggle DHCP server on/off for a provisioned network.

    When enabled, VyOS router provides DHCP for this network, assigning IPs
    to VMs/containers that use DHCP. The DHCP range is automatically calculated
    from the subnet (.10 to .250 for /24 networks).
    """
    from cyroid.models.router import RangeRouter, RouterStatus

    network = db.query(Network).filter(Network.id == network_id).first()
    if not network:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Network not found",
        )

    if not network.docker_network_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Network not provisioned. Deploy the range first.",
        )

    # Get the VyOS router for this range
    router = db.query(RangeRouter).filter(RangeRouter.range_id == network.range_id).first()
    if not router or not router.container_id or router.status != RouterStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VyOS router not available. Deploy the range first.",
        )

    try:
        from cyroid.services.vyos_service import get_vyos_service
        vyos = get_vyos_service()

        if network.dhcp_enabled:
            # Disable DHCP - remove DHCP server config
            vyos.remove_dhcp_server(router.container_id, network.name, network.subnet)
            network.dhcp_enabled = False
            logger.info(f"Disabled DHCP for network {network.name}")
        else:
            # Enable DHCP - configure DHCP server
            if not vyos.configure_dhcp_server(
                container_id=router.container_id,
                network_name=network.name,
                subnet=network.subnet,
                gateway=network.gateway,
                dns_servers=network.dns_servers,
                dns_search=network.dns_search
            ):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to configure DHCP server",
                )
            network.dhcp_enabled = True
            logger.info(f"Enabled DHCP for network {network.name}")

        db.commit()
        db.refresh(network)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle DHCP for network {network_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle DHCP: {str(e)}",
        )

    return network


@router.post("/{network_id}/teardown", response_model=NetworkResponse)
def teardown_network(network_id: UUID, db: DBSession, current_user: CurrentUser):
    """Remove the Docker network for this network configuration."""
    network = db.query(Network).filter(Network.id == network_id).first()
    if not network:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Network not found",
        )

    if not network.docker_network_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Network not provisioned",
        )

    # Check if network has running VMs
    running_vms = [vm for vm in network.vms if vm.container_id]
    if running_vms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot teardown network with running VMs",
        )

    try:
        docker = get_docker_service()

        # Remove iptables isolation rules
        docker.teardown_network_isolation(network.docker_network_id, network.subnet)

        # Disconnect traefik from the network before deleting
        docker.disconnect_traefik_from_network(network.docker_network_id)

        docker.delete_network(network.docker_network_id)

        network.docker_network_id = None
        network.is_isolated = False
        db.commit()
        db.refresh(network)

    except Exception as e:
        logger.error(f"Failed to teardown network {network_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to teardown network: {str(e)}",
        )

    return network
