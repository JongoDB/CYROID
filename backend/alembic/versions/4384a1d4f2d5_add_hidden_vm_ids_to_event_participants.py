"""Add hidden_vm_ids to event_participants

Revision ID: 4384a1d4f2d5
Revises: f97a6114c7b8
Create Date: 2026-01-25 22:24:39.569431

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4384a1d4f2d5'
down_revision: Union[str, None] = 'f97a6114c7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add hidden_vm_ids column to event_participants
    # Default is empty JSON array (all VMs visible)
    op.add_column(
        'event_participants',
        sa.Column('hidden_vm_ids', sa.JSON(), nullable=False, server_default='[]')
    )


def downgrade() -> None:
    op.drop_column('event_participants', 'hidden_vm_ids')
