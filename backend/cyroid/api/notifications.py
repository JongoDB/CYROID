# backend/cyroid/api/notifications.py
"""API endpoints for user-scoped notifications."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from cyroid.api.deps import DBSession, CurrentUser
from cyroid.models.notification import NotificationType, NotificationSeverity
from cyroid.schemas.notification import (
    NotificationCreate,
    NotificationResponse,
    NotificationList,
    NotificationMarkRead,
)
from cyroid.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=NotificationList)
def get_notifications(
    db: DBSession,
    current_user: CurrentUser,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    unread_only: bool = Query(False),
):
    """Get notifications visible to the current user.

    Returns notifications targeted to:
    - This specific user
    - Users with this user's role(s)
    - Resources the user has access to (ranges, events)
    """
    service = NotificationService(db)
    notifications, total, unread_count = service.get_user_notifications(
        user=current_user,
        limit=limit,
        offset=offset,
        unread_only=unread_only,
    )

    return NotificationList(
        notifications=[NotificationResponse.model_validate(n) for n in notifications],
        total=total,
        unread_count=unread_count,
    )


@router.post("/read", status_code=status.HTTP_200_OK)
def mark_notifications_read(
    data: NotificationMarkRead,
    db: DBSession,
    current_user: CurrentUser,
):
    """Mark specific notifications as read.

    Only marks notifications the user can actually see.
    """
    service = NotificationService(db)
    count = service.mark_as_read(data.notification_ids, current_user)
    db.commit()

    return {"marked_read": count}


@router.post("/read-all", status_code=status.HTTP_200_OK)
def mark_all_notifications_read(
    db: DBSession,
    current_user: CurrentUser,
):
    """Mark all of the user's notifications as read."""
    service = NotificationService(db)
    count = service.mark_all_as_read(current_user)
    db.commit()

    return {"marked_read": count}


@router.post("", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
def create_notification(
    data: NotificationCreate,
    db: DBSession,
    current_user: CurrentUser,
):
    """Create a new notification (admin only).

    At least one scoping field should be set:
    - user_id: Target specific user
    - target_role: Target users with this role
    - resource_type + resource_id: Target users with access to resource
    """
    # Check admin permission
    if "admin" not in (current_user.roles or []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create notifications",
        )

    # Validate at least one scoping field is set
    if not any([data.user_id, data.target_role, data.resource_type]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one scoping field must be set (user_id, target_role, or resource_type)",
        )

    service = NotificationService(db)
    notification = service.create_notification(
        notification_type=data.notification_type,
        title=data.title,
        message=data.message,
        severity=data.severity,
        user_id=data.user_id,
        target_role=data.target_role,
        resource_type=data.resource_type,
        resource_id=data.resource_id,
        source_event_id=data.source_event_id,
    )
    db.commit()

    return NotificationResponse.model_validate(notification)


@router.get("/{notification_id}", response_model=NotificationResponse)
def get_notification(
    notification_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    """Get a specific notification by ID.

    Returns 404 if notification doesn't exist or user can't see it.
    """
    service = NotificationService(db)

    # Build query with user visibility filter
    query = service._build_user_query(current_user)
    from cyroid.models.notification import Notification
    notification = query.filter(Notification.id == notification_id).first()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    return NotificationResponse.model_validate(notification)
