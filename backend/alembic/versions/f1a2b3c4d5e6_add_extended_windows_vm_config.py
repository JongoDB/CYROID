"""add_extended_windows_vm_config

Revision ID: f1a2b3c4d5e6
Revises: c7d9a3b2e4f1
Create Date: 2026-01-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'c7d9a3b2e4f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Network configuration
    op.add_column('vms', sa.Column('use_dhcp', sa.Boolean(), nullable=False, server_default='false'))

    # Additional storage
    op.add_column('vms', sa.Column('disk2_gb', sa.Integer(), nullable=True))
    op.add_column('vms', sa.Column('disk3_gb', sa.Integer(), nullable=True))

    # Shared folders
    op.add_column('vms', sa.Column('enable_shared_folder', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('vms', sa.Column('enable_global_shared', sa.Boolean(), nullable=False, server_default='false'))

    # Localization
    op.add_column('vms', sa.Column('language', sa.String(length=50), nullable=True))
    op.add_column('vms', sa.Column('keyboard', sa.String(length=20), nullable=True))
    op.add_column('vms', sa.Column('region', sa.String(length=20), nullable=True))

    # Installation mode
    op.add_column('vms', sa.Column('manual_install', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('vms', 'manual_install')
    op.drop_column('vms', 'region')
    op.drop_column('vms', 'keyboard')
    op.drop_column('vms', 'language')
    op.drop_column('vms', 'enable_global_shared')
    op.drop_column('vms', 'enable_shared_folder')
    op.drop_column('vms', 'disk3_gb')
    op.drop_column('vms', 'disk2_gb')
    op.drop_column('vms', 'use_dhcp')
