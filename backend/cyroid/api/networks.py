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
    Toggle internet access on/off for a network.

    If the range is deployed (DinD running), applies iptables rules immediately.
    If not deployed yet, just toggles the DB flag for use at next deployment.
    """
    network = db.query(Network).filter(Network.id == network_id).first()
    if not network:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Network not found",
        )

    new_state = not network.internet_enabled

    try:
        # If the range is deployed, apply iptables rules live
        range_obj = db.query(Range).filter(Range.id == network.range_id).first()
        if range_obj and range_obj.dind_docker_url and network.docker_network_id:
            from cyroid.services.dind_service import get_dind_service
            dind_service = get_dind_service()

            range_id_str = str(range_obj.id)
            dind_container = dind_service._find_container_by_range_id(range_id_str)

            if dind_container:
                range_client = dind_service.get_range_client(range_id_str, range_obj.dind_docker_url)
                bridge_id = dind_service._get_network_bridge_id(range_client, network.name)

                if bridge_id:
                    # Detect the outbound interface (carries the default route)
                    out_iface = dind_service._get_outbound_interface(dind_container)

                    if new_state:
                        # Enable internet — add FORWARD rule + ensure NAT/MASQUERADE
                        rules = [
                            f"iptables -A FORWARD -i br-{bridge_id} -o {out_iface} -j ACCEPT",
                            f"iptables -C FORWARD -i {out_iface} -m state --state ESTABLISHED,RELATED -j ACCEPT "
                            f"|| iptables -A FORWARD -i {out_iface} -m state --state ESTABLISHED,RELATED -j ACCEPT",
                            f"iptables -t nat -C POSTROUTING -o {out_iface} -j MASQUERADE "
                            f"|| iptables -t nat -A POSTROUTING -o {out_iface} -j MASQUERADE",
                        ]
                    else:
                        # Disable internet — remove FORWARD rule for this bridge
                        rules = [
                            f"iptables -D FORWARD -i br-{bridge_id} -o {out_iface} -j ACCEPT",
                        ]

                    for rule in rules:
                        exit_code, output = dind_container.exec_run(
                            ["sh", "-c", rule], privileged=True
                        )
                        if exit_code != 0:
                            output_str = output.decode() if isinstance(output, bytes) else str(output)
                            logger.debug(f"iptables rule result: {rule} -> {output_str}")

                    logger.info(f"Applied iptables rules for {'enabling' if new_state else 'disabling'} internet on {network.name}")
                else:
                    logger.warning(f"Could not resolve bridge ID for {network.name}, saving flag only")
            else:
                logger.debug(f"DinD container not found for range, saving flag only")

        network.internet_enabled = new_state
        db.commit()
        db.refresh(network)
        logger.info(f"{'Enabled' if new_state else 'Disabled'} internet for network {network.name}")

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
    Toggle DHCP flag on/off for a network.

    This sets the network's dhcp_enabled flag which is used during deployment
    to configure Docker network IPAM options.
    """
    network = db.query(Network).filter(Network.id == network_id).first()
    if not network:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Network not found",
        )

    try:
        network.dhcp_enabled = not network.dhcp_enabled
        db.commit()
        db.refresh(network)
        logger.info(f"{'Enabled' if network.dhcp_enabled else 'Disabled'} DHCP for network {network.name}")
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
