# backend/cyroid/api/cache.py
"""API endpoints for image caching and golden image management."""
import os
import threading
import logging
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel

from cyroid.api.deps import DBSession, CurrentUser, AdminUser
from cyroid.services.docker_service import get_docker_service
from cyroid.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cache", tags=["Image Cache"])

# Track active Docker image pulls for progress reporting
_active_docker_pulls: Dict[str, Dict[str, Any]] = {}

# Track active Docker image builds for progress reporting
_active_docker_builds: Dict[str, Dict[str, Any]] = {}

# Supported compressed archive extensions for ISO downloads/uploads
SUPPORTED_ARCHIVE_EXTENSIONS = (
    '.zip', '.7z', '.rar',  # Common archives
    '.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tbz2', '.tar.xz', '.txz',  # Tar variants
    '.gz', '.gzip', '.bz2', '.xz', '.lzma',  # Single-file compression
)


def is_archive_file(path_or_url: str) -> bool:
    """Check if a file path or URL points to a compressed archive."""
    lower = path_or_url.lower()
    # Handle query strings in URLs
    if '?' in lower:
        lower = lower.split('?')[0]
    return any(lower.endswith(ext) for ext in SUPPORTED_ARCHIVE_EXTENSIONS)


def get_archive_extension(path_or_url: str) -> Optional[str]:
    """Get the archive extension from a file path or URL."""
    lower = path_or_url.lower()
    if '?' in lower:
        lower = lower.split('?')[0]
    # Check for compound extensions first (.tar.gz, .tar.bz2, etc.)
    for ext in ('.tar.gz', '.tar.bz2', '.tar.xz'):
        if lower.endswith(ext):
            return ext
    # Then check single extensions
    for ext in SUPPORTED_ARCHIVE_EXTENSIONS:
        if lower.endswith(ext):
            return ext
    return None


def extract_iso_from_archive(archive_path: str, dest_dir: str) -> str:
    """
    Extract an archive and find the ISO file inside.
    Uses 7z which supports most archive formats.

    Args:
        archive_path: Path to the archive file
        dest_dir: Directory to extract to

    Returns:
        Path to the extracted ISO file

    Raises:
        ValueError: If no ISO found or multiple ISOs found
        RuntimeError: If extraction fails
    """
    import subprocess
    import shutil
    import tempfile

    # Create a temporary extraction directory
    extract_dir = tempfile.mkdtemp(prefix="iso_extract_", dir=dest_dir)

    try:
        # Use 7z for extraction - it handles most formats
        # -y: assume Yes on all queries
        # -o: output directory
        result = subprocess.run(
            ['7z', 'x', '-y', f'-o{extract_dir}', archive_path],
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout for large archives
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to extract archive: {result.stderr}")

        # Find all ISO files in the extracted content (recursive)
        iso_files = []
        for root, dirs, files in os.walk(extract_dir):
            for f in files:
                if f.lower().endswith('.iso'):
                    iso_files.append(os.path.join(root, f))

        if not iso_files:
            raise ValueError("No ISO file found in archive")

        if len(iso_files) > 1:
            # If multiple ISOs, prefer the largest one (likely the main ISO)
            iso_files.sort(key=lambda x: os.path.getsize(x), reverse=True)
            logger.warning(f"Multiple ISO files found in archive, using largest: {iso_files[0]}")

        return iso_files[0]

    except subprocess.TimeoutExpired:
        raise RuntimeError("Archive extraction timed out")
    except Exception as e:
        # Clean up on failure
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir, ignore_errors=True)
        raise


def get_windows_iso_dir() -> str:
    """Get the Windows ISO cache directory path."""
    settings = get_settings()
    return os.path.join(settings.iso_cache_dir, "windows-isos")


# Request/Response schemas
class CacheImageRequest(BaseModel):
    image: str  # Docker image name (e.g., "ubuntu:22.04")


class CachedImageResponse(BaseModel):
    id: str
    tags: List[str]
    size_bytes: int
    size_gb: float
    created: Optional[str] = None


class CacheStatusResponse(BaseModel):
    cache_dir: str
    total_count: int


class ISOCacheResponse(CacheStatusResponse):
    isos: List[dict]


class GoldenImageResponse(BaseModel):
    template_dir: str
    total_count: int
    golden_images: List[dict]


class CreateGoldenImageRequest(BaseModel):
    container_id: str
    name: str


class CacheProgressResponse(BaseModel):
    status: str
    message: str


# Linux image caching endpoints

@router.get("/images", response_model=List[CachedImageResponse])
def list_cached_images(current_user: CurrentUser):
    """List all cached Docker images."""
    docker = get_docker_service()
    images = docker.list_cached_images()
    return [
        CachedImageResponse(
            id=img["id"],
            tags=img["tags"],
            size_bytes=img["size_bytes"],
            size_gb=round(img["size_bytes"] / (1024**3), 2),
            created=img.get("created")
        )
        for img in images
    ]


@router.post("/images", response_model=CachedImageResponse, status_code=status.HTTP_201_CREATED)
def cache_image(request: CacheImageRequest, current_user: AdminUser):
    """
    Pre-pull and cache a Docker image.
    Admin only as this downloads potentially large images.
    """
    docker = get_docker_service()
    try:
        result = docker.cache_linux_image(request.image)
        return CachedImageResponse(
            id=result["id"],
            tags=result["tags"],
            size_bytes=result["size_bytes"],
            size_gb=round(result["size_bytes"] / (1024**3), 2),
            created=result.get("created")
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cache image: {str(e)}"
        )


@router.post("/images/batch", response_model=CacheProgressResponse)
def cache_images_batch(
    images: List[str],
    background_tasks: BackgroundTasks,
    current_user: AdminUser
):
    """
    Start batch caching of multiple Docker images in the background.
    Admin only.
    """
    def cache_all_images(image_list: List[str]):
        docker = get_docker_service()
        for img in image_list:
            try:
                docker.cache_linux_image(img)
            except Exception as e:
                # Log but continue with other images
                pass

    background_tasks.add_task(cache_all_images, images)
    return CacheProgressResponse(
        status="started",
        message=f"Caching {len(images)} images in background"
    )


@router.delete("/images/{image_id}")
def remove_cached_image(image_id: str, current_user: AdminUser):
    """Remove a cached Docker image. Admin only."""
    docker = get_docker_service()
    try:
        docker.client.images.remove(image_id, force=True)
        return {"status": "removed", "image_id": image_id}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove image: {str(e)}"
        )


# Async Docker image pull with progress tracking

class DockerPullRequest(BaseModel):
    image: str


def _pull_docker_image_async(image: str):
    """Background task to pull Docker image with progress tracking."""
    import docker
    import json

    # Normalize image name for storage key
    image_key = image.replace("/", "_").replace(":", "_")

    _active_docker_pulls[image_key] = {
        "status": "pulling",
        "image": image,
        "progress_percent": 0,
        "current_layer": "",
        "layers_total": 0,
        "layers_completed": 0,
        "cancelled": False,
        "error": None,
    }

    try:
        docker_service = get_docker_service()
        client = docker_service.client

        # Use low-level API to get streaming progress
        api_client = client.api

        # Track layer progress
        layers = {}

        for line in api_client.pull(image, stream=True, decode=True):
            # Check for cancellation
            if _active_docker_pulls.get(image_key, {}).get("cancelled"):
                _active_docker_pulls[image_key]["status"] = "cancelled"
                return

            if "id" in line and "progressDetail" in line:
                layer_id = line["id"]
                progress_detail = line.get("progressDetail", {})
                status_text = line.get("status", "")

                if progress_detail:
                    current = progress_detail.get("current", 0)
                    total = progress_detail.get("total", 0)
                    layers[layer_id] = {"current": current, "total": total, "status": status_text}
                elif status_text in ["Pull complete", "Already exists"]:
                    layers[layer_id] = {"current": 1, "total": 1, "status": status_text}

                # Calculate overall progress
                total_bytes = sum(l.get("total", 0) for l in layers.values())
                current_bytes = sum(l.get("current", 0) for l in layers.values())
                completed_layers = sum(1 for l in layers.values() if l.get("status") in ["Pull complete", "Already exists"])

                if total_bytes > 0:
                    progress = int((current_bytes / total_bytes) * 100)
                else:
                    progress = 0

                _active_docker_pulls[image_key].update({
                    "progress_percent": min(progress, 99),  # Don't show 100 until verified complete
                    "current_layer": layer_id,
                    "layers_total": len(layers),
                    "layers_completed": completed_layers,
                })
            elif "status" in line:
                # Handle status messages without layer ID
                logger.debug(f"Docker pull status: {line.get('status')}")

        # Verify image was pulled
        try:
            pulled_image = client.images.get(image)
            _active_docker_pulls[image_key].update({
                "status": "completed",
                "progress_percent": 100,
                "image_id": pulled_image.id,
                "size_bytes": pulled_image.attrs.get("Size", 0),
            })
        except Exception:
            _active_docker_pulls[image_key].update({
                "status": "completed",
                "progress_percent": 100,
            })

    except Exception as e:
        logger.error(f"Failed to pull Docker image {image}: {e}")
        _active_docker_pulls[image_key].update({
            "status": "failed",
            "error": str(e),
        })


@router.post("/images/pull")
def start_docker_pull(
    request: DockerPullRequest,
    background_tasks: BackgroundTasks,
    current_user: AdminUser
):
    """
    Start an async Docker image pull with progress tracking.
    Returns immediately and allows polling for status.
    """
    image = request.image
    image_key = image.replace("/", "_").replace(":", "_")

    # Check if already pulling
    if image_key in _active_docker_pulls and _active_docker_pulls[image_key].get("status") == "pulling":
        return {
            "status": "already_pulling",
            "image": image,
            "message": "Image is already being pulled",
        }

    # Check if image already cached
    docker = get_docker_service()
    try:
        existing = docker.client.images.get(image)
        return {
            "status": "already_cached",
            "image": image,
            "message": "Image is already cached",
            "image_id": existing.id,
        }
    except Exception:
        pass  # Image not cached, proceed with pull

    # Start background pull
    background_tasks.add_task(_pull_docker_image_async, image)

    return {
        "status": "pulling",
        "image": image,
        "message": f"Started pulling {image}",
    }


@router.get("/images/pull/{image_key}/status")
def get_docker_pull_status(image_key: str, current_user: CurrentUser):
    """Get status of a Docker image pull in progress."""
    # Check active pulls first
    if image_key in _active_docker_pulls:
        pull_info = _active_docker_pulls[image_key]
        return {
            "status": pull_info.get("status", "unknown"),
            "image": pull_info.get("image"),
            "progress_percent": pull_info.get("progress_percent", 0),
            "layers_total": pull_info.get("layers_total", 0),
            "layers_completed": pull_info.get("layers_completed", 0),
            "error": pull_info.get("error"),
            "image_id": pull_info.get("image_id"),
            "size_bytes": pull_info.get("size_bytes"),
        }

    # Not in active pulls - check if image exists (completed before tracking started)
    docker = get_docker_service()
    try:
        # Convert key back to image name
        image_name = image_key.replace("_", "/", 1)  # First underscore is /
        if "_" in image_name:
            # Handle tag
            parts = image_name.rsplit("_", 1)
            image_name = parts[0] + ":" + parts[1]

        existing = docker.client.images.get(image_name)
        return {
            "status": "completed",
            "image": image_name,
            "progress_percent": 100,
            "image_id": existing.id,
        }
    except Exception:
        pass

    return {
        "status": "not_found",
        "message": f"No pull found for {image_key}",
    }


@router.post("/images/pull/{image_key}/cancel")
def cancel_docker_pull(image_key: str, current_user: AdminUser):
    """Cancel an active Docker image pull."""
    if image_key not in _active_docker_pulls:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active pull found for {image_key}"
        )

    if _active_docker_pulls[image_key].get("status") != "pulling":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pull is not in progress"
        )

    _active_docker_pulls[image_key]["cancelled"] = True
    return {
        "status": "cancelling",
        "image_key": image_key,
        "message": "Cancellation requested",
    }


@router.get("/images/pulls/active")
def get_active_docker_pulls(current_user: CurrentUser):
    """Get all active Docker image pulls."""
    return {
        "pulls": [
            {
                "image_key": key,
                "image": info.get("image"),
                "status": info.get("status"),
                "progress_percent": info.get("progress_percent", 0),
                "layers_total": info.get("layers_total", 0),
                "layers_completed": info.get("layers_completed", 0),
            }
            for key, info in _active_docker_pulls.items()
            if info.get("status") == "pulling"
        ]
    }


# ============ Docker Image Build Endpoints ============

# Path to the images directory containing Dockerfiles
# In Docker: /data/images, locally: ./data/images or ./images
def _get_images_dir() -> str:
    if os.path.exists("/data/images"):
        return "/data/images"
    elif os.path.exists("data/images"):
        return os.path.abspath("data/images")
    else:
        return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "images")

IMAGES_DIR = _get_images_dir()


class DockerBuildRequest(BaseModel):
    """Request to build a Docker image."""
    image_name: str  # Directory name in images/ (e.g., "kali-attack", "samba-dc")
    tag: str = "latest"  # Tag for the built image
    no_cache: bool = False  # Whether to build without cache


class BuildableImage(BaseModel):
    """Information about a buildable image."""
    name: str
    path: str
    has_dockerfile: bool
    has_readme: bool
    description: Optional[str] = None


def _get_image_description(image_path: str) -> Optional[str]:
    """Extract description from README.md if available."""
    readme_path = os.path.join(image_path, "README.md")
    if os.path.exists(readme_path):
        try:
            with open(readme_path, 'r') as f:
                # Read first few lines to extract description
                lines = f.readlines()[:10]
                for i, line in enumerate(lines):
                    # Skip title line
                    if line.startswith("# "):
                        continue
                    # Return first non-empty, non-header line
                    line = line.strip()
                    if line and not line.startswith("#"):
                        return line[:200]  # Limit description length
        except Exception:
            pass
    return None


@router.get("/images/buildable")
def list_buildable_images(current_user: CurrentUser):
    """
    List available images that can be built from the images/ directory.
    Each image directory should contain a Dockerfile.
    """
    buildable = []

    if not os.path.exists(IMAGES_DIR):
        return {"images": [], "images_dir": IMAGES_DIR, "exists": False}

    for name in sorted(os.listdir(IMAGES_DIR)):
        image_path = os.path.join(IMAGES_DIR, name)
        if not os.path.isdir(image_path):
            continue

        dockerfile_path = os.path.join(image_path, "Dockerfile")
        readme_path = os.path.join(image_path, "README.md")

        has_dockerfile = os.path.exists(dockerfile_path)
        has_readme = os.path.exists(readme_path)

        if has_dockerfile:
            buildable.append(BuildableImage(
                name=name,
                path=image_path,
                has_dockerfile=has_dockerfile,
                has_readme=has_readme,
                description=_get_image_description(image_path),
            ))

    return {
        "images": buildable,
        "images_dir": IMAGES_DIR,
        "exists": True,
    }


def _build_docker_image_async(image_name: str, tag: str, no_cache: bool):
    """Background task to build a Docker image with progress tracking."""
    build_key = f"{image_name}_{tag}"
    image_path = os.path.join(IMAGES_DIR, image_name)
    full_tag = f"cyroid/{image_name}:{tag}"

    _active_docker_builds[build_key] = {
        "status": "building",
        "image_name": image_name,
        "tag": tag,
        "full_tag": full_tag,
        "progress_percent": 0,
        "current_step": 0,
        "total_steps": 0,
        "current_step_name": "Starting build...",
        "logs": [],
        "cancelled": False,
    }

    try:
        docker = get_docker_service()
        client = docker.client

        # Build the image with streaming output
        logger.info(f"Building Docker image {full_tag} from {image_path}")

        # Use low-level API to get streaming output
        build_output = client.api.build(
            path=image_path,
            tag=full_tag,
            rm=True,  # Remove intermediate containers
            nocache=no_cache,
            decode=True,  # Decode JSON responses
        )

        step_pattern = r"Step (\d+)/(\d+)"
        import re

        for chunk in build_output:
            # Check for cancellation
            if _active_docker_builds[build_key].get("cancelled"):
                _active_docker_builds[build_key].update({
                    "status": "cancelled",
                    "current_step_name": "Build cancelled by user",
                })
                return

            if "stream" in chunk:
                stream_line = chunk["stream"].strip()
                if stream_line:
                    # Add to logs (keep last 100 lines)
                    logs = _active_docker_builds[build_key].get("logs", [])
                    logs.append(stream_line)
                    if len(logs) > 100:
                        logs = logs[-100:]
                    _active_docker_builds[build_key]["logs"] = logs

                    # Parse step progress
                    match = re.match(step_pattern, stream_line)
                    if match:
                        current_step = int(match.group(1))
                        total_steps = int(match.group(2))
                        progress = int((current_step / total_steps) * 100)

                        _active_docker_builds[build_key].update({
                            "current_step": current_step,
                            "total_steps": total_steps,
                            "progress_percent": min(progress, 99),
                            "current_step_name": stream_line,
                        })

            elif "error" in chunk:
                error_msg = chunk.get("error", "Unknown build error")
                _active_docker_builds[build_key].update({
                    "status": "failed",
                    "error": error_msg,
                    "current_step_name": f"Error: {error_msg}",
                })
                logger.error(f"Docker build failed: {error_msg}")
                return

            elif "aux" in chunk:
                # Build complete - aux contains the image ID
                image_id = chunk.get("aux", {}).get("ID", "")
                _active_docker_builds[build_key].update({
                    "status": "completed",
                    "progress_percent": 100,
                    "image_id": image_id,
                    "current_step_name": "Build complete!",
                })
                logger.info(f"Docker build completed: {full_tag} ({image_id})")
                return

        # If we get here without aux, check if image exists
        try:
            built_image = client.images.get(full_tag)
            _active_docker_builds[build_key].update({
                "status": "completed",
                "progress_percent": 100,
                "image_id": built_image.id,
                "current_step_name": "Build complete!",
            })
        except Exception:
            _active_docker_builds[build_key].update({
                "status": "completed",
                "progress_percent": 100,
                "current_step_name": "Build complete!",
            })

    except Exception as e:
        logger.error(f"Failed to build Docker image {image_name}: {e}")
        _active_docker_builds[build_key].update({
            "status": "failed",
            "error": str(e),
            "current_step_name": f"Error: {str(e)}",
        })


@router.post("/images/build")
def start_docker_build(
    request: DockerBuildRequest,
    background_tasks: BackgroundTasks,
    current_user: AdminUser
):
    """
    Start an async Docker image build with progress tracking.
    Returns immediately and allows polling for status.
    """
    image_name = request.image_name
    tag = request.tag
    build_key = f"{image_name}_{tag}"

    # Validate image exists
    image_path = os.path.join(IMAGES_DIR, image_name)
    dockerfile_path = os.path.join(image_path, "Dockerfile")

    if not os.path.exists(dockerfile_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No Dockerfile found at {image_path}"
        )

    # Check if already building
    if build_key in _active_docker_builds and _active_docker_builds[build_key].get("status") == "building":
        return {
            "status": "already_building",
            "image_name": image_name,
            "tag": tag,
            "message": "Image is already being built",
        }

    # Start background build
    background_tasks.add_task(_build_docker_image_async, image_name, tag, request.no_cache)

    return {
        "status": "building",
        "image_name": image_name,
        "tag": tag,
        "build_key": build_key,
        "message": f"Started building cyroid/{image_name}:{tag}",
    }


@router.get("/images/build/{build_key}/status")
def get_docker_build_status(build_key: str, current_user: CurrentUser):
    """Get status of a Docker image build in progress."""
    if build_key in _active_docker_builds:
        build_info = _active_docker_builds[build_key]
        return {
            "status": build_info.get("status", "unknown"),
            "image_name": build_info.get("image_name"),
            "tag": build_info.get("tag"),
            "full_tag": build_info.get("full_tag"),
            "progress_percent": build_info.get("progress_percent", 0),
            "current_step": build_info.get("current_step", 0),
            "total_steps": build_info.get("total_steps", 0),
            "current_step_name": build_info.get("current_step_name", ""),
            "error": build_info.get("error"),
            "image_id": build_info.get("image_id"),
            "logs": build_info.get("logs", [])[-20:],  # Last 20 log lines
        }

    return {
        "status": "not_found",
        "message": f"No build found for {build_key}",
    }


@router.post("/images/build/{build_key}/cancel")
def cancel_docker_build(build_key: str, current_user: AdminUser):
    """Cancel an active Docker image build."""
    if build_key not in _active_docker_builds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active build found for {build_key}"
        )

    if _active_docker_builds[build_key].get("status") != "building":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Build is not in progress"
        )

    _active_docker_builds[build_key]["cancelled"] = True
    return {
        "status": "cancelling",
        "build_key": build_key,
        "message": "Cancellation requested",
    }


@router.get("/images/builds/active")
def get_active_docker_builds(current_user: CurrentUser):
    """Get all active Docker image builds."""
    return {
        "builds": [
            {
                "build_key": key,
                "image_name": info.get("image_name"),
                "tag": info.get("tag"),
                "full_tag": info.get("full_tag"),
                "status": info.get("status"),
                "progress_percent": info.get("progress_percent", 0),
                "current_step": info.get("current_step", 0),
                "total_steps": info.get("total_steps", 0),
                "current_step_name": info.get("current_step_name", ""),
            }
            for key, info in _active_docker_builds.items()
            if info.get("status") == "building"
        ]
    }


# Windows ISO caching endpoints

@router.get("/isos", response_model=ISOCacheResponse)
def get_iso_cache_status(current_user: CurrentUser):
    """Get status of cached Windows ISOs."""
    docker = get_docker_service()
    return docker.get_windows_iso_cache_status()


# Snapshot endpoints - supports both Windows golden images and Docker container snapshots

@router.get("/snapshots")
def get_all_snapshots(current_user: CurrentUser):
    """
    Get all VM snapshots - both Windows golden images and Docker container snapshots.

    Returns:
    - windows_golden_images: Pre-installed Windows VMs (dockur/windows storage copies)
    - docker_snapshots: Docker container commits (Linux VMs, custom containers)
    """
    docker = get_docker_service()
    return docker.get_all_snapshots()


@router.get("/golden-images", response_model=GoldenImageResponse)
def get_golden_images_status(current_user: CurrentUser):
    """Get status of Windows golden images (pre-installed templates)."""
    docker = get_docker_service()
    return docker.get_golden_images_status()


class CreateSnapshotRequest(BaseModel):
    container_id: str
    name: str
    snapshot_type: str = "auto"  # "auto", "windows", or "docker"


@router.post("/snapshots", status_code=status.HTTP_201_CREATED)
def create_snapshot(request: CreateSnapshotRequest, current_user: AdminUser):
    """
    Create a snapshot from a running container.

    For Windows VMs (dockur/windows): Creates a golden image by copying /storage directory.
    For other containers: Creates a Docker image using docker commit.

    Args:
        container_id: ID of the running container
        name: Name for the snapshot
        snapshot_type: "auto" (detect), "windows" (golden image), or "docker" (container commit)
    """
    docker = get_docker_service()

    try:
        # Get container to determine type
        container = docker.client.containers.get(request.container_id)
        image_name = container.image.tags[0] if container.image.tags else ""

        # Determine snapshot type
        is_windows = "dockur/windows" in image_name.lower() or "windows" in image_name.lower()

        if request.snapshot_type == "auto":
            use_windows_method = is_windows
        elif request.snapshot_type == "windows":
            use_windows_method = True
        else:
            use_windows_method = False

        if use_windows_method:
            result = docker.create_golden_image(request.container_id, request.name)
        else:
            # Use docker commit for Linux/custom containers
            snapshot_name = f"cyroid/snapshot/{request.name}"
            result = docker.create_container_snapshot(request.container_id, snapshot_name)

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create snapshot: {str(e)}"
        )


@router.post("/golden-images", status_code=status.HTTP_201_CREATED)
def create_golden_image(request: CreateGoldenImageRequest, current_user: AdminUser):
    """
    Create a Windows golden image from a running dockur/windows container.
    This saves the /storage directory for reuse as a template.
    Admin only as this involves significant disk operations.

    For Linux containers, use POST /snapshots with snapshot_type="docker".
    """
    docker = get_docker_service()
    try:
        result = docker.create_golden_image(request.container_id, request.name)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create golden image: {str(e)}"
        )


@router.delete("/snapshots/{snapshot_type}/{name}")
def delete_snapshot(snapshot_type: str, name: str, current_user: AdminUser):
    """
    Delete a snapshot.

    Args:
        snapshot_type: "windows" for golden images, "docker" for container snapshots
        name: Name of the snapshot to delete
    """
    import os
    import shutil
    from cyroid.config import get_settings

    if snapshot_type == "windows":
        settings = get_settings()
        golden_dir = os.path.join(settings.template_storage_dir, name)

        if not os.path.exists(golden_dir):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Windows golden image not found"
            )

        try:
            shutil.rmtree(golden_dir)
            return {"status": "deleted", "type": "windows", "name": name}
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete golden image: {str(e)}"
            )
    elif snapshot_type == "docker":
        docker = get_docker_service()
        try:
            # Look for the image
            image_name = f"cyroid/snapshot/{name}"
            docker.client.images.remove(image_name, force=True)
            return {"status": "deleted", "type": "docker", "name": image_name}
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete Docker snapshot: {str(e)}"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid snapshot_type. Use 'windows' or 'docker'"
        )


@router.delete("/golden-images/{name}")
def delete_golden_image(name: str, current_user: AdminUser):
    """Delete a Windows golden image. Admin only."""
    import os
    import shutil
    from cyroid.config import get_settings

    settings = get_settings()
    golden_dir = os.path.join(settings.template_storage_dir, name)

    if not os.path.exists(golden_dir):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Golden image not found"
        )

    try:
        shutil.rmtree(golden_dir)
        return {"status": "deleted", "name": name}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete golden image: {str(e)}"
        )


# System cache info

@router.get("/stats")
def get_cache_stats(current_user: CurrentUser):
    """Get overall cache statistics."""
    docker = get_docker_service()

    images = docker.list_cached_images()
    isos = docker.get_windows_iso_cache_status()
    golden = docker.get_golden_images_status()

    total_image_size = sum(img["size_bytes"] for img in images)
    total_iso_size = sum(iso["size_bytes"] for iso in isos["isos"])
    total_golden_size = sum(g["size_bytes"] for g in golden["golden_images"])

    return {
        "docker_images": {
            "count": len(images),
            "total_size_bytes": total_image_size,
            "total_size_gb": round(total_image_size / (1024**3), 2)
        },
        "windows_isos": {
            "count": isos["total_count"],
            "total_size_bytes": total_iso_size,
            "total_size_gb": round(total_iso_size / (1024**3), 2),
            "cache_dir": isos["cache_dir"]
        },
        "golden_images": {
            "count": golden["total_count"],
            "total_size_bytes": total_golden_size,
            "total_size_gb": round(total_golden_size / (1024**3), 2),
            "storage_dir": golden["template_dir"]
        },
        "total_cache_size_gb": round(
            (total_image_size + total_iso_size + total_golden_size) / (1024**3), 2
        )
    }


# Dockur/Windows supported versions
# These are auto-downloaded by dockur/windows when the container starts
# See: https://github.com/dockur/windows
#
# Download sources (from dockur/windows):
# - Primary: dl.bobpony.com/windows (MSDN ISOs)
# - Primary: files.dog/MSDN (community mirror)
# - Fallback: archive.org (legacy versions)
# - Microsoft: Evaluation Center for server editions (official, 180-day eval)
#
# Note: dl.bobpony.com was previously used but now returns 403 Forbidden.
# The download_urls list supports fallback - first working URL is used.

DOCKUR_WINDOWS_VERSIONS = [
    # Desktop versions - Windows 11
    {
        "version": "11",
        "name": "Windows 11 Pro",
        "size_gb": 6.3,
        "category": "desktop",
        "download_url": "https://files.dog/MSDN/Windows%2011%2C%20Version%2024H2%20(Updated%20October%202024)/en-us_windows_11_consumer_editions_version_24h2_updated_oct_2024_x64_dvd_5fc00aec.iso",
        "download_urls": [
            "https://files.dog/MSDN/Windows%2011%2C%20Version%2024H2%20(Updated%20October%202024)/en-us_windows_11_consumer_editions_version_24h2_updated_oct_2024_x64_dvd_5fc00aec.iso",
        ],
    },
    {
        "version": "11e",
        "name": "Windows 11 Enterprise",
        "size_gb": 5.8,
        "category": "desktop",
        "download_url": "https://files.dog/MSDN/Windows%2011%2C%20Version%2024H2%20(Updated%20October%202024)/en-us_windows_11_business_editions_version_24h2_updated_oct_2024_x64_dvd_0cae2f00.iso",
        "download_urls": [
            "https://files.dog/MSDN/Windows%2011%2C%20Version%2024H2%20(Updated%20October%202024)/en-us_windows_11_business_editions_version_24h2_updated_oct_2024_x64_dvd_0cae2f00.iso",
        ],
    },
    # Desktop versions - Windows 10
    {
        "version": "10",
        "name": "Windows 10 Pro",
        "size_gb": 5.7,
        "category": "desktop",
        "download_url": "https://files.dog/MSDN/Windows%2010%2C%20Version%2022H2%20(Updated%20May%202024)/en-us_windows_10_consumer_editions_version_22h2_updated_may_2024_x64_dvd_5a846042.iso",
        "download_urls": [
            "https://files.dog/MSDN/Windows%2010%2C%20Version%2022H2%20(Updated%20May%202024)/en-us_windows_10_consumer_editions_version_22h2_updated_may_2024_x64_dvd_5a846042.iso",
        ],
    },
    {
        "version": "10e",
        "name": "Windows 10 Enterprise",
        "size_gb": 5.5,
        "category": "desktop",
        "download_url": "https://files.dog/MSDN/Windows%2010%2C%20Version%2022H2%20(Updated%20May%202024)/en-us_windows_10_business_editions_version_22h2_updated_may_2024_x64_dvd_108d3e87.iso",
        "download_urls": [
            "https://files.dog/MSDN/Windows%2010%2C%20Version%2022H2%20(Updated%20May%202024)/en-us_windows_10_business_editions_version_22h2_updated_may_2024_x64_dvd_108d3e87.iso",
        ],
    },
    {
        "version": "10l",
        "name": "Windows 10 LTSC 2021",
        "size_gb": 4.6,
        "category": "desktop",
        "download_url": "https://files.dog/MSDN/Windows%2010%20Enterprise%20LTSC%202021/en-us_windows_10_enterprise_ltsc_2021_x64_dvd_d289cf96.iso",
        "download_urls": [
            "https://files.dog/MSDN/Windows%2010%20Enterprise%20LTSC%202021/en-us_windows_10_enterprise_ltsc_2021_x64_dvd_d289cf96.iso",
        ],
    },
    # Desktop versions - Windows 8.1
    {
        "version": "81",
        "name": "Windows 8.1 Pro",
        "size_gb": 3.7,
        "category": "desktop",
        "download_url": "https://files.dog/MSDN/Windows%208.1%20with%20Update/en_windows_8.1_with_update_x64_dvd_6051480.iso",
        "download_urls": [
            "https://files.dog/MSDN/Windows%208.1%20with%20Update/en_windows_8.1_with_update_x64_dvd_6051480.iso",
        ],
    },
    # Desktop versions - Legacy
    {
        "version": "7",
        "name": "Windows 7 Ultimate SP1",
        "size_gb": 3.1,
        "category": "legacy",
        "download_url": "https://files.dog/MSDN/Windows%207/en_windows_7_ultimate_with_sp1_x64_dvd_u_677332.iso",
        "download_urls": [
            "https://files.dog/MSDN/Windows%207/en_windows_7_ultimate_with_sp1_x64_dvd_u_677332.iso",
            "https://archive.org/download/en_windows_7_ultimate_with_sp1_x64_dvd_u_677332_202409/en_windows_7_ultimate_with_sp1_x64_dvd_u_677332.iso",
        ],
    },
    {
        "version": "vista",
        "name": "Windows Vista Ultimate SP2",
        "size_gb": 3.0,
        "category": "legacy",
        "download_url": "https://files.dog/MSDN/Windows%20Vista/en_windows_vista_sp2_x64_dvd_342267.iso",
        "download_urls": [
            "https://files.dog/MSDN/Windows%20Vista/en_windows_vista_sp2_x64_dvd_342267.iso",
            "https://archive.org/download/windows-vista-sp2-x64/en_windows_vista_sp2_x64_dvd_342267.iso",
        ],
    },
    {
        "version": "xp",
        "name": "Windows XP Professional SP3",
        "size_gb": 0.6,
        "category": "legacy",
        "download_url": "https://files.dog/MSDN/Windows%20XP/en_windows_xp_professional_with_service_pack_3_x86_cd_x14-80428.iso",
        "download_urls": [
            "https://files.dog/MSDN/Windows%20XP/en_windows_xp_professional_with_service_pack_3_x86_cd_x14-80428.iso",
            "https://archive.org/download/WinXPProSP3x86/en_windows_xp_professional_with_service_pack_3_x86_cd_x14-80428.iso",
        ],
    },
    {
        "version": "2k",
        "name": "Windows 2000 Professional SP4",
        "size_gb": 0.3,
        "category": "legacy",
        "download_url": "https://archive.org/download/win-2000-pro-sp-4/Win2000ProSP4.iso",
        "download_urls": [
            "https://archive.org/download/win-2000-pro-sp-4/Win2000ProSP4.iso",
        ],
    },
    # Server versions - Modern (Microsoft Evaluation Center - 180-day eval)
    {
        "version": "2025",
        "name": "Windows Server 2025 (Eval)",
        "size_gb": 5.5,
        "category": "server",
        "download_url": "https://software-static.download.prss.microsoft.com/dbazure/888969d5-f34g-4e03-ac9d-1f9786c66749/26100.1742.240906-0331.ge_release_svc_refresh_SERVER_EVAL_x64FRE_en-us.iso",
        "download_urls": [
            "https://software-static.download.prss.microsoft.com/dbazure/888969d5-f34g-4e03-ac9d-1f9786c66749/26100.1742.240906-0331.ge_release_svc_refresh_SERVER_EVAL_x64FRE_en-us.iso",
        ],
    },
    {
        "version": "2022",
        "name": "Windows Server 2022 (Eval)",
        "size_gb": 5.3,
        "category": "server",
        "download_url": "https://software-static.download.prss.microsoft.com/sg/download/888969d5-f34g-4e03-ac9d-1f9786c66749/SERVER_EVAL_x64FRE_en-us.iso",
        "download_urls": [
            "https://software-static.download.prss.microsoft.com/sg/download/888969d5-f34g-4e03-ac9d-1f9786c66749/SERVER_EVAL_x64FRE_en-us.iso",
        ],
    },
    {
        "version": "2019",
        "name": "Windows Server 2019 (Eval)",
        "size_gb": 5.0,
        "category": "server",
        "download_url": "https://software-static.download.prss.microsoft.com/pr/download/17763.3650.221105-1748.rs5_release_svc_refresh_SERVER_EVAL_x64FRE_en-us.iso",
        "download_urls": [
            "https://software-static.download.prss.microsoft.com/pr/download/17763.3650.221105-1748.rs5_release_svc_refresh_SERVER_EVAL_x64FRE_en-us.iso",
        ],
    },
    {
        "version": "2016",
        "name": "Windows Server 2016 (Eval)",
        "size_gb": 6.0,
        "category": "server",
        "download_url": "https://software-static.download.prss.microsoft.com/pr/download/Windows_Server_2016_Datacenter_EVAL_en-us_14393_refresh.ISO",
        "download_urls": [
            "https://software-static.download.prss.microsoft.com/pr/download/Windows_Server_2016_Datacenter_EVAL_en-us_14393_refresh.ISO",
        ],
    },
    # Server versions - Legacy (files.dog MSDN mirror)
    {
        "version": "2012",
        "name": "Windows Server 2012 R2",
        "size_gb": 4.3,
        "category": "server",
        "download_url": "https://files.dog/MSDN/Windows%20Server%202012%20R2/en_windows_server_2012_r2_with_update_x64_dvd_6052708.iso",
        "download_urls": [
            "https://files.dog/MSDN/Windows%20Server%202012%20R2/en_windows_server_2012_r2_with_update_x64_dvd_6052708.iso",
        ],
    },
    {
        "version": "2008",
        "name": "Windows Server 2008 R2 SP1",
        "size_gb": 3.0,
        "category": "server",
        "download_url": "https://files.dog/MSDN/Windows%20Server%202008%20R2/en_windows_server_2008_r2_with_sp1_x64_dvd_617601.iso",
        "download_urls": [
            "https://files.dog/MSDN/Windows%20Server%202008%20R2/en_windows_server_2008_r2_with_sp1_x64_dvd_617601.iso",
            "https://archive.org/download/en_windows_server_2008_r2_with_sp1_x64_dvd_617601/en_windows_server_2008_r2_with_sp1_x64_dvd_617601.iso",
        ],
    },
    {
        "version": "2003",
        "name": "Windows Server 2003 R2",
        "size_gb": 0.6,
        "category": "legacy",
        "download_url": "https://archive.org/download/en_win_srv_2003_r2_standard_x64_with_sp2_cd1_x13-05757/en_win_srv_2003_r2_standard_x64_with_sp2_cd1_x13-05757.iso",
        "download_urls": [
            "https://archive.org/download/en_win_srv_2003_r2_standard_x64_with_sp2_cd1_x13-05757/en_win_srv_2003_r2_standard_x64_with_sp2_cd1_x13-05757.iso",
        ],
    },
]


# qemus/qemu supported Linux distributions
# These are auto-downloaded by qemus/qemu when the container starts
# Download URLs sourced from: https://github.com/qemus/qemu-docker/blob/master/src/define.sh
QEMU_LINUX_VERSIONS = [
    # Popular desktop distributions
    {
        "version": "ubuntu",
        "name": "Ubuntu Desktop",
        "size_gb": 6.0,
        "category": "desktop",
        "description": "Ubuntu Desktop 24.04 LTS - Popular and user-friendly",
        "download_url": "https://releases.ubuntu.com/noble/ubuntu-24.04.3-desktop-amd64.iso",
    },
    {
        "version": "ubuntus",
        "name": "Ubuntu Server",
        "size_gb": 3.0,
        "category": "server",
        "description": "Ubuntu Server 24.04 LTS - Minimal server install",
        "download_url": "https://releases.ubuntu.com/noble/ubuntu-24.04.3-live-server-amd64.iso",
    },
    {
        "version": "debian",
        "name": "Debian",
        "size_gb": 3.3,
        "category": "desktop",
        "description": "Debian 13 Trixie - Stable and reliable",
        "download_url": "https://cdimage.debian.org/debian-cd/current-live/amd64/iso-hybrid/debian-live-13.3.0-amd64-gnome.iso",
    },
    {
        "version": "fedora",
        "name": "Fedora",
        "size_gb": 2.3,
        "category": "desktop",
        "description": "Fedora Workstation - Cutting-edge features",
        "download_url": "https://download.fedoraproject.org/pub/fedora/linux/releases/41/Workstation/x86_64/iso/Fedora-Workstation-Live-x86_64-41-1.4.iso",
    },
    {
        "version": "alpine",
        "name": "Alpine Linux",
        "size_gb": 0.06,
        "category": "server",
        "description": "Alpine Linux - Minimal and security-focused (60 MB)",
        "download_url": "https://dl-cdn.alpinelinux.org/alpine/v3.23/releases/x86_64/alpine-virt-3.23.2-x86_64.iso",
    },
    {
        "version": "arch",
        "name": "Arch Linux",
        "size_gb": 1.2,
        "category": "desktop",
        "description": "Arch Linux - Rolling release, highly customizable",
        "download_url": "https://geo.mirror.pkgbuild.com/iso/latest/archlinux-x86_64.iso",
    },
    {
        "version": "manjaro",
        "name": "Manjaro",
        "size_gb": 4.1,
        "category": "desktop",
        "description": "Manjaro - User-friendly Arch-based distro",
        "download_url": "https://sourceforge.net/projects/manjarolinux/files/gnome/26.0/manjaro-gnome-26.0-260104-linux618.iso/download",
    },
    {
        "version": "suse",
        "name": "OpenSUSE",
        "size_gb": 1.0,
        "category": "desktop",
        "description": "OpenSUSE Leap - Stable enterprise-grade",
        "download_url": "https://download.opensuse.org/distribution/leap/15.6/iso/openSUSE-Leap-15.6-DVD-x86_64-Media.iso",
    },
    {
        "version": "mint",
        "name": "Linux Mint",
        "size_gb": 2.8,
        "category": "desktop",
        "description": "Linux Mint - Windows-like experience",
        "download_url": "https://mirrors.kernel.org/linuxmint/stable/22.3/linuxmint-22.3-cinnamon-64bit.iso",
    },
    {
        "version": "zorin",
        "name": "Zorin OS",
        "size_gb": 3.8,
        "category": "desktop",
        "description": "Zorin OS - Beautiful and familiar interface",
        "download_url": "https://mirrors.edge.kernel.org/zorinos-isos/17/Zorin-OS-17.3-Core-64-bit-r2.iso",
    },
    {
        "version": "kubuntu",
        "name": "Kubuntu",
        "size_gb": 4.4,
        "category": "desktop",
        "description": "Kubuntu - Ubuntu with KDE Plasma desktop",
        "download_url": "https://cdimages.ubuntu.com/kubuntu/releases/noble/release/kubuntu-24.04.3-desktop-amd64.iso",
    },
    {
        "version": "xubuntu",
        "name": "Xubuntu",
        "size_gb": 4.0,
        "category": "desktop",
        "description": "Xubuntu - Ubuntu with lightweight XFCE desktop",
        "download_url": "https://cdimages.ubuntu.com/xubuntu/releases/noble/release/xubuntu-24.04.3-desktop-amd64.iso",
    },
    # Security-focused distributions (for cyber range training)
    {
        "version": "kali",
        "name": "Kali Linux",
        "size_gb": 3.8,
        "category": "security",
        "description": "Kali Linux - Penetration testing and security auditing",
        "download_url": "https://cdimage.kali.org/kali-2025.4/kali-linux-2025.4-installer-amd64.iso",
    },
    {
        "version": "tails",
        "name": "Tails",
        "size_gb": 1.9,
        "category": "security",
        "description": "Tails - Privacy-focused, runs from memory",
        "download_url": "https://download.tails.net/tails/stable/tails-amd64-7.3.1/tails-amd64-7.3.1.iso",
    },
    # Enterprise/server distributions
    {
        "version": "rocky",
        "name": "Rocky Linux",
        "size_gb": 2.1,
        "category": "server",
        "description": "Rocky Linux 9 - RHEL compatible enterprise OS",
        "download_url": "https://dl.rockylinux.org/pub/rocky/9/live/x86_64/Rocky-9-Workstation-x86_64-latest.iso",
    },
    {
        "version": "alma",
        "name": "Alma Linux",
        "size_gb": 2.2,
        "category": "server",
        "description": "Alma Linux 9 - RHEL compatible enterprise OS",
        "download_url": "https://repo.almalinux.org/almalinux/9/live/x86_64/AlmaLinux-9-latest-x86_64-Live-GNOME.iso",
    },
    {
        "version": "centos",
        "name": "CentOS Stream",
        "size_gb": 7.0,
        "category": "server",
        "description": "CentOS Stream 9 - RHEL upstream development",
        "download_url": "https://mirrors.centos.org/mirrorlist?path=/9-stream/BaseOS/x86_64/iso/CentOS-Stream-9-latest-x86_64-dvd1.iso&redirect=1&protocol=https",
    },
    # Other distributions
    {
        "version": "gentoo",
        "name": "Gentoo",
        "size_gb": 3.6,
        "category": "desktop",
        "description": "Gentoo - Source-based, highly customizable",
        "download_url": "https://distfiles.gentoo.org/releases/amd64/autobuilds/current-livegui-amd64/livegui-amd64-20260111T160052Z.iso",
    },
    {
        "version": "nixos",
        "name": "NixOS",
        "size_gb": 2.4,
        "category": "desktop",
        "description": "NixOS - Declarative and reproducible",
        "download_url": "https://channels.nixos.org/nixos-25.11/latest-nixos-gnome-x86_64-linux.iso",
    },
    {
        "version": "mx",
        "name": "MX Linux",
        "size_gb": 2.2,
        "category": "desktop",
        "description": "MX Linux - Lightweight and fast",
        "download_url": "https://sourceforge.net/projects/mx-linux/files/Final/Xfce/MX-25_Xfce_x64.iso/download",
    },
    {
        "version": "cachy",
        "name": "CachyOS",
        "size_gb": 2.6,
        "category": "desktop",
        "description": "CachyOS - Performance-optimized Arch-based",
        "download_url": "https://sourceforge.net/projects/cachyos-arch/files/gui-installer/desktop/251129/cachyos-desktop-linux-251129.iso/download",
    },
    {
        "version": "slack",
        "name": "Slackware",
        "size_gb": 3.7,
        "category": "server",
        "description": "Slackware - One of the oldest Linux distributions",
        "download_url": "https://slackware.nl/slackware-live/slackware64-current-live/slackware64-live-current.iso",
    },
]


# ARM64 ISO URLs for supported distributions
# These are used when running on ARM64 hosts (Apple Silicon, etc.)
QEMU_LINUX_ARM64_ISOS = {
    "ubuntu": "https://releases.ubuntu.com/24.04/ubuntu-24.04.1-live-server-arm64.iso",
    "ubuntus": "https://releases.ubuntu.com/24.04/ubuntu-24.04.1-live-server-arm64.iso",
    "debian": "https://cdimage.debian.org/debian-cd/current/arm64/iso-cd/debian-12.9.0-arm64-netinst.iso",
    "fedora": "https://download.fedoraproject.org/pub/fedora/linux/releases/41/Server/aarch64/iso/Fedora-Server-dvd-aarch64-41-1.4.iso",
    "alpine": "https://dl-cdn.alpinelinux.org/alpine/v3.21/releases/aarch64/alpine-virt-3.21.2-aarch64.iso",
    "rocky": "https://download.rockylinux.org/pub/rocky/9/isos/aarch64/Rocky-9.5-aarch64-minimal.iso",
    "alma": "https://repo.almalinux.org/almalinux/9/isos/aarch64/AlmaLinux-9-latest-aarch64-minimal.iso",
    "kali": "https://cdimage.kali.org/kali-2024.4/kali-linux-2024.4-installer-arm64.iso",
}

# Distributions with native ARM64 support
ARM64_NATIVE_DISTROS = {"ubuntu", "ubuntus", "debian", "fedora", "alpine", "rocky", "alma", "kali"}


def get_arm64_iso_url(distro_version: str) -> str | None:
    """
    Get the ARM64 ISO URL for a distribution if available.

    Args:
        distro_version: The version code (e.g., "ubuntu", "debian", "fedora")

    Returns:
        The ARM64 ISO URL if available, None otherwise
    """
    return QEMU_LINUX_ARM64_ISOS.get(distro_version)


def has_arm64_support(distro_version: str) -> bool:
    """
    Check if a distribution has native ARM64 support.

    Args:
        distro_version: The version code (e.g., "ubuntu", "debian", "fedora")

    Returns:
        True if the distribution has ARM64 support, False otherwise
    """
    return distro_version in ARM64_NATIVE_DISTROS


def get_linux_iso_dir() -> str:
    """Get the Linux ISO cache directory path."""
    settings = get_settings()
    return os.path.join(settings.iso_cache_dir, "linux-isos")


@router.get("/linux-versions")
def get_linux_versions(current_user: CurrentUser):
    """
    Get all supported Linux distributions for qemus/qemu with cached status.

    These distributions are automatically downloaded by qemus/qemu
    when a container is started - no manual ISO download needed.
    Returns cached status for each version.
    """
    linux_iso_dir = get_linux_iso_dir()

    # Get list of cached ISO files
    cached_isos = set()
    if os.path.exists(linux_iso_dir):
        for filename in os.listdir(linux_iso_dir):
            if filename.endswith((".iso", ".img", ".qcow2")):
                cached_isos.add(filename.lower())

    # Add cached status to each version
    def add_cached_status(version_list):
        result = []
        for v in version_list:
            version_info = dict(v)
            # Check for common ISO naming patterns
            version_code = v["version"]
            is_cached = any(
                version_code.lower() in iso_name or
                f"linux-{version_code}".lower() in iso_name
                for iso_name in cached_isos
            )
            version_info["cached"] = is_cached
            result.append(version_info)
        return result

    all_versions = add_cached_status(QEMU_LINUX_VERSIONS)
    desktop = [v for v in all_versions if v["category"] == "desktop"]
    server = [v for v in all_versions if v["category"] == "server"]
    security = [v for v in all_versions if v["category"] == "security"]

    cached_count = sum(1 for v in all_versions if v["cached"])

    return {
        "desktop": desktop,
        "server": server,
        "security": security,
        "all": all_versions,
        "cache_dir": linux_iso_dir,
        "cached_count": cached_count,
        "total_count": len(all_versions),
        "note": "ISOs are automatically downloaded by qemus/qemu when the VM starts. Pre-caching is optional but speeds up first boot."
    }


@router.get("/linux-isos")
def get_linux_iso_cache_status(current_user: CurrentUser):
    """Get status of cached Linux ISOs."""
    docker = get_docker_service()
    return docker.get_linux_iso_cache_status()


# Linux ISO Download endpoints

class LinuxISODownloadRequest(BaseModel):
    version: str
    url: Optional[str] = None  # Custom URL, or use default for version


# Track active Linux ISO downloads
_active_linux_downloads: dict = {}


@router.post("/linux-isos/download", status_code=status.HTTP_202_ACCEPTED)
def download_linux_iso(
    request: LinuxISODownloadRequest,
    background_tasks: BackgroundTasks,
    current_user: AdminUser
):
    """
    Download a Linux ISO from the official source or custom URL.
    Admin only as this downloads large files.

    If no URL is provided, uses the default download URL for the distribution.
    Some distributions don't have static download URLs and require manual download.
    """
    import os
    from cyroid.config import get_settings

    # Validate version
    version_info = None
    for v in QEMU_LINUX_VERSIONS:
        if v["version"] == request.version:
            version_info = v
            break

    if not version_info:
        valid_versions = [v["version"] for v in QEMU_LINUX_VERSIONS]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid version '{request.version}'. Valid versions: {', '.join(valid_versions)}"
        )

    # Determine download URL
    download_url = request.url or version_info.get("download_url")

    if not download_url:
        # No direct download URL available
        download_note = version_info.get("download_note", "No direct download available")

        response = {
            "status": "no_direct_download",
            "version": request.version,
            "name": version_info["name"],
            "message": download_note,
            "instructions": "Provide a custom URL or upload the ISO manually.",
        }

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=response
        )

    linux_iso_dir = get_linux_iso_dir()
    os.makedirs(linux_iso_dir, exist_ok=True)

    filename = f"linux-{request.version}.iso"
    filepath = os.path.join(linux_iso_dir, filename)

    # Check if already exists
    if os.path.exists(filepath):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ISO for '{request.version}' already exists. Delete it first to re-download."
        )

    # Check if already downloading
    if request.version in _active_linux_downloads and _active_linux_downloads[request.version].get("status") == "downloading":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Download already in progress for '{request.version}'"
        )

    # Start download
    _active_linux_downloads[request.version] = {
        "status": "downloading",
        "filename": filename,
        "progress_bytes": 0,
        "total_bytes": None,
        "error": None
    }

    def download_iso(url: str, dest_path: str, version: str):
        """Download ISO in background with progress tracking."""
        import requests
        import time

        try:
            # Use streaming download with progress
            response = requests.get(url, stream=True, timeout=3600, allow_redirects=True)
            response.raise_for_status()

            # Get total size if available
            total_size = response.headers.get('content-length')
            if total_size:
                total_size = int(total_size)
                _active_linux_downloads[version]["total_bytes"] = total_size

            # Download with progress tracking
            downloaded = 0
            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):  # 1MB chunks
                    # Check if download was cancelled
                    if version not in _active_linux_downloads or _active_linux_downloads[version].get("cancelled"):
                        if os.path.exists(dest_path):
                            os.remove(dest_path)
                        if version in _active_linux_downloads:
                            del _active_linux_downloads[version]
                        return
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        _active_linux_downloads[version]["progress_bytes"] = downloaded

            _active_linux_downloads[version]["status"] = "completed"
            _active_linux_downloads[version]["progress_bytes"] = os.path.getsize(dest_path)

            # Clear from active downloads after a delay (allow frontend to see completion)
            time.sleep(3)
            if version in _active_linux_downloads:
                del _active_linux_downloads[version]

        except Exception as e:
            # Clean up partial download
            if os.path.exists(dest_path):
                os.remove(dest_path)
            if version in _active_linux_downloads:
                _active_linux_downloads[version]["status"] = "failed"
                _active_linux_downloads[version]["error"] = str(e)
                # Clear failed downloads after a delay
                time.sleep(5)
                if version in _active_linux_downloads:
                    del _active_linux_downloads[version]

    background_tasks.add_task(download_iso, download_url, filepath, request.version)

    return {
        "status": "downloading",
        "version": request.version,
        "name": version_info["name"],
        "filename": filename,
        "destination": filepath,
        "source_url": download_url,
        "expected_size_gb": version_info.get("size_gb"),
        "message": f"Downloading {version_info['name']} ISO..."
    }


@router.get("/linux-isos/download/{version}/status")
def get_linux_iso_download_status(version: str, current_user: CurrentUser):
    """Check the status of a Linux ISO download."""
    linux_iso_dir = get_linux_iso_dir()
    filename = f"linux-{version}.iso"
    filepath = os.path.join(linux_iso_dir, filename)

    # IMPORTANT: Check active downloads FIRST (file exists during download)
    if version in _active_linux_downloads:
        info = _active_linux_downloads[version]
        response = {
            "status": info["status"],
            "version": version,
            "filename": info.get("filename"),
        }

        if info.get("progress_bytes") is not None:
            response["progress_bytes"] = info["progress_bytes"]
            response["progress_gb"] = round(info["progress_bytes"] / (1024**3), 2)

        if info.get("total_bytes") is not None:
            response["total_bytes"] = info["total_bytes"]
            response["total_gb"] = round(info["total_bytes"] / (1024**3), 2)
            if info["progress_bytes"]:
                response["progress_percent"] = round(info["progress_bytes"] / info["total_bytes"] * 100, 1)

        if info.get("error"):
            response["error"] = info["error"]

        return response

    # Only check file if NOT in active downloads (truly completed)
    if os.path.exists(filepath):
        size = os.path.getsize(filepath)
        return {
            "status": "completed",
            "version": version,
            "filename": filename,
            "path": filepath,
            "size_bytes": size,
            "size_gb": round(size / (1024**3), 2)
        }

    return {
        "status": "not_found",
        "version": version,
        "message": "No download in progress and ISO not found in cache"
    }


@router.post("/linux-isos/download/{version}/cancel")
def cancel_linux_iso_download(version: str, current_user: AdminUser):
    """Cancel an in-progress Linux ISO download. Admin only."""
    if version not in _active_linux_downloads:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active download found for '{version}'"
        )

    if _active_linux_downloads[version].get("status") != "downloading":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Download for '{version}' is not in progress (status: {_active_linux_downloads[version].get('status')})"
        )

    # Mark as cancelled - the download loop will detect this and clean up
    _active_linux_downloads[version]["cancelled"] = True
    _active_linux_downloads[version]["status"] = "cancelled"

    return {"status": "cancelled", "version": version, "message": f"Download for '{version}' has been cancelled"}


@router.delete("/linux-isos/{version}")
def delete_linux_iso(version: str, current_user: AdminUser):
    """Delete a cached Linux ISO. Admin only."""
    linux_iso_dir = get_linux_iso_dir()
    filename = f"linux-{version}.iso"
    filepath = os.path.join(linux_iso_dir, filename)

    # Clear any active download entry for this version
    if version in _active_linux_downloads:
        del _active_linux_downloads[version]

    if not os.path.exists(filepath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ISO for '{version}' not found"
        )

    try:
        os.remove(filepath)
        return {"status": "deleted", "version": version, "filename": filename}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete ISO: {str(e)}"
        )


@router.get("/windows-versions")
def get_windows_versions(current_user: CurrentUser):
    """
    Get all supported Windows versions for dockur/windows with cached status.

    These versions are automatically downloaded by dockur/windows
    when a container is started - no manual ISO download needed.
    Returns cached status for each version.
    """
    windows_iso_dir = get_windows_iso_dir()

    # Get list of cached ISO files
    cached_isos = set()
    if os.path.exists(windows_iso_dir):
        for filename in os.listdir(windows_iso_dir):
            if filename.endswith(".iso"):
                cached_isos.add(filename.lower())

    # Add cached status to each version
    def add_cached_status(version_list):
        result = []
        for v in version_list:
            version_info = dict(v)
            # Check for common ISO naming patterns
            version_code = v["version"]
            is_cached = any(
                version_code.lower() in iso_name or
                f"windows-{version_code}".lower() in iso_name or
                f"win{version_code}".lower() in iso_name
                for iso_name in cached_isos
            )
            version_info["cached"] = is_cached
            result.append(version_info)
        return result

    all_versions = add_cached_status(DOCKUR_WINDOWS_VERSIONS)
    desktop = [v for v in all_versions if v["category"] == "desktop"]
    server = [v for v in all_versions if v["category"] == "server"]
    legacy = [v for v in all_versions if v["category"] == "legacy"]

    cached_count = sum(1 for v in all_versions if v["cached"])

    return {
        "desktop": desktop,
        "server": server,
        "legacy": legacy,
        "all": all_versions,
        "cache_dir": windows_iso_dir,
        "cached_count": cached_count,
        "total_count": len(all_versions),
        "note": "ISOs are automatically downloaded by dockur/windows when the VM starts. Pre-caching is optional but speeds up first boot."
    }


# Custom ISO cache endpoints

# Track active custom ISO downloads
_active_custom_downloads: dict = {}

class CustomISORequest(BaseModel):
    name: str  # Display name for the ISO
    url: str   # URL to download ISO from


class CustomISOResponse(BaseModel):
    name: str
    filename: str
    path: str
    url: str
    size_bytes: int
    size_gb: float
    downloaded_at: str


@router.get("/custom-isos")
def list_custom_isos(current_user: CurrentUser):
    """List all custom ISOs in the cache."""
    import os
    import json
    from cyroid.config import get_settings

    settings = get_settings()
    custom_iso_dir = os.path.join(settings.iso_cache_dir, "custom-isos")
    metadata_file = os.path.join(custom_iso_dir, "metadata.json")

    # Ensure directory exists
    os.makedirs(custom_iso_dir, exist_ok=True)

    # Load metadata
    metadata = {}
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, "r") as f:
                metadata = json.load(f)
        except:
            metadata = {}

    isos = []
    for filename in os.listdir(custom_iso_dir):
        if filename.endswith(".iso"):
            filepath = os.path.join(custom_iso_dir, filename)
            size = os.path.getsize(filepath)
            iso_metadata = metadata.get(filename, {})
            isos.append({
                "name": iso_metadata.get("name", filename.replace(".iso", "")),
                "filename": filename,
                "path": filepath,
                "url": iso_metadata.get("url", ""),
                "size_bytes": size,
                "size_gb": round(size / (1024**3), 2),
                "downloaded_at": iso_metadata.get("downloaded_at", "")
            })

    return {
        "cache_dir": custom_iso_dir,
        "total_count": len(isos),
        "isos": isos
    }


@router.post("/custom-isos", status_code=status.HTTP_201_CREATED)
def download_custom_iso(
    request: CustomISORequest,
    background_tasks: BackgroundTasks,
    current_user: AdminUser
):
    """
    Download a custom ISO from a URL to the cache.
    Admin only as this downloads potentially large files.
    """
    import os
    import re
    from cyroid.config import get_settings

    settings = get_settings()
    custom_iso_dir = os.path.join(settings.iso_cache_dir, "custom-isos")
    os.makedirs(custom_iso_dir, exist_ok=True)

    # Sanitize filename from name
    safe_name = re.sub(r'[^\w\-.]', '_', request.name)
    if not safe_name.endswith('.iso'):
        safe_name += '.iso'

    filepath = os.path.join(custom_iso_dir, safe_name)

    # Check if already exists
    if os.path.exists(filepath):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ISO '{safe_name}' already exists in cache"
        )

    # Check if already downloading
    if safe_name in _active_custom_downloads and _active_custom_downloads[safe_name].get("status") == "downloading":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Download already in progress for '{request.name}'"
        )

    # Start download with progress tracking
    _active_custom_downloads[safe_name] = {
        "status": "downloading",
        "name": request.name,
        "filename": safe_name,
        "url": request.url,
        "progress_bytes": 0,
        "total_bytes": None,
        "error": None
    }

    def download_iso(url: str, dest_path: str, name: str, filename: str, iso_dir: str):
        """Download ISO in background with progress tracking. Supports compressed archives."""
        import requests
        import json
        import time
        import shutil
        import tempfile
        from datetime import datetime

        metadata_file = os.path.join(iso_dir, "metadata.json")
        is_archive = is_archive_file(url)
        temp_archive_path = None
        extract_dir = None

        try:
            # Determine download path (temp file for archives, final path for ISOs)
            if is_archive:
                archive_ext = get_archive_extension(url) or '.archive'
                temp_archive_path = os.path.join(iso_dir, f".tmp_{filename}{archive_ext}")
                download_path = temp_archive_path
                _active_custom_downloads[filename]["is_archive"] = True
                _active_custom_downloads[filename]["archive_status"] = "downloading"
            else:
                download_path = dest_path

            # Use streaming download with progress
            response = requests.get(url, stream=True, timeout=3600, allow_redirects=True)
            response.raise_for_status()

            # Get total size if available
            total_size = response.headers.get('content-length')
            if total_size:
                total_size = int(total_size)
                _active_custom_downloads[filename]["total_bytes"] = total_size

            # Download with progress tracking
            downloaded = 0
            with open(download_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):  # 1MB chunks
                    # Check if download was cancelled
                    if filename not in _active_custom_downloads or _active_custom_downloads[filename].get("cancelled"):
                        if os.path.exists(download_path):
                            os.remove(download_path)
                        if filename in _active_custom_downloads:
                            del _active_custom_downloads[filename]
                        return
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        _active_custom_downloads[filename]["progress_bytes"] = downloaded

            # If it's an archive, extract and find the ISO
            if is_archive:
                _active_custom_downloads[filename]["archive_status"] = "extracting"
                logger.info(f"Extracting ISO from archive: {temp_archive_path}")

                try:
                    iso_path = extract_iso_from_archive(temp_archive_path, iso_dir)
                    extract_dir = os.path.dirname(iso_path)

                    # Move extracted ISO to final destination
                    shutil.move(iso_path, dest_path)
                    logger.info(f"Extracted ISO moved to: {dest_path}")

                finally:
                    # Clean up temp archive and extraction directory
                    if temp_archive_path and os.path.exists(temp_archive_path):
                        os.remove(temp_archive_path)
                    if extract_dir and os.path.exists(extract_dir):
                        shutil.rmtree(extract_dir, ignore_errors=True)

            # Update metadata
            metadata = {}
            if os.path.exists(metadata_file):
                try:
                    with open(metadata_file, "r") as f:
                        metadata = json.load(f)
                except:
                    metadata = {}

            metadata[filename] = {
                "name": name,
                "url": url,
                "downloaded_at": datetime.utcnow().isoformat(),
                "extracted_from_archive": is_archive
            }
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)

            _active_custom_downloads[filename]["status"] = "completed"
            _active_custom_downloads[filename]["progress_bytes"] = os.path.getsize(dest_path)

            # Clear from active downloads after a delay (allow frontend to see completion)
            time.sleep(3)
            if filename in _active_custom_downloads:
                del _active_custom_downloads[filename]

        except Exception as e:
            # Clean up partial download and temp files
            if os.path.exists(dest_path):
                os.remove(dest_path)
            if temp_archive_path and os.path.exists(temp_archive_path):
                os.remove(temp_archive_path)
            if extract_dir and os.path.exists(extract_dir):
                shutil.rmtree(extract_dir, ignore_errors=True)

            if filename in _active_custom_downloads:
                _active_custom_downloads[filename]["status"] = "failed"
                _active_custom_downloads[filename]["error"] = str(e)
                # Clear failed downloads after a delay
                time.sleep(5)
                if filename in _active_custom_downloads:
                    del _active_custom_downloads[filename]

    background_tasks.add_task(
        download_iso,
        request.url,
        filepath,
        request.name,
        safe_name,
        custom_iso_dir
    )

    return {
        "status": "downloading",
        "message": f"Downloading {request.name} from {request.url}",
        "filename": safe_name,
        "name": request.name,
        "destination": filepath
    }


@router.get("/custom-isos/{filename}/status")
def get_custom_iso_download_status(filename: str, current_user: CurrentUser):
    """Check the status of a custom ISO download."""
    import os
    import json
    from cyroid.config import get_settings

    settings = get_settings()
    custom_iso_dir = os.path.join(settings.iso_cache_dir, "custom-isos")
    filepath = os.path.join(custom_iso_dir, filename)
    metadata_file = os.path.join(custom_iso_dir, "metadata.json")

    # IMPORTANT: Check active downloads FIRST (file exists during download)
    if filename in _active_custom_downloads:
        info = _active_custom_downloads[filename]
        response = {
            "status": info["status"],
            "filename": filename,
            "name": info.get("name"),
        }

        if info.get("progress_bytes") is not None:
            response["progress_bytes"] = info["progress_bytes"]
            response["progress_gb"] = round(info["progress_bytes"] / (1024**3), 2)

        if info.get("total_bytes") is not None:
            response["total_bytes"] = info["total_bytes"]
            response["total_gb"] = round(info["total_bytes"] / (1024**3), 2)
            if info["progress_bytes"]:
                response["progress_percent"] = round(info["progress_bytes"] / info["total_bytes"] * 100, 1)

        if info.get("error"):
            response["error"] = info["error"]

        return response

    # Only check file if NOT in active downloads (truly completed)
    if os.path.exists(filepath):
        size = os.path.getsize(filepath)

        # Load metadata
        metadata = {}
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, "r") as f:
                    metadata = json.load(f)
            except:
                pass

        iso_metadata = metadata.get(filename, {})

        return {
            "status": "completed",
            "filename": filename,
            "name": iso_metadata.get("name", filename.replace(".iso", "")),
            "path": filepath,
            "size_bytes": size,
            "size_gb": round(size / (1024**3), 2),
            "downloaded_at": iso_metadata.get("downloaded_at", "")
        }

    return {
        "status": "not_found",
        "filename": filename,
        "message": "No download in progress and ISO not found in cache"
    }


@router.post("/custom-isos/{filename}/cancel")
def cancel_custom_iso_download(filename: str, current_user: AdminUser):
    """Cancel an in-progress custom ISO download. Admin only."""
    if filename not in _active_custom_downloads:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active download found for '{filename}'"
        )

    if _active_custom_downloads[filename].get("status") != "downloading":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Download for '{filename}' is not in progress (status: {_active_custom_downloads[filename].get('status')})"
        )

    # Mark as cancelled - the download loop will detect this and clean up
    _active_custom_downloads[filename]["cancelled"] = True
    _active_custom_downloads[filename]["status"] = "cancelled"

    return {"status": "cancelled", "filename": filename, "message": f"Download for '{filename}' has been cancelled"}


@router.delete("/custom-isos/{filename}")
def delete_custom_iso(filename: str, current_user: AdminUser):
    """Delete a custom ISO from the cache. Admin only."""
    import os
    import json
    from cyroid.config import get_settings

    settings = get_settings()
    custom_iso_dir = os.path.join(settings.iso_cache_dir, "custom-isos")
    filepath = os.path.join(custom_iso_dir, filename)
    metadata_file = os.path.join(custom_iso_dir, "metadata.json")

    # Clear any active download entry for this filename
    if filename in _active_custom_downloads:
        del _active_custom_downloads[filename]

    if not os.path.exists(filepath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom ISO not found"
        )

    try:
        os.remove(filepath)

        # Update metadata
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, "r") as f:
                    metadata = json.load(f)
                if filename in metadata:
                    del metadata[filename]
                    with open(metadata_file, "w") as f:
                        json.dump(metadata, f, indent=2)
            except:
                pass

        return {"status": "deleted", "filename": filename}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete ISO: {str(e)}"
        )


# Recommended images for cyber ranges - categorized
#
# Categories:
# - desktop: Images with GUI desktop environment (VNC/web accessible)
# - server: Headless server/CLI images
# - services: Purpose-built service containers

RECOMMENDED_DOCKER_IMAGES = {
    "desktop": [
        # Desktop images with built-in VNC/web access
        {"name": "Ubuntu Desktop (XFCE)", "image": "linuxserver/webtop:ubuntu-xfce", "description": "Full Ubuntu desktop with XFCE, accessible via web browser", "category": "desktop", "access": "web"},
        {"name": "Debian Desktop (KDE)", "image": "linuxserver/webtop:debian-kde", "description": "Full Debian desktop with KDE Plasma, accessible via web browser", "category": "desktop", "access": "web"},
        {"name": "Fedora Desktop (XFCE)", "image": "linuxserver/webtop:fedora-xfce", "description": "Full Fedora desktop with XFCE, accessible via web browser", "category": "desktop", "access": "web"},
        {"name": "Arch Linux Desktop (XFCE)", "image": "linuxserver/webtop:arch-xfce", "description": "Full Arch Linux desktop with XFCE, accessible via web browser", "category": "desktop", "access": "web"},
        {"name": "Ubuntu 22.04 Desktop (Kasm)", "image": "kasmweb/ubuntu-jammy-desktop:1.14.0", "description": "Ubuntu 22.04 with full desktop environment via KasmVNC", "category": "desktop", "access": "vnc"},
        {"name": "Kali Linux Desktop (Kasm)", "image": "kasmweb/kali-rolling-desktop:1.14.0", "description": "Kali Linux with full desktop and security tools via KasmVNC", "category": "desktop", "access": "vnc"},
        {"name": "Ubuntu Desktop (XFCE/VNC)", "image": "consol/ubuntu-xfce-vnc", "description": "Ubuntu with XFCE desktop accessible via VNC", "category": "desktop", "access": "vnc"},
        {"name": "Ubuntu Desktop (LXDE/VNC)", "image": "dorowu/ubuntu-desktop-lxde-vnc", "description": "Lightweight Ubuntu with LXDE desktop accessible via VNC", "category": "desktop", "access": "vnc"},
    ],
    "server": [
        # Headless server/CLI images
        {"name": "Ubuntu Server 22.04 LTS", "image": "ubuntu:22.04", "description": "Ubuntu 22.04 LTS (Jammy Jellyfish) - Long-term support", "category": "server"},
        {"name": "Ubuntu Server 20.04 LTS", "image": "ubuntu:20.04", "description": "Ubuntu 20.04 LTS (Focal Fossa) - Stable release", "category": "server"},
        {"name": "Debian 12 (Bookworm)", "image": "debian:12", "description": "Debian 12 Bookworm - Current stable release", "category": "server"},
        {"name": "Debian 11 (Bullseye)", "image": "debian:11", "description": "Debian 11 Bullseye - Previous stable release", "category": "server"},
        {"name": "Fedora Server 39", "image": "fedora:39", "description": "Fedora 39 - Latest features and packages", "category": "server"},
        {"name": "Rocky Linux 9", "image": "rockylinux:9", "description": "Rocky Linux 9 - RHEL-compatible enterprise Linux", "category": "server"},
        {"name": "CentOS 7", "image": "centos:7", "description": "CentOS 7 - Legacy enterprise Linux support", "category": "server"},
        {"name": "Alpine Linux 3.19", "image": "alpine:3.19", "description": "Alpine Linux - Minimal, security-focused distribution", "category": "server"},
        {"name": "Kali Linux (CLI)", "image": "kalilinux/kali-rolling", "description": "Kali Linux rolling release - Security and pentesting tools", "category": "server"},
    ],
    "services": [
        {"name": "Nginx", "image": "nginx:latest", "description": "High-performance HTTP server and reverse proxy", "category": "services"},
        {"name": "Apache HTTP Server", "image": "httpd:latest", "description": "The Apache HTTP Server Project", "category": "services"},
        {"name": "MySQL 8", "image": "mysql:8", "description": "MySQL 8 - Popular open-source relational database", "category": "services"},
        {"name": "PostgreSQL 16", "image": "postgres:16", "description": "PostgreSQL 16 - Advanced open-source database", "category": "services"},
        {"name": "Redis 7", "image": "redis:7", "description": "Redis 7 - In-memory data structure store and cache", "category": "services"},
        {"name": "MongoDB 7", "image": "mongo:7", "description": "MongoDB 7 - Document-oriented NoSQL database", "category": "services"},
        {"name": "MariaDB 11", "image": "mariadb:11", "description": "MariaDB 11 - MySQL-compatible database server", "category": "services"},
        {"name": "Elasticsearch 8", "image": "elasticsearch:8.11.0", "description": "Elasticsearch - Distributed search and analytics engine", "category": "services"},
    ],
}


@router.get("/recommended-images")
def get_recommended_images(current_user: CurrentUser):
    """
    Get a list of recommended Docker images for cyber range templates.
    These are commonly used images that can be pre-cached.

    Categories:
    - desktop: Images with GUI desktop environment (VNC/web accessible)
    - server: Headless server/CLI images
    - services: Purpose-built service containers
    """
    # Get cached images to mark which are already cached
    docker = get_docker_service()
    cached_images = docker.list_cached_images()
    cached_tags = set()
    for img in cached_images:
        cached_tags.update(img.get("tags", []))

    def add_cached_status(image_list):
        result = []
        for img in image_list:
            img_info = dict(img)
            img_info["cached"] = img["image"] in cached_tags
            result.append(img_info)
        return result

    return {
        "desktop": add_cached_status(RECOMMENDED_DOCKER_IMAGES["desktop"]),
        "server": add_cached_status(RECOMMENDED_DOCKER_IMAGES["server"]),
        "services": add_cached_status(RECOMMENDED_DOCKER_IMAGES["services"]),
        "linux": add_cached_status(RECOMMENDED_DOCKER_IMAGES["server"]),  # Backwards compat
        "windows": DOCKUR_WINDOWS_VERSIONS,
    }


# ISO Upload endpoints
from fastapi import UploadFile, File, Form


@router.post("/isos/upload", status_code=status.HTTP_201_CREATED)
async def upload_windows_iso(
    file: UploadFile = File(...),
    version: str = Form(...),
    current_user: AdminUser = None,
):
    """
    Upload a Windows ISO file to the cache.
    The version should match a supported Windows version code (e.g., '11', '2022').
    Admin only.
    """
    import os
    import aiofiles
    from cyroid.config import get_settings

    # Validate version
    valid_versions = [v["version"] for v in DOCKUR_WINDOWS_VERSIONS]
    if version not in valid_versions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid version '{version}'. Valid versions: {', '.join(valid_versions)}"
        )

    # Validate file type
    if not file.filename or not file.filename.lower().endswith('.iso'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an ISO file"
        )

    windows_iso_dir = get_windows_iso_dir()
    os.makedirs(windows_iso_dir, exist_ok=True)

    # Save with standardized name
    filename = f"windows-{version}.iso"
    filepath = os.path.join(windows_iso_dir, filename)

    # Check if already exists
    if os.path.exists(filepath):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ISO for version '{version}' already exists. Delete it first to replace."
        )

    try:
        async with aiofiles.open(filepath, 'wb') as out_file:
            while content := await file.read(1024 * 1024):  # 1MB chunks
                await out_file.write(content)

        file_size = os.path.getsize(filepath)
        return {
            "status": "uploaded",
            "version": version,
            "filename": filename,
            "path": filepath,
            "size_bytes": file_size,
            "size_gb": round(file_size / (1024**3), 2)
        }
    except Exception as e:
        # Clean up on failure
        if os.path.exists(filepath):
            os.remove(filepath)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload ISO: {str(e)}"
        )


@router.post("/custom-isos/upload", status_code=status.HTTP_201_CREATED)
async def upload_custom_iso(
    file: UploadFile = File(...),
    name: str = Form(...),
    current_user: AdminUser = None,
):
    """
    Upload a custom ISO file or compressed archive containing an ISO to the cache.
    Supports: .iso, .zip, .7z, .rar, .tar, .tar.gz, .tgz, .tar.bz2, .gz, .bz2, .xz
    Admin only.
    """
    import os
    import re
    import json
    import shutil
    import aiofiles
    from datetime import datetime
    from cyroid.config import get_settings

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided"
        )

    # Check if file is an ISO or supported archive
    filename_lower = file.filename.lower()
    is_iso = filename_lower.endswith('.iso')
    is_archive = is_archive_file(file.filename)

    if not is_iso and not is_archive:
        supported_formats = ".iso, " + ", ".join(SUPPORTED_ARCHIVE_EXTENSIONS)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File must be an ISO or compressed archive. Supported formats: {supported_formats}"
        )

    settings = get_settings()
    custom_iso_dir = os.path.join(settings.iso_cache_dir, "custom-isos")
    os.makedirs(custom_iso_dir, exist_ok=True)

    # Sanitize filename from name
    safe_name = re.sub(r'[^\w\-.]', '_', name)
    if not safe_name.endswith('.iso'):
        safe_name += '.iso'

    filepath = os.path.join(custom_iso_dir, safe_name)
    metadata_file = os.path.join(custom_iso_dir, "metadata.json")

    # Check if already exists
    if os.path.exists(filepath):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ISO '{safe_name}' already exists. Delete it first to replace."
        )

    temp_archive_path = None
    extract_dir = None

    try:
        if is_archive:
            # Save archive to temp file first
            archive_ext = get_archive_extension(file.filename) or '.archive'
            temp_archive_path = os.path.join(custom_iso_dir, f".tmp_upload_{safe_name}{archive_ext}")

            async with aiofiles.open(temp_archive_path, 'wb') as out_file:
                while content := await file.read(1024 * 1024):  # 1MB chunks
                    await out_file.write(content)

            # Extract ISO from archive
            logger.info(f"Extracting ISO from uploaded archive: {temp_archive_path}")
            iso_path = extract_iso_from_archive(temp_archive_path, custom_iso_dir)
            extract_dir = os.path.dirname(iso_path)

            # Move extracted ISO to final destination
            shutil.move(iso_path, filepath)
            logger.info(f"Extracted ISO moved to: {filepath}")

            # Clean up
            if os.path.exists(temp_archive_path):
                os.remove(temp_archive_path)
            if extract_dir and os.path.exists(extract_dir):
                shutil.rmtree(extract_dir, ignore_errors=True)

        else:
            # Direct ISO upload
            async with aiofiles.open(filepath, 'wb') as out_file:
                while content := await file.read(1024 * 1024):  # 1MB chunks
                    await out_file.write(content)

        file_size = os.path.getsize(filepath)

        # Update metadata
        metadata = {}
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, "r") as f:
                    metadata = json.load(f)
            except:
                metadata = {}

        metadata[safe_name] = {
            "name": name,
            "url": f"uploaded:{file.filename}",
            "downloaded_at": datetime.utcnow().isoformat(),
            "extracted_from_archive": is_archive
        }
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

        return {
            "status": "uploaded",
            "name": name,
            "filename": safe_name,
            "path": filepath,
            "size_bytes": file_size,
            "size_gb": round(file_size / (1024**3), 2),
            "extracted_from_archive": is_archive
        }
    except ValueError as e:
        # Clean up on failure (e.g., no ISO found in archive)
        if os.path.exists(filepath):
            os.remove(filepath)
        if temp_archive_path and os.path.exists(temp_archive_path):
            os.remove(temp_archive_path)
        if extract_dir and os.path.exists(extract_dir):
            shutil.rmtree(extract_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # Clean up on failure
        if os.path.exists(filepath):
            os.remove(filepath)
        if temp_archive_path and os.path.exists(temp_archive_path):
            os.remove(temp_archive_path)
        if extract_dir and os.path.exists(extract_dir):
            shutil.rmtree(extract_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload ISO: {str(e)}"
        )


@router.post("/isos/download/{version}/cancel")
def cancel_windows_iso_download(version: str, current_user: AdminUser):
    """Cancel an in-progress Windows ISO download. Admin only."""
    if version not in _active_downloads:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active download found for '{version}'"
        )

    if _active_downloads[version].get("status") != "downloading":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Download for '{version}' is not in progress (status: {_active_downloads[version].get('status')})"
        )

    # Mark as cancelled - the download loop will detect this and clean up
    _active_downloads[version]["cancelled"] = True
    _active_downloads[version]["status"] = "cancelled"

    return {"status": "cancelled", "version": version, "message": f"Download for '{version}' has been cancelled"}


@router.delete("/isos/{version}")
def delete_windows_iso(version: str, current_user: AdminUser):
    """Delete a cached Windows ISO. Admin only."""
    windows_iso_dir = get_windows_iso_dir()
    filename = f"windows-{version}.iso"
    filepath = os.path.join(windows_iso_dir, filename)

    # Clear any active download entry for this version
    if version in _active_downloads:
        del _active_downloads[version]

    if not os.path.exists(filepath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ISO for version '{version}' not found"
        )

    try:
        os.remove(filepath)
        return {"status": "deleted", "version": version, "filename": filename}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete ISO: {str(e)}"
        )


@router.get("/isos/upload-info")
def get_iso_upload_info(current_user: CurrentUser):
    """Get information about ISO upload locations and requirements."""
    settings = get_settings()
    windows_iso_dir = get_windows_iso_dir()
    return {
        "windows_iso_dir": windows_iso_dir,
        "custom_iso_dir": f"{settings.iso_cache_dir}/custom-isos",
        "instructions": [
            "ISOs can be uploaded via the web interface or copied directly to the cache directories.",
            "Windows ISOs should be named to match the version code (e.g., windows-11.iso, windows-2022.iso).",
            "Custom ISOs can have any name ending in .iso.",
            "Maximum recommended file size: 10GB per ISO.",
        ],
        "supported_versions": [v["version"] for v in DOCKUR_WINDOWS_VERSIONS],
    }


# Windows ISO Download endpoint

class WindowsISODownloadRequest(BaseModel):
    version: str
    url: Optional[str] = None  # Custom URL, or use default for version


class WindowsISODownloadStatusResponse(BaseModel):
    status: str  # 'downloading', 'completed', 'failed', 'not_found'
    version: str
    filename: Optional[str] = None
    progress_bytes: Optional[int] = None
    progress_gb: Optional[float] = None
    total_bytes: Optional[int] = None
    total_gb: Optional[float] = None
    error: Optional[str] = None


# Track active downloads
_active_downloads: dict = {}


@router.post("/isos/download", status_code=status.HTTP_202_ACCEPTED)
def download_windows_iso(
    request: WindowsISODownloadRequest,
    background_tasks: BackgroundTasks,
    current_user: AdminUser
):
    """
    Download a Windows ISO from Microsoft or custom URL.
    Admin only as this downloads large files.

    If no URL is provided, uses the default download URL for the version.
    Some versions (consumer editions) don't have direct download URLs
    and require manual download from Microsoft's website.
    """
    import os
    from cyroid.config import get_settings

    # Validate version
    version_info = None
    for v in DOCKUR_WINDOWS_VERSIONS:
        if v["version"] == request.version:
            version_info = v
            break

    if not version_info:
        valid_versions = [v["version"] for v in DOCKUR_WINDOWS_VERSIONS]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid version '{request.version}'. Valid versions: {', '.join(valid_versions)}"
        )

    # Determine download URLs (support multiple fallbacks)
    download_urls = []
    if request.url:
        download_urls = [request.url]
    else:
        # Try download_urls list first, then fall back to single download_url
        download_urls = version_info.get("download_urls", [])
        if not download_urls:
            single_url = version_info.get("download_url")
            if single_url:
                download_urls = [single_url]

    if not download_urls:
        # No direct download URL available
        download_page = version_info.get("download_page")
        download_note = version_info.get("download_note", "No direct download available")

        response = {
            "status": "no_direct_download",
            "version": request.version,
            "name": version_info["name"],
            "message": download_note,
        }
        if download_page:
            response["download_page"] = download_page
            response["instructions"] = f"Visit {download_page} to download the ISO manually, then upload it."
        else:
            response["instructions"] = "Provide a custom URL or upload the ISO manually."

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=response
        )

    # Use the first URL for the response (actual download tries all URLs)
    primary_download_url = download_urls[0]

    windows_iso_dir = get_windows_iso_dir()
    os.makedirs(windows_iso_dir, exist_ok=True)

    filename = f"windows-{request.version}.iso"
    filepath = os.path.join(windows_iso_dir, filename)

    # Check if already exists
    if os.path.exists(filepath):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ISO for version '{request.version}' already exists. Delete it first to re-download."
        )

    # Check if already downloading
    if request.version in _active_downloads and _active_downloads[request.version].get("status") == "downloading":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Download already in progress for version '{request.version}'"
        )

    # Start download
    _active_downloads[request.version] = {
        "status": "downloading",
        "filename": filename,
        "progress_bytes": 0,
        "total_bytes": None,
        "error": None
    }

    def download_iso(urls: list, dest_path: str, version: str):
        """Download ISO in background with progress tracking and fallback URL support."""
        import requests
        import time

        last_error = None

        for url_index, url in enumerate(urls):
            try:
                # Update status with current URL being tried
                if url_index > 0:
                    _active_downloads[version]["fallback_attempt"] = url_index + 1
                    _active_downloads[version]["progress_bytes"] = 0

                # Use streaming download with progress
                response = requests.get(url, stream=True, timeout=3600, allow_redirects=True)
                response.raise_for_status()

                # Get total size if available
                total_size = response.headers.get('content-length')
                if total_size:
                    total_size = int(total_size)
                    _active_downloads[version]["total_bytes"] = total_size

                # Download with progress tracking
                downloaded = 0
                with open(dest_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):  # 1MB chunks
                        # Check if download was cancelled
                        if version not in _active_downloads or _active_downloads[version].get("cancelled"):
                            if os.path.exists(dest_path):
                                os.remove(dest_path)
                            if version in _active_downloads:
                                del _active_downloads[version]
                            return
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            _active_downloads[version]["progress_bytes"] = downloaded

                _active_downloads[version]["status"] = "completed"
                _active_downloads[version]["progress_bytes"] = os.path.getsize(dest_path)

                # Clear from active downloads after a delay (allow frontend to see completion)
                time.sleep(3)
                if version in _active_downloads:
                    del _active_downloads[version]
                return  # Success!

            except requests.exceptions.HTTPError as e:
                last_error = e
                # Clean up partial download before trying next URL
                if os.path.exists(dest_path):
                    os.remove(dest_path)

                # Only try next URL for 403/404 errors
                if e.response is not None and e.response.status_code in [403, 404]:
                    if url_index < len(urls) - 1:
                        # More URLs to try
                        continue
                # For other HTTP errors or no more URLs, fail
                raise

            except Exception as e:
                last_error = e
                # Clean up partial download
                if os.path.exists(dest_path):
                    os.remove(dest_path)
                # Try next URL
                if url_index < len(urls) - 1:
                    continue
                raise

        # All URLs failed
        if version in _active_downloads:
            _active_downloads[version]["status"] = "failed"
            _active_downloads[version]["error"] = f"All download mirrors failed. Last error: {last_error}"
            # Clear failed downloads after a delay
            time.sleep(5)
            if version in _active_downloads:
                del _active_downloads[version]

    background_tasks.add_task(download_iso, download_urls, filepath, request.version)

    return {
        "status": "downloading",
        "version": request.version,
        "name": version_info["name"],
        "filename": filename,
        "destination": filepath,
        "source_url": primary_download_url,
        "expected_size_gb": version_info.get("size_gb"),
        "message": f"Downloading {version_info['name']} ISO..."
    }


@router.get("/isos/download/{version}/status")
def get_windows_iso_download_status(version: str, current_user: CurrentUser):
    """Check the status of a Windows ISO download."""
    windows_iso_dir = get_windows_iso_dir()
    filename = f"windows-{version}.iso"
    filepath = os.path.join(windows_iso_dir, filename)

    # IMPORTANT: Check active downloads FIRST (file exists during download)
    if version in _active_downloads:
        info = _active_downloads[version]
        response = {
            "status": info["status"],
            "version": version,
            "filename": info.get("filename"),
        }

        if info.get("progress_bytes") is not None:
            response["progress_bytes"] = info["progress_bytes"]
            response["progress_gb"] = round(info["progress_bytes"] / (1024**3), 2)

        if info.get("total_bytes") is not None:
            response["total_bytes"] = info["total_bytes"]
            response["total_gb"] = round(info["total_bytes"] / (1024**3), 2)
            if info["progress_bytes"]:
                response["progress_percent"] = round(info["progress_bytes"] / info["total_bytes"] * 100, 1)

        if info.get("error"):
            response["error"] = info["error"]

        return response

    # Only check file if NOT in active downloads (truly completed)
    if os.path.exists(filepath):
        size = os.path.getsize(filepath)
        return {
            "status": "completed",
            "version": version,
            "filename": filename,
            "path": filepath,
            "size_bytes": size,
            "size_gb": round(size / (1024**3), 2)
        }

    return {
        "status": "not_found",
        "version": version,
        "message": "No download in progress and ISO not found in cache"
    }


