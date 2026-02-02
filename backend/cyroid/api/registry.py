# backend/cyroid/api/registry.py
"""API endpoints for local Docker registry management."""
import logging
import threading
import uuid
from typing import Any, Dict, List, Optional

import docker
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from cyroid.api.deps import CurrentUser, AdminUser
from cyroid.services.registry_service import get_registry_service, RegistryPushError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/registry", tags=["registry"])

# Track active registry pushes for progress reporting
_active_registry_pushes: Dict[str, Dict[str, Any]] = {}


class RegistryImage(BaseModel):
    """Registry image info."""
    name: str
    tags: List[str]


class RegistryStats(BaseModel):
    """Registry statistics."""
    image_count: int
    tag_count: int
    healthy: bool


class PushRequest(BaseModel):
    """Request to push image to registry."""
    image_tag: str


class PushResponse(BaseModel):
    """Response from push operation (legacy sync response)."""
    success: bool
    message: str


class PushStartResponse(BaseModel):
    """Response when starting an async push operation."""
    operation_id: str
    image_tag: str
    message: str


class RegistryPushStatus(BaseModel):
    """Status of an in-progress registry push."""
    operation_id: str
    image_tag: str
    status: str  # "pushing", "verifying", "cleaning", "completed", "failed"
    progress_percent: int
    current_layer: Optional[int] = None
    total_layers: Optional[int] = None
    error_message: Optional[str] = None


class ImageStatusResponse(BaseModel):
    """Response for image status check."""
    image_tag: str
    in_registry: bool
    on_host: bool
    needs_push: bool


class DeleteResponse(BaseModel):
    """Response from delete operation."""
    success: bool
    message: str


@router.get("/images", response_model=List[RegistryImage])
async def list_registry_images(
    current_user: CurrentUser
):
    """List all images in the local registry."""
    registry = get_registry_service()
    images = await registry.list_images()
    return [RegistryImage(**img) for img in images]


@router.get("/stats", response_model=RegistryStats)
async def get_registry_stats(
    current_user: CurrentUser
):
    """Get registry statistics."""
    registry = get_registry_service()
    stats = await registry.get_stats()
    return RegistryStats(**stats)


def _run_registry_push(operation_id: str, image_tag: str):
    """Background thread function to push image to registry with progress tracking."""
    import asyncio

    try:
        # Initialize status
        _active_registry_pushes[operation_id].update({
            "status": "pushing",
            "progress_percent": 5,
        })

        registry = get_registry_service()
        docker_client = docker.from_env()

        # Get the image
        try:
            image = docker_client.images.get(image_tag)
        except docker.errors.ImageNotFound:
            _active_registry_pushes[operation_id].update({
                "status": "failed",
                "error_message": f"Image not found locally: {image_tag}",
            })
            return

        # Tag for registry
        push_tag = registry.get_registry_tag(image_tag, for_host=True)
        image.tag(push_tag)

        _active_registry_pushes[operation_id].update({
            "status": "pushing",
            "progress_percent": 10,
        })

        # Push to registry with progress tracking
        push_output = docker_client.images.push(
            push_tag,
            stream=True,
            decode=True
        )

        # Track layer progress
        layers = {}
        for line in push_output:
            if "error" in line:
                _active_registry_pushes[operation_id].update({
                    "status": "failed",
                    "error_message": line.get("error", "Push error"),
                })
                return

            if "id" in line and "status" in line:
                layer_id = line["id"]
                layer_status = line.get("status", "")

                if layer_status in ("Pushing", "Pushed", "Layer already exists"):
                    layers[layer_id] = layer_status

                    completed = sum(1 for s in layers.values() if s in ("Pushed", "Layer already exists"))
                    total = len(layers)

                    # Progress: 10-70% for pushing layers
                    if total > 0:
                        layer_progress = int(10 + (completed / total) * 60)
                    else:
                        layer_progress = 10

                    _active_registry_pushes[operation_id].update({
                        "progress_percent": min(layer_progress, 70),
                        "current_layer": completed,
                        "total_layers": total,
                    })

        _active_registry_pushes[operation_id].update({
            "status": "verifying",
            "progress_percent": 75,
        })

        # Verify image is in registry
        loop = asyncio.new_event_loop()
        try:
            in_registry = loop.run_until_complete(registry.image_exists(image_tag))
        finally:
            loop.close()

        if not in_registry:
            _active_registry_pushes[operation_id].update({
                "status": "failed",
                "error_message": f"Image {image_tag} not found in registry after push",
            })
            return

        _active_registry_pushes[operation_id].update({
            "status": "cleaning",
            "progress_percent": 85,
        })

        # Cleanup from host
        try:
            docker_client.images.remove(push_tag, force=False)
        except docker.errors.ImageNotFound:
            pass
        except docker.errors.APIError as e:
            logger.warning(f"Could not remove registry tag {push_tag}: {e}")

        try:
            docker_client.images.remove(image_tag, force=False)
        except docker.errors.ImageNotFound:
            pass
        except docker.errors.APIError as e:
            logger.warning(f"Could not remove original image {image_tag}: {e}")

        _active_registry_pushes[operation_id].update({
            "status": "completed",
            "progress_percent": 100,
        })
        logger.info(f"Successfully pushed {image_tag} to registry (operation {operation_id})")

    except Exception as e:
        logger.error(f"Registry push failed for {image_tag}: {e}")
        _active_registry_pushes[operation_id].update({
            "status": "failed",
            "error_message": str(e),
        })


@router.post("/push", response_model=PushStartResponse)
async def push_image_to_registry(
    request: PushRequest,
    current_user: CurrentUser
):
    """Start an async push of an image to the local registry.

    Returns immediately with an operation_id. Poll /push/{operation_id}/status
    for progress updates.
    """
    # Check admin/engineer role
    if not any(role in current_user.roles for role in ['admin', 'engineer']):
        raise HTTPException(status_code=403, detail="Admin or engineer role required")

    registry = get_registry_service()

    if not await registry.is_healthy():
        raise HTTPException(status_code=503, detail="Registry is not healthy")

    # Check if already pushing this image
    for op_id, op_info in _active_registry_pushes.items():
        if op_info.get("image_tag") == request.image_tag and op_info.get("status") == "pushing":
            return PushStartResponse(
                operation_id=op_id,
                image_tag=request.image_tag,
                message="Push already in progress"
            )

    # Generate operation ID and start background push
    operation_id = str(uuid.uuid4())
    _active_registry_pushes[operation_id] = {
        "operation_id": operation_id,
        "image_tag": request.image_tag,
        "status": "starting",
        "progress_percent": 0,
        "current_layer": None,
        "total_layers": None,
        "error_message": None,
    }

    # Start background thread
    thread = threading.Thread(
        target=_run_registry_push,
        args=(operation_id, request.image_tag),
        daemon=True
    )
    thread.start()

    return PushStartResponse(
        operation_id=operation_id,
        image_tag=request.image_tag,
        message="Push started"
    )


@router.get("/push/{operation_id}/status", response_model=RegistryPushStatus)
async def get_push_status(
    operation_id: str,
    current_user: CurrentUser
):
    """Get status of an in-progress registry push operation."""
    if operation_id not in _active_registry_pushes:
        raise HTTPException(status_code=404, detail="Push operation not found")

    push_info = _active_registry_pushes[operation_id]
    return RegistryPushStatus(
        operation_id=operation_id,
        image_tag=push_info.get("image_tag", ""),
        status=push_info.get("status", "unknown"),
        progress_percent=push_info.get("progress_percent", 0),
        current_layer=push_info.get("current_layer"),
        total_layers=push_info.get("total_layers"),
        error_message=push_info.get("error_message"),
    )


@router.get("/pushes/active")
async def get_active_pushes(current_user: CurrentUser):
    """Get all active registry push operations."""
    return {
        "pushes": [
            {
                "operation_id": op_id,
                "image_tag": info.get("image_tag"),
                "status": info.get("status"),
                "progress_percent": info.get("progress_percent", 0),
                "current_layer": info.get("current_layer"),
                "total_layers": info.get("total_layers"),
            }
            for op_id, info in _active_registry_pushes.items()
            if info.get("status") in ("starting", "pushing", "verifying", "cleaning")
        ]
    }


@router.get("/status/{image_tag:path}", response_model=ImageStatusResponse)
async def get_image_status(
    image_tag: str,
    current_user: CurrentUser
):
    """Check if an image exists in registry, on host, or both.

    Args:
        image_tag: The image tag to check (e.g., 'cyroid/kali:latest')

    Returns:
        ImageStatusResponse with location information and needs_push flag
    """
    registry = get_registry_service()

    # Check registry
    in_registry = await registry.image_exists(image_tag)

    # Check host Docker
    on_host = False
    try:
        docker_client = docker.from_env()
        docker_client.images.get(image_tag)
        on_host = True
    except docker.errors.ImageNotFound:
        on_host = False

    # needs_push: image is on host but not in registry
    needs_push = on_host and not in_registry

    return ImageStatusResponse(
        image_tag=image_tag,
        in_registry=in_registry,
        on_host=on_host,
        needs_push=needs_push
    )


@router.get("/health")
async def registry_health():
    """Check registry health (no auth required for healthchecks)."""
    registry = get_registry_service()
    healthy = await registry.is_healthy()
    return {"healthy": healthy}


@router.delete("/images/{image_tag:path}", response_model=DeleteResponse)
async def delete_registry_image(
    image_tag: str,
    current_user: AdminUser
):
    """Delete image from registry (admin only).

    Note: Requires registry garbage collection to reclaim disk space.

    Args:
        image_tag: The image tag to delete (e.g., 'cyroid/kali:latest')

    Returns:
        DeleteResponse with success status and message
    """
    registry = get_registry_service()

    if not await registry.is_healthy():
        raise HTTPException(status_code=503, detail="Registry is not healthy")

    success = await registry.delete_image(image_tag)

    if success:
        return DeleteResponse(
            success=True,
            message=f"Successfully deleted {image_tag} from registry"
        )
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete {image_tag} from registry"
        )
