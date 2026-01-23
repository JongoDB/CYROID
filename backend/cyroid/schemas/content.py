# backend/cyroid/schemas/content.py
"""Pydantic schemas for Content API."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from cyroid.models.content import ContentType


# ============ Walkthrough Schemas ============

class WalkthroughStepSchema(BaseModel):
    """A single step in a walkthrough phase."""
    id: str
    title: str
    content: str
    vm: Optional[str] = None
    hints: Optional[List[str]] = None


class WalkthroughPhaseSchema(BaseModel):
    """A phase containing multiple steps."""
    id: str
    name: str
    steps: List[WalkthroughStepSchema] = Field(default_factory=list)


class WalkthroughSchema(BaseModel):
    """Complete walkthrough structure."""
    title: str
    phases: List[WalkthroughPhaseSchema] = Field(default_factory=list)


# ============ Content Asset Schemas ============

class ContentAssetBase(BaseModel):
    filename: str
    mime_type: str
    file_size: int = 0


class ContentAssetCreate(ContentAssetBase):
    pass


class ContentAssetResponse(ContentAssetBase):
    id: UUID
    content_id: UUID
    file_path: str
    sha256_hash: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ============ Content Schemas ============

class ContentBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    content_type: ContentType = ContentType.CUSTOM
    tags: List[str] = Field(default_factory=list)


class ContentCreate(ContentBase):
    body_markdown: str = ""
    walkthrough_data: Optional[WalkthroughSchema] = None
    organization: Optional[str] = None


class ContentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    content_type: Optional[ContentType] = None
    body_markdown: Optional[str] = None
    walkthrough_data: Optional[WalkthroughSchema] = None
    tags: Optional[List[str]] = None
    organization: Optional[str] = None
    is_published: Optional[bool] = None


class ContentResponse(ContentBase):
    id: UUID
    body_markdown: str
    body_html: Optional[str] = None
    walkthrough_data: Optional[Dict[str, Any]] = None
    version: str
    is_published: bool
    organization: Optional[str] = None
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime
    assets: List[ContentAssetResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class ContentListResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    content_type: ContentType
    version: str
    tags: List[str]
    is_published: bool
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContentExport(BaseModel):
    """Content export format."""
    title: str
    description: Optional[str] = None
    content_type: ContentType
    body_markdown: str
    version: str
    tags: List[str]
    organization: Optional[str] = None
    exported_at: datetime
    export_format: str = "json"


class ContentImport(BaseModel):
    """Content import format."""
    title: str
    description: Optional[str] = None
    content_type: ContentType = ContentType.CUSTOM
    body_markdown: str
    version: Optional[str] = "1.0"
    tags: List[str] = Field(default_factory=list)
    organization: Optional[str] = None
