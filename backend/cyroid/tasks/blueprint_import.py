# backend/cyroid/tasks/blueprint_import.py
"""
Async blueprint import task with progress tracking and cancellation support.
"""
import json
import logging
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

import dramatiq
from redis import Redis

from cyroid.config import get_settings
from cyroid.database import get_session_local
from cyroid.models.user import User
from cyroid.schemas.blueprint_export import BlueprintImportOptions
from cyroid.services.blueprint_export_service import get_blueprint_export_service

logger = logging.getLogger(__name__)
settings = get_settings()

# Redis key prefix for import jobs
IMPORT_JOB_PREFIX = "blueprint_import:"
IMPORT_JOB_TTL = 3600  # 1 hour TTL for job data


def get_redis() -> Redis:
    """Get Redis connection."""
    return Redis.from_url(settings.redis_url, decode_responses=True)


def get_job_key(job_id: str) -> str:
    """Get Redis key for an import job."""
    return f"{IMPORT_JOB_PREFIX}{job_id}"


def update_job_status(
    job_id: str,
    status: str,
    step: str,
    progress: int = 0,
    total_steps: int = 0,
    current_item: str = "",
    error: str = "",
    result: Optional[Dict[str, Any]] = None,
):
    """Update import job status in Redis."""
    redis = get_redis()
    job_data = {
        "status": status,  # pending, running, completed, failed, cancelled
        "step": step,
        "progress": progress,
        "total_steps": total_steps,
        "current_item": current_item,
        "error": error,
        "result": result,
        "updated_at": datetime.utcnow().isoformat(),
    }
    redis.setex(get_job_key(job_id), IMPORT_JOB_TTL, json.dumps(job_data))


def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """Get import job status from Redis."""
    redis = get_redis()
    data = redis.get(get_job_key(job_id))
    if data:
        return json.loads(data)
    return None


def is_job_cancelled(job_id: str) -> bool:
    """Check if import job has been cancelled."""
    status = get_job_status(job_id)
    return status is not None and status.get("status") == "cancelled"


def cancel_job(job_id: str) -> bool:
    """Mark an import job as cancelled."""
    status = get_job_status(job_id)
    if status and status.get("status") in ("pending", "running"):
        update_job_status(
            job_id,
            status="cancelled",
            step="Cancelled by user",
            progress=0,
            total_steps=0,
        )
        return True
    return False


def cleanup_job(job_id: str):
    """Clean up import job data."""
    redis = get_redis()
    redis.delete(get_job_key(job_id))


@dramatiq.actor(max_retries=0, time_limit=1800000)  # 30 min timeout, no retries
def import_blueprint_async(
    job_id: str,
    archive_path: str,
    user_id: str,
    options_dict: Dict[str, Any],
):
    """
    Async blueprint import task with progress tracking.

    Steps:
    1. Extracting archive...
    2. Extracting Dockerfiles...
    3. Building Docker images... (X of Y)
    4. Importing content...
    5. Creating blueprint...
    """
    db = get_session_local()()
    total_steps = 5

    try:
        update_job_status(job_id, "running", "Extracting archive...", 1, total_steps)

        if is_job_cancelled(job_id):
            return

        # Parse options
        options = BlueprintImportOptions(**options_dict)

        # Get user
        from uuid import UUID
        user = db.query(User).filter(User.id == UUID(user_id)).first()
        if not user:
            update_job_status(job_id, "failed", "Import failed", error="User not found")
            return

        # Get export service
        export_service = get_blueprint_export_service()

        # Step 1: Extract archive
        try:
            export_data, temp_dir = export_service._extract_archive(Path(archive_path))
        except Exception as e:
            update_job_status(
                job_id, "failed", "Extract failed",
                error=f"Failed to read archive: {str(e)}"
            )
            return

        try:
            if is_job_cancelled(job_id):
                return

            # Validate
            validation = export_service.validate_import(Path(archive_path), db)
            if not validation.valid and not options.new_name:
                update_job_status(
                    job_id, "failed", "Validation failed",
                    error=validation.errors[0] if validation.errors else "Validation failed"
                )
                return

            # Determine blueprint name
            blueprint_name = options.new_name or export_data.blueprint.name

            # Check name conflict
            from cyroid.models.blueprint import RangeBlueprint
            existing = db.query(RangeBlueprint).filter(
                RangeBlueprint.name == blueprint_name
            ).first()
            if existing:
                update_job_status(
                    job_id, "failed", "Name conflict",
                    error=f"Blueprint name '{blueprint_name}' already exists"
                )
                return

            if is_job_cancelled(job_id):
                return

            # Step 2: Extract Dockerfiles
            update_job_status(job_id, "running", "Extracting Dockerfiles...", 2, total_steps)

            dockerfiles_extracted = []
            dockerfiles_skipped = []
            errors = []
            warnings = []

            if hasattr(export_data, 'dockerfiles') and export_data.dockerfiles:
                extracted, skipped, extract_errors = export_service._extract_dockerfiles(
                    export_data.dockerfiles,
                    options.dockerfile_conflict_strategy,
                )
                dockerfiles_extracted.extend(extracted)
                dockerfiles_skipped.extend(skipped)
                errors.extend(extract_errors)

                if errors and options.dockerfile_conflict_strategy == "error":
                    update_job_status(
                        job_id, "failed", "Dockerfile conflict",
                        error=errors[0]
                    )
                    return

            if is_job_cancelled(job_id):
                return

            # Step 3: Build Docker images (the slow part)
            update_job_status(job_id, "running", "Building Docker images...", 3, total_steps)

            images_built = []
            if (options.build_images and
                    hasattr(export_data, 'dockerfiles') and export_data.dockerfiles):

                dockerfiles_to_build = export_data.dockerfiles
                total_images = len(dockerfiles_to_build)

                for i, dockerfile in enumerate(dockerfiles_to_build):
                    if is_job_cancelled(job_id):
                        return

                    image_tag = dockerfile.image_tag
                    current_item = f"{image_tag} — {i + 1} of {total_images}"
                    update_job_status(
                        job_id, "running",
                        f"Building Docker images ({i + 1}/{total_images})...",
                        3, total_steps,
                        current_item=current_item,
                    )

                    # Skip if image already exists
                    if export_service._image_exists(image_tag):
                        logger.info(f"Image {image_tag} already exists, skipping build")
                        continue

                    project_dir = Path("/data/images") / dockerfile.project_name
                    if not (project_dir / "Dockerfile").exists():
                        continue

                    if export_service._build_image(image_tag, project_dir):
                        images_built.append(image_tag)

                        # Create BaseImage record
                        try:
                            from cyroid.models.base_image import BaseImage
                            import docker as docker_lib

                            existing_bi = db.query(BaseImage).filter(
                                BaseImage.docker_image_tag == image_tag
                            ).first()

                            if existing_bi:
                                existing_bi.image_project_name = dockerfile.project_name
                                db.commit()
                            else:
                                client = docker_lib.from_env()
                                image = client.images.get(image_tag)
                                base_image = BaseImage(
                                    name=dockerfile.project_name,
                                    description=dockerfile.description or f"Built from Dockerfile: {dockerfile.project_name}",
                                    image_type="container",
                                    docker_image_id=image.id,
                                    docker_image_tag=image_tag,
                                    image_project_name=dockerfile.project_name,
                                    os_type="linux",
                                    vm_type="container",
                                    size_bytes=image.attrs.get("Size", 0),
                                    is_global=True,
                                    created_by=user.id,
                                )
                                db.add(base_image)
                                db.commit()
                        except Exception as e:
                            logger.warning(f"Failed to create BaseImage record for {image_tag}: {e}")
                    else:
                        warnings.append(f"Failed to build image: {image_tag}")

            # Also handle Docker image tarballs (v4.0)
            images_loaded = []
            images_skipped = []
            if (hasattr(export_data.manifest, 'docker_images_included') and
                    export_data.manifest.docker_images_included and
                    hasattr(export_data.manifest, 'docker_images') and
                    export_data.manifest.docker_images):

                update_job_status(
                    job_id, "running",
                    "Loading Docker images from archive...",
                    3, total_steps,
                    current_item=f"{len(export_data.manifest.docker_images)} images",
                )

                loaded, skipped, load_errors = export_service._extract_docker_images(
                    temp_dir,
                    export_data.manifest.docker_images,
                )
                images_loaded.extend(loaded)
                images_skipped.extend(skipped)
                for err in load_errors:
                    warnings.append(err)

            if is_job_cancelled(job_id):
                return

            # Step 4: Import content
            update_job_status(job_id, "running", "Importing content...", 4, total_steps)

            content_imported = False
            content_id = None
            if hasattr(export_data, 'content') and export_data.content:
                imported, cid, content_warnings = export_service._import_content(
                    export_data.content,
                    temp_dir,
                    options.content_conflict_strategy,
                    user,
                    db,
                )
                content_imported = imported
                content_id = cid
                warnings.extend(content_warnings)

            if is_job_cancelled(job_id):
                return

            # Step 5: Create blueprint
            update_job_status(job_id, "running", "Creating blueprint...", 5, total_steps)

            blueprint_content_ids = []
            if content_id:
                blueprint_content_ids.append(str(content_id))

            config_dict = export_data.blueprint.config.model_dump()
            if content_id:
                config_dict["content_ids"] = blueprint_content_ids

            blueprint = RangeBlueprint(
                name=blueprint_name,
                description=export_data.blueprint.description,
                config=config_dict,
                base_subnet_prefix=export_data.blueprint.base_subnet_prefix,
                version=export_data.blueprint.version,
                next_offset=0,
                created_by=user.id,
                content_ids=blueprint_content_ids,
            )
            db.add(blueprint)
            db.commit()
            db.refresh(blueprint)

            # Build result summary
            import_result = {
                "success": True,
                "blueprint_id": str(blueprint.id),
                "blueprint_name": blueprint.name,
                "templates_created": [],
                "templates_skipped": [],
                "images_built": images_built,
                "images_loaded": images_loaded,
                "images_skipped": images_skipped,
                "dockerfiles_extracted": dockerfiles_extracted,
                "dockerfiles_skipped": dockerfiles_skipped,
                "content_imported": content_imported,
                "content_id": str(content_id) if content_id else None,
                "warnings": warnings,
                "errors": [],
            }

            update_job_status(
                job_id,
                status="completed",
                step="Import complete",
                progress=total_steps,
                total_steps=total_steps,
                result=import_result,
            )

            logger.info(
                f"Async blueprint import complete: {blueprint.name} (id={blueprint.id})"
            )

        finally:
            # Clean up temp dir from extraction
            if temp_dir:
                shutil.rmtree(str(temp_dir), ignore_errors=True)

    except Exception as e:
        logger.error(f"Blueprint import failed: {e}", exc_info=True)
        update_job_status(
            job_id,
            status="failed",
            step="Import failed",
            error=str(e),
        )
    finally:
        db.close()
        # Clean up the uploaded archive file
        try:
            if os.path.exists(archive_path):
                os.unlink(archive_path)
        except Exception as e:
            logger.warning(f"Failed to clean up archive: {e}")
