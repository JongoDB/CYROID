# backend/cyroid/schemas/blueprint_export.py
"""
Schemas for blueprint export/import functionality.

Version History:
- 1.0: Original export format with templates
- 2.0: Image Library IDs (templates deprecated)
- 3.0: Includes Dockerfiles and Content Library items
- 4.0: Unified Range Blueprints (consolidates Range Export + Blueprint Export)
       Adds: include_msel, include_artifacts options
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

from cyroid.schemas.blueprint import BlueprintConfig


# ============ Template Export Schema (Deprecated) ============

class TemplateExportData(BaseModel):
    """Template data for export (deprecated - kept for backward compatibility)."""
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


# ============ Dockerfile Export Schema (v3.0) ============

class DockerfileProjectData(BaseModel):
    """Dockerfile project data for export."""
    project_name: str  # Directory name: e.g., "kali-attack"
    image_tag: str  # Full image tag: e.g., "cyroid/kali-attack:latest"
    files: Dict[str, str]  # {filename: content} - Dockerfile, scripts, etc.
    description: Optional[str] = None


# ============ Content Library Export Schema (v3.0) ============

class ContentAssetExportData(BaseModel):
    """Content asset data for export (images, files)."""
    filename: str
    mime_type: str
    sha256_hash: str
    archive_path: str  # Path within the ZIP archive


class ContentExportData(BaseModel):
    """Content Library item data for export."""
    title: str
    content_type: str  # "student_guide", "instructor_guide", etc.
    body_markdown: str
    walkthrough_data: Optional[Dict[str, Any]] = None  # Structured walkthrough content
    content_hash: str  # SHA256 hash of body_markdown for deduplication
    assets: List[ContentAssetExportData] = []


# ============ Artifact Export Schema (v4.0) ============

class ArtifactExportData(BaseModel):
    """Artifact data for export."""
    name: str
    description: Optional[str] = None
    category: str  # "tool", "script", "evidence_template", etc.
    sha256_hash: str
    file_size: int
    archive_path: str  # Path within the ZIP archive


# ============ Export Options Schema (v4.0) ============

class BlueprintExportOptions(BaseModel):
    """Options controlling what to include in the export (v4.0)."""
    include_msel: bool = Field(
        default=True,
        description="Include MSEL (Master Scenario Events List) injects"
    )
    include_dockerfiles: bool = Field(
        default=True,
        description="Include Dockerfiles from /data/images/ for referenced images"
    )
    include_docker_images: bool = Field(
        default=False,
        description="Include Docker image tarballs (large, but enables fully offline deployment)"
    )
    include_content: bool = Field(
        default=True,
        description="Include Content Library items (student guides, etc.)"
    )
    include_artifacts: bool = Field(
        default=False,
        description="Include artifact files (tools, scripts, evidence templates)"
    )


# ============ Export Schemas ============

class BlueprintExportManifest(BaseModel):
    """Manifest for blueprint export package (v4.0 unified format)."""
    version: str = "4.0"  # v4.0: Unified Range Blueprints
    export_type: str = "blueprint"
    created_at: datetime
    created_by: Optional[str] = None
    cyroid_version: Optional[str] = None  # NEW: CYROID version that created this export
    blueprint_name: str
    # What's included (v4.0)
    msel_included: bool = False
    dockerfile_count: int = 0
    content_included: bool = False
    artifact_count: int = 0  # NEW: Number of artifact files
    docker_images_included: bool = False
    docker_image_count: int = 0  # Number of Docker image tarballs
    docker_images: List[str] = []  # List of image tags exported
    # Checksums for integrity verification
    checksums: Dict[str, str] = {}


class BlueprintExportData(BaseModel):
    """Blueprint data for export."""
    name: str
    description: Optional[str] = None
    version: int = 1
    # DEPRECATED: No longer used with DinD isolation - kept for backward compatibility
    base_subnet_prefix: Optional[str] = None
    next_offset: Optional[int] = 0
    config: BlueprintConfig
    student_guide_id: Optional[str] = None  # Content Library ID (if linked)


class BlueprintExportFull(BaseModel):
    """Full blueprint export package structure (v4.0)."""
    manifest: BlueprintExportManifest
    blueprint: BlueprintExportData
    templates: List[TemplateExportData] = []  # Deprecated - kept for backward compatibility
    dockerfiles: List[DockerfileProjectData] = []  # Dockerfile projects
    content: Optional[ContentExportData] = None  # Student guide / content
    artifacts: List[ArtifactExportData] = []  # NEW: Artifact files (v4.0)


# ============ Import Schemas ============

class BlueprintImportValidation(BaseModel):
    """Validation result for blueprint import (v4.0)."""
    valid: bool
    blueprint_name: str
    manifest_version: str = "1.0"
    errors: List[str] = []
    warnings: List[str] = []
    conflicts: List[str] = []
    missing_templates: List[str] = []  # Deprecated
    included_templates: List[str] = []  # Deprecated
    included_dockerfiles: List[str] = []
    dockerfile_conflicts: List[str] = []
    missing_images: List[str] = []
    content_included: bool = False
    content_conflict: Optional[str] = None
    # v4.0 additions
    msel_included: bool = False
    included_artifacts: List[str] = []
    artifact_conflicts: List[str] = []


class BlueprintImportOptions(BaseModel):
    """Options for blueprint import."""
    template_conflict_strategy: str = Field(
        default="skip",
        description="How to handle template conflicts: skip, update, or error (deprecated)"
    )
    new_name: Optional[str] = Field(
        default=None,
        description="Rename blueprint on import to avoid name conflicts"
    )
    dockerfile_conflict_strategy: str = Field(
        default="skip",
        description="How to handle Dockerfile conflicts: skip (use existing), overwrite, or error"
    )
    content_conflict_strategy: str = Field(
        default="skip",
        description="How to handle Content Library conflicts: skip (use existing), rename, use_existing"
    )
    build_images: bool = Field(
        default=True,
        description="Automatically build Docker images from included Dockerfiles"
    )


class BlueprintImportResult(BaseModel):
    """Result of blueprint import operation (v4.0)."""
    success: bool
    blueprint_id: Optional[UUID] = None
    blueprint_name: Optional[str] = None
    templates_created: List[str] = []  # Deprecated
    templates_skipped: List[str] = []  # Deprecated
    images_built: List[str] = []
    images_loaded: List[str] = []  # Images loaded from tar and pushed to registry
    images_skipped: List[str] = []  # Images already in registry (skipped)
    dockerfiles_extracted: List[str] = []
    dockerfiles_skipped: List[str] = []
    content_imported: bool = False
    content_id: Optional[UUID] = None
    # v4.0 additions
    artifacts_imported: List[str] = []
    artifacts_skipped: List[str] = []
    errors: List[str] = []
    warnings: List[str] = []
