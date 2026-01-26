# backend/cyroid/models/content.py
"""Content models for training materials (MSELs, student guides, curricula)."""
from enum import Enum
from typing import List, Optional
from uuid import UUID

from sqlalchemy import String, Text, Boolean, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class ContentType(str, Enum):
    """Types of training content."""
    STUDENT_GUIDE = "student_guide"
    MSEL = "msel"
    CURRICULUM = "curriculum"
    INSTRUCTOR_NOTES = "instructor_notes"
    REFERENCE_MATERIAL = "reference_material"
    CUSTOM = "custom"


class Content(Base, UUIDMixin, TimestampMixin):
    """Training content that can be attached to events."""
    __tablename__ = "content"

    # Basic info
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_type: Mapped[ContentType] = mapped_column(default=ContentType.CUSTOM)

    # Content storage
    body_markdown: Mapped[str] = mapped_column(Text, default="")
    body_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Cached rendered HTML

    # Structured walkthrough data (for student_guide type)
    # Schema: {"title": str, "phases": [{"id": str, "name": str, "steps": [{"id": str, "title": str, "vm": str?, "hints": str[]?, "content": str}]}]}
    walkthrough_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Metadata
    version: Mapped[str] = mapped_column(String(20), default="1.0")
    tags: Mapped[List[str]] = mapped_column(JSON, default=list)

    # Ownership
    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    organization: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Publishing
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)

    # Source tracking - if content was auto-generated from a range deployment
    # When the source range is deleted, this content should also be deleted
    source_range_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("ranges.id", ondelete="SET NULL"),
        nullable=True
    )

    # Relationships
    created_by_user = relationship("User", foreign_keys=[created_by_id])
    source_range = relationship("Range", foreign_keys=[source_range_id])
    assets = relationship("ContentAsset", back_populates="content", cascade="all, delete-orphan")


class ContentAsset(Base, UUIDMixin, TimestampMixin):
    """Images and files embedded in content."""
    __tablename__ = "content_assets"

    content_id: Mapped[UUID] = mapped_column(ForeignKey("content.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))  # MinIO path
    mime_type: Mapped[str] = mapped_column(String(100))
    file_size: Mapped[int] = mapped_column(default=0)
    sha256_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Relationship
    content = relationship("Content", back_populates="assets")
