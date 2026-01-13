# backend/cyroid/api/connections.py
from uuid import UUID
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from cyroid.api.deps import get_db, get_current_user
from cyroid.models.user import User
from cyroid.models.range import Range
from cyroid.models.vm import VM
from cyroid.models.connection import ConnectionProtocol, ConnectionState
from cyroid.services.connection_service import ConnectionService

router = APIRouter(prefix="/connections", tags=["connections"])


class ConnectionResponse(BaseModel):
    id: UUID
    range_id: UUID
    src_vm_id: Optional[UUID]
    src_ip: str
    src_port: int
    dst_vm_id: Optional[UUID]
    dst_ip: str
    dst_port: int
    protocol: ConnectionProtocol
    state: ConnectionState
    bytes_sent: int
    bytes_received: int
    started_at: datetime
    ended_at: Optional[datetime]

    class Config:
        from_attributes = True


class ConnectionListResponse(BaseModel):
    connections: List[ConnectionResponse]
    total: int


@router.get("/{range_id}", response_model=ConnectionListResponse)
def get_range_connections(
    range_id: UUID,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get connections for a range."""
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(status_code=404, detail="Range not found")
    if range_obj.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    service = ConnectionService(db)
    connections, total = service.get_connections(range_id, limit, offset, active_only)

    return ConnectionListResponse(
        connections=[ConnectionResponse.model_validate(c) for c in connections],
        total=total
    )


@router.get("/vm/{vm_id}", response_model=List[ConnectionResponse])
def get_vm_connections(
    vm_id: UUID,
    direction: str = Query("both", pattern="^(both|incoming|outgoing)$"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get connections for a specific VM."""
    vm = db.query(VM).filter(VM.id == vm_id).first()
    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")

    range_obj = db.query(Range).filter(Range.id == vm.range_id).first()
    if range_obj.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    service = ConnectionService(db)
    connections = service.get_vm_connections(vm_id, direction, limit)

    return [ConnectionResponse.model_validate(c) for c in connections]
