# backend/alembic/versions/v1y2o3s4r5t6_add_vyos_router_support.py
"""Add VyOS router support

Revision ID: v1y2o3s4r5t6
Revises: 2eea4468d2ce
Create Date: 2026-01-15 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'v1y2o3s4r5t6'
down_revision: Union[str, None] = '2eea4468d2ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create router_status enum - use postgresql dialect for proper handling
    from sqlalchemy.dialects import postgresql
    router_status = postgresql.ENUM('pending', 'creating', 'running', 'stopped', 'error', name='routerstatus', create_type=False)
    router_status.create(op.get_bind(), checkfirst=True)

    # Create range_routers table
    op.create_table(
        'range_routers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('range_id', sa.UUID(), nullable=False),
        sa.Column('container_id', sa.String(64), nullable=True),
        sa.Column('management_ip', sa.String(15), nullable=True),
        sa.Column('status', postgresql.ENUM('pending', 'creating', 'running', 'stopped', 'error', name='routerstatus', create_type=False), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['range_id'], ['ranges.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('range_id')
    )
    op.create_index(op.f('ix_range_routers_range_id'), 'range_routers', ['range_id'], unique=True)

    # Add internet_enabled column to networks
    op.add_column('networks', sa.Column('internet_enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')))

    # Add vyos_interface column to networks
    op.add_column('networks', sa.Column('vyos_interface', sa.String(10), nullable=True))


def downgrade() -> None:
    # Remove columns from networks
    op.drop_column('networks', 'vyos_interface')
    op.drop_column('networks', 'internet_enabled')

    # Drop range_routers table
    op.drop_index(op.f('ix_range_routers_range_id'), table_name='range_routers')
    op.drop_table('range_routers')

    # Drop router_status enum
    from sqlalchemy.dialects import postgresql
    postgresql.ENUM('pending', 'creating', 'running', 'stopped', 'error', name='routerstatus').drop(op.get_bind(), checkfirst=True)
