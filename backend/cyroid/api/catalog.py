# backend/cyroid/api/catalog.py
"""Catalog API endpoints for browsing, installing, and managing catalog sources."""
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.orm import Session

from cyroid.api.deps import AdminUser, CurrentUser, DBSession
from cyroid.models.catalog import (
    CatalogInstalledItem,
    CatalogItemType,
    CatalogSource,
)
from cyroid.schemas.catalog import (
    CatalogInstalledItemResponse,
    CatalogInstallRequest,
    CatalogItemDetail,
    CatalogItemSummary,
    CatalogSourceCreate,
    CatalogSourceResponse,
    CatalogSourceUpdate,
)
from cyroid.services.catalog_service import CatalogService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/catalog", tags=["catalog"])


# ============ Helpers ============

def _get_service(db: Session) -> CatalogService:
    """Create a CatalogService instance."""
    return CatalogService(db)


def _get_source_or_404(source_id: UUID, db: Session) -> CatalogSource:
    """Fetch a catalog source by ID or raise 404."""
    source = db.query(CatalogSource).filter(CatalogSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Catalog source not found")
    return source


def _source_to_response(source: CatalogSource) -> CatalogSourceResponse:
    """Convert a CatalogSource model to a CatalogSourceResponse schema."""
    return CatalogSourceResponse(
        id=source.id,
        name=source.name,
        source_type=source.source_type,
        url=source.url,
        branch=source.branch,
        enabled=source.enabled,
        sync_status=source.sync_status,
        error_message=source.error_message,
        item_count=source.item_count,
        last_synced=source.updated_at,
        created_by=source.created_by,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


def _installed_to_response(item: CatalogInstalledItem) -> CatalogInstalledItemResponse:
    """Convert a CatalogInstalledItem model to a CatalogInstalledItemResponse schema."""
    return CatalogInstalledItemResponse(
        id=item.id,
        catalog_source_id=item.catalog_source_id,
        catalog_item_id=item.catalog_item_id,
        item_type=item.item_type,
        item_name=item.item_name,
        installed_version=item.installed_version,
        installed_checksum=item.installed_checksum,
        local_resource_id=item.local_resource_id,
        installed_by=item.installed_by,
        installed_at=item.created_at,
        update_available=False,
    )


# ============ Source Endpoints ============

@router.get("/sources", response_model=List[CatalogSourceResponse])
def list_sources(db: DBSession, current_user: CurrentUser):
    """List all catalog sources."""
    sources = db.query(CatalogSource).all()
    return [_source_to_response(s) for s in sources]


@router.post("/sources", response_model=CatalogSourceResponse, status_code=status.HTTP_201_CREATED)
def create_source(data: CatalogSourceCreate, db: DBSession, admin_user: AdminUser):
    """Create a new catalog source (admin only)."""
    source = CatalogSource(
        name=data.name,
        source_type=data.source_type,
        url=data.url,
        branch=data.branch,
        enabled=data.enabled,
        created_by=admin_user.id,
    )
    db.add(source)
    db.commit()
    db.refresh(source)

    logger.info(f"Created catalog source '{source.name}' (id={source.id})")
    return _source_to_response(source)


@router.put("/sources/{source_id}", response_model=CatalogSourceResponse)
def update_source(source_id: UUID, data: CatalogSourceUpdate, db: DBSession, admin_user: AdminUser):
    """Update a catalog source (admin only)."""
    source = _get_source_or_404(source_id, db)

    if data.name is not None:
        source.name = data.name
    if data.url is not None:
        source.url = data.url
    if data.branch is not None:
        source.branch = data.branch
    if data.enabled is not None:
        source.enabled = data.enabled

    db.commit()
    db.refresh(source)

    logger.info(f"Updated catalog source '{source.name}' (id={source.id})")
    return _source_to_response(source)


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(source_id: UUID, db: DBSession, admin_user: AdminUser):
    """Delete a catalog source and its cached data (admin only)."""
    source = _get_source_or_404(source_id, db)

    service = _get_service(db)
    service.delete_source_data(source)

    db.delete(source)
    db.commit()

    logger.info(f"Deleted catalog source '{source.name}' (id={source_id})")


@router.post("/sources/{source_id}/sync", response_model=CatalogSourceResponse)
def sync_source(source_id: UUID, db: DBSession, admin_user: AdminUser):
    """Trigger a sync for a catalog source (admin only)."""
    source = _get_source_or_404(source_id, db)

    service = _get_service(db)
    try:
        service.sync_source(source)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Sync failed: {str(e)}",
        )

    db.refresh(source)
    return _source_to_response(source)


# ============ Browsing Endpoints ============

@router.get("/items", response_model=List[CatalogItemSummary])
def list_items(
    db: DBSession,
    current_user: CurrentUser,
    source_id: Optional[UUID] = Query(None, description="Filter by catalog source"),
    item_type: Optional[CatalogItemType] = Query(None, description="Filter by item type"),
    search: Optional[str] = Query(None, description="Search text in name and description"),
    tags: Optional[str] = Query(None, description="Comma-separated tags to filter by"),
):
    """Browse catalog items across all enabled sources with optional filters."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None

    if source_id:
        sources = [_get_source_or_404(source_id, db)]
    else:
        sources = db.query(CatalogSource).filter(CatalogSource.enabled == True).all()

    service = _get_service(db)
    all_items: List[CatalogItemSummary] = []

    for source in sources:
        try:
            items = service.list_items(
                source=source,
                item_type=item_type,
                search=search,
                tags=tag_list,
            )
            all_items.extend(items)
        except FileNotFoundError:
            logger.warning(f"No index found for source '{source.name}', skipping")
        except Exception as e:
            logger.error(f"Error browsing source '{source.name}': {e}")

    return all_items


@router.get("/items/{source_id}/{item_id}", response_model=CatalogItemDetail)
def get_item_detail(source_id: UUID, item_id: str, db: DBSession, current_user: CurrentUser):
    """Get full detail for a specific catalog item including README content."""
    source = _get_source_or_404(source_id, db)

    service = _get_service(db)
    try:
        detail = service.get_item_detail(source, item_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Catalog index not found for this source")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading item detail: {str(e)}")

    if not detail:
        raise HTTPException(status_code=404, detail="Catalog item not found")

    return detail


# ============ Installation Endpoints ============

@router.post("/items/{item_id}/install", response_model=CatalogInstalledItemResponse)
def install_item(item_id: str, data: CatalogInstallRequest, db: DBSession, admin_user: AdminUser):
    """Install a catalog item into the local CYROID instance (admin only)."""
    source = _get_source_or_404(data.source_id, db)

    service = _get_service(db)
    try:
        installed = service.install_item(
            source=source,
            item_id=item_id,
            user_id=admin_user.id,
            build_images=data.build_images,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Install failed for item '{item_id}': {e}")
        raise HTTPException(status_code=500, detail=f"Installation failed: {str(e)}")

    return _installed_to_response(installed)


@router.get("/installed", response_model=List[CatalogInstalledItemResponse])
def list_installed(db: DBSession, current_user: CurrentUser):
    """List all installed catalog items."""
    items = db.query(CatalogInstalledItem).all()
    return [_installed_to_response(i) for i in items]


@router.delete("/installed/{installed_id}", status_code=status.HTTP_204_NO_CONTENT)
def uninstall_item(installed_id: UUID, db: DBSession, admin_user: AdminUser):
    """Uninstall a previously installed catalog item (admin only)."""
    installed = db.query(CatalogInstalledItem).filter(
        CatalogInstalledItem.id == installed_id
    ).first()
    if not installed:
        raise HTTPException(status_code=404, detail="Installed item not found")

    service = _get_service(db)
    try:
        service.uninstall_item(installed)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Uninstall failed for item '{installed.item_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Uninstall failed: {str(e)}")
