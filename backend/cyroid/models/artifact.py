# backend/cyroid/models/artifact.py
from enum import Enum
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from sqlalchemy import String, Integer, Text, ForeignKey, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class ArtifactType(str, Enum):
    EXECUTABLE = "executable"
    SCRIPT = "script"
    DOCUMENT = "document"
    ARCHIVE = "archive"
    CONFIG = "config"
    OTHER = "other"


class MaliciousIndicator(str, Enum):
    SAFE = "safe"
    SUSPICIOUS = "suspicious"
    MALICIOUS = "malicious"


class PlacementStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PLACED = "placed"
    VERIFIED = "verified"
    FAILED = "failed"


class Artifact(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "artifacts"

    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    file_path: Mapped[str] = mapped_column(String(500))  # Path in MinIO
    sha256_hash: Mapped[str] = mapped_column(String(64), index=True)
    file_size: Mapped[int] = mapped_column(Integer)

    artifact_type: Mapped[ArtifactType] = mapped_column(default=ArtifactType.OTHER)
    malicious_indicator: Mapped[MaliciousIndicator] = mapped_column(default=MaliciousIndicator.SAFE)
    ttps: Mapped[List[str]] = mapped_column(JSON, default=list)  # MITRE ATT&CK IDs
    tags: Mapped[List[str]] = mapped_column(JSON, default=list)

    # Ownership
    uploaded_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    uploaded_by_user = relationship("User", back_populates="artifacts")

    # Relationships
    placements: Mapped[List["ArtifactPlacement"]] = relationship(
        "ArtifactPlacement", back_populates="artifact"
    )


class ArtifactPlacement(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "artifact_placements"

    artifact_id: Mapped[UUID] = mapped_column(ForeignKey("artifacts.id"))
    vm_id: Mapped[UUID] = mapped_column(ForeignKey("vms.id", ondelete="CASCADE"))

    target_path: Mapped[str] = mapped_column(String(500))
    placement_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[PlacementStatus] = mapped_column(default=PlacementStatus.PENDING)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    artifact = relationship("Artifact", back_populates="placements")
    vm = relationship("VM", back_populates="artifact_placements")
