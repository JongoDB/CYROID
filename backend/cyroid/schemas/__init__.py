# backend/cyroid/schemas/__init__.py
from cyroid.schemas.user import UserBase, UserCreate, UserUpdate, UserResponse
from cyroid.schemas.auth import LoginRequest, TokenResponse
from cyroid.schemas.template import VMTemplateBase, VMTemplateCreate, VMTemplateUpdate, VMTemplateResponse

__all__ = [
    "UserBase", "UserCreate", "UserUpdate", "UserResponse",
    "LoginRequest", "TokenResponse",
    "VMTemplateBase", "VMTemplateCreate", "VMTemplateUpdate", "VMTemplateResponse",
]
