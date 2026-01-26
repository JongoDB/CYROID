# backend/alembic/versions/1d6b0b3f106c_add_notifications_table.py
"""Add notifications table

Revision ID: 1d6b0b3f106c
Revises: c4o5n6t7e8n9
Create Date: 2026-01-26 01:07:58.996545

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1d6b0b3f106c'
down_revision: Union[str, None] = 'c4o5n6t7e8n9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create notifications table
    op.create_table('notifications',
        sa.Column('notification_type', sa.Enum(
            'RANGE_DEPLOYED', 'RANGE_STARTED', 'RANGE_STOPPED', 'RANGE_DELETED',
            'VM_STARTED', 'VM_STOPPED', 'VM_ERROR',
            'EVENT_SCHEDULED', 'EVENT_STARTING', 'EVENT_STARTED', 'EVENT_COMPLETED', 'EVENT_CANCELLED',
            'INJECT_AVAILABLE', 'INJECT_EXECUTED',
            'EVIDENCE_SUBMITTED', 'SCORE_UPDATED',
            'USER_CREATED', 'USER_APPROVED',
            'SYSTEM_ALERT', 'INFO',
            name='notificationtype'
        ), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('severity', sa.Enum('INFO', 'WARNING', 'ERROR', 'SUCCESS', name='notificationseverity'), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('target_role', sa.String(length=50), nullable=True),
        sa.Column('resource_type', sa.String(length=50), nullable=True),
        sa.Column('resource_id', sa.Uuid(), nullable=True),
        sa.Column('source_event_id', sa.Uuid(), nullable=True),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['source_event_id'], ['event_logs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_notifications_created_at', 'notifications', ['created_at'], unique=False)
    op.create_index('ix_notifications_resource', 'notifications', ['resource_type', 'resource_id'], unique=False)
    op.create_index('ix_notifications_target_role', 'notifications', ['target_role'], unique=False)
    op.create_index('ix_notifications_user_id', 'notifications', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_notifications_user_id', table_name='notifications')
    op.drop_index('ix_notifications_target_role', table_name='notifications')
    op.drop_index('ix_notifications_resource', table_name='notifications')
    op.drop_index('ix_notifications_created_at', table_name='notifications')
    op.drop_table('notifications')
    op.execute('DROP TYPE IF EXISTS notificationtype')
    op.execute('DROP TYPE IF EXISTS notificationseverity')
