# backend/alembic/versions/f97a6114c7b8_add_per_student_range_fields.py
"""Add per-student range fields for training events

Adds:
- range_id to event_participants (for per-student range assignment)
- assigned_to_user_id to ranges (track which student owns the range)
- training_event_id to ranges (link range to source event)

Revision ID: f97a6114c7b8
Revises: k3l4m5n6o7p8
Create Date: 2026-01-25 19:22:34.119557

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f97a6114c7b8'
down_revision: Union[str, None] = 'k3l4m5n6o7p8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add range_id to event_participants (per-student range assignment)
    op.add_column('event_participants', sa.Column('range_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_event_participants_range_id',
        'event_participants', 'ranges',
        ['range_id'], ['id'],
        ondelete='SET NULL'
    )

    # Add assigned_to_user_id to ranges (student ownership)
    op.add_column('ranges', sa.Column('assigned_to_user_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_ranges_assigned_to_user_id'), 'ranges', ['assigned_to_user_id'], unique=False)
    op.create_foreign_key(
        'fk_ranges_assigned_to_user_id',
        'ranges', 'users',
        ['assigned_to_user_id'], ['id'],
        ondelete='SET NULL'
    )

    # Add training_event_id to ranges (event link)
    op.add_column('ranges', sa.Column('training_event_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_ranges_training_event_id'), 'ranges', ['training_event_id'], unique=False)
    op.create_foreign_key(
        'fk_ranges_training_event_id',
        'ranges', 'training_events',
        ['training_event_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    # Remove training_event_id from ranges
    op.drop_constraint('fk_ranges_training_event_id', 'ranges', type_='foreignkey')
    op.drop_index(op.f('ix_ranges_training_event_id'), table_name='ranges')
    op.drop_column('ranges', 'training_event_id')

    # Remove assigned_to_user_id from ranges
    op.drop_constraint('fk_ranges_assigned_to_user_id', 'ranges', type_='foreignkey')
    op.drop_index(op.f('ix_ranges_assigned_to_user_id'), table_name='ranges')
    op.drop_column('ranges', 'assigned_to_user_id')

    # Remove range_id from event_participants
    op.drop_constraint('fk_event_participants_range_id', 'event_participants', type_='foreignkey')
    op.drop_column('event_participants', 'range_id')
