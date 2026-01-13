# backend/cyroid/services/connection_service.py
from uuid import UUID
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
from cyroid.models.connection import Connection, ConnectionProtocol, ConnectionState
from cyroid.models.vm import VM


class ConnectionService:
    def __init__(self, db: Session):
        self.db = db

    def log_connection(
        self,
        range_id: UUID,
        src_ip: str,
        src_port: int,
        dst_ip: str,
        dst_port: int,
        protocol: ConnectionProtocol = ConnectionProtocol.TCP,
        src_vm_id: Optional[UUID] = None,
        dst_vm_id: Optional[UUID] = None
    ) -> Connection:
        """Log a new connection between VMs."""
        # Try to resolve VM IDs from IPs if not provided
        if not src_vm_id:
            src_vm = self.db.query(VM).filter(
                VM.range_id == range_id,
                VM.ip_address == src_ip
            ).first()
            if src_vm:
                src_vm_id = src_vm.id

        if not dst_vm_id:
            dst_vm = self.db.query(VM).filter(
                VM.range_id == range_id,
                VM.ip_address == dst_ip
            ).first()
            if dst_vm:
                dst_vm_id = dst_vm.id

        connection = Connection(
            range_id=range_id,
            src_vm_id=src_vm_id,
            src_ip=src_ip,
            src_port=src_port,
            dst_vm_id=dst_vm_id,
            dst_ip=dst_ip,
            dst_port=dst_port,
            protocol=protocol,
            state=ConnectionState.ESTABLISHED
        )
        self.db.add(connection)
        self.db.commit()
        self.db.refresh(connection)
        return connection

    def close_connection(
        self,
        connection_id: UUID,
        state: ConnectionState = ConnectionState.CLOSED,
        bytes_sent: int = 0,
        bytes_received: int = 0
    ) -> Optional[Connection]:
        """Mark a connection as closed."""
        connection = self.db.query(Connection).filter(Connection.id == connection_id).first()
        if not connection:
            return None

        connection.state = state
        connection.ended_at = datetime.utcnow()
        connection.bytes_sent = bytes_sent
        connection.bytes_received = bytes_received
        self.db.commit()
        self.db.refresh(connection)
        return connection

    def get_connections(
        self,
        range_id: UUID,
        limit: int = 100,
        offset: int = 0,
        active_only: bool = False
    ) -> tuple[List[Connection], int]:
        """Get connections for a range."""
        query = self.db.query(Connection).filter(Connection.range_id == range_id)

        if active_only:
            query = query.filter(Connection.state == ConnectionState.ESTABLISHED)

        total = query.count()
        connections = query.order_by(desc(Connection.started_at)).offset(offset).limit(limit).all()

        return connections, total

    def get_vm_connections(
        self,
        vm_id: UUID,
        direction: str = "both",
        limit: int = 50
    ) -> List[Connection]:
        """Get connections for a specific VM."""
        if direction == "outgoing":
            query = self.db.query(Connection).filter(Connection.src_vm_id == vm_id)
        elif direction == "incoming":
            query = self.db.query(Connection).filter(Connection.dst_vm_id == vm_id)
        else:
            query = self.db.query(Connection).filter(
                (Connection.src_vm_id == vm_id) | (Connection.dst_vm_id == vm_id)
            )

        return query.order_by(desc(Connection.started_at)).limit(limit).all()
