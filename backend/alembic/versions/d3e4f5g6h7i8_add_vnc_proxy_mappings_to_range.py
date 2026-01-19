"""Add vnc_proxy_mappings to range

Adds a JSON column to store VNC proxy port mappings for DinD-based ranges.
The mappings store vm_id -> {proxy_host, proxy_port, original_port} for
routing VNC traffic through the nginx proxy inside DinD.

Revision ID: d3e4f5g6h7i8
Revises: c2d3i4n5d6i7
Create Date: 2026-01-19 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'd3e4f5g6h7i8'
down_revision = 'c2d3i4n5d6i7'
branch_labels = None
depends_on = None


def upgrade():
    # Add vnc_proxy_mappings JSON column to ranges table
    op.add_column(
        'ranges',
        sa.Column('vnc_proxy_mappings', sa.JSON(), nullable=True)
    )


def downgrade():
    # Drop the vnc_proxy_mappings column
    op.drop_column('ranges', 'vnc_proxy_mappings')
