# backend/cyroid/services/blueprint_seeder.py
"""Blueprint seeder service for built-in CYROID blueprints."""

import logging
from pathlib import Path
from typing import List, Optional

import yaml
from sqlalchemy.orm import Session

from cyroid.models.blueprint import RangeBlueprint

logger = logging.getLogger(__name__)

# Default path to seed blueprints directory
SEED_BLUEPRINTS_DIR = Path(__file__).parent.parent.parent.parent / "data" / "seed-blueprints"


def load_manifest(seed_dir: Path = SEED_BLUEPRINTS_DIR) -> dict:
    """Load the seed blueprints manifest."""
    manifest_path = seed_dir / "manifest.yaml"
    if not manifest_path.exists():
        logger.warning(f"Seed blueprints manifest not found at {manifest_path}")
        return {"version": 0, "blueprints": []}

    with open(manifest_path) as f:
        return yaml.safe_load(f)


def load_blueprint_yaml(seed_id: str, seed_dir: Path = SEED_BLUEPRINTS_DIR) -> Optional[dict]:
    """Load a single blueprint YAML file."""
    manifest = load_manifest(seed_dir)
    for entry in manifest.get("blueprints", []):
        if entry.get("seed_id") == seed_id:
            file_path = seed_dir / entry.get("file")
            if file_path.exists():
                with open(file_path) as f:
                    return yaml.safe_load(f)
    return None


def build_config_from_yaml(blueprint_data: dict) -> dict:
    """Build the config JSON from blueprint YAML structure."""
    config = {
        "networks": [],
        "vms": [],
        "router": blueprint_data.get("router"),
        "msel": None
    }

    # Convert networks
    for net in blueprint_data.get("networks", []):
        config["networks"].append({
            "name": net.get("name"),
            "subnet": net.get("subnet"),
            "gateway": net.get("gateway"),
            "is_isolated": net.get("is_isolated", False)
        })

    # Convert VMs
    for vm in blueprint_data.get("vms", []):
        config["vms"].append({
            "hostname": vm.get("hostname"),
            "ip_address": vm.get("ip_address"),
            "network_name": vm.get("network_name"),
            "template_name": vm.get("template_name"),
            "cpu": vm.get("cpu", 1),
            "ram_mb": vm.get("ram_mb", 1024),
            "disk_gb": vm.get("disk_gb", 20),
            "position_x": vm.get("position_x"),
            "position_y": vm.get("position_y")
        })

    # Convert events to MSEL format if present
    events = blueprint_data.get("events", [])
    if events:
        msel_content = yaml.dump({"events": events}, default_flow_style=False)
        config["msel"] = {
            "content": msel_content,
            "format": "yaml"
        }

    return config


def seed_blueprint(db: Session, blueprint_data: dict) -> Optional[RangeBlueprint]:
    """Seed or update a single blueprint."""
    seed_id = blueprint_data.get("seed_id")
    if not seed_id:
        logger.warning("Blueprint missing seed_id, skipping")
        return None

    # Check if already exists
    existing = db.query(RangeBlueprint).filter(RangeBlueprint.seed_id == seed_id).first()

    # Build the config from the YAML structure
    config = build_config_from_yaml(blueprint_data)

    if existing:
        # Update existing seed blueprint
        logger.info(f"Updating seed blueprint: {seed_id}")
        existing.name = blueprint_data.get("name", existing.name)
        existing.description = blueprint_data.get("description", existing.description)
        existing.base_subnet_prefix = blueprint_data.get("base_subnet_prefix", existing.base_subnet_prefix)
        existing.config = config
        db.flush()
        return existing
    else:
        # Create new seed blueprint
        logger.info(f"Creating seed blueprint: {seed_id}")
        blueprint = RangeBlueprint(
            name=blueprint_data.get("name", seed_id),
            description=blueprint_data.get("description", ""),
            base_subnet_prefix=blueprint_data.get("base_subnet_prefix", "10.100"),
            config=config,
            version=1,
            next_offset=0,
            is_seed=True,
            seed_id=seed_id,
            created_by=None,  # No user for seed blueprints
        )
        db.add(blueprint)
        db.flush()
        return blueprint


def seed_all_blueprints(db: Session, seed_dir: Path = SEED_BLUEPRINTS_DIR) -> List[RangeBlueprint]:
    """Seed all blueprints from the manifest."""
    manifest = load_manifest(seed_dir)
    seeded = []

    for entry in manifest.get("blueprints", []):
        seed_id = entry.get("seed_id")
        file_name = entry.get("file")

        if not seed_id or not file_name:
            continue

        file_path = seed_dir / file_name
        if not file_path.exists():
            logger.warning(f"Blueprint file not found: {file_path}")
            continue

        with open(file_path) as f:
            blueprint_data = yaml.safe_load(f)

        if blueprint_data:
            blueprint = seed_blueprint(db, blueprint_data)
            if blueprint:
                seeded.append(blueprint)

    db.commit()
    logger.info(f"Seeded {len(seeded)} blueprints")
    return seeded


def seed_builtin_blueprints():
    """Seed builtin blueprints - called from startup or migration."""
    from cyroid.database import SessionLocal

    db = SessionLocal()
    try:
        seed_all_blueprints(db)
    finally:
        db.close()
