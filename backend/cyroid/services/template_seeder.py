# backend/cyroid/services/template_seeder.py
"""Template seeder service for built-in CYROID templates."""

import os
import logging
from pathlib import Path
from typing import List, Optional

import yaml
from sqlalchemy.orm import Session

from cyroid.models.template import VMTemplate, OSType, VMType

logger = logging.getLogger(__name__)

# Default path to seed templates directory
SEED_TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "data" / "seed-templates"


def load_manifest(seed_dir: Path = SEED_TEMPLATES_DIR) -> dict:
    """Load the seed templates manifest."""
    manifest_path = seed_dir / "manifest.yaml"
    if not manifest_path.exists():
        logger.warning(f"Seed templates manifest not found at {manifest_path}")
        return {"version": 0, "templates": []}

    with open(manifest_path) as f:
        return yaml.safe_load(f)


def load_template_yaml(seed_id: str, seed_dir: Path = SEED_TEMPLATES_DIR) -> Optional[dict]:
    """Load a single template YAML file."""
    # Find the template file from manifest
    manifest = load_manifest(seed_dir)
    for entry in manifest.get("templates", []):
        if entry.get("seed_id") == seed_id:
            file_path = seed_dir / entry.get("file")
            if file_path.exists():
                with open(file_path) as f:
                    return yaml.safe_load(f)
    return None


def get_os_type(os_type_str: str) -> OSType:
    """Convert string to OSType enum."""
    return OSType(os_type_str.lower())


def get_vm_type(vm_type_str: str) -> VMType:
    """Convert string to VMType enum."""
    mapping = {
        "container": VMType.CONTAINER,
        "linux_vm": VMType.LINUX_VM,
        "windows_vm": VMType.WINDOWS_VM,
    }
    return mapping.get(vm_type_str.lower(), VMType.CONTAINER)


def seed_template(db: Session, template_data: dict) -> Optional[VMTemplate]:
    """Seed or update a single template."""
    seed_id = template_data.get("seed_id")
    if not seed_id:
        logger.warning("Template missing seed_id, skipping")
        return None

    # Check if already exists
    existing = db.query(VMTemplate).filter(VMTemplate.seed_id == seed_id).first()

    if existing:
        # Update existing seed template
        logger.info(f"Updating seed template: {seed_id}")
        existing.name = template_data.get("name", existing.name)
        existing.description = template_data.get("description", existing.description)
        existing.os_type = get_os_type(template_data.get("os_type", "linux"))
        existing.os_variant = template_data.get("os_variant", "")
        existing.vm_type = get_vm_type(template_data.get("vm_type", "container"))
        existing.base_image = template_data.get("base_image", "")
        existing.default_cpu = template_data.get("default_cpu", 2)
        existing.default_ram_mb = template_data.get("default_ram_mb", 4096)
        existing.default_disk_gb = template_data.get("default_disk_gb", 40)
        existing.native_arch = template_data.get("native_arch", "x86_64")
        existing.tags = template_data.get("tags", [])
        existing.linux_distro = template_data.get("linux_distro")
        existing.boot_mode = template_data.get("boot_mode", "uefi")
        existing.disk_type = template_data.get("disk_type", "scsi")
        db.flush()
        return existing
    else:
        # Create new seed template
        logger.info(f"Creating seed template: {seed_id}")
        template = VMTemplate(
            name=template_data.get("name", seed_id),
            description=template_data.get("description", ""),
            os_type=get_os_type(template_data.get("os_type", "linux")),
            os_variant=template_data.get("os_variant", ""),
            vm_type=get_vm_type(template_data.get("vm_type", "container")),
            base_image=template_data.get("base_image", ""),
            default_cpu=template_data.get("default_cpu", 2),
            default_ram_mb=template_data.get("default_ram_mb", 4096),
            default_disk_gb=template_data.get("default_disk_gb", 40),
            native_arch=template_data.get("native_arch", "x86_64"),
            tags=template_data.get("tags", []),
            linux_distro=template_data.get("linux_distro"),
            boot_mode=template_data.get("boot_mode", "uefi"),
            disk_type=template_data.get("disk_type", "scsi"),
            is_seed=True,
            seed_id=seed_id,
            created_by=None,  # No user for seed templates
        )
        db.add(template)
        db.flush()
        return template


def seed_all_templates(db: Session, seed_dir: Path = SEED_TEMPLATES_DIR) -> List[VMTemplate]:
    """Seed all templates from the manifest."""
    manifest = load_manifest(seed_dir)
    seeded = []

    for entry in manifest.get("templates", []):
        seed_id = entry.get("seed_id")
        file_name = entry.get("file")

        if not seed_id or not file_name:
            continue

        file_path = seed_dir / file_name
        if not file_path.exists():
            logger.warning(f"Template file not found: {file_path}")
            continue

        with open(file_path) as f:
            template_data = yaml.safe_load(f)

        if template_data:
            template = seed_template(db, template_data)
            if template:
                seeded.append(template)

    db.commit()
    logger.info(f"Seeded {len(seeded)} templates")
    return seeded


def seed_builtin_templates():
    """Seed builtin templates - called from Alembic migration."""
    from cyroid.database import SessionLocal

    db = SessionLocal()
    try:
        seed_all_templates(db)
    finally:
        db.close()
