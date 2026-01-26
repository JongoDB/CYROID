# backend/cyroid/services/notification_service.py
"""Service for creating and querying user-scoped notifications."""
import logging
from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from cyroid.models.notification import Notification, NotificationType, NotificationSeverity
from cyroid.models.user import User
from cyroid.models.range import Range
from cyroid.models.event import TrainingEvent, EventParticipant
from cyroid.services.event_broadcaster import get_broadcaster

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing user-scoped notifications."""

    def __init__(self, db: Session):
        self.db = db

    def create_notification(
        self,
        notification_type: NotificationType,
        title: str,
        message: str,
        severity: NotificationSeverity = NotificationSeverity.INFO,
        user_id: Optional[UUID] = None,
        target_role: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[UUID] = None,
        source_event_id: Optional[UUID] = None,
        broadcast: bool = True,
    ) -> Notification:
        """Create a new notification with specified scoping.

        Args:
            notification_type: Type of notification
            title: Short title for the notification
            message: Full message text
            severity: Severity level (info, warning, error, success)
            user_id: Target specific user (optional)
            target_role: Target users with this role (optional)
            resource_type: Resource type for access-based scoping (optional)
            resource_id: Resource ID for access-based scoping (optional)
            source_event_id: Link to source EventLog entry (optional)
            broadcast: Whether to broadcast via WebSocket

        Returns:
            Created Notification instance
        """
        notification = Notification(
            notification_type=notification_type,
            title=title,
            message=message,
            severity=severity,
            user_id=user_id,
            target_role=target_role,
            resource_type=resource_type,
            resource_id=resource_id,
            source_event_id=source_event_id,
        )
        self.db.add(notification)
        self.db.flush()

        if broadcast:
            self._broadcast_notification(notification)

        return notification

    def _broadcast_notification(self, notification: Notification):
        """Broadcast notification to relevant WebSocket clients."""
        try:
            broadcaster = get_broadcaster()
            event_data = {
                "event_type": "notification",
                "notification_id": str(notification.id),
                "notification_type": notification.notification_type.value,
                "title": notification.title,
                "message": notification.message,
                "severity": notification.severity.value,
                "user_id": str(notification.user_id) if notification.user_id else None,
                "target_role": notification.target_role,
                "resource_type": notification.resource_type,
                "resource_id": str(notification.resource_id) if notification.resource_id else None,
                "timestamp": notification.created_at.isoformat(),
            }
            broadcaster.broadcast(event_data)
        except Exception as e:
            logger.warning(f"Failed to broadcast notification: {e}")

    def get_user_notifications(
        self,
        user: User,
        limit: int = 50,
        offset: int = 0,
        unread_only: bool = False,
    ) -> Tuple[List[Notification], int, int]:
        """Get notifications visible to a specific user.

        Args:
            user: The user to get notifications for
            limit: Maximum number to return
            offset: Pagination offset
            unread_only: Only return unread notifications

        Returns:
            Tuple of (notifications, total_count, unread_count)
        """
        # Build query for notifications this user can see
        query = self._build_user_query(user)

        if unread_only:
            query = query.filter(Notification.read_at.is_(None))

        # Get total and unread counts
        total = query.count()
        unread_query = self._build_user_query(user).filter(Notification.read_at.is_(None))
        unread_count = unread_query.count()

        # Get paginated results
        notifications = query.order_by(
            Notification.created_at.desc()
        ).offset(offset).limit(limit).all()

        return notifications, total, unread_count

    def _build_user_query(self, user: User):
        """Build query for notifications visible to a user."""
        from sqlalchemy import or_

        # Start with base query
        query = self.db.query(Notification)

        # Build OR conditions for visibility
        conditions = []

        # 1. Direct user targeting
        conditions.append(Notification.user_id == user.id)

        # 2. Role-based targeting
        if user.roles:
            for role in user.roles:
                conditions.append(Notification.target_role == role)

        # 3. Resource-based targeting (check user access)
        # For ranges - user owns or is assigned
        range_subquery = self.db.query(Range.id).filter(
            or_(
                Range.created_by == user.id,
                Range.assigned_to_user_id == user.id,
            )
        ).subquery()
        conditions.append(
            (Notification.resource_type == "range") &
            (Notification.resource_id.in_(range_subquery))
        )

        # For events - user is participant
        event_subquery = self.db.query(EventParticipant.event_id).filter(
            EventParticipant.user_id == user.id
        ).subquery()
        conditions.append(
            (Notification.resource_type == "event") &
            (Notification.resource_id.in_(event_subquery))
        )

        # Admin sees all admin-only notifications
        if "admin" in (user.roles or []):
            conditions.append(Notification.target_role == "admin")

        return query.filter(or_(*conditions))

    def mark_as_read(self, notification_ids: List[UUID], user: User) -> int:
        """Mark notifications as read for a user.

        Args:
            notification_ids: List of notification IDs to mark read
            user: The user marking as read

        Returns:
            Number of notifications updated
        """
        # Only update notifications the user can see
        query = self._build_user_query(user).filter(
            Notification.id.in_(notification_ids),
            Notification.read_at.is_(None),
        )

        count = query.update(
            {"read_at": datetime.utcnow()},
            synchronize_session=False
        )
        self.db.flush()
        return count

    def mark_all_as_read(self, user: User) -> int:
        """Mark all notifications as read for a user.

        Returns:
            Number of notifications updated
        """
        query = self._build_user_query(user).filter(
            Notification.read_at.is_(None)
        )

        count = query.update(
            {"read_at": datetime.utcnow()},
            synchronize_session=False
        )
        self.db.flush()
        return count

    def delete_old_notifications(self, days: int = 30) -> int:
        """Delete notifications older than specified days.

        Args:
            days: Age threshold in days

        Returns:
            Number of notifications deleted
        """
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)

        count = self.db.query(Notification).filter(
            Notification.created_at < cutoff
        ).delete(synchronize_session=False)
        self.db.flush()

        if count > 0:
            logger.info(f"Deleted {count} notifications older than {days} days")

        return count


# Convenience functions for creating common notifications
def notify_user(
    db: Session,
    user_id: UUID,
    title: str,
    message: str,
    notification_type: NotificationType = NotificationType.INFO,
    severity: NotificationSeverity = NotificationSeverity.INFO,
) -> Notification:
    """Create a notification for a specific user."""
    service = NotificationService(db)
    return service.create_notification(
        notification_type=notification_type,
        title=title,
        message=message,
        severity=severity,
        user_id=user_id,
    )


def notify_role(
    db: Session,
    role: str,
    title: str,
    message: str,
    notification_type: NotificationType = NotificationType.INFO,
    severity: NotificationSeverity = NotificationSeverity.INFO,
) -> Notification:
    """Create a notification for all users with a specific role."""
    service = NotificationService(db)
    return service.create_notification(
        notification_type=notification_type,
        title=title,
        message=message,
        severity=severity,
        target_role=role,
    )


def notify_event_participants(
    db: Session,
    event_id: UUID,
    title: str,
    message: str,
    notification_type: NotificationType = NotificationType.INFO,
    severity: NotificationSeverity = NotificationSeverity.INFO,
) -> Notification:
    """Create a notification for all participants of an event."""
    service = NotificationService(db)
    return service.create_notification(
        notification_type=notification_type,
        title=title,
        message=message,
        severity=severity,
        resource_type="event",
        resource_id=event_id,
    )


def notify_range_users(
    db: Session,
    range_id: UUID,
    title: str,
    message: str,
    notification_type: NotificationType = NotificationType.INFO,
    severity: NotificationSeverity = NotificationSeverity.INFO,
) -> Notification:
    """Create a notification for users with access to a range."""
    service = NotificationService(db)
    return service.create_notification(
        notification_type=notification_type,
        title=title,
        message=message,
        severity=severity,
        resource_type="range",
        resource_id=range_id,
    )
