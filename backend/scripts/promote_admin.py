#!/usr/bin/env python3
"""Promote a user to admin role.

Usage:
    python scripts/promote_admin.py [username]

If no username is provided, promotes the first user found.
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cyroid.database import get_engine, get_session_local
from cyroid.models.user import User, UserRole
from cyroid.models.base import Base


def promote_user(username: str = None):
    """Promote a user to admin role."""
    # Ensure tables exist
    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    SessionLocal = get_session_local()
    db = SessionLocal()

    try:
        if username:
            user = db.query(User).filter(User.username == username).first()
            if not user:
                print(f"Error: User '{username}' not found")
                return False
        else:
            # Get first user
            user = db.query(User).order_by(User.created_at.asc()).first()
            if not user:
                print("Error: No users found in database")
                return False

        if user.role == UserRole.ADMIN:
            print(f"User '{user.username}' is already an admin")
            return True

        old_role = user.role.value
        user.role = UserRole.ADMIN
        db.commit()

        print(f"Successfully promoted '{user.username}' from {old_role} to admin")
        return True

    finally:
        db.close()


def list_users():
    """List all users."""
    SessionLocal = get_session_local()
    db = SessionLocal()

    try:
        users = db.query(User).order_by(User.created_at.asc()).all()
        if not users:
            print("No users found")
            return

        print("\nAll users:")
        print("-" * 60)
        for user in users:
            print(f"  {user.username} ({user.email}) - {user.role.value} {'[ACTIVE]' if user.is_active else '[INACTIVE]'}")
        print("-" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--list":
        list_users()
    else:
        username = sys.argv[1] if len(sys.argv) > 1 else None
        list_users()
        print()
        promote_user(username)
        print()
        list_users()
