# backend/cyroid/models/vm_network.py
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID
from sqlalchemy import String, ForeignKey, Boolean, UniqueConstraint, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from cyroid.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from cyroid.models.vm import VM
    from cyroid.models.network import Network


class VMNetwork(Base, UUIDMixin):
    """Junction table for VM-to-Network many-to-many relationship.

    Each row represents a network interface on a VM, with its IP address
    in that network's subnet. One interface per VM is marked as primary.
    """
    __tablename__ = "vm_networks"

    vm_id: Mapped[UUID] = mapped_column(
        ForeignKey("vms.id", ondelete="CASCADE"),
        nullable=False
    )
    network_id: Mapped[UUID] = mapped_column(
        ForeignKey("networks.id", ondelete="CASCADE"),
        nullable=False
    )
    ip_address: Mapped[str] = mapped_column(String(15), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    vm: Mapped["VM"] = relationship("VM", back_populates="network_interfaces")
    network: Mapped["Network"] = relationship("Network", back_populates="vm_interfaces")

    __table_args__ = (
        # VM can only connect to a network once
        UniqueConstraint('vm_id', 'network_id', name='uq_vm_network'),
        # No duplicate IPs in the same network
        UniqueConstraint('network_id', 'ip_address', name='uq_network_ip'),
    )
