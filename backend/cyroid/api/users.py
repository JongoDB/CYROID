# backend/cyroid/api/users.py
"""User management API endpoints with ABAC attribute support."""
from typing import List
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import joinedload

from cyroid.api.deps import DBSession, AdminUser, CurrentUser
from cyroid.models.user import User, UserRole, UserAttribute, AVAILABLE_ROLES
from cyroid.schemas.user import (
    UserResponse, UserUpdate, UserDetailResponse,
    UserAttributeCreate, UserAttributeResponse, AdminCreateUser
)
from cyroid.utils.security import get_password_hash

router = APIRouter(prefix="/users", tags=["User Management"])


@router.get("", response_model=List[UserResponse])
def list_users(db: DBSession, current_user: AdminUser):
    """List all users with their attributes. Admin only."""
    users = db.query(User).options(joinedload(User.attributes)).order_by(User.created_at.desc()).all()
    return users


@router.get("/pending", response_model=List[UserResponse])
def list_pending_users(db: DBSession, current_user: AdminUser):
    """List all users pending approval. Admin only."""
    users = db.query(User).options(joinedload(User.attributes)).filter(
        User.is_approved == False
    ).order_by(User.created_at.desc()).all()
    return users


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user_data: AdminCreateUser, db: DBSession, current_user: AdminUser):
    """
    Create a new user as admin.
    Admin-created users are pre-approved and can optionally have password reset required.
    """
    # Check if username exists
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    # Check if email exists
    existing_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Validate roles
    for role in user_data.roles:
        if role not in AVAILABLE_ROLES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role '{role}'. Available roles: {', '.join(AVAILABLE_ROLES)}"
            )

    # Determine legacy role (first role or engineer)
    legacy_role = UserRole.ADMIN if 'admin' in user_data.roles else UserRole.ENGINEER

    # Create user - admin created users are auto-approved
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        role=legacy_role,
        is_approved=user_data.is_approved,
        password_reset_required=True,  # Force password change on first login
    )
    db.add(user)
    db.flush()

    # Add role attributes
    for role in user_data.roles:
        role_attr = UserAttribute(
            user_id=user.id,
            attribute_type='role',
            attribute_value=role
        )
        db.add(role_attr)

    # Add tag attributes
    for tag in user_data.tags:
        tag_attr = UserAttribute(
            user_id=user.id,
            attribute_type='tag',
            attribute_value=tag
        )
        db.add(tag_attr)

    db.commit()
    db.refresh(user)
    return user


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: CurrentUser):
    """Get current user's profile with attributes."""
    return current_user


@router.get("/{user_id}", response_model=UserDetailResponse)
def get_user(user_id: UUID, db: DBSession, current_user: AdminUser):
    """Get a specific user by ID with full attribute details. Admin only."""
    user = db.query(User).options(joinedload(User.attributes)).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(user_id: UUID, user_update: UserUpdate, db: DBSession, current_user: AdminUser):
    """
    Update a user's email or active status. Admin only.
    Use attribute endpoints to manage roles and tags.
    """
    user = db.query(User).options(joinedload(User.attributes)).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Prevent admin from deactivating themselves
    if user.id == current_user.id and user_update.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )

    # Apply updates
    if user_update.email is not None:
        existing = db.query(User).filter(
            User.email == user_update.email,
            User.id != user_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use"
            )
        user.email = user_update.email

    if user_update.is_active is not None:
        user.is_active = user_update.is_active

    if user_update.is_approved is not None:
        user.is_approved = user_update.is_approved

    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/approve", response_model=UserResponse)
def approve_user(user_id: UUID, db: DBSession, current_user: AdminUser):
    """Approve a pending user registration. Admin only."""
    user = db.query(User).options(joinedload(User.attributes)).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_approved:
        raise HTTPException(status_code=400, detail="User is already approved")

    user.is_approved = True
    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/deny", status_code=status.HTTP_204_NO_CONTENT)
def deny_user(user_id: UUID, db: DBSession, current_user: AdminUser):
    """Deny a pending user registration (deletes the user). Admin only."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_approved:
        raise HTTPException(status_code=400, detail="Cannot deny an already approved user. Use delete instead.")

    db.delete(user)
    db.commit()
    return None


@router.post("/{user_id}/reset-password", response_model=UserResponse)
def admin_reset_password(user_id: UUID, db: DBSession, current_user: AdminUser):
    """
    Force a user to reset their password on next login.
    Sets password_reset_required flag to True.
    Admin only.
    """
    user = db.query(User).options(joinedload(User.attributes)).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_reset_required = True
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: UUID, db: DBSession, current_user: AdminUser):
    """Delete a user. Admin only. Admins cannot delete themselves."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )

    db.delete(user)
    db.commit()
    return None


# ============================================================================
# Attribute Management Endpoints
# ============================================================================

@router.get("/{user_id}/attributes", response_model=List[UserAttributeResponse])
def list_user_attributes(user_id: UUID, db: DBSession, current_user: AdminUser):
    """List all attributes for a user. Admin only."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return db.query(UserAttribute).filter(UserAttribute.user_id == user_id).all()


@router.post("/{user_id}/attributes", response_model=UserAttributeResponse, status_code=status.HTTP_201_CREATED)
def add_user_attribute(user_id: UUID, attr_data: UserAttributeCreate, db: DBSession, current_user: AdminUser):
    """
    Add an attribute to a user. Admin only.

    - attribute_type: 'role' or 'tag'
    - attribute_value: Role name or tag string
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate attribute type
    if attr_data.attribute_type not in ('role', 'tag'):
        raise HTTPException(
            status_code=400,
            detail="attribute_type must be 'role' or 'tag'"
        )

    # Validate role value if it's a role
    if attr_data.attribute_type == 'role' and attr_data.attribute_value not in AVAILABLE_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Available roles: {', '.join(AVAILABLE_ROLES)}"
        )

    # Check for duplicate
    existing = db.query(UserAttribute).filter(
        UserAttribute.user_id == user_id,
        UserAttribute.attribute_type == attr_data.attribute_type,
        UserAttribute.attribute_value == attr_data.attribute_value
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="User already has this attribute"
        )

    # Create attribute
    attr = UserAttribute(
        user_id=user_id,
        attribute_type=attr_data.attribute_type,
        attribute_value=attr_data.attribute_value
    )
    db.add(attr)

    # If adding an admin role, also update legacy role column
    if attr_data.attribute_type == 'role' and attr_data.attribute_value == 'admin':
        user.role = UserRole.ADMIN

    db.commit()
    db.refresh(attr)
    return attr


@router.delete("/{user_id}/attributes/{attribute_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_user_attribute(user_id: UUID, attribute_id: UUID, db: DBSession, current_user: AdminUser):
    """
    Remove an attribute from a user. Admin only.

    Admins cannot remove their own admin role to prevent lockout.
    """
    attr = db.query(UserAttribute).filter(
        UserAttribute.id == attribute_id,
        UserAttribute.user_id == user_id
    ).first()
    if not attr:
        raise HTTPException(status_code=404, detail="Attribute not found")

    # Prevent admin from removing their own admin role
    if (user_id == current_user.id and
        attr.attribute_type == 'role' and
        attr.attribute_value == 'admin'):
        raise HTTPException(
            status_code=400,
            detail="Cannot remove your own admin role"
        )

    db.delete(attr)
    db.commit()
    return None


# ============================================================================
# Utility Endpoints
# ============================================================================

@router.get("/roles/available", response_model=List[dict])
def get_available_roles(current_user: CurrentUser):
    """Get list of available user roles with descriptions."""
    return [
        {
            "value": "admin",
            "label": "Administrator",
            "description": "Full system access including user management and cache operations"
        },
        {
            "value": "engineer",
            "label": "Engineer",
            "description": "Create and manage cyber ranges, VMs, and templates"
        },
        {
            "value": "facilitator",
            "label": "Facilitator",
            "description": "Run exercises and manage MSEL/injects"
        },
        {
            "value": "evaluator",
            "label": "Evaluator",
            "description": "View ranges and evaluate exercise performance"
        },
    ]


@router.get("/tags/all", response_model=List[str])
def get_all_tags(db: DBSession, current_user: CurrentUser):
    """Get all unique tags used across users (for autocomplete)."""
    tags = db.query(UserAttribute.attribute_value).filter(
        UserAttribute.attribute_type == 'tag'
    ).distinct().all()
    return [t[0] for t in tags]
