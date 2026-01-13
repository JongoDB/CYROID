# backend/cyroid/schemas/user.py
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, EmailStr

from cyroid.models.user import UserRole


class UserBase(BaseModel):
    username: str
    email: EmailStr


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    is_approved: Optional[bool] = None


class PasswordChangeRequest(BaseModel):
    """Request to change user's own password."""
    current_password: str
    new_password: str


class AdminCreateUser(BaseModel):
    """Admin request to create a new user."""
    username: str
    email: EmailStr
    password: str
    roles: List[str] = ["engineer"]  # Default role
    tags: List[str] = []
    is_approved: bool = True  # Admin-created users are auto-approved


# ABAC Attribute Schemas
class UserAttributeCreate(BaseModel):
    attribute_type: str  # 'role' or 'tag'
    attribute_value: str


class UserAttributeResponse(BaseModel):
    id: UUID
    attribute_type: str
    attribute_value: str
    created_at: datetime

    class Config:
        from_attributes = True


class UserResponse(UserBase):
    id: UUID
    role: UserRole  # Keep for backwards compatibility
    roles: List[str]  # New: list of role attribute values
    tags: List[str]  # New: list of tag attribute values
    is_active: bool
    is_approved: bool
    password_reset_required: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserDetailResponse(UserResponse):
    """Extended user response with full attribute details."""
    attributes: List[UserAttributeResponse]

    class Config:
        from_attributes = True


# Resource Tag Schemas
class ResourceTagCreate(BaseModel):
    tag: str


class ResourceTagResponse(BaseModel):
    id: UUID
    resource_type: str
    resource_id: UUID
    tag: str
    created_at: datetime

    class Config:
        from_attributes = True


class ResourceTagsResponse(BaseModel):
    resource_type: str
    resource_id: UUID
    tags: List[str]
