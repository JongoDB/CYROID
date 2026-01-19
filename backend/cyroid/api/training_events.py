# backend/cyroid/api/training_events.py
"""Training Events API endpoints for scheduling and role-based content delivery."""
import logging
from datetime import datetime, timezone
from typing import Annotated, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from cyroid.api.deps import get_current_user, get_db
from cyroid.models.user import User
from cyroid.models.event import TrainingEvent, EventParticipant, EventStatus
from cyroid.models.content import Content
from cyroid.models.blueprint import RangeBlueprint
from cyroid.schemas.event import (
    EventCreate,
    EventUpdate,
    EventResponse,
    EventListResponse,
    EventDetailResponse,
    EventParticipantCreate,
    EventParticipantResponse,
    EventBriefingResponse,
    EventContentItem,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/training-events", tags=["training-events"])

# Type aliases
DBSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def can_manage_event(event: TrainingEvent, user: User) -> bool:
    """Check if user can manage (edit/delete) an event."""
    return event.created_by_id == user.id or user.is_admin


def can_view_event(event: TrainingEvent, user: User) -> bool:
    """Check if user can view an event based on roles/tags."""
    # Admin can see all
    if user.is_admin:
        return True
    # Owner can see their events
    if event.created_by_id == user.id:
        return True
    # Check role-based access
    if event.allowed_roles:
        user_roles = user.roles or []
        if any(role in event.allowed_roles for role in user_roles):
            return True
    # Check tag-based access
    if event.tags:
        user_tags = user.tags or []
        if any(tag in event.tags for tag in user_tags):
            return True
    # If no roles/tags specified, event is public
    if not event.allowed_roles and not event.tags:
        return True
    return False


def get_user_event_role(event: TrainingEvent, user: User, db: Session) -> str:
    """Get the user's role in a specific event."""
    # Check if they're registered as a participant
    participant = db.query(EventParticipant).filter(
        EventParticipant.event_id == event.id,
        EventParticipant.user_id == user.id,
    ).first()
    if participant:
        return participant.role
    # If they're the creator, they're the instructor
    if event.created_by_id == user.id:
        return "instructor"
    # Default based on their global role
    if user.has_role("admin") or user.has_role("engineer"):
        return "instructor"
    if user.has_role("evaluator"):
        return "evaluator"
    return "student"


def build_event_response(event: TrainingEvent, db: Session) -> dict:
    """Build event response with computed fields."""
    participant_count = db.query(EventParticipant).filter(
        EventParticipant.event_id == event.id
    ).count()

    blueprint_name = None
    if event.blueprint_id:
        blueprint = db.query(RangeBlueprint).filter(
            RangeBlueprint.id == event.blueprint_id
        ).first()
        if blueprint:
            blueprint_name = blueprint.name

    created_by = db.query(User).filter(User.id == event.created_by_id).first()
    created_by_username = created_by.username if created_by else None

    return {
        **{c.name: getattr(event, c.name) for c in event.__table__.columns},
        "participant_count": participant_count,
        "blueprint_name": blueprint_name,
        "created_by_username": created_by_username,
    }


# ============ Event CRUD ============

@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(
    data: EventCreate,
    db: DBSession,
    current_user: CurrentUser,
):
    """Create a new training event."""
    # Validate blueprint if provided
    if data.blueprint_id:
        blueprint = db.query(RangeBlueprint).filter(
            RangeBlueprint.id == data.blueprint_id
        ).first()
        if not blueprint:
            raise HTTPException(status_code=404, detail="Blueprint not found")

    # Validate content IDs if provided
    for content_id in data.content_ids:
        try:
            uuid_content_id = UUID(content_id)
            content = db.query(Content).filter(Content.id == uuid_content_id).first()
            if not content:
                raise HTTPException(status_code=404, detail=f"Content {content_id} not found")
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid content ID: {content_id}")

    event = TrainingEvent(
        name=data.name,
        description=data.description,
        start_datetime=data.start_datetime,
        end_datetime=data.end_datetime,
        is_all_day=data.is_all_day,
        timezone=data.timezone,
        organization=data.organization,
        location=data.location,
        blueprint_id=data.blueprint_id,
        content_ids=data.content_ids,
        allowed_roles=data.allowed_roles,
        tags=data.tags,
        created_by_id=current_user.id,
        status=EventStatus.DRAFT,
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    logger.info(f"Event created: {event.name} by {current_user.username}")
    return build_event_response(event, db)


@router.get("", response_model=List[EventListResponse])
def list_events(
    db: DBSession,
    current_user: CurrentUser,
    status_filter: Optional[EventStatus] = Query(None, alias="status"),
    start_after: Optional[datetime] = Query(None, description="Events starting after this date"),
    start_before: Optional[datetime] = Query(None, description="Events starting before this date"),
    my_events: bool = Query(False, description="Only show events I created or participate in"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    search: Optional[str] = Query(None, description="Search in name and description"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List training events with optional filters."""
    query = db.query(TrainingEvent)

    # Status filter
    if status_filter:
        query = query.filter(TrainingEvent.status == status_filter)

    # Date range filters
    if start_after:
        query = query.filter(TrainingEvent.start_datetime >= start_after)
    if start_before:
        query = query.filter(TrainingEvent.start_datetime <= start_before)

    # Tag filter
    if tag:
        query = query.filter(TrainingEvent.tags.contains([tag]))

    # Search
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                TrainingEvent.name.ilike(search_pattern),
                TrainingEvent.description.ilike(search_pattern),
            )
        )

    # My events filter
    if my_events:
        # Events created by user OR user is a participant
        participant_event_ids = db.query(EventParticipant.event_id).filter(
            EventParticipant.user_id == current_user.id
        ).subquery()
        query = query.filter(
            or_(
                TrainingEvent.created_by_id == current_user.id,
                TrainingEvent.id.in_(participant_event_ids)
            )
        )

    # Get all matching events, then filter by visibility
    events = query.order_by(TrainingEvent.start_datetime.asc()).all()

    # Filter by visibility (role/tag access)
    visible_events = [e for e in events if can_view_event(e, current_user)]

    # Paginate
    paginated = visible_events[offset:offset + limit]

    # Build responses
    results = []
    for event in paginated:
        participant_count = db.query(EventParticipant).filter(
            EventParticipant.event_id == event.id
        ).count()
        results.append(EventListResponse(
            id=event.id,
            name=event.name,
            description=event.description,
            start_datetime=event.start_datetime,
            end_datetime=event.end_datetime,
            is_all_day=event.is_all_day,
            timezone=event.timezone,
            organization=event.organization,
            location=event.location,
            status=event.status,
            tags=event.tags,
            allowed_roles=event.allowed_roles,
            participant_count=participant_count,
            has_blueprint=event.blueprint_id is not None,
            created_by_id=event.created_by_id,
            created_at=event.created_at,
        ))

    return results


@router.get("/{event_id}", response_model=EventDetailResponse)
def get_event(
    event_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    """Get event details by ID."""
    event = db.query(TrainingEvent).filter(TrainingEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if not can_view_event(event, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to view this event")

    # Get participants
    participants = db.query(EventParticipant).filter(
        EventParticipant.event_id == event_id
    ).all()

    participant_responses = []
    for p in participants:
        user = db.query(User).filter(User.id == p.user_id).first()
        participant_responses.append(EventParticipantResponse(
            id=p.id,
            event_id=p.event_id,
            user_id=p.user_id,
            role=p.role,
            is_confirmed=p.is_confirmed,
            created_at=p.created_at,
            username=user.username if user else None,
        ))

    response_dict = build_event_response(event, db)
    response_dict["participants"] = participant_responses
    return response_dict


@router.put("/{event_id}", response_model=EventResponse)
def update_event(
    event_id: UUID,
    data: EventUpdate,
    db: DBSession,
    current_user: CurrentUser,
):
    """Update an event."""
    event = db.query(TrainingEvent).filter(TrainingEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if not can_manage_event(event, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to edit this event")

    # Can't update running/completed events (except status)
    if event.status in [EventStatus.RUNNING, EventStatus.COMPLETED]:
        if data.model_dump(exclude_unset=True).keys() - {"status"}:
            raise HTTPException(status_code=400, detail="Cannot modify running or completed events")

    update_data = data.model_dump(exclude_unset=True)

    # Validate blueprint if changed
    if "blueprint_id" in update_data and update_data["blueprint_id"]:
        blueprint = db.query(RangeBlueprint).filter(
            RangeBlueprint.id == update_data["blueprint_id"]
        ).first()
        if not blueprint:
            raise HTTPException(status_code=404, detail="Blueprint not found")

    for field, value in update_data.items():
        setattr(event, field, value)

    db.commit()
    db.refresh(event)

    logger.info(f"Event updated: {event.name} by {current_user.username}")
    return build_event_response(event, db)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    """Delete an event."""
    event = db.query(TrainingEvent).filter(TrainingEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if not can_manage_event(event, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to delete this event")

    if event.status == EventStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Cannot delete a running event")

    db.delete(event)
    db.commit()

    logger.info(f"Event deleted: {event.name} by {current_user.username}")


# ============ Event Status Management ============

@router.post("/{event_id}/publish", response_model=EventResponse)
def publish_event(
    event_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    """Publish (schedule) an event."""
    event = db.query(TrainingEvent).filter(TrainingEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if not can_manage_event(event, current_user):
        raise HTTPException(status_code=403, detail="Not authorized")

    if event.status != EventStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only draft events can be published")

    event.status = EventStatus.SCHEDULED
    db.commit()
    db.refresh(event)

    logger.info(f"Event published: {event.name}")
    return build_event_response(event, db)


@router.post("/{event_id}/start", response_model=EventResponse)
def start_event(
    event_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    auto_deploy: bool = Query(False, description="Auto-deploy the blueprint if attached"),
):
    """Start an event (optionally deploy the blueprint)."""
    event = db.query(TrainingEvent).filter(TrainingEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if not can_manage_event(event, current_user):
        raise HTTPException(status_code=403, detail="Not authorized")

    if event.status not in [EventStatus.SCHEDULED, EventStatus.DRAFT]:
        raise HTTPException(status_code=400, detail="Event cannot be started from current status")

    event.status = EventStatus.RUNNING
    db.commit()

    # TODO: If auto_deploy and blueprint_id, trigger blueprint deployment
    # This would create a range instance and store its ID in event.range_id

    db.refresh(event)
    logger.info(f"Event started: {event.name}")
    return build_event_response(event, db)


@router.post("/{event_id}/complete", response_model=EventResponse)
def complete_event(
    event_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    """Mark an event as completed."""
    event = db.query(TrainingEvent).filter(TrainingEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if not can_manage_event(event, current_user):
        raise HTTPException(status_code=403, detail="Not authorized")

    event.status = EventStatus.COMPLETED
    db.commit()
    db.refresh(event)

    logger.info(f"Event completed: {event.name}")
    return build_event_response(event, db)


@router.post("/{event_id}/cancel", response_model=EventResponse)
def cancel_event(
    event_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    """Cancel an event."""
    event = db.query(TrainingEvent).filter(TrainingEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if not can_manage_event(event, current_user):
        raise HTTPException(status_code=403, detail="Not authorized")

    event.status = EventStatus.CANCELLED
    db.commit()
    db.refresh(event)

    logger.info(f"Event cancelled: {event.name}")
    return build_event_response(event, db)


# ============ Participants ============

@router.get("/{event_id}/participants", response_model=List[EventParticipantResponse])
def list_participants(
    event_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    """List event participants."""
    event = db.query(TrainingEvent).filter(TrainingEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if not can_view_event(event, current_user):
        raise HTTPException(status_code=403, detail="Not authorized")

    participants = db.query(EventParticipant).filter(
        EventParticipant.event_id == event_id
    ).all()

    results = []
    for p in participants:
        user = db.query(User).filter(User.id == p.user_id).first()
        results.append(EventParticipantResponse(
            id=p.id,
            event_id=p.event_id,
            user_id=p.user_id,
            role=p.role,
            is_confirmed=p.is_confirmed,
            created_at=p.created_at,
            username=user.username if user else None,
        ))

    return results


@router.post("/{event_id}/participants", response_model=EventParticipantResponse)
def add_participant(
    event_id: UUID,
    data: EventParticipantCreate,
    db: DBSession,
    current_user: CurrentUser,
):
    """Add a participant to an event."""
    event = db.query(TrainingEvent).filter(TrainingEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if not can_manage_event(event, current_user):
        raise HTTPException(status_code=403, detail="Not authorized")

    # Check if user exists
    user = db.query(User).filter(User.id == data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if already a participant
    existing = db.query(EventParticipant).filter(
        EventParticipant.event_id == event_id,
        EventParticipant.user_id == data.user_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="User is already a participant")

    participant = EventParticipant(
        event_id=event_id,
        user_id=data.user_id,
        role=data.role,
        is_confirmed=True,
    )

    db.add(participant)
    db.commit()
    db.refresh(participant)

    return EventParticipantResponse(
        id=participant.id,
        event_id=participant.event_id,
        user_id=participant.user_id,
        role=participant.role,
        is_confirmed=participant.is_confirmed,
        created_at=participant.created_at,
        username=user.username,
    )


@router.post("/{event_id}/join", response_model=EventParticipantResponse)
def join_event(
    event_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    role: str = Query("student", description="Role to join as"),
):
    """Join an event as a participant (self-registration)."""
    event = db.query(TrainingEvent).filter(TrainingEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if not can_view_event(event, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to join this event")

    # Check if already a participant
    existing = db.query(EventParticipant).filter(
        EventParticipant.event_id == event_id,
        EventParticipant.user_id == current_user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already joined this event")

    participant = EventParticipant(
        event_id=event_id,
        user_id=current_user.id,
        role=role,
        is_confirmed=True,
    )

    db.add(participant)
    db.commit()
    db.refresh(participant)

    return EventParticipantResponse(
        id=participant.id,
        event_id=participant.event_id,
        user_id=participant.user_id,
        role=participant.role,
        is_confirmed=participant.is_confirmed,
        created_at=participant.created_at,
        username=current_user.username,
    )


@router.delete("/{event_id}/participants/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_participant(
    event_id: UUID,
    user_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    """Remove a participant from an event."""
    event = db.query(TrainingEvent).filter(TrainingEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Can remove if: admin, event owner, or self
    if not (can_manage_event(event, current_user) or user_id == current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    participant = db.query(EventParticipant).filter(
        EventParticipant.event_id == event_id,
        EventParticipant.user_id == user_id,
    ).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")

    db.delete(participant)
    db.commit()


# ============ Role-Based Content Delivery ============

@router.get("/{event_id}/briefing", response_model=EventBriefingResponse)
def get_event_briefing(
    event_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    """Get briefing content for an event, filtered by user's role."""
    event = db.query(TrainingEvent).filter(TrainingEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if not can_view_event(event, current_user):
        raise HTTPException(status_code=403, detail="Not authorized")

    # Get user's role in this event
    user_role = get_user_event_role(event, current_user, db)

    # Get content items
    content_items = []
    for content_id_str in event.content_ids:
        try:
            content_uuid = UUID(content_id_str)
            content = db.query(Content).filter(Content.id == content_uuid).first()
            if content and content.is_published:
                # Role-based content filtering
                # Students see: student_guide, reference_material
                # Instructors see: all
                # Evaluators see: all except instructor_notes
                content_type = content.content_type.value

                should_include = False
                if user_role == "instructor":
                    should_include = True
                elif user_role == "evaluator":
                    should_include = content_type != "instructor_notes"
                elif user_role == "student":
                    should_include = content_type in ["student_guide", "reference_material", "custom"]
                else:  # observer
                    should_include = content_type in ["student_guide", "reference_material"]

                if should_include:
                    content_items.append(EventContentItem(
                        id=content.id,
                        title=content.title,
                        description=content.description,
                        content_type=content_type,
                        body_html=content.body_html,
                        version=content.version,
                    ))
        except ValueError:
            continue

    # Get range status if linked
    range_status = None
    if event.range_id:
        from cyroid.models.range import Range
        range_obj = db.query(Range).filter(Range.id == event.range_id).first()
        if range_obj:
            range_status = range_obj.status.value

    return EventBriefingResponse(
        event_id=event.id,
        event_name=event.name,
        user_role=user_role,
        content_items=content_items,
        range_id=event.range_id,
        range_status=range_status,
    )
