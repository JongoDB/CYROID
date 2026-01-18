# backend/alembic/versions/e57dfc82c9fc_drop_scenarios_table.py
"""Drop scenarios table - moved to filesystem-based

Revision ID: e57dfc82c9fc
Revises: d46cfc71bfdb
Create Date: 2026-01-18 10:30:00.000000

Scenarios are now managed directly from the filesystem (data/scenarios/*.yaml)
instead of being stored in the database. This provides immediate visibility
of scenario files without needing database seeding.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e57dfc82c9fc'
down_revision: Union[str, None] = 'd46cfc71bfdb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the scenarios table - data is now filesystem-based
    op.drop_index(op.f('ix_scenarios_name'), table_name='scenarios')
    op.drop_table('scenarios')


def downgrade() -> None:
    # Recreate the scenarios table (for rollback)
    op.create_table('scenarios',
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('difficulty', sa.String(length=20), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=False),
        sa.Column('event_count', sa.Integer(), nullable=False),
        sa.Column('required_roles', sa.JSON(), nullable=False),
        sa.Column('events', sa.JSON(), nullable=False),
        sa.Column('is_seed', sa.Boolean(), nullable=False),
        sa.Column('seed_id', sa.String(length=100), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('seed_id')
    )
    op.create_index(op.f('ix_scenarios_name'), 'scenarios', ['name'], unique=False)
