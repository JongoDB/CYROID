"""add boot_source to vm model

Revision ID: b1o2o3t4s5r6
Revises: s1e2e3d4t5p6
Create Date: 2026-01-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1o2o3t4s5r6'
down_revision: Union[str, None] = 'e4f5g6h7i8j9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add boot_source column to vms table
    # Allows 'golden_image' or 'fresh_install' for QEMU-based VMs
    op.add_column('vms', sa.Column('boot_source', sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column('vms', 'boot_source')
