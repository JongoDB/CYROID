# backend/cyroid/models/user.py
from enum import Enum
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class UserRole(str, Enum):
    ADMIN = "admin"
    ENGINEER = "engineer"
    FACILITATOR = "facilitator"
    EVALUATOR = "evaluator"


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(default=UserRole.ENGINEER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    templates = relationship("VMTemplate", back_populates="created_by_user")
    ranges = relationship("Range", back_populates="created_by_user")
    artifacts = relationship("Artifact", back_populates="uploaded_by_user")
