"""add container_config to base_image

Revision ID: j2k3l4m5n6o7
Revises: b2c3d4e5f6a7
Create Date: 2026-01-21

Adds container_config JSON field to base_images table for storing
Docker runtime options (capabilities, devices, security options).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'j2k3l4m5n6o7'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add container_config JSON column to base_images
    op.add_column('base_images', sa.Column('container_config', sa.JSON(), nullable=True))


def downgrade() -> None:
    # Remove container_config column
    op.drop_column('base_images', 'container_config')
