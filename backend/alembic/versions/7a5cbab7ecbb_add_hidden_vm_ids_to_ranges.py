"""Add hidden_vm_ids to ranges

Revision ID: 7a5cbab7ecbb
Revises: 4384a1d4f2d5
Create Date: 2026-01-25 22:41:41.736151

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7a5cbab7ecbb'
down_revision: Union[str, None] = '4384a1d4f2d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'ranges',
        sa.Column('hidden_vm_ids', sa.JSON(), nullable=False, server_default='[]')
    )


def downgrade() -> None:
    op.drop_column('ranges', 'hidden_vm_ids')
