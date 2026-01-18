# backend/cyroid/services/scenario_filesystem.py
"""
Filesystem-based scenario service.

Scenarios are YAML files stored in data/scenarios/. No database required.
Files are read directly from disk with caching based on modification time.
"""
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

import yaml

logger = logging.getLogger(__name__)

# Default scenarios directory - can be overridden via environment
SCENARIOS_DIR = Path(os.environ.get("SCENARIOS_DIR", "/data/scenarios"))


@dataclass
class ScenarioEvent:
    """A single event within a scenario."""
    sequence: int
    delay_minutes: int
    title: str
    target_role: str
    description: Optional[str] = None
    actions: List[dict] = field(default_factory=list)


@dataclass
class Scenario:
    """A training scenario loaded from YAML."""
    id: str  # filename without extension (e.g., "ransomware-attack")
    name: str
    description: str
    category: str
    difficulty: str
    duration_minutes: int
    required_roles: List[str]
    events: List[ScenarioEvent]
    file_path: str
    modified_at: datetime

    @property
    def event_count(self) -> int:
        return len(self.events)


class ScenarioCache:
    """Simple cache for parsed scenarios with modification time tracking."""

    def __init__(self):
        self._cache: Dict[str, tuple[float, Scenario]] = {}  # {filename: (mtime, scenario)}

    def get(self, file_path: Path) -> Optional[Scenario]:
        """Get cached scenario if file hasn't changed."""
        key = str(file_path)
        if key not in self._cache:
            return None

        cached_mtime, scenario = self._cache[key]
        try:
            current_mtime = file_path.stat().st_mtime
            if current_mtime == cached_mtime:
                return scenario
        except OSError:
            pass

        # File changed or deleted, invalidate cache
        del self._cache[key]
        return None

    def set(self, file_path: Path, scenario: Scenario):
        """Cache a parsed scenario with its modification time."""
        try:
            mtime = file_path.stat().st_mtime
            self._cache[str(file_path)] = (mtime, scenario)
        except OSError:
            pass

    def invalidate(self, file_path: Optional[Path] = None):
        """Invalidate cache for a specific file or all files."""
        if file_path:
            self._cache.pop(str(file_path), None)
        else:
            self._cache.clear()


# Global cache instance
_cache = ScenarioCache()


def _parse_scenario_yaml(file_path: Path) -> Optional[Scenario]:
    """Parse a scenario YAML file."""
    try:
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)

        if not data:
            logger.warning(f"Empty scenario file: {file_path}")
            return None

        # Parse events
        events = []
        for event_data in data.get('events', []):
            events.append(ScenarioEvent(
                sequence=event_data.get('sequence', 0),
                delay_minutes=event_data.get('delay_minutes', 0),
                title=event_data.get('title', ''),
                description=event_data.get('description'),
                target_role=event_data.get('target_role', ''),
                actions=event_data.get('actions', []),
            ))

        # Use seed_id if present, otherwise use filename
        scenario_id = data.get('seed_id', file_path.stem)

        scenario = Scenario(
            id=scenario_id,
            name=data.get('name', scenario_id),
            description=data.get('description', ''),
            category=data.get('category', 'red-team'),
            difficulty=data.get('difficulty', 'intermediate'),
            duration_minutes=data.get('duration_minutes', 60),
            required_roles=data.get('required_roles', []),
            events=events,
            file_path=str(file_path),
            modified_at=datetime.fromtimestamp(file_path.stat().st_mtime),
        )

        return scenario

    except yaml.YAMLError as e:
        logger.error(f"Invalid YAML in scenario file {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error parsing scenario file {file_path}: {e}")
        return None


def get_scenarios_dir() -> Path:
    """Get the scenarios directory path."""
    return SCENARIOS_DIR


def list_scenarios(
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
) -> List[Scenario]:
    """
    List all scenarios from the filesystem.

    Args:
        category: Filter by category (red-team, blue-team, insider-threat)
        difficulty: Filter by difficulty (beginner, intermediate, advanced)

    Returns:
        List of Scenario objects
    """
    scenarios = []
    scenarios_dir = get_scenarios_dir()

    if not scenarios_dir.exists():
        logger.warning(f"Scenarios directory not found: {scenarios_dir}")
        return []

    for file_path in sorted(scenarios_dir.glob("*.yaml")):
        if file_path.name == 'manifest.yaml':
            continue  # Skip manifest file if present

        # Check cache first
        scenario = _cache.get(file_path)
        if scenario is None:
            scenario = _parse_scenario_yaml(file_path)
            if scenario:
                _cache.set(file_path, scenario)

        if scenario:
            # Apply filters
            if category and scenario.category != category:
                continue
            if difficulty and scenario.difficulty != difficulty:
                continue
            scenarios.append(scenario)

    return scenarios


def get_scenario(scenario_id: str) -> Optional[Scenario]:
    """
    Get a specific scenario by ID.

    Args:
        scenario_id: The scenario ID (filename without extension or seed_id)

    Returns:
        Scenario object or None if not found
    """
    scenarios_dir = get_scenarios_dir()

    # Try direct filename match first
    file_path = scenarios_dir / f"{scenario_id}.yaml"
    if file_path.exists():
        scenario = _cache.get(file_path)
        if scenario is None:
            scenario = _parse_scenario_yaml(file_path)
            if scenario:
                _cache.set(file_path, scenario)
        return scenario

    # Fall back to scanning all files for matching seed_id
    for file_path in scenarios_dir.glob("*.yaml"):
        if file_path.name == 'manifest.yaml':
            continue

        scenario = _cache.get(file_path)
        if scenario is None:
            scenario = _parse_scenario_yaml(file_path)
            if scenario:
                _cache.set(file_path, scenario)

        if scenario and scenario.id == scenario_id:
            return scenario

    return None


def save_scenario(
    scenario_id: str,
    data: Dict[str, Any],
    overwrite: bool = False,
) -> Scenario:
    """
    Save a scenario to the filesystem.

    Args:
        scenario_id: The scenario ID (will be used as filename)
        data: The scenario data (dict matching YAML structure)
        overwrite: Whether to overwrite existing file

    Returns:
        The saved Scenario object

    Raises:
        FileExistsError: If file exists and overwrite=False
        ValueError: If scenario data is invalid
    """
    scenarios_dir = get_scenarios_dir()
    scenarios_dir.mkdir(parents=True, exist_ok=True)

    file_path = scenarios_dir / f"{scenario_id}.yaml"

    if file_path.exists() and not overwrite:
        raise FileExistsError(f"Scenario '{scenario_id}' already exists")

    # Validate required fields
    required_fields = ['name', 'description', 'category', 'difficulty', 'duration_minutes', 'required_roles', 'events']
    for field in required_fields:
        if field not in data:
            raise ValueError(f"Missing required field: {field}")

    # Add seed_id if not present
    if 'seed_id' not in data:
        data['seed_id'] = scenario_id

    # Write YAML file
    with open(file_path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    # Invalidate cache and parse the new file
    _cache.invalidate(file_path)
    scenario = _parse_scenario_yaml(file_path)

    if scenario:
        _cache.set(file_path, scenario)
        logger.info(f"Saved scenario: {scenario_id}")
        return scenario
    else:
        raise ValueError("Failed to parse saved scenario")


def delete_scenario(scenario_id: str) -> bool:
    """
    Delete a scenario from the filesystem.

    Args:
        scenario_id: The scenario ID

    Returns:
        True if deleted, False if not found
    """
    scenarios_dir = get_scenarios_dir()
    file_path = scenarios_dir / f"{scenario_id}.yaml"

    if not file_path.exists():
        # Try to find by seed_id
        for fp in scenarios_dir.glob("*.yaml"):
            scenario = _cache.get(fp)
            if scenario is None:
                scenario = _parse_scenario_yaml(fp)
            if scenario and scenario.id == scenario_id:
                file_path = fp
                break
        else:
            return False

    try:
        file_path.unlink()
        _cache.invalidate(file_path)
        logger.info(f"Deleted scenario: {scenario_id}")
        return True
    except OSError as e:
        logger.error(f"Failed to delete scenario {scenario_id}: {e}")
        return False


def refresh_cache():
    """Clear the scenario cache to force re-reading from disk."""
    _cache.invalidate()
    logger.info("Scenario cache invalidated")


def scenario_to_dict(scenario: Scenario, include_events: bool = False) -> Dict[str, Any]:
    """Convert a Scenario to a dictionary for API response."""
    result = {
        'id': scenario.id,
        'name': scenario.name,
        'description': scenario.description,
        'category': scenario.category,
        'difficulty': scenario.difficulty,
        'duration_minutes': scenario.duration_minutes,
        'event_count': scenario.event_count,
        'required_roles': scenario.required_roles,
        'modified_at': scenario.modified_at.isoformat(),
    }

    if include_events:
        result['events'] = [
            {
                'sequence': e.sequence,
                'delay_minutes': e.delay_minutes,
                'title': e.title,
                'description': e.description,
                'target_role': e.target_role,
                'actions': e.actions,
            }
            for e in scenario.events
        ]

    return result
