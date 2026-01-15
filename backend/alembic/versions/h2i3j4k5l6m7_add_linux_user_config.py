"""add linux user config

Revision ID: h2i3j4k5l6m7
Revises: g1h2i3j4k5l6
Create Date: 2026-01-15 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'h2i3j4k5l6m7'
down_revision: Union[str, None] = 'g1h2i3j4k5l6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add Linux user configuration fields
    op.add_column('vms', sa.Column('linux_username', sa.String(length=64), nullable=True))
    op.add_column('vms', sa.Column('linux_password', sa.String(length=128), nullable=True))
    op.add_column('vms', sa.Column('linux_user_sudo', sa.Boolean(), nullable=True, server_default='true'))


def downgrade() -> None:
    op.drop_column('vms', 'linux_user_sudo')
    op.drop_column('vms', 'linux_password')
    op.drop_column('vms', 'linux_username')
