"""Add source_range_id to content for cleanup tracking

Revision ID: c4o5n6t7e8n9
Revises: k3l4m5n6o7p8
Create Date: 2026-01-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4o5n6t7e8n9'
down_revision: Union[str, None] = 'k3l4m5n6o7p8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add source_range_id column to track which range created this content
    # This enables cleanup when a range is deleted (Issue #152)
    op.add_column('content', sa.Column('source_range_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_content_source_range_id',
        'content',
        'ranges',
        ['source_range_id'],
        ['id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_content_source_range_id', 'content', ['source_range_id'])


def downgrade() -> None:
    op.drop_index('ix_content_source_range_id', table_name='content')
    op.drop_constraint('fk_content_source_range_id', 'content', type_='foreignkey')
    op.drop_column('content', 'source_range_id')
