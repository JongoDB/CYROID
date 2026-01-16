# backend/alembic/versions/w2x3y4z5a6b7_add_dns_search_and_dhcp.py
"""Add dns_search and dhcp_enabled to networks

Revision ID: w2x3y4z5a6b7
Revises: v1y2o3s4r5t6
Create Date: 2026-01-16 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'w2x3y4z5a6b7'
down_revision: Union[str, None] = 'v1y2o3s4r5t6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add dns_search column to networks (search domain like "corp.local")
    op.add_column('networks', sa.Column('dns_search', sa.String(255), nullable=True))

    # Add dhcp_enabled column to networks (VyOS DHCP server for this network)
    op.add_column('networks', sa.Column('dhcp_enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')))


def downgrade() -> None:
    op.drop_column('networks', 'dhcp_enabled')
    op.drop_column('networks', 'dns_search')
