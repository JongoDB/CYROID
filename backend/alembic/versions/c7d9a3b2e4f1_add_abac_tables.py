"""add_abac_tables

Revision ID: c7d9a3b2e4f1
Revises: 55ac0fc66160
Create Date: 2026-01-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d9a3b2e4f1'
down_revision: Union[str, None] = '55ac0fc66160'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create user_attributes table
    op.create_table('user_attributes',
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('attribute_type', sa.String(length=50), nullable=False),
        sa.Column('attribute_value', sa.String(length=100), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'attribute_type', 'attribute_value', name='uq_user_attribute')
    )
    op.create_index('ix_user_attributes_user_id', 'user_attributes', ['user_id'])
    op.create_index('ix_user_attributes_type_value', 'user_attributes', ['attribute_type', 'attribute_value'])

    # Create resource_tags table
    op.create_table('resource_tags',
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('resource_id', sa.Uuid(), nullable=False),
        sa.Column('tag', sa.String(length=100), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('resource_type', 'resource_id', 'tag', name='uq_resource_tag')
    )
    op.create_index('ix_resource_tags_lookup', 'resource_tags', ['resource_type', 'resource_id'])
    op.create_index('ix_resource_tags_by_tag', 'resource_tags', ['resource_type', 'tag'])

    # Migrate existing user roles to user_attributes
    # This creates a role attribute for each existing user based on their role column
    op.execute("""
        INSERT INTO user_attributes (id, user_id, attribute_type, attribute_value, created_at, updated_at)
        SELECT gen_random_uuid(), id, 'role', role, created_at, NOW()
        FROM users
    """)


def downgrade() -> None:
    op.drop_index('ix_resource_tags_by_tag', table_name='resource_tags')
    op.drop_index('ix_resource_tags_lookup', table_name='resource_tags')
    op.drop_table('resource_tags')

    op.drop_index('ix_user_attributes_type_value', table_name='user_attributes')
    op.drop_index('ix_user_attributes_user_id', table_name='user_attributes')
    op.drop_table('user_attributes')
