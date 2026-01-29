# backend/cyroid/api/registry.py
"""API endpoints for local Docker registry management."""
import logging
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from cyroid.api.deps import CurrentUser
from cyroid.services.registry_service import get_registry_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/registry", tags=["registry"])


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
    """Response from push operation."""
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


@router.post("/push", response_model=PushResponse)
async def push_image_to_registry(
    request: PushRequest,
    current_user: CurrentUser
):
    """Manually push an image to the local registry."""
    # Check admin/engineer role
    if not any(role in current_user.roles for role in ['admin', 'engineer']):
        raise HTTPException(status_code=403, detail="Admin or engineer role required")

    registry = get_registry_service()

    if not await registry.is_healthy():
        raise HTTPException(status_code=503, detail="Registry is not healthy")

    success = await registry.push_image(request.image_tag)

    if success:
        return PushResponse(success=True, message=f"Successfully pushed {request.image_tag}")
    else:
        raise HTTPException(status_code=500, detail=f"Failed to push {request.image_tag}")


@router.get("/health")
async def registry_health():
    """Check registry health (no auth required for healthchecks)."""
    registry = get_registry_service()
    healthy = await registry.is_healthy()
    return {"healthy": healthy}
