# backend/alembic/script.py.mako
"""add_network_os_type

Revision ID: d46cfc71bfdb
Revises: 2ad21707424c
Create Date: 2026-01-18 14:05:55.182405

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd46cfc71bfdb'
down_revision: Union[str, None] = '2ad21707424c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add NETWORK value to the ostype enum
    op.execute("ALTER TYPE ostype ADD VALUE IF NOT EXISTS 'NETWORK'")


def downgrade() -> None:
    # PostgreSQL doesn't support removing enum values easily
    # This would require recreating the enum type
    pass
