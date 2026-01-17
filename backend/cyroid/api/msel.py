# backend/cyroid/api/msel.py
from uuid import UUID
from typing import List, Optional, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from cyroid.api.deps import get_db, get_current_user
from cyroid.models.user import User
from cyroid.models.range import Range
from cyroid.models.msel import MSEL
from cyroid.models.inject import Inject, InjectStatus
from cyroid.services.msel_parser import MSELParser
from cyroid.services.inject_service import InjectService
from cyroid.services.docker_service import DockerService, get_docker_service
from cyroid.models.vm import VM

router = APIRouter(prefix="/msel", tags=["msel"])


class MSELImport(BaseModel):
    name: str
    content: str


class InjectResponse(BaseModel):
    id: UUID
    sequence_number: int
    inject_time_minutes: int
    title: str
    description: Optional[str]
    actions: List[Any]
    status: str
    executed_at: Optional[datetime]

    class Config:
        from_attributes = True


class MSELResponse(BaseModel):
    id: UUID
    name: str
    range_id: UUID
    content: Optional[str] = None
    walkthrough: Optional[dict] = None
    injects: List[InjectResponse]

    class Config:
        from_attributes = True


@router.post("/{range_id}/import", status_code=201, response_model=MSELResponse)
def import_msel(
    range_id: UUID,
    data: MSELImport,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Import an MSEL document for a range."""
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(status_code=404, detail="Range not found")
    if range_obj.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Delete existing MSEL if any
    existing = db.query(MSEL).filter(MSEL.range_id == range_id).first()
    if existing:
        db.delete(existing)
        db.commit()

    # Parse MSEL
    parser = MSELParser()
    parsed_injects = parser.parse(data.content)
    walkthrough = parser.parse_walkthrough(data.content)

    # Create MSEL
    msel = MSEL(
        range_id=range_id,
        name=data.name,
        content=data.content,
        walkthrough=walkthrough
    )
    db.add(msel)
    db.commit()
    db.refresh(msel)

    # Create Injects
    for inject_data in parsed_injects:
        inject = Inject(
            msel_id=msel.id,
            sequence_number=inject_data['sequence_number'],
            inject_time_minutes=inject_data['inject_time_minutes'],
            title=inject_data['title'],
            description=inject_data.get('description', ''),
            actions=inject_data['actions']
        )
        db.add(inject)

    db.commit()

    # Return with injects
    injects = db.query(Inject).filter(Inject.msel_id == msel.id).order_by(Inject.sequence_number).all()

    return MSELResponse(
        id=msel.id,
        name=msel.name,
        range_id=msel.range_id,
        walkthrough=msel.walkthrough,
        injects=[
            InjectResponse(
                id=i.id,
                sequence_number=i.sequence_number,
                inject_time_minutes=i.inject_time_minutes,
                title=i.title,
                description=i.description,
                actions=i.actions or [],
                status=i.status.value,
                executed_at=i.executed_at
            )
            for i in injects
        ]
    )


@router.get("/{range_id}", response_model=MSELResponse)
def get_msel(
    range_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the MSEL for a range."""
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(status_code=404, detail="Range not found")
    if range_obj.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    msel = db.query(MSEL).filter(MSEL.range_id == range_id).first()
    if not msel:
        raise HTTPException(status_code=404, detail="No MSEL found for this range")

    injects = db.query(Inject).filter(Inject.msel_id == msel.id).order_by(Inject.sequence_number).all()

    return MSELResponse(
        id=msel.id,
        name=msel.name,
        range_id=msel.range_id,
        content=msel.content,
        walkthrough=msel.walkthrough,
        injects=[
            InjectResponse(
                id=i.id,
                sequence_number=i.sequence_number,
                inject_time_minutes=i.inject_time_minutes,
                title=i.title,
                description=i.description,
                actions=i.actions or [],
                status=i.status.value,
                executed_at=i.executed_at
            )
            for i in injects
        ]
    )


@router.delete("/{range_id}", status_code=204)
def delete_msel(
    range_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete the MSEL for a range."""
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(status_code=404, detail="Range not found")
    if range_obj.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    msel = db.query(MSEL).filter(MSEL.range_id == range_id).first()
    if not msel:
        raise HTTPException(status_code=404, detail="No MSEL found for this range")

    db.delete(msel)
    db.commit()


class InjectExecutionResponse(BaseModel):
    success: bool
    inject_id: UUID
    status: str
    results: List[Any]


@router.post("/inject/{inject_id}/execute", response_model=InjectExecutionResponse)
def execute_inject(
    inject_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    docker_service: DockerService = Depends(get_docker_service)
):
    """Execute an inject manually."""
    inject = db.query(Inject).filter(Inject.id == inject_id).first()
    if not inject:
        raise HTTPException(status_code=404, detail="Inject not found")

    msel = db.query(MSEL).filter(MSEL.id == inject.msel_id).first()
    if not msel:
        raise HTTPException(status_code=404, detail="MSEL not found")

    range_obj = db.query(Range).filter(Range.id == msel.range_id).first()
    if not range_obj:
        raise HTTPException(status_code=404, detail="Range not found")

    if range_obj.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Check inject status
    if inject.status == InjectStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Inject already executed")
    if inject.status == InjectStatus.EXECUTING:
        raise HTTPException(status_code=400, detail="Inject already executing")

    # Build VM map by hostname
    vms = db.query(VM).filter(VM.range_id == range_obj.id).all()
    vm_map = {vm.hostname: vm for vm in vms}

    # Execute inject
    service = InjectService(db, docker_service)
    result = service.execute_inject(inject, vm_map)

    return InjectExecutionResponse(
        success=result['success'],
        inject_id=inject.id,
        status=inject.status.value,
        results=result.get('results', [])
    )


@router.post("/inject/{inject_id}/skip", status_code=200)
def skip_inject(
    inject_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Skip an inject."""
    inject = db.query(Inject).filter(Inject.id == inject_id).first()
    if not inject:
        raise HTTPException(status_code=404, detail="Inject not found")

    msel = db.query(MSEL).filter(MSEL.id == inject.msel_id).first()
    range_obj = db.query(Range).filter(Range.id == msel.range_id).first()

    if range_obj.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if inject.status != InjectStatus.PENDING:
        raise HTTPException(status_code=400, detail="Can only skip pending injects")

    inject.status = InjectStatus.SKIPPED
    inject.execution_log = "Skipped by user"
    db.commit()

    return {"status": "skipped", "inject_id": str(inject.id)}
