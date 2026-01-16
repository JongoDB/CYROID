# backend/alembic/versions/x3y4z5a6b7c8_add_multi_arch_support.py
"""Add multi-architecture support to templates

Revision ID: x3y4z5a6b7c8
Revises: w2x3y4z5a6b7
Create Date: 2026-01-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'x3y4z5a6b7c8'
down_revision: Union[str, None] = 'w2x3y4z5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add multi-architecture columns to vm_templates
    # iso_url_x86: Architecture-specific ISO URL for x86_64 systems
    op.add_column('vm_templates', sa.Column('iso_url_x86', sa.String(500), nullable=True))

    # iso_url_arm64: Architecture-specific ISO URL for ARM64/aarch64 systems
    op.add_column('vm_templates', sa.Column('iso_url_arm64', sa.String(500), nullable=True))

    # native_arch: The native/primary architecture for this template
    # Defaults to 'x86_64' for backward compatibility with existing templates
    op.add_column('vm_templates', sa.Column('native_arch', sa.String(20), server_default='x86_64', nullable=False))


def downgrade() -> None:
    op.drop_column('vm_templates', 'native_arch')
    op.drop_column('vm_templates', 'iso_url_arm64')
    op.drop_column('vm_templates', 'iso_url_x86')
