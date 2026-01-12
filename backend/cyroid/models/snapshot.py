# backend/cyroid/models/snapshot.py
from typing import Optional
from uuid import UUID
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class Snapshot(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "snapshots"

    vm_id: Mapped[UUID] = mapped_column(ForeignKey("vms.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Docker image ID (snapshot stored as image)
    docker_image_id: Mapped[Optional[str]] = mapped_column(String(64))

    # Relationships
    vm = relationship("VM", back_populates="snapshots")
