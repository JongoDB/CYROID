"""Add DinD container tracking to ranges

Adds columns to track the Docker-in-Docker container that provides
network isolation for each range instance.

Revision ID: c2d3i4n5d6i7
Revises: b1p2s3e4e5d6
Create Date: 2026-01-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'c2d3i4n5d6i7'
down_revision = 'b1p2s3e4e5d6'
branch_labels = None
depends_on = None


def upgrade():
    # Add DinD tracking columns to ranges table
    op.add_column(
        'ranges',
        sa.Column('dind_container_id', sa.String(64), nullable=True)
    )
    op.add_column(
        'ranges',
        sa.Column('dind_container_name', sa.String(64), nullable=True)
    )
    op.add_column(
        'ranges',
        sa.Column('dind_mgmt_ip', sa.String(45), nullable=True)
    )
    op.add_column(
        'ranges',
        sa.Column('dind_docker_url', sa.String(128), nullable=True)
    )

    # Create indexes for faster lookups
    op.create_index(
        'ix_ranges_dind_container_id',
        'ranges',
        ['dind_container_id']
    )
    op.create_index(
        'ix_ranges_dind_container_name',
        'ranges',
        ['dind_container_name']
    )


def downgrade():
    # Drop indexes first
    op.drop_index('ix_ranges_dind_container_name', table_name='ranges')
    op.drop_index('ix_ranges_dind_container_id', table_name='ranges')

    # Drop columns
    op.drop_column('ranges', 'dind_docker_url')
    op.drop_column('ranges', 'dind_mgmt_ip')
    op.drop_column('ranges', 'dind_container_name')
    op.drop_column('ranges', 'dind_container_id')
