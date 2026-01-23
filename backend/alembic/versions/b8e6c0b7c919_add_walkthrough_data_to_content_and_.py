# backend/alembic/script.py.mako
"""add walkthrough_data to content and student_guide_id to ranges

Revision ID: b8e6c0b7c919
Revises: j2k3l4m5n6o7
Create Date: 2026-01-23 14:52:13.802609

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b8e6c0b7c919'
down_revision: Union[str, None] = 'j2k3l4m5n6o7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add walkthrough_data JSON column to content table (for student_guide structured data)
    op.add_column('content', sa.Column('walkthrough_data', sa.JSON(), nullable=True))

    # Add student_guide_id foreign key to ranges table (link to Content Library)
    op.add_column('ranges', sa.Column('student_guide_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_ranges_student_guide_id',
        'ranges', 'content',
        ['student_guide_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    # Remove student_guide_id from ranges
    op.drop_constraint('fk_ranges_student_guide_id', 'ranges', type_='foreignkey')
    op.drop_column('ranges', 'student_guide_id')

    # Remove walkthrough_data from content
    op.drop_column('content', 'walkthrough_data')
