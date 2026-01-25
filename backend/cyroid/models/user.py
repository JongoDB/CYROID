# backend/cyroid/models/user.py
from enum import Enum
from typing import List
from uuid import UUID

from sqlalchemy import String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


# Keep for backwards compatibility during migration
class UserRole(str, Enum):
    ADMIN = "admin"
    ENGINEER = "engineer"
    STUDENT = "student"  # Renamed from FACILITATOR
    EVALUATOR = "evaluator"


# Available roles as constants (for validation)
AVAILABLE_ROLES = ["admin", "engineer", "student", "evaluator"]


class UserAttribute(Base, UUIDMixin, TimestampMixin):
    """User attributes for ABAC - stores roles and tags."""
    __tablename__ = "user_attributes"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    attribute_type: Mapped[str] = mapped_column(String(50))  # 'role' or 'tag'
    attribute_value: Mapped[str] = mapped_column(String(100))

    user = relationship("User", back_populates="attributes")

    __table_args__ = (
        UniqueConstraint('user_id', 'attribute_type', 'attribute_value', name='uq_user_attribute'),
    )


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    # Keep role column for backwards compatibility (will be removed in future migration)
    role: Mapped[UserRole] = mapped_column(default=UserRole.ENGINEER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Password reset flag - when True, user must change password on next login
    password_reset_required: Mapped[bool] = mapped_column(Boolean, default=False)
    # Registration approval - new users need admin approval (first user auto-approved)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)

    # ABAC attributes relationship
    attributes = relationship("UserAttribute", back_populates="user", cascade="all, delete-orphan")

    # Existing relationships
    ranges = relationship("Range", back_populates="created_by_user", foreign_keys="Range.created_by")
    artifacts = relationship("Artifact", back_populates="uploaded_by_user")
    # Image Library relationships
    base_images = relationship("BaseImage", back_populates="created_by_user")
    golden_images = relationship("GoldenImage", back_populates="created_by_user")

    @property
    def roles(self) -> List[str]:
        """Get all roles from attributes."""
        return [a.attribute_value for a in self.attributes if a.attribute_type == 'role']

    @property
    def tags(self) -> List[str]:
        """Get all tags from attributes."""
        return [a.attribute_value for a in self.attributes if a.attribute_type == 'tag']

    @property
    def is_admin(self) -> bool:
        """Check if user has admin role."""
        return 'admin' in self.roles

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        return role in self.roles

    def has_any_role(self, *roles: str) -> bool:
        """Check if user has any of the specified roles."""
        return any(r in self.roles for r in roles)

    def has_tag(self, tag: str) -> bool:
        """Check if user has a specific tag."""
        return tag in self.tags

    def has_any_tag(self, *tags: str) -> bool:
        """Check if user has any of the specified tags."""
        return any(t in self.tags for t in tags)
