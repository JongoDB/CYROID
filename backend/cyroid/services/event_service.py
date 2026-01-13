# backend/cyroid/services/event_service.py
from uuid import UUID
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from cyroid.models.event_log import EventLog, EventType


class EventService:
    def __init__(self, db: Session):
        self.db = db

    def log_event(
        self,
        range_id: UUID,
        event_type: EventType,
        message: str,
        vm_id: Optional[UUID] = None,
        extra_data: Optional[str] = None
    ) -> EventLog:
        event = EventLog(
            range_id=range_id,
            vm_id=vm_id,
            event_type=event_type,
            message=message,
            extra_data=extra_data
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def get_events(
        self,
        range_id: UUID,
        limit: int = 100,
        offset: int = 0,
        event_types: Optional[List[EventType]] = None
    ) -> tuple[List[EventLog], int]:
        query = self.db.query(EventLog).filter(EventLog.range_id == range_id)

        if event_types:
            query = query.filter(EventLog.event_type.in_(event_types))

        total = query.count()
        events = query.order_by(desc(EventLog.created_at)).offset(offset).limit(limit).all()

        return events, total

    def get_vm_events(self, vm_id: UUID, limit: int = 50) -> List[EventLog]:
        return self.db.query(EventLog).filter(
            EventLog.vm_id == vm_id
        ).order_by(desc(EventLog.created_at)).limit(limit).all()
