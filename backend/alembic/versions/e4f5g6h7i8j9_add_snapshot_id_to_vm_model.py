# backend/alembic/script.py.mako
"""add snapshot_id to vm model

Revision ID: e4f5g6h7i8j9
Revises: 3e5c6dd8470c
Create Date: 2026-01-19 23:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4f5g6h7i8j9'
down_revision: Union[str, None] = '3e5c6dd8470c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make template_id nullable (VMs can now be created from snapshots instead)
    op.alter_column('vms', 'template_id',
               existing_type=sa.UUID(),
               nullable=True)

    # Add snapshot_id column with foreign key to snapshots table
    op.add_column('vms', sa.Column('snapshot_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_vms_snapshot_id',
        'vms', 'snapshots',
        ['snapshot_id'], ['id']
    )


def downgrade() -> None:
    from sqlalchemy import text

    # Remove snapshot_id foreign key and column
    op.drop_constraint('fk_vms_snapshot_id', 'vms', type_='foreignkey')
    op.drop_column('vms', 'snapshot_id')

    # Check if any VMs have null template_id before making it non-nullable
    conn = op.get_bind()
    result = conn.execute(text("SELECT COUNT(*) FROM vms WHERE template_id IS NULL"))
    count = result.scalar()

    if count > 0:
        raise ValueError(
            f"Cannot downgrade: {count} VMs exist with null template_id. "
            "Delete these VMs or assign templates before downgrading."
        )

    # Make template_id not nullable again (safe if check passed)
    op.alter_column('vms', 'template_id',
               existing_type=sa.UUID(),
               nullable=False)
