"""Add template cache fields

Revision ID: b2c8f4a1d3e5
Revises: 10989eb9fc62
Create Date: 2026-01-12 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c8f4a1d3e5'
down_revision: Union[str, None] = '10989eb9fc62'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add cache-related fields to vm_templates table
    op.add_column('vm_templates', sa.Column('golden_image_path', sa.String(500), nullable=True))
    op.add_column('vm_templates', sa.Column('cached_iso_path', sa.String(500), nullable=True))
    op.add_column('vm_templates', sa.Column('is_cached', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('vm_templates', 'is_cached')
    op.drop_column('vm_templates', 'cached_iso_path')
    op.drop_column('vm_templates', 'golden_image_path')
