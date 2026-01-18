"""Add deployment event types to EventType enum

Revision ID: d8e9f0a1b2c3
Revises: c7c4ced81dd3
Create Date: 2024-01-18

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'd8e9f0a1b2c3'
down_revision = 'c7c4ced81dd3'
branch_labels = None
depends_on = None


def upgrade():
    """Add missing EventType enum values for deployment progress tracking."""
    # These values were added to the Python EventType enum but not to the database
    # They are required for range deployment to work properly
    # Note: Existing enum values use uppercase (RANGE_DEPLOYED, VM_CREATED, etc.)
    op.execute("ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'DEPLOYMENT_STARTED'")
    op.execute("ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'DEPLOYMENT_STEP'")
    op.execute("ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'DEPLOYMENT_COMPLETED'")
    op.execute("ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'DEPLOYMENT_FAILED'")
    op.execute("ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'ROUTER_CREATING'")
    op.execute("ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'ROUTER_CREATED'")
    op.execute("ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'NETWORK_CREATING'")
    op.execute("ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'NETWORK_CREATED'")
    op.execute("ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'VM_CREATING'")


def downgrade():
    # PostgreSQL doesn't support removing enum values directly
    # To downgrade, would need to:
    # 1. Create new enum type without these values
    # 2. Update column to use new type
    # 3. Drop old type
    # This is complex and typically not done for enum additions
    pass
