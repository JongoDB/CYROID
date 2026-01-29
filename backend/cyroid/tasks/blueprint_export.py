# backend/cyroid/tasks/blueprint_export.py
"""
Async blueprint export task with progress tracking and cancellation support.
"""
import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List, Set
from uuid import UUID

import dramatiq
import docker
from redis import Redis

from cyroid.config import get_settings
from cyroid.database import get_session_local
from cyroid.models.blueprint import RangeBlueprint
from cyroid.schemas.blueprint import BlueprintConfig
from cyroid.schemas.blueprint_export import BlueprintExportOptions
from cyroid.services.blueprint_export_service import get_blueprint_export_service

logger = logging.getLogger(__name__)
settings = get_settings()

# Redis key prefix for export jobs
EXPORT_JOB_PREFIX = "blueprint_export:"
EXPORT_JOB_TTL = 3600  # 1 hour TTL for job data


def get_redis() -> Redis:
    """Get Redis connection."""
    return Redis.from_url(settings.redis_url, decode_responses=True)


def get_job_key(job_id: str) -> str:
    """Get Redis key for a job."""
    return f"{EXPORT_JOB_PREFIX}{job_id}"


def update_job_status(
    job_id: str,
    status: str,
    step: str,
    progress: int = 0,
    total_steps: int = 0,
    current_item: str = "",
    error: str = "",
    download_path: str = "",
    filename: str = "",
):
    """Update job status in Redis."""
    redis = get_redis()
    job_data = {
        "status": status,  # pending, running, completed, failed, cancelled
        "step": step,
        "progress": progress,
        "total_steps": total_steps,
        "current_item": current_item,
        "error": error,
        "download_path": download_path,
        "filename": filename,
        "updated_at": datetime.utcnow().isoformat(),
    }
    redis.setex(get_job_key(job_id), EXPORT_JOB_TTL, json.dumps(job_data))


def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """Get job status from Redis."""
    redis = get_redis()
    data = redis.get(get_job_key(job_id))
    if data:
        return json.loads(data)
    return None


def is_job_cancelled(job_id: str) -> bool:
    """Check if job has been cancelled."""
    status = get_job_status(job_id)
    return status is not None and status.get("status") == "cancelled"


def cancel_job(job_id: str) -> bool:
    """Mark a job as cancelled."""
    status = get_job_status(job_id)
    if status and status.get("status") in ("pending", "running"):
        update_job_status(
            job_id,
            status="cancelled",
            step="Cancelled by user",
            progress=0,
            total_steps=0,
        )
        # Clean up any temp files
        if status.get("download_path"):
            try:
                temp_dir = Path(status["download_path"]).parent
                if temp_dir.exists() and "cyroid-export" in str(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Failed to clean up temp dir: {e}")
        return True
    return False


def cleanup_job(job_id: str):
    """Clean up job data and files."""
    status = get_job_status(job_id)
    if status and status.get("download_path"):
        try:
            download_path = Path(status["download_path"])
            if download_path.exists():
                # Remove the zip file
                download_path.unlink()
            # Remove the temp directory if empty
            temp_dir = download_path.parent
            if temp_dir.exists() and "cyroid-export" in str(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Failed to clean up export files: {e}")

    # Remove from Redis
    redis = get_redis()
    redis.delete(get_job_key(job_id))


@dramatiq.actor(max_retries=0, time_limit=1800000)  # 30 min timeout, no retries
def export_blueprint_async(
    job_id: str,
    blueprint_id: str,
    user_id: str,
    options_dict: Dict[str, Any],
):
    """
    Async blueprint export task with progress tracking.

    Steps:
    1. Load blueprint and validate
    2. Collect Dockerfiles (if enabled)
    3. Collect Content (if enabled)
    4. Collect Artifacts (if enabled)
    5. Export Docker images (if enabled) - with per-image progress
    6. Create ZIP archive
    7. Mark complete with download path
    """
    db = get_session_local()()
    temp_dir = None

    try:
        update_job_status(job_id, "running", "Initializing export...", 0, 6)

        # Check cancellation
        if is_job_cancelled(job_id):
            return

        # Parse options
        options = BlueprintExportOptions(**options_dict)

        # Load blueprint
        update_job_status(job_id, "running", "Loading blueprint...", 1, 6)
        blueprint = db.query(RangeBlueprint).filter(
            RangeBlueprint.id == UUID(blueprint_id)
        ).first()

        if not blueprint:
            update_job_status(job_id, "failed", "Blueprint not found", error="Blueprint not found")
            return

        config = BlueprintConfig.model_validate(blueprint.config)

        # Create export directory in shared location (accessible by both api and worker)
        export_base = Path(settings.global_shared_dir) / "exports"
        export_base.mkdir(parents=True, exist_ok=True)
        temp_dir = Path(tempfile.mkdtemp(prefix="cyroid-export-", dir=export_base))

        # Store temp dir path for potential cleanup
        update_job_status(
            job_id, "running", "Preparing export...", 1, 6,
            download_path=str(temp_dir / "placeholder.zip")
        )

        if is_job_cancelled(job_id):
            return

        # Get export service
        export_service = get_blueprint_export_service()

        # Step 2: Collect Dockerfiles
        update_job_status(job_id, "running", "Collecting Dockerfiles...", 2, 6)
        dockerfiles = []
        if options.include_dockerfiles:
            project_map = export_service._collect_referenced_image_projects(config, db)
            if project_map:
                dockerfiles = export_service._collect_dockerfile_projects(project_map)
                if dockerfiles:
                    dockerfiles_dir = temp_dir / "dockerfiles"
                    dockerfiles_dir.mkdir(exist_ok=True)
                    for project in dockerfiles:
                        if is_job_cancelled(job_id):
                            return
                        project_dir = dockerfiles_dir / project.project_name
                        project_dir.mkdir(exist_ok=True)
                        for filename, content in project.files.items():
                            file_path = project_dir / filename
                            file_path.parent.mkdir(parents=True, exist_ok=True)
                            file_path.write_text(content, encoding='utf-8')

        if is_job_cancelled(job_id):
            return

        # Step 3: Collect Content
        update_job_status(job_id, "running", "Collecting content...", 3, 6)
        content_data = None
        content_files = []
        # Note: Content collection would go here if content_id was provided

        if is_job_cancelled(job_id):
            return

        # Step 4: Collect Artifacts
        update_job_status(job_id, "running", "Collecting artifacts...", 4, 6)
        artifacts_data = []
        if options.include_artifacts:
            artifact_ids = []
            if hasattr(config, 'artifact_ids') and config.artifact_ids:
                artifact_ids = config.artifact_ids
            if artifact_ids:
                artifacts_data, _ = export_service._collect_artifacts(
                    artifact_ids, temp_dir, db
                )

        if is_job_cancelled(job_id):
            return

        # Step 5: Export Docker images (the slow part)
        exported_images = []
        if options.include_docker_images:
            image_tags = export_service._collect_image_tags_from_config(config, db)
            if image_tags:
                exported_images = _export_docker_images_with_progress(
                    job_id, image_tags, temp_dir
                )

        if is_job_cancelled(job_id):
            return

        # Step 6: Create ZIP archive
        update_job_status(job_id, "running", "Creating ZIP archive...", 5, 6)

        # Build the export data structure
        from cyroid.schemas.blueprint_export import (
            BlueprintExportData, BlueprintExportFull, BlueprintExportManifest
        )

        # Handle MSEL option
        export_config = config
        if hasattr(config, 'msel') and config.msel and not options.include_msel:
            config_dict = config.model_dump()
            config_dict['msel'] = None
            export_config = BlueprintConfig.model_validate(config_dict)

        blueprint_data = BlueprintExportData(
            name=blueprint.name,
            description=blueprint.description,
            version=blueprint.version,
            base_subnet_prefix=blueprint.base_subnet_prefix or "10.0.0.0/8",
            next_offset=blueprint.next_offset or 0,
            config=export_config,
            student_guide_id=None,
        )

        # Get version
        try:
            version_file = Path("/app/VERSION")
            if version_file.exists():
                cyroid_version = version_file.read_text().strip()
            else:
                cyroid_version = "unknown"
        except Exception:
            cyroid_version = "unknown"

        # Build manifest
        manifest = BlueprintExportManifest(
            version="4.0",
            created_at=datetime.utcnow(),
            cyroid_version=cyroid_version,
            blueprint_name=blueprint.name,
            msel_included=bool(hasattr(config, 'msel') and config.msel and options.include_msel),
            dockerfile_count=len(dockerfiles) if dockerfiles else 0,
            content_included=bool(content_data),
            artifact_count=len(artifacts_data) if artifacts_data else 0,
            docker_images_included=bool(exported_images),
            docker_image_count=len(exported_images),
            docker_images=exported_images,
        )

        # Write blueprint.json
        export_full = BlueprintExportFull(
            manifest=manifest,
            blueprint=blueprint_data,
            templates=[],
            dockerfiles=dockerfiles if dockerfiles else [],
            content=content_data if content_data else None,
            artifacts=artifacts_data if artifacts_data else [],
        )

        blueprint_json = temp_dir / "blueprint.json"
        blueprint_json.write_text(
            json.dumps(export_full.model_dump(), indent=2, default=str),
            encoding='utf-8'
        )

        # Write manifest.json
        manifest_json = temp_dir / "manifest.json"
        manifest_json.write_text(
            json.dumps(manifest.model_dump(), indent=2, default=str),
            encoding='utf-8'
        )

        if is_job_cancelled(job_id):
            return

        # Create ZIP with no compression (ZIP_STORED) for speed
        # Docker image tarballs are already compressed, so re-compressing wastes CPU
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in blueprint.name)
        filename = f"blueprint-{safe_name}-{timestamp}.zip"
        archive_path = temp_dir / filename

        _create_zip_stored(temp_dir, archive_path, job_id)

        # Step 7: Complete
        update_job_status(
            job_id,
            status="completed",
            step="Export complete",
            progress=6,
            total_steps=6,
            download_path=str(archive_path),
            filename=filename,
        )

        logger.info(f"Blueprint export complete: {archive_path}")

    except Exception as e:
        logger.error(f"Blueprint export failed: {e}", exc_info=True)
        update_job_status(
            job_id,
            status="failed",
            step="Export failed",
            error=str(e),
        )
    finally:
        db.close()
        # Note: Don't clean up temp_dir here - it's needed for download
        # Cleanup happens after download or on cancel


def _export_docker_images_with_progress(
    job_id: str,
    image_tags: Set[str],
    temp_dir: Path,
) -> List[str]:
    """
    Export Docker images with parallel exports for maximum performance.

    Optimizations:
    1. Exports multiple images in parallel using ThreadPoolExecutor (up to 4 concurrent)
    2. Progress tracking per-image with aggregated status updates
    3. Single Redis connection reused across all threads
    """
    image_list = list(image_tags)
    total = len(image_list)

    if not image_list:
        return []

    images_dir = temp_dir / "images"
    images_dir.mkdir(exist_ok=True)

    # Create Docker client
    try:
        client = docker.from_env()
    except Exception as e:
        logger.error(f"Failed to connect to Docker: {e}")
        return []

    # Create a single Redis connection to reuse (avoids port exhaustion)
    redis = get_redis()

    # Thread-safe tracking
    lock = threading.Lock()
    exported = []
    failed = []
    in_progress = {}  # image_tag -> progress_info
    cancelled = threading.Event()

    def check_cancelled() -> bool:
        """Check cancellation using shared Redis connection."""
        if cancelled.is_set():
            return True
        try:
            data = redis.get(get_job_key(job_id))
            if data:
                status = json.loads(data)
                if status.get("status") == "cancelled":
                    cancelled.set()
                    return True
        except Exception:
            pass
        return False

    def update_aggregate_progress():
        """Update job status with aggregate progress from all parallel exports."""
        with lock:
            if not in_progress and not exported:
                return

            # Build status string showing all active exports
            active = []
            for tag, info in in_progress.items():
                short_tag = tag.split("/")[-1] if "/" in tag else tag
                if info.get("mb"):
                    active.append(f"{short_tag}: {info['mb']:.0f}MB")
                else:
                    active.append(short_tag)

            done_count = len(exported)
            active_count = len(in_progress)

            if active:
                current_item = " | ".join(active[:3])  # Show up to 3 concurrent
                if len(active) > 3:
                    current_item += f" (+{len(active)-3} more)"
            else:
                current_item = ""

            step = f"Exporting Docker images ({done_count}/{total} complete, {active_count} active)"

        update_job_status(
            job_id,
            status="running",
            step=step,
            progress=4,
            total_steps=6,
            current_item=current_item,
        )

    def export_single_image(image_tag: str) -> Optional[str]:
        """Export a single image using Docker SDK with progress tracking."""
        if check_cancelled():
            return None

        safe_name = image_tag.replace("/", "_").replace(":", "_")
        tarball_path = images_dir / f"{safe_name}.tar"

        # Track this image as in-progress
        with lock:
            in_progress[image_tag] = {"mb": 0}

        try:
            logger.info(f"Exporting: {image_tag}")

            # Get image (should already be available locally)
            try:
                image = client.images.get(image_tag)
            except docker.errors.ImageNotFound:
                logger.warning(f"Image {image_tag} not found locally, skipping")
                return None

            # Export using Docker SDK with chunked writing
            bytes_written = 0
            last_update = time.time()
            UPDATE_INTERVAL = 0.5  # Update progress every 0.5 seconds

            with open(tarball_path, 'wb') as f:
                for chunk in image.save(named=True):
                    if check_cancelled():
                        f.close()
                        tarball_path.unlink(missing_ok=True)
                        return None

                    f.write(chunk)
                    bytes_written += len(chunk)

                    # Update progress periodically (not every chunk)
                    current_time = time.time()
                    if current_time - last_update >= UPDATE_INTERVAL:
                        mb = bytes_written / 1024 / 1024
                        with lock:
                            in_progress[image_tag] = {"mb": mb}
                        update_aggregate_progress()
                        last_update = current_time

            # Final size
            size_mb = tarball_path.stat().st_size / 1024 / 1024
            logger.info(f"Exported: {image_tag} ({size_mb:.1f} MB)")

            return image_tag

        except Exception as e:
            logger.error(f"Failed to export {image_tag}: {e}")
            tarball_path.unlink(missing_ok=True)
            return None
        finally:
            with lock:
                in_progress.pop(image_tag, None)

    # Determine parallelism - use up to 4 concurrent exports
    # (more than 4 tends to slow things down due to disk I/O contention)
    max_workers = min(4, total)

    update_job_status(
        job_id,
        status="running",
        step=f"Exporting Docker images (0/{total} complete)",
        progress=4,
        total_steps=6,
        current_item=f"Starting {max_workers} parallel exports...",
    )

    # Export images in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(export_single_image, tag): tag for tag in image_list}

        for future in as_completed(futures):
            if check_cancelled():
                # Cancel remaining futures
                for f in futures:
                    f.cancel()
                # Clean up
                try:
                    shutil.rmtree(images_dir, ignore_errors=True)
                except Exception:
                    pass
                return []

            result = future.result()
            if result:
                with lock:
                    exported.append(result)
                update_aggregate_progress()
            else:
                tag = futures[future]
                with lock:
                    failed.append(tag)

    if failed:
        logger.warning(f"Failed to export {len(failed)} images: {failed}")

    return exported


def _create_zip_stored(
    source_dir: Path,
    output_path: Path,
    job_id: str,
) -> None:
    """
    Create a ZIP archive with no compression (ZIP_STORED) for maximum speed.

    Docker image tarballs and other binary data don't benefit from compression,
    so using ZIP_STORED avoids wasting CPU cycles on futile compression attempts.
    """
    # Collect all files to add
    files_to_add = []
    total_size = 0
    for root, dirs, files in os.walk(source_dir):
        # Skip the output zip itself
        for file in files:
            file_path = Path(root) / file
            if file_path == output_path:
                continue
            rel_path = file_path.relative_to(source_dir)
            size = file_path.stat().st_size
            files_to_add.append((file_path, str(rel_path), size))
            total_size += size

    logger.info(f"Creating ZIP archive with {len(files_to_add)} files, {total_size / 1024 / 1024:.1f} MB total")

    # Create ZIP with no compression
    bytes_written = 0
    last_progress_update = 0
    PROGRESS_UPDATE_INTERVAL = 100 * 1024 * 1024  # Update every 100MB

    with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_STORED) as zf:
        for file_path, arc_name, size in files_to_add:
            # Check cancellation periodically
            if is_job_cancelled(job_id):
                zf.close()
                output_path.unlink(missing_ok=True)
                return

            zf.write(file_path, arc_name)
            bytes_written += size

            # Update progress
            if bytes_written - last_progress_update >= PROGRESS_UPDATE_INTERVAL:
                last_progress_update = bytes_written
                mb_written = bytes_written / 1024 / 1024
                total_mb = total_size / 1024 / 1024
                pct = int((bytes_written / total_size) * 100) if total_size > 0 else 0
                update_job_status(
                    job_id,
                    status="running",
                    step="Creating ZIP archive...",
                    progress=5,
                    total_steps=6,
                    current_item=f"{mb_written:.0f}MB / {total_mb:.0f}MB ({pct}%)",
                )

    logger.info(f"ZIP archive created: {output_path} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")
