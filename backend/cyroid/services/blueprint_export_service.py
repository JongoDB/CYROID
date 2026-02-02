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
import asyncio
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
from typing import Optional, Dict, List, Tuple, Set, Any, Callable
from uuid import UUID

import docker
from sqlalchemy import select
from sqlalchemy.orm import Session

from .registry_service import get_registry_service, RegistryPushError

from cyroid.models.blueprint import RangeBlueprint
from cyroid.models.vm_enums import OSType, VMType
from cyroid.models.base_image import BaseImage
from cyroid.models.golden_image import GoldenImage
from cyroid.models.snapshot import Snapshot
from cyroid.models.content import Content, ContentAsset
from cyroid.models.artifact import Artifact
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
    ArtifactExportData,
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
        - base_image_id (preferred - UUID lookup)
        - golden_image_id -> base_image
        - snapshot_id -> golden_image -> base_image
        - base_image_tag (preferred fallback - looks up by docker_image_tag)
        - template_name (deprecated fallback - looks up by name)

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

            # Fallback: look up by base_image_tag (preferred for seed blueprints)
            if not base_image and hasattr(vm, 'base_image_tag') and vm.base_image_tag:
                base_image = db.query(BaseImage).filter(
                    BaseImage.docker_image_tag == vm.base_image_tag
                ).first()

            # Fallback: look up by template_name (deprecated - kept for backward compatibility)
            if not base_image and hasattr(vm, 'template_name') and vm.template_name:
                base_image = db.query(BaseImage).filter(
                    BaseImage.name == vm.template_name
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
    # Artifact Collection Methods (v4.0)
    # =========================================================================

    def _collect_artifacts(
        self,
        artifact_ids: List[str],
        temp_dir: Path,
        db: Session,
    ) -> Tuple[List[ArtifactExportData], List[str]]:
        """
        Collect artifacts and download them to temp directory.

        Args:
            artifact_ids: List of artifact UUIDs to export
            temp_dir: Temporary directory to store files
            db: Database session

        Returns:
            Tuple of (artifact_data_list, file_paths)
        """
        from cyroid.services.storage_service import get_storage_service

        artifacts_data: List[ArtifactExportData] = []
        file_paths: List[str] = []

        # Create artifacts directory
        artifacts_dir = temp_dir / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)

        storage = get_storage_service()

        for artifact_id in artifact_ids:
            try:
                artifact = db.query(Artifact).filter(Artifact.id == UUID(artifact_id)).first()
                if not artifact:
                    logger.warning(f"Artifact {artifact_id} not found")
                    continue

                # Generate archive path
                archive_filename = f"{artifact.sha256_hash[:8]}_{artifact.name}"
                archive_path = f"artifacts/{archive_filename}"
                local_path = artifacts_dir / archive_filename

                # Download from MinIO
                try:
                    storage.client.fget_object(storage.bucket, artifact.file_path, str(local_path))
                    file_paths.append(str(local_path))

                    artifacts_data.append(ArtifactExportData(
                        name=artifact.name,
                        description=artifact.description,
                        category=artifact.category.value if hasattr(artifact.category, 'value') else str(artifact.category),
                        sha256_hash=artifact.sha256_hash,
                        file_size=artifact.file_size,
                        archive_path=archive_path,
                    ))
                    logger.debug(f"Collected artifact: {artifact.name}")

                except Exception as e:
                    logger.warning(f"Could not download artifact {artifact.name}: {e}")

            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid artifact ID {artifact_id}: {e}")

        return artifacts_data, file_paths

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
    # Docker Image Export Methods (v4.0)
    # =========================================================================

    def _collect_image_tags_from_config(
        self,
        config: BlueprintConfig,
        db: Session,
    ) -> Set[str]:
        """
        Collect all Docker image tags referenced by VMs in the config.

        Returns:
            Set of Docker image tags
        """
        image_tags: Set[str] = set()

        for vm in config.vms:
            image_tag = None

            # Try to get image tag from BaseImage reference
            if hasattr(vm, 'base_image_id') and vm.base_image_id:
                try:
                    base_image = db.query(BaseImage).filter(
                        BaseImage.id == UUID(vm.base_image_id)
                    ).first()
                    if base_image and base_image.docker_image_tag:
                        image_tag = base_image.docker_image_tag
                except (ValueError, TypeError):
                    pass

            # Try golden image -> base image
            if not image_tag and hasattr(vm, 'golden_image_id') and vm.golden_image_id:
                try:
                    golden = db.query(GoldenImage).filter(
                        GoldenImage.id == UUID(vm.golden_image_id)
                    ).first()
                    if golden and golden.base_image_id:
                        base_image = db.query(BaseImage).filter(
                            BaseImage.id == golden.base_image_id
                        ).first()
                        if base_image and base_image.docker_image_tag:
                            image_tag = base_image.docker_image_tag
                except (ValueError, TypeError):
                    pass

            # Try snapshot -> golden -> base
            if not image_tag and hasattr(vm, 'snapshot_id') and vm.snapshot_id:
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
                            if base_image and base_image.docker_image_tag:
                                image_tag = base_image.docker_image_tag
                except (ValueError, TypeError):
                    pass

            # Fallback: direct base_image_tag field
            if not image_tag and hasattr(vm, 'base_image_tag') and vm.base_image_tag:
                image_tag = vm.base_image_tag

            # Fallback: template_name lookup
            if not image_tag and hasattr(vm, 'template_name') and vm.template_name:
                base_image = db.query(BaseImage).filter(
                    BaseImage.name == vm.template_name
                ).first()
                if base_image and base_image.docker_image_tag:
                    image_tag = base_image.docker_image_tag

            if image_tag:
                image_tags.add(image_tag)

        return image_tags

    def _export_docker_images(
        self,
        image_tags: Set[str],
        temp_dir: Path,
    ) -> Tuple[List[str], List[str]]:
        """
        Export Docker images as tarballs to the temp directory.

        Args:
            image_tags: Set of Docker image tags to export
            temp_dir: Temporary directory to store tarballs

        Returns:
            Tuple of (exported_images, errors)
        """
        exported: List[str] = []
        errors: List[str] = []

        if not image_tags:
            return exported, errors

        # Create images directory
        images_dir = temp_dir / "images"
        images_dir.mkdir(exist_ok=True)

        try:
            client = docker.from_env()
        except Exception as e:
            logger.error(f"Failed to connect to Docker: {e}")
            errors.append(f"Failed to connect to Docker: {e}")
            return exported, errors

        for image_tag in image_tags:
            try:
                # Check if image exists locally
                try:
                    image = client.images.get(image_tag)
                except docker.errors.ImageNotFound:
                    logger.warning(f"Image {image_tag} not found locally, attempting pull")
                    try:
                        image = client.images.pull(image_tag)
                    except Exception as pull_err:
                        errors.append(f"Image {image_tag} not found and pull failed: {pull_err}")
                        continue

                # Generate safe filename
                safe_name = self._safe_image_name(image_tag)
                tarball_path = images_dir / f"{safe_name}.tar"

                # Export image using docker save
                logger.info(f"Exporting Docker image: {image_tag} -> {tarball_path}")

                with open(tarball_path, 'wb') as f:
                    for chunk in image.save(named=True):
                        f.write(chunk)

                exported.append(image_tag)
                logger.info(f"Exported Docker image: {image_tag} ({tarball_path.stat().st_size / 1024 / 1024:.1f} MB)")

            except Exception as e:
                logger.error(f"Failed to export image {image_tag}: {e}")
                errors.append(f"Failed to export {image_tag}: {e}")

        return exported, errors

    # =========================================================================
    # Docker Image Import Methods (v4.0)
    # =========================================================================

    async def _load_image_to_registry(
        self,
        tar_path: Path,
        progress_callback: Optional[Callable[[str, int], None]] = None
    ) -> List[str]:
        """Load image from tar file and push to registry.

        Args:
            tar_path: Path to the image tar file
            progress_callback: Optional progress callback

        Returns:
            List of image tags that were loaded and pushed

        Raises:
            RegistryPushError: If registry is not healthy or push fails
        """
        registry = get_registry_service()

        # Check registry health first
        if not await registry.is_healthy():
            raise RegistryPushError("Registry is not healthy, cannot push imported images")

        # Load image to host Docker temporarily
        try:
            docker_client = docker.from_env()
        except Exception as e:
            raise RegistryPushError(f"Failed to connect to Docker: {e}")

        if progress_callback:
            progress_callback("Loading image from tar...", 10)

        # Load the image
        loaded_tags: List[str] = []
        try:
            with open(tar_path, "rb") as f:
                images = docker_client.images.load(f)
                for img in images:
                    loaded_tags.extend(img.tags)
        except Exception as e:
            raise RegistryPushError(f"Failed to load image from {tar_path}: {e}")

        if not loaded_tags:
            logger.warning(f"No tags found in image tar: {tar_path}")
            return []

        if progress_callback:
            progress_callback(f"Loaded {len(loaded_tags)} tags, pushing to registry...", 30)

        # Push each tag to registry
        pushed_tags: List[str] = []
        for i, tag in enumerate(loaded_tags):
            try:
                if progress_callback:
                    percent = 30 + int((i / len(loaded_tags)) * 60)
                    progress_callback(f"Pushing {tag}...", percent)

                # Push to registry and cleanup host
                await registry.push_and_cleanup(tag, progress_callback=None)
                pushed_tags.append(tag)
                logger.info(f"Pushed imported image to registry: {tag}")

            except RegistryPushError:
                raise
            except Exception as e:
                logger.error(f"Failed to push {tag} to registry: {e}")
                raise RegistryPushError(f"Failed to push {tag} to registry: {e}")

        if progress_callback:
            progress_callback("Push complete", 100)

        return pushed_tags

    def _extract_docker_images(
        self,
        archive_dir: Path,
        docker_images: List[str],
        progress_callback: Optional[Callable[[str, int], None]] = None,
    ) -> Tuple[List[str], List[str], List[str]]:
        """
        Extract Docker images from tar files in archive and push to registry.

        Args:
            archive_dir: Path to extracted archive directory
            docker_images: List of image tags from manifest
            progress_callback: Optional progress callback

        Returns:
            Tuple of (loaded_tags, skipped_tags, errors)
        """
        loaded: List[str] = []
        skipped: List[str] = []
        errors: List[str] = []

        images_dir = archive_dir / "images"
        if not images_dir.exists():
            logger.debug("No images directory in archive")
            return loaded, skipped, errors

        registry = get_registry_service()

        for i, image_tag in enumerate(docker_images):
            # Build the tar file path from the image tag
            safe_name = self._safe_image_name(image_tag)
            tar_path = images_dir / f"{safe_name}.tar"

            if not tar_path.exists():
                logger.warning(f"Image tar not found for {image_tag}: {tar_path}")
                errors.append(f"Image tar not found: {image_tag}")
                continue

            # Check if image already exists in registry
            loop = asyncio.new_event_loop()
            try:
                already_exists = loop.run_until_complete(registry.image_exists(image_tag))
            finally:
                loop.close()

            if already_exists:
                logger.info(f"Skipping Docker image (already in registry): {image_tag}")
                skipped.append(image_tag)
                continue

            # Load and push to registry
            logger.info(f"Loading Docker image from tar: {image_tag}")

            loop = asyncio.new_event_loop()
            try:
                tags = loop.run_until_complete(
                    self._load_image_to_registry(tar_path, progress_callback)
                )
                loaded.extend(tags)
            except RegistryPushError as e:
                logger.error(f"Failed to push image to registry: {e}")
                errors.append(str(e))
            except Exception as e:
                logger.error(f"Failed to load/push image {image_tag}: {e}")
                errors.append(f"Failed to load/push {image_tag}: {e}")
            finally:
                loop.close()

        return loaded, skipped, errors

    # =========================================================================
    # Export Size Estimation
    # =========================================================================

    def estimate_export_size(
        self,
        blueprint_id: UUID,
        db: Session,
        include_docker_images: bool = False,
    ) -> Dict[str, Any]:
        """
        Estimate the export size for a blueprint.

        Args:
            blueprint_id: UUID of the blueprint
            db: Database session
            include_docker_images: Whether to include Docker image sizes

        Returns:
            Dict with size estimates
        """
        from cyroid.models.blueprint import RangeBlueprint

        blueprint = db.query(RangeBlueprint).filter(RangeBlueprint.id == blueprint_id).first()
        if not blueprint:
            raise ValueError(f"Blueprint {blueprint_id} not found")

        config = BlueprintConfig.model_validate(blueprint.config)

        result = {
            "blueprint_id": str(blueprint_id),
            "blueprint_name": blueprint.name,
            "base_size_bytes": 10000,  # Estimate for JSON files
            "docker_images": [],
            "docker_images_total_bytes": 0,
            "total_bytes": 10000,
        }

        if include_docker_images:
            image_tags = self._collect_image_tags_from_config(config, db)

            try:
                client = docker.from_env()

                for image_tag in image_tags:
                    try:
                        image = client.images.get(image_tag)
                        size_bytes = image.attrs.get("Size", 0)
                        result["docker_images"].append({
                            "tag": image_tag,
                            "size_bytes": size_bytes,
                            "size_human": self._format_size(size_bytes),
                        })
                        result["docker_images_total_bytes"] += size_bytes
                    except docker.errors.ImageNotFound:
                        result["docker_images"].append({
                            "tag": image_tag,
                            "size_bytes": 0,
                            "size_human": "Unknown (not pulled)",
                            "missing": True,
                        })
                    except Exception as e:
                        logger.warning(f"Failed to get size for {image_tag}: {e}")
                        result["docker_images"].append({
                            "tag": image_tag,
                            "size_bytes": 0,
                            "size_human": "Unknown",
                            "error": str(e),
                        })

            except Exception as e:
                logger.error(f"Failed to connect to Docker: {e}")
                result["error"] = f"Failed to connect to Docker: {e}"

        result["total_bytes"] = result["base_size_bytes"] + result["docker_images_total_bytes"]
        result["total_human"] = self._format_size(result["total_bytes"])
        result["docker_images_total_human"] = self._format_size(result["docker_images_total_bytes"])

        return result

    def _format_size(self, size_bytes: int) -> str:
        """Format bytes as human-readable string."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / 1024 / 1024:.1f} MB"
        else:
            return f"{size_bytes / 1024 / 1024 / 1024:.2f} GB"

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
            # Handle MSEL option (v4.0)
            # ============================================================
            export_config = config
            msel_included = False

            if hasattr(config, 'msel') and config.msel:
                if options.include_msel:
                    msel_included = True
                else:
                    # Create a copy of config without MSEL
                    config_dict = config.model_dump()
                    config_dict['msel'] = None
                    export_config = BlueprintConfig.model_validate(config_dict)
                    logger.info("MSEL excluded from export per options")

            # ============================================================
            # Collect Artifacts (v4.0)
            # ============================================================
            artifacts_data: List[ArtifactExportData] = []
            artifact_files: List[str] = []

            if options.include_artifacts:
                # Get artifact IDs from blueprint config if available
                artifact_ids = []
                if hasattr(config, 'artifact_ids') and config.artifact_ids:
                    artifact_ids = config.artifact_ids
                elif hasattr(blueprint, 'artifact_ids') and blueprint.artifact_ids:
                    artifact_ids = blueprint.artifact_ids

                if artifact_ids:
                    artifacts_data, artifact_files = self._collect_artifacts(
                        artifact_ids, temp_path, db
                    )
                    logger.info(f"Collected {len(artifacts_data)} artifacts for export")

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

            if options.include_content:
                # Use explicit content_id if provided, otherwise use first from blueprint's content_ids
                export_content_id = content_id
                if not export_content_id and blueprint.content_ids:
                    try:
                        export_content_id = UUID(blueprint.content_ids[0])
                        logger.info(f"Using content_id from blueprint.content_ids: {export_content_id}")
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Could not parse content_id from blueprint.content_ids: {e}")

                if export_content_id:
                    result = self._collect_content_data(export_content_id, temp_path, db)
                    if result:
                        content_data, content_files = result
                        logger.info(f"Collected content '{content_data.title}' with {len(content_data.assets)} assets")

            # ============================================================
            # Export Docker Images (v4.0)
            # ============================================================
            exported_images: List[str] = []
            image_export_errors: List[str] = []

            if options.include_docker_images:
                # Collect all image tags from config
                image_tags = self._collect_image_tags_from_config(config, db)

                if image_tags:
                    logger.info(f"Exporting {len(image_tags)} Docker images...")
                    exported_images, image_export_errors = self._export_docker_images(
                        image_tags, temp_path
                    )
                    if exported_images:
                        logger.info(f"Exported {len(exported_images)} Docker images")
                    if image_export_errors:
                        for err in image_export_errors:
                            logger.warning(f"Image export warning: {err}")

            # ============================================================
            # Build Export Structure
            # ============================================================

            # Build blueprint export data
            blueprint_data = BlueprintExportData(
                name=blueprint.name,
                description=blueprint.description,
                version=blueprint.version,
                base_subnet_prefix=blueprint.base_subnet_prefix or "10.0.0.0/8",
                next_offset=blueprint.next_offset or 0,
                config=export_config,  # Use export_config which may have MSEL stripped
                student_guide_id=str(content_id) if content_id else None,
            )

            # Get CYROID version
            try:
                cyroid_version = get_settings().app_version
            except Exception:
                cyroid_version = None

            # Build export structure (v4.0)
            export_data = BlueprintExportFull(
                manifest=BlueprintExportManifest(
                    version="4.0",  # v4.0: Unified Range Blueprints
                    export_type="blueprint",
                    created_at=datetime.utcnow(),
                    created_by=user.username,
                    cyroid_version=cyroid_version,
                    blueprint_name=blueprint.name,
                    msel_included=msel_included,
                    dockerfile_count=len(dockerfiles),
                    content_included=content_data is not None,
                    artifact_count=len(artifacts_data),
                    docker_images_included=len(exported_images) > 0,
                    docker_image_count=len(exported_images),
                    docker_images=exported_images,
                    checksums={},  # Will be computed after writing files
                ),
                blueprint=blueprint_data,
                templates=[],  # Deprecated
                dockerfiles=dockerfiles,
                content=content_data,
                artifacts=artifacts_data,
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

            logger.info(f"Created blueprint export v4.0: {archive_path} "
                       f"(msel={'yes' if msel_included else 'no'}, "
                       f"dockerfiles={len(dockerfiles)}, "
                       f"content={'yes' if content_data else 'no'}, "
                       f"artifacts={len(artifacts_data)}, "
                       f"docker_images={len(exported_images)})")
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

        Supports multiple formats:
        - v4.0: Unified Range Blueprints (blueprint.json with version "4.0")
        - v3.0: Blueprint Export (blueprint.json with version "3.0")
        - v2.0: Range Export (range.json) - converted to blueprint format

        Returns:
            Tuple of (export_data, temp_dir_path)
            Caller is responsible for cleaning up temp_dir_path.
        """
        temp_dir = tempfile.mkdtemp(prefix="cyroid-blueprint-import-")

        # Handle both ZIP and tar.gz archives
        archive_str = str(archive_path)
        if archive_str.endswith('.tar.gz') or archive_str.endswith('.tgz'):
            import tarfile
            with tarfile.open(archive_path, "r:gz") as tf:
                tf.extractall(temp_dir)
        else:
            with zipfile.ZipFile(archive_path, "r") as zf:
                zf.extractall(temp_dir)

        # Check for v2.0 Range Export format (uses range.json)
        range_json_path = os.path.join(temp_dir, "range.json")
        blueprint_json_path = os.path.join(temp_dir, "blueprint.json")

        if os.path.exists(range_json_path) and not os.path.exists(blueprint_json_path):
            # Convert v2.0 Range Export to Blueprint format
            logger.info("Detected v2.0 Range Export format, converting to blueprint")
            data = self._convert_range_export_to_blueprint(range_json_path)
        elif os.path.exists(blueprint_json_path):
            with open(blueprint_json_path, "r") as f:
                data = json.load(f)
        else:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise ValueError("Archive missing blueprint.json or range.json")

        return BlueprintExportFull.model_validate(data), Path(temp_dir)

    def _convert_range_export_to_blueprint(self, range_json_path: str) -> dict:
        """
        Convert v2.0 Range Export format to Blueprint format.

        Range exports have a different structure focused on range instances,
        this converts them to the blueprint format for import.
        """
        with open(range_json_path, "r") as f:
            range_data = json.load(f)

        # Extract the relevant fields from range export
        # Range export format has: manifest, range, networks, vms, msel, artifacts, etc.
        range_info = range_data.get("range", {})
        networks = range_data.get("networks", [])
        vms = range_data.get("vms", [])
        msel_data = range_data.get("msel")

        # Build config similar to BlueprintConfig
        config = {
            "networks": networks,
            "vms": vms,
            "msel": msel_data,
        }

        # Build manifest
        manifest = {
            "version": "2.0",  # Mark as converted from v2.0
            "export_type": "blueprint",
            "created_at": range_data.get("manifest", {}).get("created_at", datetime.utcnow().isoformat()),
            "created_by": range_data.get("manifest", {}).get("created_by"),
            "blueprint_name": range_info.get("name", "Imported Range"),
            "msel_included": msel_data is not None,
            "dockerfile_count": 0,
            "content_included": False,
            "artifact_count": len(range_data.get("artifacts", [])),
            "docker_images_included": False,
            "checksums": {},
        }

        # Build blueprint data
        blueprint = {
            "name": range_info.get("name", "Imported Range"),
            "description": range_info.get("description"),
            "version": 1,
            "base_subnet_prefix": "10.0.0.0/8",
            "next_offset": 0,
            "config": config,
            "student_guide_id": None,
        }

        # Convert artifacts if present
        artifacts = []
        for artifact in range_data.get("artifacts", []):
            artifacts.append({
                "name": artifact.get("name"),
                "description": artifact.get("description"),
                "category": artifact.get("category", "tool"),
                "sha256_hash": artifact.get("sha256_hash", ""),
                "file_size": artifact.get("file_size", 0),
                "archive_path": artifact.get("archive_path", ""),
            })

        return {
            "manifest": manifest,
            "blueprint": blueprint,
            "templates": [],
            "dockerfiles": [],
            "content": None,
            "artifacts": artifacts,
        }

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

        Supports v2.0 (Range Export), v3.0, and v4.0 formats.

        Returns:
            BlueprintImportValidation with validation status and conflicts
        """
        errors: List[str] = []
        warnings: List[str] = []
        included_dockerfiles: List[str] = []
        dockerfile_conflicts: List[str] = []
        missing_images: List[str] = []
        content_conflict: Optional[str] = None
        included_artifacts: List[str] = []
        artifact_conflicts: List[str] = []
        msel_included = False

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

        # Add warning for legacy formats
        if manifest_version == "2.0":
            warnings.append("This is a v2.0 Range Export format - converted to blueprint format for import")
        elif manifest_version == "3.0":
            warnings.append("This is a v3.0 Blueprint format - consider re-exporting as v4.0 for full feature support")

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

        # ============================================================
        # Validate MSEL (v4.0)
        # ============================================================
        if hasattr(export_data.manifest, 'msel_included'):
            msel_included = export_data.manifest.msel_included
        elif hasattr(config, 'msel') and config.msel:
            msel_included = True

        # ============================================================
        # Validate Artifacts (v4.0)
        # ============================================================
        if hasattr(export_data, 'artifacts') and export_data.artifacts:
            for artifact in export_data.artifacts:
                included_artifacts.append(artifact.name)

                # Check for artifact with same hash
                existing_artifact = db.query(Artifact).filter(
                    Artifact.sha256_hash == artifact.sha256_hash
                ).first()
                if existing_artifact:
                    artifact_conflicts.append(artifact.name)
                    warnings.append(f"Artifact '{artifact.name}' already exists (hash match)")

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
            msel_included=msel_included,
            included_artifacts=included_artifacts,
            artifact_conflicts=artifact_conflicts,
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
        Import a blueprint from an archive (v3.0/v4.0 with Dockerfiles, Content, and Docker Images).

        Automatically:
        1. Extracts Dockerfiles to /data/images/
        2. Builds missing Docker images from Dockerfiles
        3. Loads Docker image tarballs and pushes to registry (v4.0)
        4. Creates BaseImage records
        5. Imports Content Library items

        Returns:
            BlueprintImportResult with success status and created resources
        """
        errors: List[str] = []
        warnings: List[str] = []
        templates_created: List[str] = []
        templates_skipped: List[str] = []
        images_built: List[str] = []
        images_loaded: List[str] = []  # Images loaded from tar and pushed to registry
        images_skipped: List[str] = []  # Images already in registry
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
            # Load Docker Images from Tarballs (v4.0)
            # ============================================================
            if (hasattr(export_data.manifest, 'docker_images_included') and
                export_data.manifest.docker_images_included and
                hasattr(export_data.manifest, 'docker_images') and
                export_data.manifest.docker_images):

                logger.info(f"Loading {len(export_data.manifest.docker_images)} Docker images from archive...")
                loaded, skipped, load_errors = self._extract_docker_images(
                    temp_dir,
                    export_data.manifest.docker_images,
                )
                images_loaded.extend(loaded)
                images_skipped.extend(skipped)

                if load_errors:
                    # Image load failures are warnings, not fatal errors
                    for err in load_errors:
                        warnings.append(err)

                if images_loaded:
                    logger.info(f"Loaded and pushed {len(images_loaded)} images to registry")
                if images_skipped:
                    logger.info(f"Skipped {len(images_skipped)} images (already in registry)")

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
            # Build content_ids list - include imported content for static reference
            blueprint_content_ids: List[str] = []
            if content_id:
                blueprint_content_ids.append(str(content_id))

            # Also update config's content_ids so deploy uses the static reference
            config_dict = export_data.blueprint.config.model_dump()
            if content_id:
                config_dict["content_ids"] = blueprint_content_ids

            blueprint = RangeBlueprint(
                name=blueprint_name,
                description=export_data.blueprint.description,
                config=config_dict,
                base_subnet_prefix=export_data.blueprint.base_subnet_prefix,
                version=export_data.blueprint.version,
                next_offset=0,  # Reset offset for new instance
                created_by=user.id,
                content_ids=blueprint_content_ids,  # Link imported content
            )
            db.add(blueprint)
            db.commit()
            db.refresh(blueprint)

            logger.info(
                f"Imported blueprint: {blueprint.name} (id={blueprint.id}) "
                f"dockerfiles={len(dockerfiles_extracted)}, "
                f"images_built={len(images_built)}, "
                f"images_loaded={len(images_loaded)}, "
                f"content={'yes' if content_imported else 'no'}"
            )

            return BlueprintImportResult(
                success=True,
                blueprint_id=blueprint.id,
                blueprint_name=blueprint.name,
                templates_created=templates_created,
                templates_skipped=templates_skipped,
                images_built=images_built,
                images_loaded=images_loaded,
                images_skipped=images_skipped,
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
                images_loaded=images_loaded,
                images_skipped=images_skipped,
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
