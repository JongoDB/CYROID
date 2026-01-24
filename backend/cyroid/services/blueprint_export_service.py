# backend/cyroid/services/blueprint_export_service.py
"""
Blueprint export/import service.

Exports blueprints as portable packages that can be imported into separate CYROID instances,
including all dependencies needed for successful deployment.

Version History:
- 1.0: Original export format with templates
- 2.0: Image Library IDs (templates deprecated)
- 3.0: Includes Dockerfiles and Content Library items
"""
import hashlib
import io
import json
import logging
import os
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Set, Any
from uuid import UUID

import docker
from sqlalchemy import select
from sqlalchemy.orm import Session

from cyroid.models.blueprint import RangeBlueprint
from cyroid.models.template import OSType, VMType
from cyroid.models.base_image import BaseImage
from cyroid.models.golden_image import GoldenImage
from cyroid.models.snapshot import Snapshot
from cyroid.models.content import Content, ContentAsset
from cyroid.models.user import User
from cyroid.config import get_settings
from cyroid.schemas.blueprint import BlueprintConfig
from cyroid.schemas.blueprint_export import (
    BlueprintExportManifest,
    BlueprintExportFull,
    BlueprintExportData,
    TemplateExportData,
    DockerfileProjectData,
    ContentExportData,
    ContentAssetExportData,
    BlueprintExportOptions,
    BlueprintImportValidation,
    BlueprintImportOptions,
    BlueprintImportResult,
)

# Directory where Dockerfiles are stored
IMAGES_DIR = "/data/images"

logger = logging.getLogger(__name__)


class BlueprintExportService:
    """Service for blueprint export/import."""

    # =========================================================================
    # Data Collection Methods
    # =========================================================================

    # NOTE: _collect_template_data removed - templates are deprecated
    # Blueprints now reference images via base_image_id, golden_image_id, or snapshot_id

    def _compute_file_checksum(self, content: bytes) -> str:
        """Compute SHA256 checksum of file content."""
        return hashlib.sha256(content).hexdigest()

    # =========================================================================
    # Dockerfile Collection Methods (v3.0)
    # =========================================================================

    def _collect_referenced_image_projects(
        self,
        config: BlueprintConfig,
        db: Session,
    ) -> Dict[str, str]:
        """
        Collect image project names from VMs' BaseImage references.

        Handles multiple reference methods:
        - base_image_id (preferred)
        - golden_image_id -> base_image
        - snapshot_id -> golden_image -> base_image
        - template_name (deprecated fallback - looks up by name)
        - base_image_tag (fallback - looks up by tag)

        Returns:
            Dict mapping project_name to docker_image_tag
        """
        project_map: Dict[str, str] = {}

        for vm in config.vms:
            base_image = None

            # Get the BaseImage through various paths
            if hasattr(vm, 'base_image_id') and vm.base_image_id:
                try:
                    base_image = db.query(BaseImage).filter(
                        BaseImage.id == UUID(vm.base_image_id)
                    ).first()
                except (ValueError, TypeError):
                    pass

            elif hasattr(vm, 'golden_image_id') and vm.golden_image_id:
                try:
                    golden = db.query(GoldenImage).filter(
                        GoldenImage.id == UUID(vm.golden_image_id)
                    ).first()
                    if golden and golden.base_image_id:
                        base_image = db.query(BaseImage).filter(
                            BaseImage.id == golden.base_image_id
                        ).first()
                except (ValueError, TypeError):
                    pass

            elif hasattr(vm, 'snapshot_id') and vm.snapshot_id:
                try:
                    snapshot = db.query(Snapshot).filter(
                        Snapshot.id == UUID(vm.snapshot_id)
                    ).first()
                    if snapshot and snapshot.golden_image_id:
                        golden = db.query(GoldenImage).filter(
                            GoldenImage.id == snapshot.golden_image_id
                        ).first()
                        if golden and golden.base_image_id:
                            base_image = db.query(BaseImage).filter(
                                BaseImage.id == golden.base_image_id
                            ).first()
                except (ValueError, TypeError):
                    pass

            # Fallback: look up by template_name (deprecated but still used)
            if not base_image and hasattr(vm, 'template_name') and vm.template_name:
                base_image = db.query(BaseImage).filter(
                    BaseImage.name == vm.template_name
                ).first()

            # Fallback: look up by base_image_tag
            if not base_image and hasattr(vm, 'base_image_tag') and vm.base_image_tag:
                base_image = db.query(BaseImage).filter(
                    BaseImage.docker_image_tag == vm.base_image_tag
                ).first()

            # If we found a BaseImage with a project name, add it
            if base_image and base_image.image_project_name:
                project_name = base_image.image_project_name
                image_tag = base_image.docker_image_tag or f"cyroid/{project_name}:latest"
                project_map[project_name] = image_tag

        return project_map

    def _collect_dockerfile_projects(
        self,
        project_map: Dict[str, str],
    ) -> List[DockerfileProjectData]:
        """
        Read all files from Dockerfile project directories.

        Args:
            project_map: Dict mapping project_name -> docker_image_tag

        Returns:
            List of DockerfileProjectData objects
        """
        dockerfile_projects: List[DockerfileProjectData] = []

        for project_name, image_tag in project_map.items():
            project_dir = Path(IMAGES_DIR) / project_name

            if not project_dir.exists():
                logger.warning(f"Dockerfile project directory not found: {project_dir}")
                continue

            # Collect all files in the project directory
            files: Dict[str, str] = {}
            description: Optional[str] = None

            for item in project_dir.rglob("*"):
                if item.is_file():
                    rel_path = str(item.relative_to(project_dir))

                    # Skip binary files and large files
                    if item.stat().st_size > 1024 * 1024:  # 1MB limit
                        logger.warning(f"Skipping large file in Dockerfile project: {rel_path}")
                        continue

                    try:
                        content = item.read_text(encoding='utf-8')
                        files[rel_path] = content

                        # Extract description from README if present
                        if rel_path.lower() == 'readme.md':
                            # Use first line or paragraph as description
                            lines = content.strip().split('\n')
                            if lines:
                                # Skip heading marker
                                first_line = lines[0].lstrip('#').strip()
                                description = first_line[:200]  # Limit length

                    except (UnicodeDecodeError, IOError) as e:
                        logger.warning(f"Could not read file {rel_path}: {e}")

            if not files:
                logger.warning(f"No files found in Dockerfile project: {project_name}")
                continue

            if 'Dockerfile' not in files:
                logger.warning(f"No Dockerfile found in project: {project_name}")
                continue

            dockerfile_projects.append(DockerfileProjectData(
                project_name=project_name,
                image_tag=image_tag,
                files=files,
                description=description,
            ))

        return dockerfile_projects

    # =========================================================================
    # Content Collection Methods (v3.0)
    # =========================================================================

    def _collect_content_data(
        self,
        content_id: UUID,
        temp_dir: Path,
        db: Session,
    ) -> Optional[Tuple[ContentExportData, List[str]]]:
        """
        Export Content Library item and its assets.

        Args:
            content_id: UUID of the Content to export
            temp_dir: Temporary directory to store asset files
            db: Database session

        Returns:
            Tuple of (ContentExportData, list of asset archive paths) or None if not found
        """
        content = db.query(Content).filter(Content.id == content_id).first()
        if not content:
            logger.warning(f"Content {content_id} not found")
            return None

        # Compute content hash for deduplication
        content_hash = hashlib.sha256(content.body_markdown.encode()).hexdigest()

        # Collect asset data
        asset_data: List[ContentAssetExportData] = []
        asset_files: List[str] = []

        # Create content_assets directory in temp_dir
        assets_dir = temp_dir / "content_assets"
        assets_dir.mkdir(exist_ok=True)

        for asset in content.assets:
            # Archive path uses a unique prefix to avoid collisions
            archive_filename = f"{asset.sha256_hash[:8]}_{asset.filename}"
            archive_path = f"content_assets/{archive_filename}"

            asset_data.append(ContentAssetExportData(
                filename=asset.filename,
                mime_type=asset.mime_type,
                sha256_hash=asset.sha256_hash or "",
                archive_path=archive_path,
            ))

            # Download asset from MinIO to temp directory
            try:
                self._download_content_asset(asset, assets_dir / archive_filename)
                asset_files.append(str(assets_dir / archive_filename))
            except Exception as e:
                logger.warning(f"Could not download asset {asset.filename}: {e}")

        return ContentExportData(
            title=content.title,
            content_type=content.content_type.value if hasattr(content.content_type, 'value') else str(content.content_type),
            body_markdown=content.body_markdown,
            walkthrough_data=content.walkthrough_data,
            content_hash=content_hash,
            assets=asset_data,
        ), asset_files

    def _download_content_asset(self, asset: ContentAsset, dest_path: Path) -> None:
        """Download a content asset from MinIO to local path."""
        try:
            from cyroid.services.storage_service import get_storage_service

            storage = get_storage_service()

            # Download the asset using storage service's client
            storage.client.fget_object(storage.bucket, asset.file_path, str(dest_path))
            logger.debug(f"Downloaded asset {asset.filename} to {dest_path}")

        except Exception as e:
            logger.error(f"Failed to download asset {asset.file_path}: {e}")
            raise

    # =========================================================================
    # Image Building Methods
    # =========================================================================

    def _image_exists(self, image_name: str) -> bool:
        """Check if a Docker image exists locally."""
        try:
            client = docker.from_env()
            client.images.get(image_name)
            return True
        except docker.errors.ImageNotFound:
            return False
        except Exception as e:
            logger.warning(f"Error checking image {image_name}: {e}")
            return False

    def _safe_image_name(self, image_name: str) -> str:
        """Convert image name to safe directory name."""
        # Replace / and : with underscores
        return image_name.replace("/", "_").replace(":", "_")

    def _build_image(self, image_name: str, dockerfile_dir: Path) -> bool:
        """Build a Docker image from a Dockerfile."""
        try:
            client = docker.from_env()
            logger.info(f"Building image {image_name} from {dockerfile_dir}")

            # Build the image
            image, build_logs = client.images.build(
                path=str(dockerfile_dir),
                tag=image_name,
                rm=True,
                forcerm=True,
            )

            # Log build output
            for log in build_logs:
                if 'stream' in log:
                    logger.debug(log['stream'].strip())

            logger.info(f"Successfully built image {image_name}")
            return True
        except docker.errors.BuildError as e:
            logger.error(f"Failed to build image {image_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error building image {image_name}: {e}")
            return False

    def _build_missing_images(
        self,
        image_names: List[str],
        archive_dir: Path,
    ) -> Tuple[List[str], List[str]]:
        """
        Build any missing container images from Dockerfiles in the archive.

        Returns:
            Tuple of (images_built, errors)
        """
        images_built: List[str] = []
        errors: List[str] = []

        dockerfiles_dir = archive_dir / "dockerfiles"
        if not dockerfiles_dir.exists():
            logger.debug("No dockerfiles directory in archive")
            return images_built, errors

        for image_name in image_names:
            if not image_name:
                continue

            # Check if image already exists
            if self._image_exists(image_name):
                logger.debug(f"Image {image_name} already exists")
                continue

            # Look for Dockerfile
            safe_name = self._safe_image_name(image_name)
            dockerfile_dir = dockerfiles_dir / safe_name

            if not dockerfile_dir.exists():
                # Try without tag
                if ":" in image_name:
                    base_name = image_name.split(":")[0]
                    safe_base = self._safe_image_name(base_name)
                    dockerfile_dir = dockerfiles_dir / safe_base

            if not dockerfile_dir.exists() or not (dockerfile_dir / "Dockerfile").exists():
                logger.warning(f"No Dockerfile found for {image_name}")
                continue

            # Build the image
            if self._build_image(image_name, dockerfile_dir):
                images_built.append(image_name)
            else:
                errors.append(f"Failed to build image: {image_name}")

        return images_built, errors

    # =========================================================================
    # Export Methods
    # =========================================================================

    def export_blueprint(
        self,
        blueprint_id: UUID,
        user: User,
        db: Session,
        options: Optional[BlueprintExportOptions] = None,
        content_id: Optional[UUID] = None,
    ) -> Tuple[Path, str]:
        """
        Export a blueprint as a portable ZIP package.

        Args:
            blueprint_id: UUID of the blueprint to export
            user: The user performing the export
            db: Database session
            options: Export options (defaults to include Dockerfiles and content)
            content_id: Optional Content Library ID to include

        Returns:
            Tuple of (archive_path, filename)
        """
        if options is None:
            options = BlueprintExportOptions()

        # Load blueprint
        blueprint = db.query(RangeBlueprint).filter(RangeBlueprint.id == blueprint_id).first()
        if not blueprint:
            raise ValueError(f"Blueprint {blueprint_id} not found")

        config = BlueprintConfig.model_validate(blueprint.config)

        # Create temporary directory for export
        temp_dir = tempfile.mkdtemp(prefix="cyroid-blueprint-export-")
        temp_path = Path(temp_dir)

        try:
            # ============================================================
            # Collect Dockerfiles (v3.0)
            # ============================================================
            dockerfiles: List[DockerfileProjectData] = []

            if options.include_dockerfiles:
                # Get project names from VM references
                project_map = self._collect_referenced_image_projects(config, db)

                if project_map:
                    # Collect Dockerfile projects (pass full map for correct image tags)
                    dockerfiles = self._collect_dockerfile_projects(project_map)

                    # Write Dockerfile projects to temp directory
                    if dockerfiles:
                        dockerfiles_dir = temp_path / "dockerfiles"
                        dockerfiles_dir.mkdir(exist_ok=True)

                        for project in dockerfiles:
                            project_dir = dockerfiles_dir / project.project_name
                            project_dir.mkdir(exist_ok=True)

                            for filename, content in project.files.items():
                                file_path = project_dir / filename
                                file_path.parent.mkdir(parents=True, exist_ok=True)
                                file_path.write_text(content, encoding='utf-8')

                    logger.info(f"Collected {len(dockerfiles)} Dockerfile projects for export")

            # ============================================================
            # Collect Content (v3.0)
            # ============================================================
            content_data: Optional[ContentExportData] = None
            content_files: List[str] = []

            if options.include_content and content_id:
                result = self._collect_content_data(content_id, temp_path, db)
                if result:
                    content_data, content_files = result
                    logger.info(f"Collected content '{content_data.title}' with {len(content_data.assets)} assets")

            # ============================================================
            # Build Export Structure
            # ============================================================

            # Build blueprint export data
            blueprint_data = BlueprintExportData(
                name=blueprint.name,
                description=blueprint.description,
                version=blueprint.version,
                base_subnet_prefix=blueprint.base_subnet_prefix,
                next_offset=blueprint.next_offset,
                config=config,
                student_guide_id=str(content_id) if content_id else None,
            )

            # Build export structure
            export_data = BlueprintExportFull(
                manifest=BlueprintExportManifest(
                    version="3.0",  # v3.0 for Dockerfile/Content support
                    export_type="blueprint",
                    created_at=datetime.utcnow(),
                    created_by=user.username,
                    blueprint_name=blueprint.name,
                    template_count=0,  # Deprecated
                    dockerfile_count=len(dockerfiles),
                    content_included=content_data is not None,
                    docker_images_included=options.include_docker_images,
                    checksums={},  # Will be computed after writing files
                ),
                blueprint=blueprint_data,
                templates=[],  # Deprecated
                dockerfiles=dockerfiles,
                content=content_data,
            )

            # Write blueprint.json
            blueprint_json_path = temp_path / "blueprint.json"
            blueprint_content = json.dumps(
                export_data.model_dump(mode="json"),
                indent=2,
                default=str
            )
            blueprint_json_path.write_text(blueprint_content)

            # Compute checksums
            checksums = {
                "blueprint.json": self._compute_file_checksum(blueprint_content.encode())
            }

            # Add Dockerfile checksums
            for project in dockerfiles:
                for filename, content in project.files.items():
                    key = f"dockerfiles/{project.project_name}/{filename}"
                    checksums[key] = self._compute_file_checksum(content.encode())

            # Update manifest with checksums
            export_data.manifest.checksums = checksums

            # Rewrite manifest.json with checksums
            manifest_path = temp_path / "manifest.json"
            manifest_path.write_text(
                json.dumps(export_data.manifest.model_dump(mode="json"), indent=2, default=str)
            )

            # ============================================================
            # Create ZIP Archive
            # ============================================================
            timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in blueprint.name)
            filename = f"blueprint-{safe_name}-{timestamp}.zip"
            archive_path = os.path.join(tempfile.gettempdir(), filename)

            with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, temp_dir)
                        zf.write(file_path, arcname)

            logger.info(f"Created blueprint export: {archive_path} "
                       f"(dockerfiles={len(dockerfiles)}, content={'yes' if content_data else 'no'})")
            return Path(archive_path), filename

        finally:
            # Cleanup temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

    # =========================================================================
    # Import Methods
    # =========================================================================

    def _extract_archive(self, archive_path: Path) -> Tuple[BlueprintExportFull, Path]:
        """
        Extract and parse a blueprint export archive.

        Returns:
            Tuple of (export_data, temp_dir_path)
            Caller is responsible for cleaning up temp_dir_path.
        """
        temp_dir = tempfile.mkdtemp(prefix="cyroid-blueprint-import-")

        # Extract archive
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(temp_dir)

        # Read the main blueprint JSON
        blueprint_json_path = os.path.join(temp_dir, "blueprint.json")
        if not os.path.exists(blueprint_json_path):
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise ValueError("Archive missing blueprint.json")

        with open(blueprint_json_path, "r") as f:
            data = json.load(f)

        return BlueprintExportFull.model_validate(data), Path(temp_dir)

    def _read_archive(self, archive_path: Path) -> BlueprintExportFull:
        """Read and parse a blueprint export archive (convenience method)."""
        export_data, temp_dir = self._extract_archive(archive_path)
        shutil.rmtree(temp_dir, ignore_errors=True)
        return export_data

    def validate_import(
        self,
        archive_path: Path,
        db: Session,
    ) -> BlueprintImportValidation:
        """
        Validate a blueprint import archive and detect conflicts.

        Returns:
            BlueprintImportValidation with validation status and conflicts
        """
        errors: List[str] = []
        warnings: List[str] = []
        included_dockerfiles: List[str] = []
        dockerfile_conflicts: List[str] = []
        missing_images: List[str] = []
        content_conflict: Optional[str] = None

        try:
            export_data = self._read_archive(archive_path)
        except Exception as e:
            return BlueprintImportValidation(
                valid=False,
                blueprint_name="unknown",
                errors=[f"Failed to read archive: {str(e)}"],
            )

        blueprint_name = export_data.blueprint.name
        manifest_version = export_data.manifest.version
        conflicts: List[str] = []

        # Check blueprint name conflict
        existing = db.query(RangeBlueprint).filter(
            RangeBlueprint.name == blueprint_name
        ).first()
        if existing:
            conflicts.append(f"Blueprint name '{blueprint_name}' already exists")

        # Validate that VMs have image library sources or fallback fields
        config = export_data.blueprint.config
        for vm in config.vms:
            has_source = (
                (hasattr(vm, 'base_image_id') and vm.base_image_id) or
                (hasattr(vm, 'golden_image_id') and vm.golden_image_id) or
                (hasattr(vm, 'snapshot_id') and vm.snapshot_id)
            )
            has_fallback = (
                (hasattr(vm, 'base_image_tag') and vm.base_image_tag) or
                (hasattr(vm, 'template_name') and vm.template_name)
            )
            if not has_source and not has_fallback:
                errors.append(f"VM '{vm.hostname}' has no image source or fallback")

        # ============================================================
        # Validate Dockerfiles (v3.0)
        # ============================================================
        if hasattr(export_data, 'dockerfiles') and export_data.dockerfiles:
            for dockerfile in export_data.dockerfiles:
                included_dockerfiles.append(dockerfile.project_name)

                # Check if Dockerfile project already exists
                project_dir = Path(IMAGES_DIR) / dockerfile.project_name
                if project_dir.exists():
                    dockerfile_conflicts.append(dockerfile.project_name)
                    warnings.append(f"Dockerfile project '{dockerfile.project_name}' already exists locally")

                # Check if the image needs to be built
                if not self._image_exists(dockerfile.image_tag):
                    missing_images.append(dockerfile.image_tag)

        # ============================================================
        # Validate Content (v3.0)
        # ============================================================
        content_included = False
        if hasattr(export_data, 'content') and export_data.content:
            content_included = True

            # Check for content with same title
            existing_content = db.query(Content).filter(
                Content.title == export_data.content.title
            ).first()
            if existing_content:
                content_conflict = f"Content '{export_data.content.title}' already exists (id={existing_content.id})"
                warnings.append(content_conflict)

        is_valid = len(errors) == 0

        return BlueprintImportValidation(
            valid=is_valid,
            blueprint_name=blueprint_name,
            manifest_version=manifest_version,
            errors=errors,
            warnings=warnings,
            conflicts=conflicts,
            missing_templates=[],  # Deprecated
            included_templates=[],  # Deprecated
            included_dockerfiles=included_dockerfiles,
            dockerfile_conflicts=dockerfile_conflicts,
            missing_images=missing_images,
            content_included=content_included,
            content_conflict=content_conflict,
        )

    # =========================================================================
    # Import Helper Methods (v3.0)
    # =========================================================================

    def _extract_dockerfiles(
        self,
        dockerfiles: List[DockerfileProjectData],
        conflict_strategy: str,
    ) -> Tuple[List[str], List[str], List[str]]:
        """
        Extract Dockerfile projects to /data/images/.

        Args:
            dockerfiles: List of DockerfileProjectData from the archive
            conflict_strategy: "skip", "overwrite", or "error"

        Returns:
            Tuple of (extracted, skipped, errors)
        """
        extracted: List[str] = []
        skipped: List[str] = []
        errors: List[str] = []

        images_dir = Path(IMAGES_DIR)
        images_dir.mkdir(parents=True, exist_ok=True)

        for dockerfile in dockerfiles:
            project_dir = images_dir / dockerfile.project_name

            if project_dir.exists():
                if conflict_strategy == "skip":
                    skipped.append(dockerfile.project_name)
                    logger.info(f"Skipping existing Dockerfile project: {dockerfile.project_name}")
                    continue
                elif conflict_strategy == "error":
                    errors.append(f"Dockerfile project '{dockerfile.project_name}' already exists")
                    continue
                elif conflict_strategy == "overwrite":
                    shutil.rmtree(project_dir)
                    logger.info(f"Overwriting existing Dockerfile project: {dockerfile.project_name}")

            # Create project directory and write files
            try:
                project_dir.mkdir(parents=True, exist_ok=True)

                for filename, content in dockerfile.files.items():
                    file_path = project_dir / filename
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_text(content, encoding='utf-8')

                extracted.append(dockerfile.project_name)
                logger.info(f"Extracted Dockerfile project: {dockerfile.project_name}")

            except Exception as e:
                errors.append(f"Failed to extract {dockerfile.project_name}: {str(e)}")
                logger.error(f"Failed to extract Dockerfile project {dockerfile.project_name}: {e}")

        return extracted, skipped, errors

    def _build_and_register_images(
        self,
        dockerfiles: List[DockerfileProjectData],
        user: User,
        db: Session,
    ) -> Tuple[List[str], List[str]]:
        """
        Build Docker images from extracted Dockerfiles and register BaseImage entries.

        Args:
            dockerfiles: List of DockerfileProjectData to build
            user: User to set as creator
            db: Database session

        Returns:
            Tuple of (images_built, errors)
        """
        images_built: List[str] = []
        errors: List[str] = []

        for dockerfile in dockerfiles:
            image_tag = dockerfile.image_tag
            project_dir = Path(IMAGES_DIR) / dockerfile.project_name

            # Skip if image already exists
            if self._image_exists(image_tag):
                logger.info(f"Image {image_tag} already exists, skipping build")
                continue

            # Check if Dockerfile exists
            if not (project_dir / "Dockerfile").exists():
                logger.warning(f"No Dockerfile found at {project_dir}")
                continue

            # Build the image
            if self._build_image(image_tag, project_dir):
                images_built.append(image_tag)

                # Create or update BaseImage record
                try:
                    existing = db.query(BaseImage).filter(
                        BaseImage.docker_image_tag == image_tag
                    ).first()

                    if existing:
                        existing.image_project_name = dockerfile.project_name
                        db.commit()
                        logger.info(f"Updated BaseImage for {image_tag}")
                    else:
                        # Get the image ID from Docker
                        client = docker.from_env()
                        image = client.images.get(image_tag)

                        base_image = BaseImage(
                            name=dockerfile.project_name,
                            description=dockerfile.description or f"Built from Dockerfile: {dockerfile.project_name}",
                            image_type="container",
                            docker_image_id=image.id,
                            docker_image_tag=image_tag,
                            image_project_name=dockerfile.project_name,
                            os_type="linux",  # Default
                            vm_type="container",
                            size_bytes=image.attrs.get("Size", 0),
                            is_global=True,
                            created_by=user.id,
                        )
                        db.add(base_image)
                        db.commit()
                        logger.info(f"Created BaseImage for {image_tag}")

                except Exception as e:
                    logger.warning(f"Failed to create BaseImage record for {image_tag}: {e}")
            else:
                errors.append(f"Failed to build image: {image_tag}")

        return images_built, errors

    def _import_content(
        self,
        content_data: ContentExportData,
        temp_dir: Path,
        conflict_strategy: str,
        user: User,
        db: Session,
    ) -> Tuple[bool, Optional[UUID], List[str]]:
        """
        Import Content Library item and its assets.

        Args:
            content_data: ContentExportData from the archive
            temp_dir: Temp directory containing extracted assets
            conflict_strategy: "skip", "rename", "use_existing"
            user: User to set as creator
            db: Database session

        Returns:
            Tuple of (imported, content_id, warnings)
        """
        warnings: List[str] = []

        # Check for existing content with same title
        existing = db.query(Content).filter(Content.title == content_data.title).first()

        if existing:
            if conflict_strategy == "use_existing":
                return False, existing.id, [f"Using existing content: {content_data.title}"]
            elif conflict_strategy == "skip":
                return False, None, [f"Skipped content import: {content_data.title} already exists"]
            elif conflict_strategy == "rename":
                # Generate a unique name
                i = 1
                new_title = f"{content_data.title} (imported)"
                while db.query(Content).filter(Content.title == new_title).first():
                    i += 1
                    new_title = f"{content_data.title} (imported {i})"
                content_data.title = new_title
                warnings.append(f"Renamed content to: {new_title}")

        try:
            # Import ContentType enum
            from cyroid.models.content import ContentType

            # Create the Content record
            content = Content(
                title=content_data.title,
                content_type=ContentType(content_data.content_type),
                body_markdown=content_data.body_markdown,
                walkthrough_data=content_data.walkthrough_data,
                version="1.0",
                created_by_id=user.id,
                is_published=False,
            )
            db.add(content)
            db.flush()  # Get the content ID

            # Import assets
            for asset_data in content_data.assets:
                asset_path = temp_dir / asset_data.archive_path

                if not asset_path.exists():
                    warnings.append(f"Asset file not found: {asset_data.archive_path}")
                    continue

                # Upload to MinIO
                try:
                    minio_path = self._upload_content_asset(
                        asset_path,
                        content.id,
                        asset_data.filename,
                    )

                    # Create ContentAsset record
                    asset = ContentAsset(
                        content_id=content.id,
                        filename=asset_data.filename,
                        file_path=minio_path,
                        mime_type=asset_data.mime_type,
                        file_size=asset_path.stat().st_size,
                        sha256_hash=asset_data.sha256_hash,
                    )
                    db.add(asset)

                except Exception as e:
                    warnings.append(f"Failed to upload asset {asset_data.filename}: {e}")

            db.commit()
            db.refresh(content)

            logger.info(f"Imported content: {content.title} (id={content.id})")
            return True, content.id, warnings

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to import content: {e}")
            return False, None, [f"Failed to import content: {str(e)}"]

    def _upload_content_asset(
        self,
        local_path: Path,
        content_id: UUID,
        filename: str,
    ) -> str:
        """Upload a content asset to MinIO."""
        try:
            from cyroid.services.storage_service import get_storage_service

            storage = get_storage_service()

            # Generate MinIO path
            minio_path = f"content/{content_id}/{filename}"

            # Upload the file
            storage.client.fput_object(storage.bucket, minio_path, str(local_path))
            logger.debug(f"Uploaded asset {filename} to {minio_path}")

            return minio_path

        except Exception as e:
            logger.error(f"Failed to upload asset to MinIO: {e}")
            raise

    def import_blueprint(
        self,
        archive_path: Path,
        options: BlueprintImportOptions,
        user: User,
        db: Session,
    ) -> BlueprintImportResult:
        """
        Import a blueprint from an archive (v3.0 with Dockerfiles and Content).

        Automatically:
        1. Extracts Dockerfiles to /data/images/
        2. Builds missing Docker images
        3. Creates BaseImage records
        4. Imports Content Library items

        Returns:
            BlueprintImportResult with success status and created resources
        """
        errors: List[str] = []
        warnings: List[str] = []
        templates_created: List[str] = []
        templates_skipped: List[str] = []
        images_built: List[str] = []
        dockerfiles_extracted: List[str] = []
        dockerfiles_skipped: List[str] = []
        content_imported: bool = False
        content_id: Optional[UUID] = None
        temp_dir: Optional[Path] = None

        try:
            export_data, temp_dir = self._extract_archive(archive_path)
        except Exception as e:
            return BlueprintImportResult(
                success=False,
                errors=[f"Failed to read archive: {str(e)}"],
            )

        try:
            # Validate first
            validation = self.validate_import(archive_path, db)
            if not validation.valid and not options.new_name:
                return BlueprintImportResult(
                    success=False,
                    errors=validation.errors,
                    warnings=validation.warnings,
                )

            # Determine blueprint name
            blueprint_name = options.new_name or export_data.blueprint.name

            # Check for name conflict again with potential new name
            existing = db.query(RangeBlueprint).filter(
                RangeBlueprint.name == blueprint_name
            ).first()
            if existing:
                return BlueprintImportResult(
                    success=False,
                    errors=[f"Blueprint name '{blueprint_name}' already exists"],
                    images_built=images_built,
                )

            # ============================================================
            # Extract Dockerfiles (v3.0)
            # ============================================================
            if hasattr(export_data, 'dockerfiles') and export_data.dockerfiles:
                extracted, skipped, extract_errors = self._extract_dockerfiles(
                    export_data.dockerfiles,
                    options.dockerfile_conflict_strategy,
                )
                dockerfiles_extracted.extend(extracted)
                dockerfiles_skipped.extend(skipped)
                errors.extend(extract_errors)

                if errors and options.dockerfile_conflict_strategy == "error":
                    return BlueprintImportResult(
                        success=False,
                        errors=errors,
                        warnings=warnings,
                        dockerfiles_extracted=dockerfiles_extracted,
                        dockerfiles_skipped=dockerfiles_skipped,
                    )

                # Build images if requested
                if options.build_images and export_data.dockerfiles:
                    built, build_errors = self._build_and_register_images(
                        export_data.dockerfiles,
                        user,
                        db,
                    )
                    images_built.extend(built)
                    for err in build_errors:
                        warnings.append(err)  # Build failures are warnings, not errors

            # ============================================================
            # Import Content (v3.0)
            # ============================================================
            if hasattr(export_data, 'content') and export_data.content:
                imported, cid, content_warnings = self._import_content(
                    export_data.content,
                    temp_dir,
                    options.content_conflict_strategy,
                    user,
                    db,
                )
                content_imported = imported
                content_id = cid
                warnings.extend(content_warnings)

            # ============================================================
            # Create the Blueprint
            # ============================================================
            blueprint = RangeBlueprint(
                name=blueprint_name,
                description=export_data.blueprint.description,
                config=export_data.blueprint.config.model_dump(),
                base_subnet_prefix=export_data.blueprint.base_subnet_prefix,
                version=export_data.blueprint.version,
                next_offset=0,  # Reset offset for new instance
                created_by=user.id,
            )
            db.add(blueprint)
            db.commit()
            db.refresh(blueprint)

            logger.info(
                f"Imported blueprint: {blueprint.name} (id={blueprint.id}) "
                f"dockerfiles={len(dockerfiles_extracted)}, "
                f"images_built={len(images_built)}, "
                f"content={'yes' if content_imported else 'no'}"
            )

            return BlueprintImportResult(
                success=True,
                blueprint_id=blueprint.id,
                blueprint_name=blueprint.name,
                templates_created=templates_created,
                templates_skipped=templates_skipped,
                images_built=images_built,
                dockerfiles_extracted=dockerfiles_extracted,
                dockerfiles_skipped=dockerfiles_skipped,
                content_imported=content_imported,
                content_id=content_id,
                warnings=warnings,
            )

        except Exception as e:
            db.rollback()
            logger.exception("Blueprint import failed")
            return BlueprintImportResult(
                success=False,
                errors=[f"Import failed: {str(e)}"],
                warnings=warnings,
                images_built=images_built,
                dockerfiles_extracted=dockerfiles_extracted,
                dockerfiles_skipped=dockerfiles_skipped,
            )

        finally:
            # Clean up temp directory
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)


# Singleton instance
_blueprint_export_service: Optional[BlueprintExportService] = None


def get_blueprint_export_service() -> BlueprintExportService:
    """Get the blueprint export service singleton."""
    global _blueprint_export_service
    if _blueprint_export_service is None:
        _blueprint_export_service = BlueprintExportService()
    return _blueprint_export_service
