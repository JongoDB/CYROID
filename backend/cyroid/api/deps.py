# backend/cyroid/api/deps.py
from typing import Annotated, List
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from cyroid.database import get_db
from cyroid.models.user import User, UserRole
from cyroid.models.resource_tag import ResourceTag
from cyroid.models.event import EventParticipant, TrainingEvent
from cyroid.models.range import Range
from cyroid.utils.security import decode_access_token

security = HTTPBearer()


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Extract and validate user from JWT token, loading attributes."""
    token = credentials.credentials
    user_id = decode_access_token(token)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Eagerly load attributes to avoid N+1 queries
    user = db.query(User).options(joinedload(User.attributes)).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return user


# Legacy role-based check (for backwards compatibility)
def require_role(*roles: UserRole):
    """Legacy role checker using old role enum field."""
    def role_checker(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {', '.join(r.value for r in roles)}",
            )
        return current_user
    return role_checker


# ABAC-based authorization checks
def require_any_role(*role_values: str):
    """
    Require user to have at least one of the specified roles (ABAC).
    Uses the new attributes system.
    """
    def checker(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if not current_user.has_any_role(*role_values):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {', '.join(role_values)}",
            )
        return current_user
    return checker


def require_admin():
    """Require user to have admin role."""
    def checker(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrator access required",
            )
        return current_user
    return checker


def require_any_tag(*tags: str):
    """Require user to have at least one of the specified tags."""
    def checker(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if not current_user.has_any_tag(*tags):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required tag: {', '.join(tags)}",
            )
        return current_user
    return checker


def get_student_accessible_range_ids(user_id: UUID, db: Session) -> List[UUID]:
    """
    Get range IDs accessible to a student via:
    1. Direct assignment (Range.assigned_to_user_id)
    2. Event participation (EventParticipant.range_id)

    Returns:
        List of range UUIDs the student can access
    """
    accessible_ids = set()

    # 1. Ranges directly assigned to user
    direct_ranges = db.query(Range.id).filter(
        Range.assigned_to_user_id == user_id
    ).all()
    accessible_ids.update(r.id for r in direct_ranges)

    # 2. Ranges assigned via event participation
    participant_ranges = db.query(EventParticipant.range_id).filter(
        EventParticipant.user_id == user_id,
        EventParticipant.range_id.isnot(None)
    ).all()
    accessible_ids.update(r.range_id for r in participant_ranges if r.range_id)

    return list(accessible_ids)


def is_student_only(user: User) -> bool:
    """
    Check if user has ONLY the student role (and no elevated roles).
    Students get assignment-based visibility instead of tag-based.
    """
    user_roles = set(user.roles)
    elevated_roles = {'admin', 'engineer', 'evaluator', 'white_cell'}
    return user_roles == {'student'} or (not user_roles.intersection(elevated_roles) and 'student' in user_roles)


def filter_by_visibility(
    query,
    resource_type: str,
    current_user: User,
    db: Session,
    model_class
):
    """
    Filter query to only return resources visible to the user based on tags.

    Visibility rules:
    1. Admins can see ALL resources
    2. Students (with no elevated roles) see ONLY assigned resources
    3. Other non-admin users see:
       - Resources they own
       - Resources with NO tags (public)
       - Resources with at least one matching tag

    Args:
        query: SQLAlchemy query object
        resource_type: Type of resource ('range', 'template', 'artifact')
        current_user: Current authenticated user
        db: Database session
        model_class: The SQLAlchemy model class (Range, BaseImage, Artifact)

    Returns:
        Filtered query
    """
    # Admins see everything
    if current_user.is_admin:
        return query

    # Students see only assigned resources (for ranges only)
    if resource_type == 'range' and is_student_only(current_user):
        accessible_ids = get_student_accessible_range_ids(current_user.id, db)
        if not accessible_ids:
            # No assignments - return empty result
            return query.filter(model_class.id == None)
        return query.filter(model_class.id.in_(accessible_ids))

    # Tag-based visibility for other users/resources
    user_tags = current_user.tags

    # Get all resource IDs that have ANY tags
    tagged_resource_ids = db.query(ResourceTag.resource_id).filter(
        ResourceTag.resource_type == resource_type
    ).distinct().subquery()

    if not user_tags:
        # User has no tags - only see untagged resources
        return query.filter(~model_class.id.in_(tagged_resource_ids))

    # User has tags - get resources matching their tags
    matching_resource_ids = db.query(ResourceTag.resource_id).filter(
        ResourceTag.resource_type == resource_type,
        ResourceTag.tag.in_(user_tags)
    ).distinct().subquery()

    # Return: untagged resources OR resources matching user's tags
    return query.filter(
        or_(
            ~model_class.id.in_(tagged_resource_ids),  # Untagged (public)
            model_class.id.in_(matching_resource_ids)   # Matching tags
        )
    )


def check_resource_access(
    resource_type: str,
    resource_id: UUID,
    current_user: User,
    db: Session,
    owner_id: UUID = None
) -> bool:
    """
    Check if user can access a specific resource.

    Access granted if:
    1. User is admin
    2. User is the owner (if owner_id provided)
    3. For ranges: student is assigned (directly or via event)
    4. Resource has no tags (public)
    5. User has at least one matching tag

    Returns True if access is granted, raises HTTPException otherwise.
    """
    # Admins always have access
    if current_user.is_admin:
        return True

    # Owners always have access to their own resources
    if owner_id and owner_id == current_user.id:
        return True

    # For ranges: check if student is assigned
    if resource_type == 'range' and is_student_only(current_user):
        accessible_ids = get_student_accessible_range_ids(current_user.id, db)
        if resource_id in accessible_ids:
            return True
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned to this lab",
        )

    # Check resource tags (for non-student users or non-range resources)
    resource_tags = db.query(ResourceTag.tag).filter(
        ResourceTag.resource_type == resource_type,
        ResourceTag.resource_id == resource_id
    ).all()

    tag_values = [t.tag for t in resource_tags]

    # No tags = public
    if not tag_values:
        return True

    # Check for matching tags
    if current_user.has_any_tag(*tag_values):
        return True

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You don't have access to this resource",
    )


# Type aliases for common dependencies
CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin())]
DBSession = Annotated[Session, Depends(get_db)]


def get_current_user_from_token_param(
    token: str = None,
    db: Session = Depends(get_db),
) -> User:
    """
    Extract and validate user from JWT token passed as query parameter.
    Used for browser download endpoints where headers can't be set.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token required",
        )

    user_id = decode_access_token(token)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user = db.query(User).options(joinedload(User.attributes)).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return user


# For download endpoints that need browser-native downloads
DownloadUser = Annotated[User, Depends(get_current_user_from_token_param)]
