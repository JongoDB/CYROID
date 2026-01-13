# backend/cyroid/api/events.py
from uuid import UUID
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from cyroid.api.deps import get_db, get_current_user
from cyroid.models.user import User
from cyroid.models.range import Range
from cyroid.models.vm import VM
from cyroid.models.event_log import EventType
from cyroid.schemas.event_log import EventLogResponse, EventLogList
from cyroid.services.event_service import EventService

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/{range_id}", response_model=EventLogList)
def get_range_events(
    range_id: UUID,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    event_types: Optional[List[EventType]] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(status_code=404, detail="Range not found")
    if range_obj.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    service = EventService(db)
    events, total = service.get_events(range_id, limit, offset, event_types)

    return EventLogList(
        events=[EventLogResponse.model_validate(e) for e in events],
        total=total
    )


@router.get("/vm/{vm_id}", response_model=List[EventLogResponse])
def get_vm_events(
    vm_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    vm = db.query(VM).filter(VM.id == vm_id).first()
    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")

    range_obj = db.query(Range).filter(Range.id == vm.range_id).first()
    if range_obj.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    service = EventService(db)
    events = service.get_vm_events(vm_id, limit)

    return [EventLogResponse.model_validate(e) for e in events]
