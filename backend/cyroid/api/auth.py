# backend/cyroid/api/auth.py
from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import joinedload

from cyroid.api.deps import DBSession, CurrentUser
from cyroid.models.user import User, UserRole, UserAttribute
from cyroid.schemas.auth import LoginRequest, TokenResponse, PasswordChangeResponse
from cyroid.schemas.user import UserCreate, UserResponse, PasswordChangeRequest
from cyroid.utils.security import verify_password, get_password_hash, create_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: DBSession):
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

    # First user becomes admin automatically and is auto-approved
    user_count = db.query(User).count()
    is_first_user = user_count == 0
    role = UserRole.ADMIN if is_first_user else UserRole.ENGINEER

    # Create user
    # First user is auto-approved; subsequent users need admin approval
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        role=role,  # Legacy field
        is_approved=is_first_user,  # First user auto-approved, others need approval
    )
    db.add(user)
    db.flush()  # Get user.id before adding attributes

    # Add default role attribute (ABAC)
    role_attr = UserAttribute(
        user_id=user.id,
        attribute_type='role',
        attribute_value='admin' if is_first_user else 'engineer'
    )
    db.add(role_attr)

    db.commit()
    db.refresh(user)

    return user


@router.post("/login", response_model=TokenResponse)
def login(credentials: LoginRequest, db: DBSession):
    # Allow login with either username or email
    from sqlalchemy import or_
    user = db.query(User).options(joinedload(User.attributes)).filter(
        or_(
            User.username == credentials.username,
            User.email == credentials.username  # username field can contain email
        )
    ).first()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    if not user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is pending approval. Please contact an administrator.",
        )

    access_token = create_access_token(user.id)
    return TokenResponse(
        access_token=access_token,
        password_reset_required=user.password_reset_required
    )


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: CurrentUser):
    return current_user


@router.post("/change-password", response_model=PasswordChangeResponse)
def change_password(password_data: PasswordChangeRequest, db: DBSession, current_user: CurrentUser):
    """
    Change the current user's password.
    Requires confirmation of the current password.
    Also clears password_reset_required flag if set.
    """
    # Verify current password
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    # Validate new password is different
    if password_data.current_password == password_data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )

    # Validate new password length
    if len(password_data.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters",
        )

    # Update password and clear reset flag
    current_user.hashed_password = get_password_hash(password_data.new_password)
    current_user.password_reset_required = False

    db.commit()

    return PasswordChangeResponse(message="Password changed successfully")
