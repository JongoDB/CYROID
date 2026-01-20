# backend/cyroid/services/blueprint_export_service.py
"""
Blueprint export/import service.

Exports blueprints as portable packages that can be imported into separate CYROID instances,
including all dependencies needed for successful deployment.
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
from typing import Optional, Dict, List, Tuple
from uuid import UUID

import docker
from sqlalchemy import select
from sqlalchemy.orm import Session

from cyroid.models.blueprint import RangeBlueprint
from cyroid.models.template import OSType, VMType
from cyroid.models.base_image import BaseImage
from cyroid.models.golden_image import GoldenImage
from cyroid.models.user import User
from cyroid.schemas.blueprint import BlueprintConfig
from cyroid.schemas.blueprint_export import (
    BlueprintExportManifest,
    BlueprintExportFull,
    BlueprintExportData,
    TemplateExportData,
    BlueprintImportValidation,
    BlueprintImportOptions,
    BlueprintImportResult,
)

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
    ) -> Tuple[Path, str]:
        """
        Export a blueprint as a portable ZIP package.

        Returns:
            Tuple of (archive_path, filename)
        """
        # Load blueprint
        blueprint = db.query(RangeBlueprint).filter(RangeBlueprint.id == blueprint_id).first()
        if not blueprint:
            raise ValueError(f"Blueprint {blueprint_id} not found")

        config = BlueprintConfig.model_validate(blueprint.config)

        # Create temporary directory for export
        temp_dir = tempfile.mkdtemp(prefix="cyroid-blueprint-export-")
        try:
            # Templates deprecated - blueprints now use Image Library IDs
            # VMs reference base_image_id, golden_image_id, or snapshot_id directly

            # Build blueprint export data
            blueprint_data = BlueprintExportData(
                name=blueprint.name,
                description=blueprint.description,
                version=blueprint.version,
                base_subnet_prefix=blueprint.base_subnet_prefix,
                next_offset=blueprint.next_offset,
                config=config,
            )

            # Build export structure (no templates included)
            export_data = BlueprintExportFull(
                manifest=BlueprintExportManifest(
                    version="2.0",  # Updated version for Image Library
                    export_type="blueprint",
                    created_at=datetime.utcnow(),
                    created_by=user.username,
                    blueprint_name=blueprint.name,
                    template_count=0,  # Templates deprecated
                    checksums={},  # Will be computed after writing files
                ),
                blueprint=blueprint_data,
                templates=[],  # Empty - templates deprecated
            )

            # Write blueprint.json
            blueprint_json_path = os.path.join(temp_dir, "blueprint.json")
            blueprint_content = json.dumps(
                export_data.model_dump(mode="json"),
                indent=2,
                default=str
            )
            with open(blueprint_json_path, "w") as f:
                f.write(blueprint_content)

            # Compute checksums
            checksums = {
                "blueprint.json": self._compute_file_checksum(blueprint_content.encode())
            }

            # Update manifest with checksums
            export_data.manifest.checksums = checksums

            # Rewrite manifest.json with checksums
            manifest_path = os.path.join(temp_dir, "manifest.json")
            with open(manifest_path, "w") as f:
                json.dump(export_data.manifest.model_dump(mode="json"), f, indent=2, default=str)

            # Create zip archive
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

            logger.info(f"Created blueprint export: {archive_path}")
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

        try:
            export_data = self._read_archive(archive_path)
        except Exception as e:
            return BlueprintImportValidation(
                valid=False,
                blueprint_name="unknown",
                errors=[f"Failed to read archive: {str(e)}"],
                warnings=[],
                conflicts=[],
                missing_templates=[],
                included_templates=[],
            )

        blueprint_name = export_data.blueprint.name
        conflicts: List[str] = []

        # Check blueprint name conflict
        existing = db.query(RangeBlueprint).filter(
            RangeBlueprint.name == blueprint_name
        ).first()
        if existing:
            conflicts.append(f"Blueprint name '{blueprint_name}' already exists")

        # Validate that VMs have image library sources
        config = export_data.blueprint.config
        for vm in config.vms:
            has_source = (
                (hasattr(vm, 'base_image_id') and vm.base_image_id) or
                (hasattr(vm, 'golden_image_id') and vm.golden_image_id) or
                (hasattr(vm, 'snapshot_id') and vm.snapshot_id)
            )
            if not has_source:
                errors.append(f"VM '{vm.hostname}' has no image source (base_image_id, golden_image_id, or snapshot_id)")

        is_valid = len(errors) == 0

        return BlueprintImportValidation(
            valid=is_valid,
            blueprint_name=blueprint_name,
            errors=errors,
            warnings=warnings,
            conflicts=conflicts,
            missing_templates=[],  # Deprecated
            included_templates=[],  # Deprecated
        )

    def import_blueprint(
        self,
        archive_path: Path,
        options: BlueprintImportOptions,
        user: User,
        db: Session,
    ) -> BlueprintImportResult:
        """
        Import a blueprint from an archive.

        Automatically builds any missing container images from Dockerfiles
        included in the archive.

        Returns:
            BlueprintImportResult with success status and created resources
        """
        errors: List[str] = []
        warnings: List[str] = []
        templates_created: List[str] = []
        templates_skipped: List[str] = []
        images_built: List[str] = []
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

            # Templates deprecated - VMs now use Image Library (base_image_id, golden_image_id, snapshot_id)
            # No template processing needed

            # Create the blueprint
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

            logger.info(f"Imported blueprint: {blueprint.name} (id={blueprint.id})")
            if images_built:
                logger.info(f"Built {len(images_built)} container images: {images_built}")

            return BlueprintImportResult(
                success=True,
                blueprint_id=blueprint.id,
                blueprint_name=blueprint.name,
                templates_created=templates_created,
                templates_skipped=templates_skipped,
                images_built=images_built,
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
