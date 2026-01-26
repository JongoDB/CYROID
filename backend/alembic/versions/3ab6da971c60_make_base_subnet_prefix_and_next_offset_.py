# backend/alembic/script.py.mako
"""make base_subnet_prefix and next_offset nullable

Revision ID: 3ab6da971c60
Revises: 1d6b0b3f106c
Create Date: 2026-01-26 03:21:42.105643

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3ab6da971c60'
down_revision: Union[str, None] = '1d6b0b3f106c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make base_subnet_prefix and next_offset nullable
    # These columns are deprecated with DinD isolation and kept for backward compatibility
    op.alter_column('range_blueprints', 'base_subnet_prefix',
               existing_type=sa.VARCHAR(length=20),
               nullable=True)
    op.alter_column('range_blueprints', 'next_offset',
               existing_type=sa.INTEGER(),
               nullable=True)


def downgrade() -> None:
    # Set default values for any NULL rows before making non-nullable
    op.execute("UPDATE range_blueprints SET next_offset = 0 WHERE next_offset IS NULL")
    op.execute("UPDATE range_blueprints SET base_subnet_prefix = '10.0.0.0/8' WHERE base_subnet_prefix IS NULL")

    op.alter_column('range_blueprints', 'next_offset',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('range_blueprints', 'base_subnet_prefix',
               existing_type=sa.VARCHAR(length=20),
               nullable=False)
