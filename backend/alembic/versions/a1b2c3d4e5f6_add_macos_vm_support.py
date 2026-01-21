"""add_macos_vm_support

Revision ID: a1b2c3d4e5f6
Revises: 690fe2a2cae1
Create Date: 2026-01-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "690fe2a2cae1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add macos_version column to vms table
    op.add_column("vms", sa.Column("macos_version", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("vms", "macos_version")
