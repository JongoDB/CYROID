# backend/cyroid/services/scenario_seeder.py
"""Scenario seeder service for built-in training scenarios."""

import logging
from pathlib import Path
from typing import List, Optional

import yaml
from sqlalchemy.orm import Session

from cyroid.models.scenario import Scenario

logger = logging.getLogger(__name__)

# Default path to seed scenarios directory
SEED_SCENARIOS_DIR = Path(__file__).parent.parent.parent.parent / "data" / "seed-scenarios"


def load_manifest(seed_dir: Path = SEED_SCENARIOS_DIR) -> dict:
    """Load the seed scenarios manifest."""
    manifest_path = seed_dir / "manifest.yaml"
    if not manifest_path.exists():
        logger.warning(f"Seed scenarios manifest not found at {manifest_path}")
        return {"version": 0, "scenarios": []}

    with open(manifest_path) as f:
        return yaml.safe_load(f)


def seed_scenario(db: Session, scenario_data: dict) -> Optional[Scenario]:
    """Seed or update a single scenario."""
    seed_id = scenario_data.get("seed_id")
    if not seed_id:
        logger.warning("Scenario missing seed_id, skipping")
        return None

    # Check if already exists
    existing = db.query(Scenario).filter(Scenario.seed_id == seed_id).first()

    events = scenario_data.get("events", [])
    event_count = len(events)

    if existing:
        # Update existing seed scenario
        logger.info(f"Updating seed scenario: {seed_id}")
        existing.name = scenario_data.get("name", existing.name)
        existing.description = scenario_data.get("description", existing.description)
        existing.category = scenario_data.get("category", existing.category)
        existing.difficulty = scenario_data.get("difficulty", existing.difficulty)
        existing.duration_minutes = scenario_data.get("duration_minutes", existing.duration_minutes)
        existing.event_count = event_count
        existing.required_roles = scenario_data.get("required_roles", [])
        existing.events = events
        db.flush()
        return existing
    else:
        # Create new seed scenario
        logger.info(f"Creating seed scenario: {seed_id}")
        scenario = Scenario(
            name=scenario_data.get("name", seed_id),
            description=scenario_data.get("description", ""),
            category=scenario_data.get("category", "red-team"),
            difficulty=scenario_data.get("difficulty", "intermediate"),
            duration_minutes=scenario_data.get("duration_minutes", 60),
            event_count=event_count,
            required_roles=scenario_data.get("required_roles", []),
            events=events,
            is_seed=True,
            seed_id=seed_id,
        )
        db.add(scenario)
        db.flush()
        return scenario


def seed_all_scenarios(db: Session, seed_dir: Path = SEED_SCENARIOS_DIR) -> List[Scenario]:
    """Seed all scenarios from the manifest."""
    manifest = load_manifest(seed_dir)
    seeded = []

    for entry in manifest.get("scenarios", []):
        seed_id = entry.get("seed_id")
        file_name = entry.get("file")

        if not seed_id or not file_name:
            continue

        file_path = seed_dir / file_name
        if not file_path.exists():
            logger.warning(f"Scenario file not found: {file_path}")
            continue

        with open(file_path) as f:
            scenario_data = yaml.safe_load(f)

        if scenario_data:
            scenario = seed_scenario(db, scenario_data)
            if scenario:
                seeded.append(scenario)

    db.commit()
    logger.info(f"Seeded {len(seeded)} scenarios")
    return seeded
