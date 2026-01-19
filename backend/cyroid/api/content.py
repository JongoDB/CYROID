# backend/cyroid/api/content.py
"""Content API endpoints for training materials."""
import hashlib
import logging
import markdown
from datetime import datetime, timezone
from typing import Annotated, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from fastapi.responses import Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from cyroid.api.deps import get_current_user, get_db
from cyroid.config import get_settings
from cyroid.models.user import User
from cyroid.models.content import Content, ContentAsset, ContentType
from cyroid.schemas.content import (
    ContentCreate,
    ContentUpdate,
    ContentResponse,
    ContentListResponse,
    ContentAssetResponse,
    ContentExport,
    ContentImport,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/content", tags=["content"])

# Type aliases
DBSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def render_markdown_to_html(md_content: str) -> str:
    """Render markdown to HTML with extensions."""
    extensions = [
        'markdown.extensions.fenced_code',
        'markdown.extensions.tables',
        'markdown.extensions.codehilite',
        'markdown.extensions.toc',
    ]
    return markdown.markdown(md_content, extensions=extensions)


# ============ Content CRUD ============

@router.post("", response_model=ContentResponse, status_code=status.HTTP_201_CREATED)
def create_content(
    data: ContentCreate,
    db: DBSession,
    current_user: CurrentUser,
):
    """Create new content."""
    # Render HTML from markdown
    body_html = render_markdown_to_html(data.body_markdown) if data.body_markdown else None

    content = Content(
        title=data.title,
        description=data.description,
        content_type=data.content_type,
        body_markdown=data.body_markdown,
        body_html=body_html,
        tags=data.tags,
        organization=data.organization,
        created_by_id=current_user.id,
    )

    db.add(content)
    db.commit()
    db.refresh(content)

    logger.info(f"Content created: {content.title} by {current_user.username}")
    return content


@router.get("", response_model=List[ContentListResponse])
def list_content(
    db: DBSession,
    current_user: CurrentUser,
    content_type: Optional[ContentType] = Query(None, description="Filter by content type"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    search: Optional[str] = Query(None, description="Search in title and description"),
    published_only: bool = Query(False, description="Only show published content"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List all content with optional filters."""
    query = db.query(Content)

    # Filter by content type
    if content_type:
        query = query.filter(Content.content_type == content_type)

    # Filter by tag
    if tag:
        query = query.filter(Content.tags.contains([tag]))

    # Search
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Content.title.ilike(search_pattern),
                Content.description.ilike(search_pattern),
            )
        )

    # Published filter
    if published_only:
        query = query.filter(Content.is_published == True)

    # Order and paginate
    query = query.order_by(Content.updated_at.desc())
    total = query.count()
    content_list = query.offset(offset).limit(limit).all()

    return content_list


@router.get("/{content_id}", response_model=ContentResponse)
def get_content(
    content_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    """Get content by ID."""
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    return content


@router.put("/{content_id}", response_model=ContentResponse)
def update_content(
    content_id: UUID,
    data: ContentUpdate,
    db: DBSession,
    current_user: CurrentUser,
):
    """Update content."""
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Check permission (owner or admin)
    if content.created_by_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to edit this content")

    # Update fields
    update_data = data.model_dump(exclude_unset=True)

    # Re-render HTML if markdown changed
    if "body_markdown" in update_data:
        update_data["body_html"] = render_markdown_to_html(update_data["body_markdown"])

    for field, value in update_data.items():
        setattr(content, field, value)

    db.commit()
    db.refresh(content)

    logger.info(f"Content updated: {content.title} by {current_user.username}")
    return content


@router.delete("/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_content(
    content_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    """Delete content."""
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Check permission (owner or admin)
    if content.created_by_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to delete this content")

    db.delete(content)
    db.commit()

    logger.info(f"Content deleted: {content.title} by {current_user.username}")


# ============ Publishing ============

@router.post("/{content_id}/publish", response_model=ContentResponse)
def publish_content(
    content_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    """Publish content."""
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    if content.created_by_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    content.is_published = True
    db.commit()
    db.refresh(content)

    return content


@router.post("/{content_id}/unpublish", response_model=ContentResponse)
def unpublish_content(
    content_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    """Unpublish content."""
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    if content.created_by_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    content.is_published = False
    db.commit()
    db.refresh(content)

    return content


# ============ Versioning ============

@router.post("/{content_id}/version", response_model=ContentResponse)
def create_content_version(
    content_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    new_version: str = Query(..., description="New version string (e.g., '1.1', '2.0')"),
):
    """Create a new version of content (duplicates with new version)."""
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Create new content as a copy
    new_content = Content(
        title=content.title,
        description=content.description,
        content_type=content.content_type,
        body_markdown=content.body_markdown,
        body_html=content.body_html,
        version=new_version,
        tags=content.tags.copy() if content.tags else [],
        organization=content.organization,
        created_by_id=current_user.id,
        is_published=False,
    )

    db.add(new_content)
    db.commit()
    db.refresh(new_content)

    logger.info(f"Content version created: {new_content.title} v{new_version}")
    return new_content


# ============ Export/Import ============

@router.get("/{content_id}/export")
def export_content(
    content_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    format: str = Query("json", description="Export format: json, md, html"),
):
    """Export content in various formats."""
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    if format == "md":
        # Return raw markdown
        return Response(
            content=content.body_markdown,
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{content.title}.md"'},
        )
    elif format == "html":
        # Return rendered HTML
        html = content.body_html or render_markdown_to_html(content.body_markdown)
        full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{content.title}</title>
    <style>
        body {{ font-family: system-ui, sans-serif; max-width: 800px; margin: 0 auto; padding: 2rem; }}
        pre {{ background: #f4f4f4; padding: 1rem; overflow-x: auto; }}
        code {{ background: #f4f4f4; padding: 0.2rem 0.4rem; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 0.5rem; text-align: left; }}
    </style>
</head>
<body>
<h1>{content.title}</h1>
{html}
</body>
</html>"""
        return Response(
            content=full_html,
            media_type="text/html",
            headers={"Content-Disposition": f'attachment; filename="{content.title}.html"'},
        )
    else:
        # Return JSON with metadata
        export_data = ContentExport(
            title=content.title,
            description=content.description,
            content_type=content.content_type,
            body_markdown=content.body_markdown,
            version=content.version,
            tags=content.tags or [],
            organization=content.organization,
            exported_at=datetime.now(timezone.utc),
        )
        return export_data


@router.post("/import", response_model=ContentResponse)
def import_content(
    data: ContentImport,
    db: DBSession,
    current_user: CurrentUser,
):
    """Import content from JSON."""
    body_html = render_markdown_to_html(data.body_markdown) if data.body_markdown else None

    content = Content(
        title=data.title,
        description=data.description,
        content_type=data.content_type,
        body_markdown=data.body_markdown,
        body_html=body_html,
        version=data.version or "1.0",
        tags=data.tags or [],
        organization=data.organization,
        created_by_id=current_user.id,
    )

    db.add(content)
    db.commit()
    db.refresh(content)

    logger.info(f"Content imported: {content.title} by {current_user.username}")
    return content


# ============ Assets ============

@router.post("/{content_id}/assets", response_model=ContentAssetResponse)
async def upload_asset(
    content_id: UUID,
    file: UploadFile = File(...),
    db: DBSession = None,
    current_user: CurrentUser = None,
):
    """Upload an asset (image) to content."""
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    if content.created_by_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Validate file type
    allowed_types = ["image/png", "image/jpeg", "image/gif", "image/webp", "image/svg+xml"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"File type not allowed. Allowed: {allowed_types}")

    # Read file and calculate hash
    file_content = await file.read()
    file_hash = hashlib.sha256(file_content).hexdigest()
    file_size = len(file_content)

    # Store in MinIO
    settings = get_settings()
    from minio import Minio

    minio_client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )

    bucket_name = "cyroid-content"
    # Ensure bucket exists
    if not minio_client.bucket_exists(bucket_name):
        minio_client.make_bucket(bucket_name)

    file_path = f"{content_id}/{file_hash[:8]}_{file.filename}"

    from io import BytesIO
    minio_client.put_object(
        bucket_name,
        file_path,
        BytesIO(file_content),
        file_size,
        content_type=file.content_type,
    )

    # Create database record
    asset = ContentAsset(
        content_id=content_id,
        filename=file.filename,
        file_path=f"{bucket_name}/{file_path}",
        mime_type=file.content_type,
        file_size=file_size,
        sha256_hash=file_hash,
    )

    db.add(asset)
    db.commit()
    db.refresh(asset)

    logger.info(f"Asset uploaded: {file.filename} to content {content_id}")
    return asset


@router.delete("/{content_id}/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(
    content_id: UUID,
    asset_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    """Delete an asset from content."""
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    if content.created_by_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    asset = db.query(ContentAsset).filter(
        ContentAsset.id == asset_id,
        ContentAsset.content_id == content_id,
    ).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Delete from MinIO
    try:
        settings = get_settings()
        from minio import Minio

        minio_client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

        parts = asset.file_path.split("/", 1)
        if len(parts) == 2:
            bucket_name, object_name = parts
            minio_client.remove_object(bucket_name, object_name)
    except Exception as e:
        logger.warning(f"Failed to delete asset from MinIO: {e}")

    db.delete(asset)
    db.commit()

    logger.info(f"Asset deleted: {asset.filename} from content {content_id}")


# ============ Content Types ============

@router.get("/types/available")
def get_content_types():
    """Get available content types."""
    return [
        {"value": ct.value, "label": ct.value.replace("_", " ").title()}
        for ct in ContentType
    ]
