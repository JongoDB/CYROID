"""add vm_networks table for multi-NIC support

Revision ID: m1n2i3c4r5a6
Revises: 847984248700
Create Date: 2026-01-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'm1n2i3c4r5a6'
down_revision: Union[str, None] = '847984248700'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create vm_networks table for multi-NIC support
    op.create_table('vm_networks',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('vm_id', sa.Uuid(), nullable=False),
        sa.Column('network_id', sa.Uuid(), nullable=False),
        sa.Column('ip_address', sa.String(15), nullable=False),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['network_id'], ['networks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['vm_id'], ['vms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('network_id', 'ip_address', name='uq_network_ip'),
        sa.UniqueConstraint('vm_id', 'network_id', name='uq_vm_network')
    )

    # Migrate existing VM network assignments
    # Copy each VM's network_id and ip_address into vm_networks as primary interface
    op.execute("""
        INSERT INTO vm_networks (id, vm_id, network_id, ip_address, is_primary, created_at)
        SELECT gen_random_uuid(), id, network_id, ip_address, true, created_at
        FROM vms
        WHERE network_id IS NOT NULL AND ip_address IS NOT NULL
    """)


def downgrade() -> None:
    op.drop_table('vm_networks')
