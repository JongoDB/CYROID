"""Add seed blueprint fields

Revision ID: b1p2s3e4e5d6
Revises: 47632f1ca0b1
Create Date: 2026-01-18 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'b1p2s3e4e5d6'
down_revision = '47632f1ca0b1'
branch_labels = None
depends_on = None


def upgrade():
    # Add is_seed and seed_id columns to range_blueprints
    op.add_column('range_blueprints', sa.Column('is_seed', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('range_blueprints', sa.Column('seed_id', sa.String(100), nullable=True))
    op.create_unique_constraint('uq_range_blueprints_seed_id', 'range_blueprints', ['seed_id'])

    # Make created_by nullable for seed blueprints
    op.alter_column('range_blueprints', 'created_by',
                    existing_type=sa.UUID(),
                    nullable=True)


def downgrade():
    # Make created_by not nullable again (may fail if there are seed blueprints)
    op.alter_column('range_blueprints', 'created_by',
                    existing_type=sa.UUID(),
                    nullable=False)

    op.drop_constraint('uq_range_blueprints_seed_id', 'range_blueprints', type_='unique')
    op.drop_column('range_blueprints', 'seed_id')
    op.drop_column('range_blueprints', 'is_seed')
