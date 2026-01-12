# backend/cyroid/api/networks.py
from typing import List
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from cyroid.api.deps import DBSession, CurrentUser
from cyroid.models.network import Network
from cyroid.models.range import Range
from cyroid.schemas.network import NetworkCreate, NetworkUpdate, NetworkResponse

router = APIRouter(prefix="/networks", tags=["Networks"])


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

    db.delete(network)
    db.commit()
