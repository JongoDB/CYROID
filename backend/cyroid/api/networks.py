# backend/cyroid/api/networks.py
from typing import List
from uuid import UUID
import logging

from fastapi import APIRouter, HTTPException, status

from cyroid.api.deps import DBSession, CurrentUser
from cyroid.models.network import Network, IsolationLevel
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

        # Determine if network should be internal based on isolation level
        internal = network.isolation_level in [IsolationLevel.COMPLETE, IsolationLevel.CONTROLLED]

        docker_network_id = docker.create_network(
            name=f"cyroid-{network.name}-{str(network.id)[:8]}",
            subnet=network.subnet,
            gateway=network.gateway,
            internal=internal,
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
        # This allows management access without exposing VMs to traefik-routing
        docker.connect_traefik_to_network(docker_network_id)

        # Set up iptables rules to isolate this network from host/infrastructure
        # This prevents VMs from accessing CYROID services or the host
        docker.setup_network_isolation(docker_network_id, network.subnet)

        logger.info(f"Provisioned and isolated network {network.name} for VM routing")

    except Exception as e:
        logger.error(f"Failed to provision network {network_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to provision network: {str(e)}",
        )

    return network


@router.post("/{network_id}/isolate", response_model=NetworkResponse)
def isolate_network(network_id: UUID, db: DBSession, current_user: CurrentUser):
    """Apply iptables isolation rules to an existing provisioned network."""
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

        # Connect traefik if not already connected
        docker.connect_traefik_to_network(network.docker_network_id)

        # Set up iptables rules
        docker.setup_network_isolation(network.docker_network_id, network.subnet)

        logger.info(f"Applied isolation rules to network {network.name}")

    except Exception as e:
        logger.error(f"Failed to isolate network {network_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to isolate network: {str(e)}",
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
        db.commit()
        db.refresh(network)

    except Exception as e:
        logger.error(f"Failed to teardown network {network_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to teardown network: {str(e)}",
        )

    return network
