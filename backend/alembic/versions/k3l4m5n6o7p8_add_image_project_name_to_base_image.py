"""add image_project_name to base_image

Revision ID: k3l4m5n6o7p8
Revises: b8e6c0b7c919
Create Date: 2026-01-24

Adds image_project_name field to base_images table to track which
Dockerfile project directory (/data/images/{project_name}/) built the image.
This enables blueprint export to include Dockerfiles for reproducibility.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'k3l4m5n6o7p8'
down_revision: Union[str, None] = 'b8e6c0b7c919'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add image_project_name column with index for fast lookups
    op.add_column('base_images', sa.Column('image_project_name', sa.String(100), nullable=True))
    op.create_index('ix_base_images_image_project_name', 'base_images', ['image_project_name'])


def downgrade() -> None:
    # Remove index and column
    op.drop_index('ix_base_images_image_project_name', table_name='base_images')
    op.drop_column('base_images', 'image_project_name')
