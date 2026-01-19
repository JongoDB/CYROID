# backend/alembic/script.py.mako
"""rename_facilitator_to_student

Revision ID: 97a13d8b30f4
Revises: d8e9f0a1b2c3
Create Date: 2026-01-19 01:56:43.424160

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '97a13d8b30f4'
down_revision: Union[str, None] = 'd8e9f0a1b2c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename 'facilitator' role to 'student' in user_attributes table
    op.execute("""
        UPDATE user_attributes
        SET attribute_value = 'student'
        WHERE attribute_type = 'role' AND attribute_value = 'facilitator'
    """)

    # Update the legacy role column in users table (if any exist)
    # Note: We need to handle the enum type change carefully
    # First update any facilitator values to a temporary value, then alter the enum
    op.execute("""
        UPDATE users SET role = 'ENGINEER' WHERE role = 'FACILITATOR'
    """)


def downgrade() -> None:
    # Rename 'student' role back to 'facilitator' in user_attributes table
    op.execute("""
        UPDATE user_attributes
        SET attribute_value = 'facilitator'
        WHERE attribute_type = 'role' AND attribute_value = 'student'
    """)

    # Revert users table
    op.execute("""
        UPDATE users SET role = 'FACILITATOR' WHERE role = 'STUDENT'
    """)
