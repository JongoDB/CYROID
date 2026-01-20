"""add image library models

Revision ID: i1m2a3g4e5l6
Revises: b1o2o3t4s5r6
Create Date: 2026-01-20

This migration adds the three-tier Image Library system:
- base_images: Container images and cached ISOs
- golden_images: First snapshots or imported VMs
- Updates to snapshots: lineage fields (golden_image_id, parent_snapshot_id)
- Updates to vms: image source fields (base_image_id, golden_image_id)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'i1m2a3g4e5l6'
down_revision: Union[str, None] = 'b1o2o3t4s5r6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create base_images table
    op.create_table(
        'base_images',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('image_type', sa.String(20), nullable=False),
        # Container-specific
        sa.Column('docker_image_id', sa.String(128), nullable=True),
        sa.Column('docker_image_tag', sa.String(255), nullable=True),
        # ISO-specific
        sa.Column('iso_path', sa.String(500), nullable=True),
        sa.Column('iso_source', sa.String(50), nullable=True),
        sa.Column('iso_version', sa.String(50), nullable=True),
        # Metadata
        sa.Column('os_type', sa.String(20), nullable=False),
        sa.Column('vm_type', sa.String(20), nullable=False),
        sa.Column('native_arch', sa.String(20), nullable=False, server_default='x86_64'),
        # Resource defaults
        sa.Column('default_cpu', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('default_ram_mb', sa.Integer(), nullable=False, server_default='4096'),
        sa.Column('default_disk_gb', sa.Integer(), nullable=False, server_default='40'),
        # Size
        sa.Column('size_bytes', sa.BigInteger(), nullable=True),
        # Visibility
        sa.Column('is_global', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=False, server_default='[]'),
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_base_images_name', 'base_images', ['name'])

    # Create golden_images table
    op.create_table(
        'golden_images',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        # Source tracking
        sa.Column('source', sa.String(20), nullable=False),
        sa.Column('base_image_id', sa.UUID(), nullable=True),
        sa.Column('source_vm_id', sa.UUID(), nullable=True),
        # Storage - container
        sa.Column('docker_image_id', sa.String(128), nullable=True),
        sa.Column('docker_image_tag', sa.String(255), nullable=True),
        # Storage - disk images
        sa.Column('disk_image_path', sa.String(500), nullable=True),
        sa.Column('import_format', sa.String(20), nullable=True),
        # Metadata
        sa.Column('os_type', sa.String(20), nullable=False),
        sa.Column('vm_type', sa.String(20), nullable=False),
        sa.Column('native_arch', sa.String(20), nullable=False, server_default='x86_64'),
        # Resource defaults
        sa.Column('default_cpu', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('default_ram_mb', sa.Integer(), nullable=False, server_default='4096'),
        sa.Column('default_disk_gb', sa.Integer(), nullable=False, server_default='40'),
        # Display
        sa.Column('display_type', sa.String(20), nullable=True),
        sa.Column('vnc_port', sa.Integer(), nullable=False, server_default='8006'),
        # Size
        sa.Column('size_bytes', sa.BigInteger(), nullable=True),
        # Visibility
        sa.Column('is_global', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=False, server_default='[]'),
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['base_image_id'], ['base_images.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['source_vm_id'], ['vms.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_golden_images_name', 'golden_images', ['name'])

    # Add lineage fields to snapshots table
    op.add_column('snapshots', sa.Column('golden_image_id', sa.UUID(), nullable=True))
    op.add_column('snapshots', sa.Column('parent_snapshot_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_snapshots_golden_image_id',
        'snapshots', 'golden_images',
        ['golden_image_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_snapshots_parent_snapshot_id',
        'snapshots', 'snapshots',
        ['parent_snapshot_id'], ['id'],
        ondelete='SET NULL'
    )

    # Add image source fields to vms table
    op.add_column('vms', sa.Column('base_image_id', sa.UUID(), nullable=True))
    op.add_column('vms', sa.Column('golden_image_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_vms_base_image_id',
        'vms', 'base_images',
        ['base_image_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_vms_golden_image_id',
        'vms', 'golden_images',
        ['golden_image_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    # Remove foreign keys and columns from vms
    op.drop_constraint('fk_vms_golden_image_id', 'vms', type_='foreignkey')
    op.drop_constraint('fk_vms_base_image_id', 'vms', type_='foreignkey')
    op.drop_column('vms', 'golden_image_id')
    op.drop_column('vms', 'base_image_id')

    # Remove foreign keys and columns from snapshots
    op.drop_constraint('fk_snapshots_parent_snapshot_id', 'snapshots', type_='foreignkey')
    op.drop_constraint('fk_snapshots_golden_image_id', 'snapshots', type_='foreignkey')
    op.drop_column('snapshots', 'parent_snapshot_id')
    op.drop_column('snapshots', 'golden_image_id')

    # Drop golden_images table
    op.drop_index('ix_golden_images_name', table_name='golden_images')
    op.drop_table('golden_images')

    # Drop base_images table
    op.drop_index('ix_base_images_name', table_name='base_images')
    op.drop_table('base_images')
