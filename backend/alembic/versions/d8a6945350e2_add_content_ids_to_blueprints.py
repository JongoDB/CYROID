# backend/alembic/script.py.mako
"""add content_ids to blueprints

Revision ID: d8a6945350e2
Revises: 7a5cbab7ecbb
Create Date: 2026-01-25 23:18:55.293229

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd8a6945350e2'
down_revision: Union[str, None] = '7a5cbab7ecbb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('range_blueprints', sa.Column('content_ids', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('range_blueprints', 'content_ids')
