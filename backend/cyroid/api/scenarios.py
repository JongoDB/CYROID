# backend/cyroid/api/scenarios.py
"""Scenarios API endpoints for training scenarios."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from cyroid.api.deps import get_db, get_current_user
from cyroid.models.scenario import Scenario
from cyroid.models.user import User
from cyroid.schemas.scenario import ScenarioListResponse, ScenarioDetailResponse

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("", response_model=List[ScenarioListResponse])
def list_scenarios(
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all available training scenarios.

    Args:
        category: Filter by category (red-team, blue-team, insider-threat)
        difficulty: Filter by difficulty (beginner, intermediate, advanced)

    Returns:
        List of scenarios without event details.
    """
    query = db.query(Scenario)

    if category:
        query = query.filter(Scenario.category == category)
    if difficulty:
        query = query.filter(Scenario.difficulty == difficulty)

    scenarios = query.order_by(Scenario.category, Scenario.difficulty).all()
    return scenarios


@router.get("/{scenario_id}", response_model=ScenarioDetailResponse)
def get_scenario(
    scenario_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a scenario with full event details.

    Args:
        scenario_id: UUID of the scenario to retrieve.

    Returns:
        Full scenario details including all events.
    """
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scenario
