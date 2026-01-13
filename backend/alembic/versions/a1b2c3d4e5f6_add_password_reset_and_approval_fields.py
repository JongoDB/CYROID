"""add_password_reset_and_approval_fields

Revision ID: a1b2c3d4e5f6
Revises: 89e9aed193fa
Create Date: 2026-01-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '89e9aed193fa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add password_reset_required column - defaults to False
    op.add_column('users', sa.Column('password_reset_required', sa.Boolean(), nullable=False, server_default='false'))

    # Add is_approved column - defaults to False for new registrations
    op.add_column('users', sa.Column('is_approved', sa.Boolean(), nullable=False, server_default='false'))

    # Set all existing users as approved (they were able to register before this feature)
    op.execute("UPDATE users SET is_approved = true")


def downgrade() -> None:
    op.drop_column('users', 'is_approved')
    op.drop_column('users', 'password_reset_required')
