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
# Sync from Cache
# ============================================================================

class SyncResult(BaseModel):
    """Result of syncing cache to library."""
    docker_images_synced: int
    windows_isos_synced: int
    linux_isos_synced: int
    custom_isos_synced: int
    total_synced: int


@router.post("/sync-from-cache", response_model=SyncResult)
def sync_from_cache(
    db: DBSession,
    current_user: CurrentUser,
):
    """
    Sync cached images to the Image Library.

    Creates BaseImage records for all cached Docker images and ISOs
    that don't already have corresponding records.
    """
    from cyroid.services.docker_service import get_docker_service
    from cyroid.config import get_settings
    import os

    docker = get_docker_service()
    settings = get_settings()

    docker_synced = 0
    windows_synced = 0
    linux_synced = 0
    custom_synced = 0

    # Sync Docker images
    cached_images = docker.list_cached_images()
    for img in cached_images:
        # list_cached_images returns {"tags": [...], "id": ..., "size_bytes": ...}
        tags = img.get("tags", [])
        if not tags:
            continue

        # Use first tag as the primary identifier
        image_tag = tags[0]

        # Check if BaseImage already exists for any of the tags
        existing = db.query(BaseImage).filter(
            BaseImage.docker_image_tag == image_tag
        ).first()

        if not existing:
            # Parse image name for metadata
            image_name = image_tag.split("/")[-1].split(":")[0]

            # Determine OS type from image name
            os_type = "linux"  # default
            if "windows" in image_tag.lower() or "dockur" in image_tag.lower():
                os_type = "windows"
            elif any(net in image_tag.lower() for net in ["openwrt", "vyos", "pfsense", "opnsense"]):
                os_type = "network"

            # Determine VM type
            vm_type = "container"
            if "dockur/windows" in image_tag.lower():
                vm_type = "windows_vm"

            base_image = BaseImage(
                name=image_name,
                description=f"Container image: {image_tag}",
                image_type="container",
                docker_image_id=img.get("id"),
                docker_image_tag=image_tag,
                os_type=os_type,
                vm_type=vm_type,
                native_arch="x86_64",
                default_cpu=2,
                default_ram_mb=4096 if os_type == "windows" else 2048,
                default_disk_gb=64 if os_type == "windows" else 20,
                size_bytes=img.get("size_bytes"),
                is_global=True,
            )
            db.add(base_image)
            docker_synced += 1

    # Sync Windows ISOs
    # get_windows_iso_cache_status returns {"isos": [{"filename": ..., "path": ..., "size_bytes": ...}]}
    iso_cache = docker.get_windows_iso_cache_status()
    for iso in iso_cache.get("isos", []):
        iso_path = iso.get("path")
        if not iso_path:
            continue

        # Check if BaseImage already exists for this ISO path
        existing = db.query(BaseImage).filter(
            BaseImage.iso_path == iso_path
        ).first()

        if not existing:
            # Extract version from filename (e.g., "win11x64.iso" -> "11")
            filename = iso.get("filename", "")
            version = "Unknown"
            name = filename.replace('.iso', '')

            # Try to extract Windows version from common filename patterns
            import re
            version_match = re.search(r'win(\d+)', filename.lower())
            if version_match:
                version = version_match.group(1)
                name = f"Windows {version}"
            elif "windows" in filename.lower():
                name = filename.replace('.iso', '').replace('-', ' ').replace('_', ' ')

            base_image = BaseImage(
                name=name,
                description=f"Windows ISO: {filename}",
                image_type="iso",
                iso_path=iso_path,
                iso_source="windows",
                iso_version=version,
                os_type="windows",
                vm_type="windows_vm",
                native_arch="x86_64",
                default_cpu=2,
                default_ram_mb=4096,
                default_disk_gb=64,
                size_bytes=iso.get("size_bytes"),
                is_global=True,
            )
            db.add(base_image)
            windows_synced += 1

    # Sync Linux ISOs (directory is "linux-isos" per docker_service.py)
    linux_iso_dir = os.path.join(settings.iso_cache_dir, 'linux-isos')
    if os.path.exists(linux_iso_dir):
        for filename in os.listdir(linux_iso_dir):
            if filename.endswith('.iso') or filename.endswith('.img') or filename.endswith('.qcow2'):
                iso_path = os.path.join(linux_iso_dir, filename)

                # Check if BaseImage already exists
                existing = db.query(BaseImage).filter(
                    BaseImage.iso_path == iso_path
                ).first()

                if not existing:
                    # Extract name from filename
                    name = filename.rsplit('.', 1)[0].replace('-', ' ').replace('_', ' ')
                    base_image = BaseImage(
                        name=name,
                        description=f"Linux ISO: {filename}",
                        image_type="iso",
                        iso_path=iso_path,
                        iso_source="linux",
                        os_type="linux",
                        vm_type="linux_vm",
                        native_arch="x86_64",
                        default_cpu=2,
                        default_ram_mb=2048,
                        default_disk_gb=20,
                        size_bytes=os.path.getsize(iso_path),
                        is_global=True,
                    )
                    db.add(base_image)
                    linux_synced += 1

    # Sync Custom ISOs (directory is "custom-isos")
    custom_iso_dir = os.path.join(settings.iso_cache_dir, 'custom-isos')
    if os.path.exists(custom_iso_dir):
        for filename in os.listdir(custom_iso_dir):
            if filename.endswith('.iso') or filename.endswith('.img'):
                iso_path = os.path.join(custom_iso_dir, filename)

                # Check if BaseImage already exists
                existing = db.query(BaseImage).filter(
                    BaseImage.iso_path == iso_path
                ).first()

                if not existing:
                    name = filename.rsplit('.', 1)[0].replace('-', ' ').replace('_', ' ')
                    base_image = BaseImage(
                        name=name,
                        description=f"Custom ISO: {filename}",
                        image_type="iso",
                        iso_path=iso_path,
                        iso_source="custom",
                        os_type="custom",
                        vm_type="linux_vm",  # Default, can be updated
                        native_arch="x86_64",
                        default_cpu=2,
                        default_ram_mb=2048,
                        default_disk_gb=20,
                        size_bytes=os.path.getsize(iso_path),
                        is_global=True,
                    )
                    db.add(base_image)
                    custom_synced += 1

    db.commit()

    total = docker_synced + windows_synced + linux_synced + custom_synced
    logger.info(f"Synced {total} images from cache to library")

    return SyncResult(
        docker_images_synced=docker_synced,
        windows_isos_synced=windows_synced,
        linux_isos_synced=linux_synced,
        custom_isos_synced=custom_synced,
        total_synced=total,
    )


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
