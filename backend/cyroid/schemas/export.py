# backend/cyroid/schemas/export.py
"""
Comprehensive range export/import schemas.

Supports two export modes:
- Online: Lightweight export without Docker images (zip archive)
- Offline: Complete export with Docker images for air-gapped deployment (tar.gz)
"""
from datetime import datetime
from typing import Optional, List, Any, Literal
from uuid import UUID
from pydantic import BaseModel, Field


# =============================================================================
# Export Components and Manifest
# =============================================================================

class ExportComponents(BaseModel):
    """Flags indicating what's included in the export."""
    networks: bool = True
    vms: bool = True
    templates: bool = True
    msel: bool = False
    artifacts: bool = False
    snapshots: bool = False
    docker_images: bool = False  # Only in offline mode
    walkthrough: bool = False  # Content Library student guide


class ExportManifest(BaseModel):
    """Top-level manifest for exported range archive."""
    version: str = "2.0"
    export_type: Literal["online", "offline"]
    created_at: datetime
    created_by: str  # Username
    source_range_id: str  # Original UUID (for reference only)
    source_range_name: str
    checksum: Optional[str] = None  # SHA256 of archive contents
    components: ExportComponents


# =============================================================================
# Range Metadata
# =============================================================================

class RangeExportMetadata(BaseModel):
    """Basic range information for export."""
    name: str
    description: Optional[str] = None


# =============================================================================
# Network Export
# =============================================================================

class NetworkExportData(BaseModel):
    """Full network configuration for export."""
    name: str
    subnet: str  # CIDR notation
    gateway: str
    dns_servers: Optional[str] = None  # Comma-separated
    is_isolated: bool = True  # Network isolation enabled


# =============================================================================
# VM Export - Complete Configuration (30+ fields)
# =============================================================================

class VMExportData(BaseModel):
    """Complete VM configuration for export - all fields captured."""
    # Core identity
    hostname: str
    ip_address: str
    network_name: str  # Reference by name for portability
    # Image Library sources (exactly one should be set)
    base_image_id: Optional[str] = None
    golden_image_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    # Fallback fields for cross-environment portability
    base_image_tag: Optional[str] = None  # Docker image tag (preferred fallback)
    base_image_name: Optional[str] = None  # BaseImage name
    # Deprecated: kept for backward compatibility with older exports
    template_name: Optional[str] = None

    # Compute resources
    cpu: int
    ram_mb: int
    disk_gb: int
    disk2_gb: Optional[int] = None  # Additional storage
    disk3_gb: Optional[int] = None  # Additional storage

    # Windows-specific settings
    windows_version: Optional[str] = None  # Version code: 11, 10, 2022, etc.
    windows_username: Optional[str] = None
    windows_password: Optional[str] = None  # Encrypted in export
    iso_url: Optional[str] = None  # Remote ISO download URL
    iso_path: Optional[str] = None  # Local ISO path
    display_type: Optional[str] = None  # "desktop" or "server"

    # Linux-specific settings
    linux_distro: Optional[str] = None  # ubuntu, kali, debian, etc.
    linux_username: Optional[str] = None
    linux_password: Optional[str] = None  # Encrypted in export
    linux_user_sudo: bool = True
    boot_mode: Optional[str] = None  # "uefi" or "legacy"
    disk_type: Optional[str] = None  # "scsi", "blk", or "ide"

    # Network configuration
    use_dhcp: bool = False
    gateway: Optional[str] = None
    dns_servers: Optional[str] = None  # Comma-separated

    # Storage/sharing
    enable_shared_folder: bool = False  # Per-VM /shared
    enable_global_shared: bool = False  # Global /global (read-only)

    # Localization
    language: Optional[str] = None  # e.g., "French", "German"
    keyboard: Optional[str] = None  # e.g., "en-US", "de-DE"
    region: Optional[str] = None  # e.g., "en-US", "fr-FR"

    # Installation mode
    manual_install: bool = False  # Interactive install mode

    # UI positioning
    position_x: int = 0
    position_y: int = 0


# =============================================================================
# VM Template Export
# =============================================================================

class TemplateExportData(BaseModel):
    """Full VM template definition for export."""
    name: str
    description: Optional[str] = None
    os_type: str  # windows, linux, custom
    os_variant: str  # e.g., "Ubuntu 22.04", "Windows Server 2022"
    base_image: str  # Docker image, linux distro code, or windows version
    vm_type: str  # container, linux_vm, windows_vm

    # Linux VM-specific
    linux_distro: Optional[str] = None
    boot_mode: Optional[str] = None
    disk_type: Optional[str] = None

    # Default specs
    default_cpu: int = 2
    default_ram_mb: int = 4096
    default_disk_gb: int = 40

    # Configuration
    config_script: Optional[str] = None  # Bash or PowerShell
    tags: List[str] = Field(default_factory=list)

    # Caching info (for reference)
    golden_image_path: Optional[str] = None
    cached_iso_path: Optional[str] = None
    is_cached: bool = False


# =============================================================================
# MSEL and Inject Export
# =============================================================================

class InjectExportData(BaseModel):
    """Individual inject with portable VM references."""
    sequence_number: int
    inject_time_minutes: int  # Minutes from exercise start
    title: str
    description: Optional[str] = None
    target_vm_hostnames: List[str] = Field(default_factory=list)  # Hostnames instead of UUIDs
    actions: List[Any] = Field(default_factory=list)  # List of {action_type, parameters}
    status: str = "pending"  # pending, executing, completed, failed, skipped


class MSELExportData(BaseModel):
    """Full MSEL with injects for export."""
    name: str
    content: str  # Raw markdown
    injects: List[InjectExportData] = Field(default_factory=list)


# =============================================================================
# Walkthrough Export (Content Library Student Guide)
# =============================================================================

class WalkthroughExportData(BaseModel):
    """Student guide/walkthrough for export."""
    title: str
    description: Optional[str] = None
    content_type: str = "student_guide"
    body_markdown: str = ""
    walkthrough_data: Optional[dict] = None  # Structured phases/steps
    version: str = "1.0"
    tags: List[str] = Field(default_factory=list)
    content_hash: str  # SHA256 of walkthrough_data JSON for deduplication


# =============================================================================
# Artifact Export
# =============================================================================

class ArtifactExportData(BaseModel):
    """Artifact metadata for export."""
    name: str
    description: Optional[str] = None
    sha256_hash: str  # Used as portable identifier
    file_size: int
    artifact_type: str  # executable, script, document, archive, config, other
    malicious_indicator: str  # safe, suspicious, malicious
    ttps: List[str] = Field(default_factory=list)  # MITRE ATT&CK IDs
    tags: List[str] = Field(default_factory=list)
    file_path_in_archive: str  # Relative path within archive


class ArtifactPlacementExportData(BaseModel):
    """Artifact placement with portable references."""
    artifact_sha256: str  # Reference artifact by hash
    vm_hostname: str  # Reference VM by hostname
    target_path: str  # Where to place on VM


# =============================================================================
# Snapshot Export
# =============================================================================

class SnapshotExportData(BaseModel):
    """Snapshot metadata for export."""
    name: str
    description: Optional[str] = None
    vm_hostname: str  # Reference VM by hostname
    docker_image_id: Optional[str] = None
    image_tar_path: Optional[str] = None  # For offline exports


# =============================================================================
# Docker Image Export (Offline mode only)
# =============================================================================

class DockerImageExportData(BaseModel):
    """Docker image reference for offline export."""
    image_name: str  # e.g., "dockurr/windows:latest"
    image_id: str  # SHA256 hash
    tar_path: str  # Relative path in archive
    size_bytes: int


# =============================================================================
# Complete Range Export Structure
# =============================================================================

class RangeExportFull(BaseModel):
    """Complete range export structure - the main export document."""
    manifest: ExportManifest
    range: RangeExportMetadata
    networks: List[NetworkExportData] = Field(default_factory=list)
    vms: List[VMExportData] = Field(default_factory=list)
    templates: List[TemplateExportData] = Field(default_factory=list)
    msel: Optional[MSELExportData] = None
    walkthrough: Optional[WalkthroughExportData] = None  # Content Library student guide
    artifacts: List[ArtifactExportData] = Field(default_factory=list)
    artifact_placements: List[ArtifactPlacementExportData] = Field(default_factory=list)
    snapshots: List[SnapshotExportData] = Field(default_factory=list)
    docker_images: List[DockerImageExportData] = Field(default_factory=list)  # Offline only


# =============================================================================
# Export Request and Job Status
# =============================================================================

class ExportRequest(BaseModel):
    """Request parameters for range export."""
    include_templates: bool = True
    include_msel: bool = True
    include_walkthrough: bool = True  # Content Library student guide
    include_artifacts: bool = True
    include_snapshots: bool = False
    include_docker_images: bool = False  # Enables offline mode
    encrypt_passwords: bool = True  # Encrypt sensitive data


class ExportJobStatus(BaseModel):
    """Status of a background export job."""
    job_id: str
    status: Literal["pending", "in_progress", "completed", "failed"]
    progress_percent: int = 0
    current_step: str = ""
    download_url: Optional[str] = None
    error_message: Optional[str] = None
    file_size_bytes: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


# =============================================================================
# Import Validation and Conflicts
# =============================================================================

class TemplateConflict(BaseModel):
    """Template name collision during import."""
    template_name: str
    existing_template_id: str
    action: Literal["use_existing", "create_new", "skip"] = "use_existing"


class NetworkConflict(BaseModel):
    """Network subnet overlap during import."""
    network_name: str
    subnet: str
    overlapping_range_name: str
    overlapping_network_name: str


class ImportConflicts(BaseModel):
    """All detected conflicts during import validation."""
    template_conflicts: List[TemplateConflict] = Field(default_factory=list)
    network_conflicts: List[NetworkConflict] = Field(default_factory=list)
    name_conflict: bool = False  # Range name already exists


class ImportSummary(BaseModel):
    """Summary of what will be imported."""
    range_name: str
    networks_count: int = 0
    vms_count: int = 0
    templates_to_create: int = 0
    templates_existing: int = 0
    artifacts_count: int = 0
    artifact_placements_count: int = 0
    injects_count: int = 0
    walkthrough_status: Optional[str] = None  # "reuse_existing", "create_new", "create_renamed", None
    estimated_size_mb: Optional[float] = None


class ImportValidationResult(BaseModel):
    """Result of import validation before execution."""
    valid: bool
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    conflicts: ImportConflicts
    summary: ImportSummary


class ImportOptions(BaseModel):
    """Options for controlling import behavior."""
    name_override: Optional[str] = None  # Override range name
    template_conflict_action: Literal["use_existing", "create_new", "skip"] = "use_existing"
    skip_artifacts: bool = False
    skip_msel: bool = False
    skip_walkthrough: bool = False  # Skip Content Library student guide
    dry_run: bool = False  # Validate only, don't execute


class ImportResult(BaseModel):
    """Result of import execution."""
    success: bool
    range_id: Optional[UUID] = None
    range_name: Optional[str] = None
    networks_created: int = 0
    vms_created: int = 0
    templates_created: int = 0
    artifacts_imported: int = 0
    walkthrough_imported: bool = False
    walkthrough_reused: bool = False
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
