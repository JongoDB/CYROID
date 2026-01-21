# backend/alembic/versions/a1r2c3h4v5m6_add_arch_to_vms.py
"""Add arch field to VMs for architecture selection

Revision ID: a1r2c3h4v5m6
Revises: i1m2a3g4e5l6
Create Date: 2026-01-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1r2c3h4v5m6'
down_revision: Union[str, None] = 'i1m2a3g4e5l6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add arch column to VMs table
    # Stores the target architecture (x86_64 or arm64)
    # NULL means "use host architecture" (backwards compatible)
    op.add_column('vms', sa.Column('arch', sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column('vms', 'arch')
