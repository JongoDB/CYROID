# backend/alembic/versions/y4z5a6b7c8d9_add_vm_environment.py
"""Add environment column to VMs for blueprint-level env var support

Revision ID: y4z5a6b7c8d9
Revises: x3y4z5a6b7c8
Create Date: 2026-02-13 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'y4z5a6b7c8d9'
down_revision: Union[str, None] = 'x3y4z5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('vms', sa.Column('environment', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('vms', 'environment')
