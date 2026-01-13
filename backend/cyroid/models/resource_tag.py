# backend/cyroid/models/resource_tag.py
"""Resource tags for ABAC visibility control."""
from uuid import UUID

from sqlalchemy import String, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class ResourceTag(Base, UUIDMixin, TimestampMixin):
    """
    Tags applied to resources (ranges, templates, artifacts) for visibility control.

    Users can only see resources that either:
    1. Have no tags (public)
    2. Have at least one tag matching the user's tags
    3. Admin users can see all resources regardless of tags
    """
    __tablename__ = "resource_tags"

    resource_type: Mapped[str] = mapped_column(String(50))  # 'range', 'template', 'artifact'
    resource_id: Mapped[UUID] = mapped_column()
    tag: Mapped[str] = mapped_column(String(100))

    __table_args__ = (
        UniqueConstraint('resource_type', 'resource_id', 'tag', name='uq_resource_tag'),
        Index('ix_resource_tags_lookup', 'resource_type', 'resource_id'),
        Index('ix_resource_tags_by_tag', 'resource_type', 'tag'),
    )
