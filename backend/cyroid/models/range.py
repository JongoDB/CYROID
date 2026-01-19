# backend/cyroid/models/range.py
from datetime import datetime
from enum import Enum
from typing import Optional, List
from uuid import UUID
from sqlalchemy import String, Text, ForeignKey, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class RangeStatus(str, Enum):
    DRAFT = "draft"
    DEPLOYING = "deploying"
    RUNNING = "running"
    STOPPED = "stopped"
    ARCHIVED = "archived"
    ERROR = "error"


class Range(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ranges"

    name: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[RangeStatus] = mapped_column(default=RangeStatus.DRAFT)

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    # Lifecycle timestamps
    deployed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    stopped_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # DinD (Docker-in-Docker) container tracking for network isolation
    dind_container_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )
    dind_container_name: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )
    dind_mgmt_ip: Mapped[Optional[str]] = mapped_column(
        String(45), nullable=True  # IPv4 or IPv6
    )
    dind_docker_url: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True
    )

    # VNC proxy port mappings (JSON: {vm_id: {proxy_host, proxy_port, original_port}})
    vnc_proxy_mappings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Ownership
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_by_user = relationship("User", back_populates="ranges")

    # Relationships
    networks: Mapped[List["Network"]] = relationship(
        "Network", back_populates="range", cascade="all, delete-orphan"
    )
    vms: Mapped[List["VM"]] = relationship(
        "VM", back_populates="range", cascade="all, delete-orphan"
    )
    event_logs: Mapped[List["EventLog"]] = relationship(
        "EventLog", back_populates="range", cascade="all, delete-orphan"
    )
    connections: Mapped[List["Connection"]] = relationship(
        "Connection", back_populates="range", cascade="all, delete-orphan"
    )
    msel: Mapped[Optional["MSEL"]] = relationship(
        "MSEL", back_populates="range", uselist=False, cascade="all, delete-orphan"
    )
    router: Mapped[Optional["RangeRouter"]] = relationship(
        "RangeRouter", back_populates="range", uselist=False, cascade="all, delete-orphan"
    )
