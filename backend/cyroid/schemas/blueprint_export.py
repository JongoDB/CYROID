# backend/cyroid/schemas/blueprint_export.py
"""
Schemas for blueprint export/import functionality.

Version History:
- 1.0: Original export format with templates
- 2.0: Image Library IDs (templates deprecated)
- 3.0: Includes Dockerfiles and Content Library items
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


# ============ Export Options Schema (v3.0) ============

class BlueprintExportOptions(BaseModel):
    """Options controlling what to include in the export."""
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


# ============ Export Schemas ============

class BlueprintExportManifest(BaseModel):
    """Manifest for blueprint export package."""
    version: str = "3.0"  # Updated for Dockerfile/Content support
    export_type: str = "blueprint"
    created_at: datetime
    created_by: Optional[str] = None
    blueprint_name: str
    template_count: int = 0  # Deprecated
    dockerfile_count: int = 0  # NEW: Number of Dockerfile projects
    content_included: bool = False  # NEW: Whether content is included
    docker_images_included: bool = False  # NEW: Whether Docker image tarballs are included
    checksums: Dict[str, str] = {}


class BlueprintExportData(BaseModel):
    """Blueprint data for export."""
    name: str
    description: Optional[str] = None
    version: int = 1
    base_subnet_prefix: str
    next_offset: int = 0
    config: BlueprintConfig
    student_guide_id: Optional[str] = None  # Content Library ID (if linked)


class BlueprintExportFull(BaseModel):
    """Full blueprint export package structure."""
    manifest: BlueprintExportManifest
    blueprint: BlueprintExportData
    templates: List[TemplateExportData] = []  # Deprecated - kept for backward compatibility
    dockerfiles: List[DockerfileProjectData] = []  # NEW: Dockerfile projects
    content: Optional[ContentExportData] = None  # NEW: Student guide / content


# ============ Import Schemas ============

class BlueprintImportValidation(BaseModel):
    """Validation result for blueprint import."""
    valid: bool
    blueprint_name: str
    manifest_version: str = "1.0"  # NEW: Version of the export format
    errors: List[str] = []
    warnings: List[str] = []
    conflicts: List[str] = []
    missing_templates: List[str] = []  # Deprecated
    included_templates: List[str] = []  # Deprecated
    included_dockerfiles: List[str] = []  # NEW: Dockerfile projects included
    dockerfile_conflicts: List[str] = []  # NEW: Dockerfiles that already exist
    missing_images: List[str] = []  # NEW: Images that need to be built
    content_included: bool = False  # NEW: Whether content is included
    content_conflict: Optional[str] = None  # NEW: Existing content with same title


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
    """Result of blueprint import operation."""
    success: bool
    blueprint_id: Optional[UUID] = None
    blueprint_name: Optional[str] = None
    templates_created: List[str] = []  # Deprecated
    templates_skipped: List[str] = []  # Deprecated
    images_built: List[str] = []
    dockerfiles_extracted: List[str] = []  # NEW: Dockerfile projects extracted
    dockerfiles_skipped: List[str] = []  # NEW: Skipped due to conflicts
    content_imported: bool = False  # NEW: Whether content was imported
    content_id: Optional[UUID] = None  # NEW: ID of imported/existing content
    errors: List[str] = []
    warnings: List[str] = []
