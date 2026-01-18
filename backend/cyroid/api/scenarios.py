# backend/cyroid/api/scenarios.py
"""
Scenarios API endpoints for training scenarios.

Scenarios are read directly from YAML files in data/scenarios/.
No database required - files are immediately visible when added.
"""
import os
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from cyroid.api.deps import get_current_user
from cyroid.models.user import User
from cyroid.services.scenario_filesystem import (
    list_scenarios as fs_list_scenarios,
    get_scenario as fs_get_scenario,
    save_scenario as fs_save_scenario,
    delete_scenario as fs_delete_scenario,
    refresh_cache,
    scenario_to_dict,
    get_scenarios_dir,
)

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


# Response models
class ScenarioEventResponse(BaseModel):
    sequence: int
    delay_minutes: int
    title: str
    description: Optional[str] = None
    target_role: str
    actions: List[dict] = []


class ScenarioListItem(BaseModel):
    id: str
    name: str
    description: str
    category: str
    difficulty: str
    duration_minutes: int
    event_count: int
    required_roles: List[str]
    modified_at: str


class ScenarioDetail(ScenarioListItem):
    events: List[ScenarioEventResponse]


class ScenarioUpload(BaseModel):
    name: str
    description: str
    category: str
    difficulty: str
    duration_minutes: int
    required_roles: List[str]
    events: List[dict]


class ScenariosListResponse(BaseModel):
    scenarios: List[ScenarioListItem]
    scenarios_dir: str
    total: int


@router.get("")
def list_scenarios(
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    current_user: User = Depends(get_current_user),
) -> ScenariosListResponse:
    """
    List all available training scenarios.

    Scenarios are read directly from YAML files in the scenarios directory.
    No restart required - new files are immediately visible.

    Args:
        category: Filter by category (red-team, blue-team, insider-threat)
        difficulty: Filter by difficulty (beginner, intermediate, advanced)

    Returns:
        List of scenarios without event details.
    """
    scenarios = fs_list_scenarios(category=category, difficulty=difficulty)

    return ScenariosListResponse(
        scenarios=[
            ScenarioListItem(**scenario_to_dict(s, include_events=False))
            for s in scenarios
        ],
        scenarios_dir=str(get_scenarios_dir()),
        total=len(scenarios),
    )


@router.get("/{scenario_id}")
def get_scenario(
    scenario_id: str,
    current_user: User = Depends(get_current_user),
) -> ScenarioDetail:
    """
    Get a scenario with full event details.

    Args:
        scenario_id: ID of the scenario (filename without extension or seed_id)

    Returns:
        Full scenario details including all events.
    """
    scenario = fs_get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    return ScenarioDetail(**scenario_to_dict(scenario, include_events=True))


@router.post("")
def create_scenario(
    scenario: ScenarioUpload,
    scenario_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
) -> ScenarioDetail:
    """
    Create a new scenario by saving a YAML file.

    Args:
        scenario: Scenario data
        scenario_id: Optional ID (defaults to slugified name)

    Returns:
        The created scenario.
    """
    # Generate ID from name if not provided
    if not scenario_id:
        scenario_id = scenario.name.lower().replace(" ", "-").replace("_", "-")
        # Remove non-alphanumeric characters except hyphens
        scenario_id = "".join(c for c in scenario_id if c.isalnum() or c == "-")

    data = {
        "name": scenario.name,
        "description": scenario.description,
        "category": scenario.category,
        "difficulty": scenario.difficulty,
        "duration_minutes": scenario.duration_minutes,
        "required_roles": scenario.required_roles,
        "events": scenario.events,
    }

    try:
        saved = fs_save_scenario(scenario_id, data, overwrite=False)
        return ScenarioDetail(**scenario_to_dict(saved, include_events=True))
    except FileExistsError:
        raise HTTPException(
            status_code=409,
            detail=f"Scenario '{scenario_id}' already exists. Use PUT to update."
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{scenario_id}")
def update_scenario(
    scenario_id: str,
    scenario: ScenarioUpload,
    current_user: User = Depends(get_current_user),
) -> ScenarioDetail:
    """
    Update an existing scenario.

    Args:
        scenario_id: ID of the scenario to update
        scenario: Updated scenario data

    Returns:
        The updated scenario.
    """
    # Check if exists
    existing = fs_get_scenario(scenario_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Scenario not found")

    data = {
        "name": scenario.name,
        "description": scenario.description,
        "category": scenario.category,
        "difficulty": scenario.difficulty,
        "duration_minutes": scenario.duration_minutes,
        "required_roles": scenario.required_roles,
        "events": scenario.events,
    }

    try:
        saved = fs_save_scenario(scenario_id, data, overwrite=True)
        return ScenarioDetail(**scenario_to_dict(saved, include_events=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{scenario_id}")
def delete_scenario(
    scenario_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Delete a scenario.

    Args:
        scenario_id: ID of the scenario to delete

    Returns:
        Success message.
    """
    if not fs_delete_scenario(scenario_id):
        raise HTTPException(status_code=404, detail="Scenario not found")

    return {"message": f"Scenario '{scenario_id}' deleted"}


@router.post("/upload")
async def upload_scenario(
    file: UploadFile = File(...),
    overwrite: bool = Form(default=False),
    current_user: User = Depends(get_current_user),
) -> ScenarioDetail:
    """
    Upload a scenario YAML file.

    Args:
        file: YAML file to upload
        overwrite: Whether to overwrite if exists

    Returns:
        The uploaded scenario.
    """
    if not file.filename or not file.filename.endswith(('.yaml', '.yml')):
        raise HTTPException(
            status_code=400,
            detail="File must be a YAML file (.yaml or .yml)"
        )

    # Read and parse the YAML content
    import yaml
    try:
        content = await file.read()
        data = yaml.safe_load(content.decode('utf-8'))
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {e}")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded")

    if not data:
        raise HTTPException(status_code=400, detail="Empty YAML file")

    # Extract scenario ID from filename or seed_id
    scenario_id = data.get('seed_id') or file.filename.rsplit('.', 1)[0]

    try:
        saved = fs_save_scenario(scenario_id, data, overwrite=overwrite)
        return ScenarioDetail(**scenario_to_dict(saved, include_events=True))
    except FileExistsError:
        raise HTTPException(
            status_code=409,
            detail=f"Scenario '{scenario_id}' already exists. Set overwrite=true to replace."
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/refresh")
def refresh_scenarios(
    current_user: User = Depends(get_current_user),
):
    """
    Refresh the scenario cache.

    Forces re-reading all scenarios from disk. Useful after manually
    adding or modifying scenario files.

    Returns:
        List of scenarios after refresh.
    """
    refresh_cache()
    scenarios = fs_list_scenarios()

    return {
        "message": "Scenario cache refreshed",
        "total": len(scenarios),
        "scenarios": [s.id for s in scenarios],
    }
