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
from cyroid.models.template import VMTemplate, OSType, VMType
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

    def _collect_template_data(self, template: VMTemplate) -> TemplateExportData:
        """Collect full template definition for export."""
        return TemplateExportData(
            name=template.name,
            description=template.description,
            os_type=template.os_type.value,
            os_variant=template.os_variant,
            base_image=template.base_image,
            vm_type=template.vm_type.value,
            linux_distro=template.linux_distro,
            boot_mode=template.boot_mode,
            disk_type=template.disk_type,
            default_cpu=template.default_cpu,
            default_ram_mb=template.default_ram_mb,
            default_disk_gb=template.default_disk_gb,
            config_script=template.config_script,
            tags=template.tags or [],
        )

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
        templates: List[TemplateExportData],
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

        for template in templates:
            # Only process container templates
            if template.vm_type != "container":
                continue

            image_name = template.base_image
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
            # Collect template names from VMs in config
            template_names = {vm.template_name for vm in config.vms}

            # Load templates
            templates_data: List[TemplateExportData] = []
            if template_names:
                stmt = select(VMTemplate).where(VMTemplate.name.in_(template_names))
                result = db.execute(stmt)
                for template in result.scalars():
                    templates_data.append(self._collect_template_data(template))

            # Build blueprint export data
            blueprint_data = BlueprintExportData(
                name=blueprint.name,
                description=blueprint.description,
                version=blueprint.version,
                base_subnet_prefix=blueprint.base_subnet_prefix,
                next_offset=blueprint.next_offset,
                config=config,
            )

            # Build export structure
            export_data = BlueprintExportFull(
                manifest=BlueprintExportManifest(
                    version="1.0",
                    export_type="blueprint",
                    created_at=datetime.utcnow(),
                    created_by=user.username,
                    blueprint_name=blueprint.name,
                    template_count=len(templates_data),
                    checksums={},  # Will be computed after writing files
                ),
                blueprint=blueprint_data,
                templates=templates_data,
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

            # Write templates as individual files for easy inspection
            templates_dir = os.path.join(temp_dir, "templates")
            os.makedirs(templates_dir, exist_ok=True)
            for template in templates_data:
                template_filename = f"{template.name.replace('/', '_').replace(' ', '_')}.json"
                template_path = os.path.join(templates_dir, template_filename)
                template_content = json.dumps(template.model_dump(), indent=2)
                with open(template_path, "w") as f:
                    f.write(template_content)
                checksums[f"templates/{template_filename}"] = self._compute_file_checksum(
                    template_content.encode()
                )

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
        missing_templates: List[str] = []
        included_templates = [t.name for t in export_data.templates]

        # Check blueprint name conflict
        existing = db.query(RangeBlueprint).filter(
            RangeBlueprint.name == blueprint_name
        ).first()
        if existing:
            conflicts.append(f"Blueprint name '{blueprint_name}' already exists")

        # Get template names used by blueprint VMs
        config = export_data.blueprint.config
        needed_templates = {vm.template_name for vm in config.vms}
        included_template_names = {t.name for t in export_data.templates}

        # Check which templates exist in target system
        if needed_templates:
            stmt = select(VMTemplate.name).where(VMTemplate.name.in_(needed_templates))
            result = db.execute(stmt)
            existing_template_names = {row[0] for row in result}
        else:
            existing_template_names = set()

        # Templates that are neither included nor existing
        for tpl_name in needed_templates:
            if tpl_name not in included_template_names and tpl_name not in existing_template_names:
                missing_templates.append(tpl_name)
                errors.append(f"Template '{tpl_name}' is required but not included and not found in target system")

        # Check for template conflicts (template exists with same name)
        for tpl_name in included_template_names:
            if tpl_name in existing_template_names:
                warnings.append(f"Template '{tpl_name}' already exists - will use existing")

        # Check subnet prefix conflicts (informational only)
        base_prefix = export_data.blueprint.base_subnet_prefix
        # This is just a warning since subnets are dynamic based on offset

        is_valid = len(errors) == 0

        return BlueprintImportValidation(
            valid=is_valid,
            blueprint_name=blueprint_name,
            errors=errors,
            warnings=warnings,
            conflicts=conflicts,
            missing_templates=missing_templates,
            included_templates=included_templates,
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

            # Build any missing container images from included Dockerfiles
            logger.info("Checking for missing container images...")
            built, build_errors = self._build_missing_images(
                export_data.templates,
                temp_dir,
            )
            images_built.extend(built)
            if build_errors:
                warnings.extend(build_errors)

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

            # Process templates
            for template_data in export_data.templates:
                existing_template = db.query(VMTemplate).filter(
                    VMTemplate.name == template_data.name
                ).first()

                if existing_template:
                    if options.template_conflict_strategy == "skip":
                        templates_skipped.append(template_data.name)
                        warnings.append(f"Template '{template_data.name}' exists - skipped")
                    elif options.template_conflict_strategy == "update":
                        # Update existing template
                        existing_template.description = template_data.description
                        existing_template.os_type = OSType(template_data.os_type)
                        existing_template.os_variant = template_data.os_variant
                        existing_template.base_image = template_data.base_image
                        existing_template.vm_type = VMType(template_data.vm_type)
                        existing_template.linux_distro = template_data.linux_distro
                        existing_template.boot_mode = template_data.boot_mode
                        existing_template.disk_type = template_data.disk_type
                        existing_template.default_cpu = template_data.default_cpu
                        existing_template.default_ram_mb = template_data.default_ram_mb
                        existing_template.default_disk_gb = template_data.default_disk_gb
                        existing_template.config_script = template_data.config_script
                        existing_template.tags = template_data.tags
                        templates_created.append(f"{template_data.name} (updated)")
                    else:  # error
                        errors.append(f"Template '{template_data.name}' already exists")
                else:
                    # Create new template
                    new_template = VMTemplate(
                        name=template_data.name,
                        description=template_data.description,
                        os_type=OSType(template_data.os_type),
                        os_variant=template_data.os_variant,
                        base_image=template_data.base_image,
                        vm_type=VMType(template_data.vm_type),
                        linux_distro=template_data.linux_distro,
                        boot_mode=template_data.boot_mode,
                        disk_type=template_data.disk_type,
                        default_cpu=template_data.default_cpu,
                        default_ram_mb=template_data.default_ram_mb,
                        default_disk_gb=template_data.default_disk_gb,
                        config_script=template_data.config_script,
                        tags=template_data.tags,
                        created_by=user.id,
                    )
                    db.add(new_template)
                    templates_created.append(template_data.name)

            if errors and options.template_conflict_strategy == "error":
                db.rollback()
                return BlueprintImportResult(
                    success=False,
                    errors=errors,
                    warnings=warnings,
                    images_built=images_built,
                )

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
