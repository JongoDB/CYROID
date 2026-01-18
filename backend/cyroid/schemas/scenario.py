# backend/cyroid/schemas/scenario.py
from datetime import datetime
from typing import Optional, List, Any
from uuid import UUID
from pydantic import BaseModel, Field


class ScenarioEvent(BaseModel):
    """A single event within a scenario."""
    sequence: int
    delay_minutes: int
    title: str
    description: Optional[str] = None
    target_role: str
    actions: List[dict] = Field(default_factory=list)


class ScenarioBase(BaseModel):
    """Base scenario fields."""
    name: str = Field(..., min_length=1, max_length=100)
    description: str
    category: str = Field(..., pattern="^(red-team|blue-team|insider-threat)$")
    difficulty: str = Field(..., pattern="^(beginner|intermediate|advanced)$")
    duration_minutes: int = Field(..., ge=1)
    event_count: int = Field(..., ge=1)
    required_roles: List[str]


class ScenarioListResponse(ScenarioBase):
    """Scenario response for list endpoint (no events)."""
    id: UUID
    is_seed: bool = True
    seed_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ScenarioDetailResponse(ScenarioListResponse):
    """Full scenario response including events."""
    events: List[ScenarioEvent]


class ApplyScenarioRequest(BaseModel):
    """Request to apply a scenario to a range."""
    scenario_id: UUID
    role_mapping: dict  # {"domain-controller": "vm-uuid-1", "workstation": "vm-uuid-2"}


class ApplyScenarioResponse(BaseModel):
    """Response after applying a scenario."""
    msel_id: UUID
    inject_count: int
    status: str = "applied"
