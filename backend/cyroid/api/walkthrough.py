# backend/cyroid/api/walkthrough.py
from uuid import UUID
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from cyroid.api.deps import get_db, get_current_user
from cyroid.models.user import User
from cyroid.models.range import Range
from cyroid.models.msel import MSEL
from cyroid.models.walkthrough_progress import WalkthroughProgress


router = APIRouter(prefix="/ranges", tags=["walkthrough"])


class WalkthroughResponse(BaseModel):
    walkthrough: Optional[dict] = None


class WalkthroughProgressResponse(BaseModel):
    range_id: UUID
    user_id: UUID
    completed_steps: List[str]
    current_phase: Optional[str]
    current_step: Optional[str]
    updated_at: str

    class Config:
        from_attributes = True


class WalkthroughProgressUpdate(BaseModel):
    completed_steps: List[str]
    current_phase: Optional[str] = None
    current_step: Optional[str] = None


@router.get("/{range_id}/walkthrough", response_model=WalkthroughResponse)
def get_walkthrough(
    range_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the walkthrough content for a range."""
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(status_code=404, detail="Range not found")

    msel = db.query(MSEL).filter(MSEL.range_id == range_id).first()
    walkthrough = msel.walkthrough if msel else None

    return WalkthroughResponse(walkthrough=walkthrough)


@router.get("/{range_id}/walkthrough/progress", response_model=Optional[WalkthroughProgressResponse])
def get_walkthrough_progress(
    range_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the user's progress through the walkthrough."""
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(status_code=404, detail="Range not found")

    progress = db.query(WalkthroughProgress).filter(
        WalkthroughProgress.range_id == range_id,
        WalkthroughProgress.user_id == current_user.id
    ).first()

    if not progress:
        return None

    return WalkthroughProgressResponse(
        range_id=progress.range_id,
        user_id=progress.user_id,
        completed_steps=progress.completed_steps or [],
        current_phase=progress.current_phase,
        current_step=progress.current_step,
        updated_at=progress.updated_at.isoformat()
    )


@router.put("/{range_id}/walkthrough/progress", response_model=WalkthroughProgressResponse)
def update_walkthrough_progress(
    range_id: UUID,
    data: WalkthroughProgressUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update the user's progress through the walkthrough."""
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(status_code=404, detail="Range not found")

    progress = db.query(WalkthroughProgress).filter(
        WalkthroughProgress.range_id == range_id,
        WalkthroughProgress.user_id == current_user.id
    ).first()

    if progress:
        progress.completed_steps = data.completed_steps
        progress.current_phase = data.current_phase
        progress.current_step = data.current_step
    else:
        progress = WalkthroughProgress(
            range_id=range_id,
            user_id=current_user.id,
            completed_steps=data.completed_steps,
            current_phase=data.current_phase,
            current_step=data.current_step
        )
        db.add(progress)

    db.commit()
    db.refresh(progress)

    return WalkthroughProgressResponse(
        range_id=progress.range_id,
        user_id=progress.user_id,
        completed_steps=progress.completed_steps or [],
        current_phase=progress.current_phase,
        current_step=progress.current_step,
        updated_at=progress.updated_at.isoformat()
    )
