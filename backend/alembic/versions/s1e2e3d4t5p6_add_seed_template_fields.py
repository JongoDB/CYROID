"""Add seed template identification fields

Revision ID: s1e2e3d4t5p6
Revises: fd5d01a50586
Create Date: 2026-01-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 's1e2e3d4t5p6'
down_revision: Union[str, None] = 'fd5d01a50586'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_seed column (boolean, default False)
    op.add_column('vm_templates', sa.Column('is_seed', sa.Boolean(), nullable=False, server_default='false'))

    # Add seed_id column (unique identifier for built-in templates)
    op.add_column('vm_templates', sa.Column('seed_id', sa.String(100), nullable=True))
    op.create_unique_constraint('uq_vm_templates_seed_id', 'vm_templates', ['seed_id'])

    # Make created_by nullable (for seed templates without a creator)
    op.alter_column('vm_templates', 'created_by',
                    existing_type=sa.UUID(),
                    nullable=True)


def downgrade() -> None:
    # Restore created_by to non-nullable (will fail if null values exist)
    op.alter_column('vm_templates', 'created_by',
                    existing_type=sa.UUID(),
                    nullable=False)

    op.drop_constraint('uq_vm_templates_seed_id', 'vm_templates', type_='unique')
    op.drop_column('vm_templates', 'seed_id')
    op.drop_column('vm_templates', 'is_seed')
