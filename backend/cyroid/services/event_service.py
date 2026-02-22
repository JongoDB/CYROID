# backend/cyroid/services/event_service.py
import asyncio
import json
import logging
from uuid import UUID
from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from cyroid.models.event_log import EventLog, EventType

logger = logging.getLogger(__name__)


class EventService:
    def __init__(self, db: Session):
        self.db = db

    def log_event(
        self,
        range_id: UUID,
        event_type: EventType,
        message: str,
        vm_id: Optional[UUID] = None,
        network_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        extra_data: Optional[str] = None,
        broadcast: bool = True
    ) -> EventLog:
        """
        Log an event to the database and optionally broadcast to WebSocket clients.

        Args:
            range_id: The range this event belongs to
            event_type: Type of event
            message: Human-readable message
            vm_id: Optional VM this event relates to
            network_id: Optional network this event relates to
            user_id: Optional user who triggered this event
            extra_data: Optional JSON string with additional data
            broadcast: Whether to broadcast to WebSocket clients (default True)

        Returns:
            The created EventLog instance
        """
        event = EventLog(
            range_id=range_id,
            vm_id=vm_id,
            network_id=network_id,
            user_id=user_id,
            event_type=event_type,
            message=message,
            extra_data=extra_data
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)

        # Broadcast to WebSocket clients
        if broadcast:
            self._broadcast_event(event)

        return event

    def _broadcast_event(self, event: EventLog) -> None:
        """Broadcast an event to WebSocket clients via Redis pub/sub."""
        try:
            from cyroid.services.event_broadcaster import broadcast_event

            # Parse extra_data if present
            data = None
            if event.extra_data:
                try:
                    data = json.loads(event.extra_data)
                except json.JSONDecodeError:
                    data = {"raw": event.extra_data}

            # Add event metadata to data
            if data is None:
                data = {}
            data["event_id"] = str(event.id)

            # Run async broadcast in background
            # Use asyncio.create_task if we're in an async context
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(broadcast_event(
                    event_type=event.event_type.value,
                    message=event.message,
                    range_id=event.range_id,
                    vm_id=event.vm_id,
                    network_id=event.network_id,
                    data=data
                ))
            except RuntimeError:
                # No running event loop (sync endpoint in thread pool).
                # Use a fresh Redis connection to avoid stale event loop issues
                # with the singleton broadcaster's async Redis client.
                self._broadcast_sync(event, data)

        except Exception as e:
            # Don't fail the event logging if broadcast fails
            logger.warning(f"Failed to broadcast event: {e}")

    def _broadcast_sync(self, event: EventLog, data: dict) -> None:
        """Broadcast event using synchronous Redis (for sync endpoint contexts)."""
        try:
            import redis as sync_redis
            from cyroid.services.event_broadcaster import (
                EVENTS_CHANNEL, RANGE_CHANNEL_PREFIX, VM_CHANNEL_PREFIX, RealtimeEvent
            )
            from cyroid.config import get_settings
            from datetime import datetime

            settings = get_settings()
            rt_event = RealtimeEvent(
                event_type=event.event_type.value,
                range_id=str(event.range_id) if event.range_id else None,
                vm_id=str(event.vm_id) if event.vm_id else None,
                network_id=str(event.network_id) if event.network_id else None,
                message=event.message,
                data=data,
                timestamp=datetime.utcnow().isoformat()
            )
            payload = rt_event.model_dump_json()

            # Use a short-lived sync Redis connection
            r = sync_redis.from_url(settings.redis_url, decode_responses=True)
            try:
                r.publish(EVENTS_CHANNEL, payload)
                if event.range_id:
                    r.publish(f"{RANGE_CHANNEL_PREFIX}{event.range_id}", payload)
                if event.vm_id:
                    r.publish(f"{VM_CHANNEL_PREFIX}{event.vm_id}", payload)
            finally:
                r.close()
        except Exception as e:
            logger.warning(f"Failed to broadcast event (sync): {e}")

    def get_events(
        self,
        range_id: UUID,
        limit: int = 100,
        offset: int = 0,
        event_types: Optional[List[EventType]] = None
    ) -> tuple[List[EventLog], int]:
        query = self.db.query(EventLog).options(
            joinedload(EventLog.user)
        ).filter(EventLog.range_id == range_id)

        if event_types:
            query = query.filter(EventLog.event_type.in_(event_types))

        total = query.count()
        events = query.order_by(desc(EventLog.created_at)).offset(offset).limit(limit).all()

        return events, total

    def get_vm_events(self, vm_id: UUID, limit: int = 50) -> List[EventLog]:
        return self.db.query(EventLog).options(
            joinedload(EventLog.user)
        ).filter(
            EventLog.vm_id == vm_id
        ).order_by(desc(EventLog.created_at)).limit(limit).all()
