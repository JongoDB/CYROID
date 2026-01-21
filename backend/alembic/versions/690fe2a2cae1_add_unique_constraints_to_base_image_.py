# backend/alembic/versions/690fe2a2cae1_add_unique_constraints_to_base_image_.py
"""add unique constraints to base_image iso_path and docker_image_tag

Revision ID: 690fe2a2cae1
Revises: a1r2c3h4v5m6
Create Date: 2026-01-21 18:52:09.376260

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '690fe2a2cae1'
down_revision: Union[str, None] = 'a1r2c3h4v5m6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # First, remove any existing duplicates before adding unique constraints
    # Keep the oldest record (by created_at) for each duplicate iso_path
    op.execute("""
        DELETE FROM base_images b1
        WHERE iso_path IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM base_images b2
            WHERE b2.iso_path = b1.iso_path
            AND b2.created_at < b1.created_at
        )
    """)

    # Keep the oldest record (by created_at) for each duplicate docker_image_tag
    op.execute("""
        DELETE FROM base_images b1
        WHERE docker_image_tag IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM base_images b2
            WHERE b2.docker_image_tag = b1.docker_image_tag
            AND b2.created_at < b1.created_at
        )
    """)

    # Now add unique constraints
    op.create_unique_constraint('uq_base_images_iso_path', 'base_images', ['iso_path'])
    op.create_unique_constraint('uq_base_images_docker_image_tag', 'base_images', ['docker_image_tag'])


def downgrade() -> None:
    op.drop_constraint('uq_base_images_docker_image_tag', 'base_images', type_='unique')
    op.drop_constraint('uq_base_images_iso_path', 'base_images', type_='unique')
