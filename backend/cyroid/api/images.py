# cyroid/api/images.py
"""API endpoints for Image Library management.

The Image Library consists of three tiers:
- Base Images: Container images and cached ISOs
- Golden Images: First snapshots or imported VMs
- Snapshots: Follow-on snapshots (forks)
"""
from typing import List, Optional
from uuid import UUID
import logging

from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel

from cyroid.api.deps import DBSession, CurrentUser
from cyroid.models.base_image import BaseImage
from cyroid.models.golden_image import GoldenImage
from cyroid.models.snapshot import Snapshot
from cyroid.schemas.base_image import (
    BaseImageCreate, BaseImageUpdate, BaseImageResponse, BaseImageBrief
)
from cyroid.schemas.golden_image import (
    GoldenImageCreate, GoldenImageUpdate, GoldenImageResponse, GoldenImageBrief,
    GoldenImageImportRequest
)
from cyroid.schemas.snapshot import SnapshotResponse, SnapshotBrief

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/images", tags=["Image Library"])


# ============================================================================
# Library Statistics
# ============================================================================

class LibraryStats(BaseModel):
    """Statistics about the Image Library."""
    base_images_count: int
    golden_images_count: int
    snapshots_count: int
    total_size_bytes: int


@router.get("/library/stats", response_model=LibraryStats)
def get_library_stats(
    db: DBSession,
    current_user: CurrentUser,
):
    """Get statistics about the Image Library."""
    from sqlalchemy import func

    base_count = db.query(BaseImage).count()
    golden_count = db.query(GoldenImage).count()
    snapshot_count = db.query(Snapshot).filter(Snapshot.is_global == True).count()

    # Calculate total size using func.sum
    base_size = db.query(func.coalesce(func.sum(BaseImage.size_bytes), 0)).scalar() or 0
    golden_size = db.query(func.coalesce(func.sum(GoldenImage.size_bytes), 0)).scalar() or 0

    return LibraryStats(
        base_images_count=base_count,
        golden_images_count=golden_count,
        snapshots_count=snapshot_count,
        total_size_bytes=base_size + golden_size,
    )


# ============================================================================
# Base Images
# ============================================================================

@router.get("/base", response_model=List[BaseImageResponse])
def list_base_images(
    image_type: Optional[str] = None,
    os_type: Optional[str] = None,
    db: DBSession = None,
    current_user: CurrentUser = None,
):
    """List all base images in the library."""
    query = db.query(BaseImage)

    if image_type:
        query = query.filter(BaseImage.image_type == image_type)
    if os_type:
        query = query.filter(BaseImage.os_type == os_type)

    return query.order_by(BaseImage.created_at.desc()).all()


@router.post("/base", response_model=BaseImageResponse, status_code=status.HTTP_201_CREATED)
def create_base_image(
    image_data: BaseImageCreate,
    db: DBSession,
    current_user: CurrentUser,
):
    """Create a new base image record."""
    base_image = BaseImage(
        name=image_data.name,
        description=image_data.description,
        image_type=image_data.image_type,
        docker_image_id=image_data.docker_image_id,
        docker_image_tag=image_data.docker_image_tag,
        iso_path=image_data.iso_path,
        iso_source=image_data.iso_source,
        iso_version=image_data.iso_version,
        os_type=image_data.os_type,
        vm_type=image_data.vm_type,
        native_arch=image_data.native_arch,
        default_cpu=image_data.default_cpu,
        default_ram_mb=image_data.default_ram_mb,
        default_disk_gb=image_data.default_disk_gb,
        size_bytes=image_data.size_bytes,
        tags=image_data.tags,
        created_by=current_user.id,
    )
    db.add(base_image)
    db.commit()
    db.refresh(base_image)
    return base_image


@router.get("/base/{image_id}", response_model=BaseImageResponse)
def get_base_image(
    image_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    """Get a specific base image."""
    base_image = db.query(BaseImage).filter(BaseImage.id == image_id).first()
    if not base_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Base image not found",
        )
    return base_image


@router.patch("/base/{image_id}", response_model=BaseImageResponse)
def update_base_image(
    image_id: UUID,
    update_data: BaseImageUpdate,
    db: DBSession,
    current_user: CurrentUser,
):
    """Update a base image."""
    base_image = db.query(BaseImage).filter(BaseImage.id == image_id).first()
    if not base_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Base image not found",
        )

    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(base_image, key, value)

    db.commit()
    db.refresh(base_image)
    return base_image


@router.delete("/base/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_base_image(
    image_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    """Delete a base image."""
    base_image = db.query(BaseImage).filter(BaseImage.id == image_id).first()
    if not base_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Base image not found",
        )

    # Check for dependent golden images
    dependent_golden = db.query(GoldenImage).filter(
        GoldenImage.base_image_id == image_id
    ).count()
    if dependent_golden > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete: {dependent_golden} golden image(s) depend on this base image",
        )

    db.delete(base_image)
    db.commit()


# ============================================================================
# Golden Images
# ============================================================================

@router.get("/golden", response_model=List[GoldenImageResponse])
def list_golden_images(
    source: Optional[str] = None,
    os_type: Optional[str] = None,
    db: DBSession = None,
    current_user: CurrentUser = None,
):
    """List all golden images in the library."""
    query = db.query(GoldenImage)

    if source:
        query = query.filter(GoldenImage.source == source)
    if os_type:
        query = query.filter(GoldenImage.os_type == os_type)

    golden_images = query.order_by(GoldenImage.created_at.desc()).all()

    # Populate base_image relationship for lineage display
    result = []
    for gi in golden_images:
        gi_dict = GoldenImageResponse.model_validate(gi).model_dump()
        if gi.base_image:
            gi_dict['base_image'] = BaseImageBrief.model_validate(gi.base_image)
        result.append(GoldenImageResponse(**gi_dict))

    return result


@router.post("/golden", response_model=GoldenImageResponse, status_code=status.HTTP_201_CREATED)
def create_golden_image(
    image_data: GoldenImageCreate,
    db: DBSession,
    current_user: CurrentUser,
):
    """Create a new golden image record (usually done automatically on first snapshot)."""
    golden_image = GoldenImage(
        name=image_data.name,
        description=image_data.description,
        source=image_data.source,
        base_image_id=image_data.base_image_id,
        os_type=image_data.os_type,
        vm_type=image_data.vm_type,
        native_arch=image_data.native_arch,
        default_cpu=image_data.default_cpu,
        default_ram_mb=image_data.default_ram_mb,
        default_disk_gb=image_data.default_disk_gb,
        display_type=image_data.display_type,
        vnc_port=image_data.vnc_port,
        tags=image_data.tags,
        created_by=current_user.id,
    )
    db.add(golden_image)
    db.commit()
    db.refresh(golden_image)
    return golden_image


@router.get("/golden/{image_id}", response_model=GoldenImageResponse)
def get_golden_image(
    image_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    """Get a specific golden image."""
    golden_image = db.query(GoldenImage).filter(GoldenImage.id == image_id).first()
    if not golden_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Golden image not found",
        )

    result = GoldenImageResponse.model_validate(golden_image).model_dump()
    if golden_image.base_image:
        result['base_image'] = BaseImageBrief.model_validate(golden_image.base_image)

    return GoldenImageResponse(**result)


@router.patch("/golden/{image_id}", response_model=GoldenImageResponse)
def update_golden_image(
    image_id: UUID,
    update_data: GoldenImageUpdate,
    db: DBSession,
    current_user: CurrentUser,
):
    """Update a golden image."""
    golden_image = db.query(GoldenImage).filter(GoldenImage.id == image_id).first()
    if not golden_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Golden image not found",
        )

    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(golden_image, key, value)

    db.commit()
    db.refresh(golden_image)
    return golden_image


@router.delete("/golden/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_golden_image(
    image_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    """Delete a golden image."""
    golden_image = db.query(GoldenImage).filter(GoldenImage.id == image_id).first()
    if not golden_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Golden image not found",
        )

    # Check for dependent snapshots
    dependent_snapshots = db.query(Snapshot).filter(
        Snapshot.golden_image_id == image_id
    ).count()
    if dependent_snapshots > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete: {dependent_snapshots} snapshot(s) depend on this golden image",
        )

    # Delete Docker image if exists
    if golden_image.docker_image_id:
        try:
            from cyroid.services.docker_service import get_docker_service
            docker = get_docker_service()
            docker.client.images.remove(golden_image.docker_image_id, force=True)
        except Exception as e:
            logger.warning(f"Failed to remove golden image Docker image: {e}")

    db.delete(golden_image)
    db.commit()


@router.post("/golden/import", response_model=GoldenImageResponse, status_code=status.HTTP_201_CREATED)
async def import_golden_image(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    os_type: str = Form(...),
    vm_type: str = Form(...),
    native_arch: str = Form("x86_64"),
    default_cpu: int = Form(2),
    default_ram_mb: int = Form(4096),
    default_disk_gb: int = Form(40),
    db: DBSession = None,
    current_user: CurrentUser = None,
):
    """Import an OVA/QCOW2/VMDK file as a golden image."""
    from cyroid.services.image_import_service import ImageImportService

    # Validate file extension
    filename = file.filename.lower()
    valid_extensions = {'.ova', '.qcow2', '.vmdk', '.vdi'}
    ext = None
    for e in valid_extensions:
        if filename.endswith(e):
            ext = e
            break

    if not ext:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format. Supported: {', '.join(valid_extensions)}",
        )

    try:
        import_service = ImageImportService()
        golden_image = await import_service.import_vm_image(
            file=file,
            name=name,
            description=description,
            os_type=os_type,
            vm_type=vm_type,
            native_arch=native_arch,
            default_cpu=default_cpu,
            default_ram_mb=default_ram_mb,
            default_disk_gb=default_disk_gb,
            user_id=current_user.id,
            db=db,
        )
        return golden_image
    except Exception as e:
        logger.error(f"Failed to import image: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import image: {str(e)}",
        )


# ============================================================================
# Snapshots (read-only from this router - create via /snapshots endpoint)
# ============================================================================

@router.get("/snapshots", response_model=List[SnapshotResponse])
def list_library_snapshots(
    os_type: Optional[str] = None,
    db: DBSession = None,
    current_user: CurrentUser = None,
):
    """List all global snapshots in the library (forks)."""
    query = db.query(Snapshot).filter(Snapshot.is_global == True)

    if os_type:
        query = query.filter(Snapshot.os_type == os_type)

    return query.order_by(Snapshot.created_at.desc()).all()


# ============================================================================
# Unified Library View
# ============================================================================

class LibraryImage(BaseModel):
    """Unified view of an image in the library."""
    id: UUID
    name: str
    category: str  # base, golden, snapshot
    image_type: Optional[str] = None  # container, iso (for base images)
    source: Optional[str] = None  # snapshot, import (for golden images)
    os_type: str
    vm_type: str
    native_arch: str
    default_cpu: int
    default_ram_mb: int
    default_disk_gb: int
    size_bytes: Optional[int] = None
    lineage: Optional[str] = None  # e.g., "From: Ubuntu 22.04"


@router.get("/library", response_model=List[LibraryImage])
def list_library(
    category: Optional[str] = None,  # base, golden, snapshot
    os_type: Optional[str] = None,
    db: DBSession = None,
    current_user: CurrentUser = None,
):
    """Get unified view of all images in the library."""
    result = []

    # Base Images
    if category is None or category == "base":
        query = db.query(BaseImage)
        if os_type:
            query = query.filter(BaseImage.os_type == os_type)
        for img in query.all():
            result.append(LibraryImage(
                id=img.id,
                name=img.name,
                category="base",
                image_type=img.image_type,
                os_type=img.os_type,
                vm_type=img.vm_type,
                native_arch=img.native_arch,
                default_cpu=img.default_cpu,
                default_ram_mb=img.default_ram_mb,
                default_disk_gb=img.default_disk_gb,
                size_bytes=img.size_bytes,
            ))

    # Golden Images
    if category is None or category == "golden":
        query = db.query(GoldenImage)
        if os_type:
            query = query.filter(GoldenImage.os_type == os_type)
        for img in query.all():
            lineage = None
            if img.base_image:
                lineage = f"From: {img.base_image.name}"
            result.append(LibraryImage(
                id=img.id,
                name=img.name,
                category="golden",
                source=img.source,
                os_type=img.os_type,
                vm_type=img.vm_type,
                native_arch=img.native_arch,
                default_cpu=img.default_cpu,
                default_ram_mb=img.default_ram_mb,
                default_disk_gb=img.default_disk_gb,
                size_bytes=img.size_bytes,
                lineage=lineage,
            ))

    # Snapshots
    if category is None or category == "snapshot":
        query = db.query(Snapshot).filter(Snapshot.is_global == True)
        if os_type:
            query = query.filter(Snapshot.os_type == os_type)
        for img in query.all():
            lineage = None
            if img.golden_image:
                lineage = f"Fork of: {img.golden_image.name}"
            result.append(LibraryImage(
                id=img.id,
                name=img.name,
                category="snapshot",
                os_type=img.os_type or "unknown",
                vm_type=img.vm_type or "unknown",
                native_arch="x86_64",  # Default
                default_cpu=img.default_cpu,
                default_ram_mb=img.default_ram_mb,
                default_disk_gb=img.default_disk_gb,
                lineage=lineage,
            ))

    return result
