# backend/alembic/script.py.mako
"""Add catalog source and installed item models

Revision ID: 847984248700
Revises: 2ea1a8ea3c48
Create Date: 2026-01-28 22:39:48.183784

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '847984248700'
down_revision: Union[str, None] = '2ea1a8ea3c48'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('catalog_sources',
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('source_type', sa.Enum('GIT', 'HTTP', 'LOCAL', name='catalogsourcetype'), nullable=False),
    sa.Column('url', sa.String(length=500), nullable=False),
    sa.Column('branch', sa.String(length=100), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('sync_status', sa.Enum('IDLE', 'SYNCING', 'ERROR', name='catalogsyncstatus'), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('item_count', sa.Integer(), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_catalog_sources_name'), 'catalog_sources', ['name'], unique=False)
    op.create_table('catalog_installed_items',
    sa.Column('catalog_source_id', sa.Uuid(), nullable=False),
    sa.Column('catalog_item_id', sa.String(length=200), nullable=False),
    sa.Column('item_type', sa.Enum('BLUEPRINT', 'SCENARIO', 'IMAGE', 'TEMPLATE', 'CONTENT', name='catalogitemtype'), nullable=False),
    sa.Column('item_name', sa.String(length=200), nullable=False),
    sa.Column('installed_version', sa.String(length=100), nullable=False),
    sa.Column('installed_checksum', sa.String(length=100), nullable=True),
    sa.Column('local_resource_id', sa.Uuid(), nullable=True),
    sa.Column('installed_by', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['catalog_source_id'], ['catalog_sources.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['installed_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_catalog_installed_items_catalog_item_id'), 'catalog_installed_items', ['catalog_item_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_catalog_installed_items_catalog_item_id'), table_name='catalog_installed_items')
    op.drop_table('catalog_installed_items')
    op.drop_index(op.f('ix_catalog_sources_name'), table_name='catalog_sources')
    op.drop_table('catalog_sources')
