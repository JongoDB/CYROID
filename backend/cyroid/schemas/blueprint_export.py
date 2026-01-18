# backend/cyroid/schemas/blueprint_export.py
"""
Schemas for blueprint export/import functionality.
"""
from typing import Optional, List, Dict
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

from cyroid.schemas.blueprint import BlueprintConfig


# ============ Template Export Schema ============

class TemplateExportData(BaseModel):
    """Template data for export."""
    name: str
    description: Optional[str] = None
    os_type: str  # OSType enum value
    os_variant: Optional[str] = None
    base_image: Optional[str] = None
    vm_type: str  # VMType enum value
    linux_distro: Optional[str] = None
    boot_mode: Optional[str] = None
    disk_type: Optional[str] = None
    default_cpu: int = 1
    default_ram_mb: int = 1024
    default_disk_gb: int = 20
    config_script: Optional[str] = None
    tags: List[str] = []


# ============ Export Schemas ============

class BlueprintExportManifest(BaseModel):
    """Manifest for blueprint export package."""
    version: str = "1.0"
    export_type: str = "blueprint"
    created_at: datetime
    created_by: Optional[str] = None
    blueprint_name: str
    template_count: int
    checksums: Dict[str, str] = {}


class BlueprintExportData(BaseModel):
    """Blueprint data for export."""
    name: str
    description: Optional[str] = None
    version: int = 1
    base_subnet_prefix: str
    next_offset: int = 0
    config: BlueprintConfig


class BlueprintExportFull(BaseModel):
    """Full blueprint export package structure."""
    manifest: BlueprintExportManifest
    blueprint: BlueprintExportData
    templates: List[TemplateExportData] = []


# ============ Import Schemas ============

class BlueprintImportValidation(BaseModel):
    """Validation result for blueprint import."""
    valid: bool
    blueprint_name: str
    errors: List[str] = []
    warnings: List[str] = []
    conflicts: List[str] = []
    missing_templates: List[str] = []
    included_templates: List[str] = []


class BlueprintImportOptions(BaseModel):
    """Options for blueprint import."""
    template_conflict_strategy: str = Field(
        default="skip",
        description="How to handle template conflicts: skip, update, or error"
    )
    new_name: Optional[str] = Field(
        default=None,
        description="Rename blueprint on import to avoid name conflicts"
    )


class BlueprintImportResult(BaseModel):
    """Result of blueprint import operation."""
    success: bool
    blueprint_id: Optional[UUID] = None
    blueprint_name: Optional[str] = None
    templates_created: List[str] = []
    templates_skipped: List[str] = []
    errors: List[str] = []
    warnings: List[str] = []
