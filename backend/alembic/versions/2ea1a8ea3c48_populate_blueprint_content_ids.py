# backend/alembic/versions/2ea1a8ea3c48_populate_blueprint_content_ids.py
"""populate_blueprint_content_ids

Creates Content entries for existing blueprints with MSEL walkthrough data
and populates their content_ids field. This enables static content references
instead of creating content on each range deployment.

Revision ID: 2ea1a8ea3c48
Revises: 3ab6da971c60
Create Date: 2026-01-26 17:08:45.821695

"""
from typing import Sequence, Union
import json
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '2ea1a8ea3c48'
down_revision: Union[str, None] = '3ab6da971c60'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create Content from MSEL walkthrough and populate blueprint content_ids."""
    bind = op.get_bind()
    session = Session(bind=bind)

    # Get a default user for created_by (first admin user)
    default_user_result = session.execute(text(
        "SELECT id FROM users WHERE role = 'ADMIN' LIMIT 1"
    )).fetchone()
    default_user_id = default_user_result[0] if default_user_result else None

    if not default_user_id:
        # Fall back to any user
        any_user_result = session.execute(text("SELECT id FROM users LIMIT 1")).fetchone()
        default_user_id = any_user_result[0] if any_user_result else None

    if not default_user_id:
        print("No users found, skipping migration")
        return

    # Find blueprints with MSEL walkthrough but no content_ids
    result = session.execute(text("""
        SELECT id, name, config, content_ids, created_by
        FROM range_blueprints
        WHERE config::text LIKE '%walkthrough%'
    """))

    for row in result:
        bp_id = row[0]
        bp_name = row[1]
        config = row[2] if isinstance(row[2], dict) else json.loads(row[2]) if row[2] else {}
        existing_content_ids = row[3] or []
        created_by = row[4] or default_user_id

        # Skip if already has content_ids
        if existing_content_ids:
            continue

        # Get walkthrough from MSEL
        msel = config.get('msel', {})
        walkthrough = msel.get('walkthrough') if msel else None
        if not walkthrough:
            continue

        # Create Content entry
        content_id = str(uuid.uuid4())
        walkthrough_title = walkthrough.get('title', f"{bp_name} - Student Guide")
        walkthrough_json = json.dumps(walkthrough)
        tags_json = json.dumps(['migrated', 'blueprint-walkthrough'])

        session.execute(text("""
            INSERT INTO content (id, title, description, content_type, body_markdown, walkthrough_data,
                                 version, created_by_id, tags, is_published, created_at, updated_at)
            VALUES (:id, :title, :description, 'STUDENT_GUIDE', '', CAST(:walkthrough_data AS jsonb),
                    '1.0', :created_by, CAST(:tags AS jsonb), true, NOW(), NOW())
        """), {
            'id': content_id,
            'title': walkthrough_title,
            'description': f"Migrated from blueprint: {bp_name}",
            'walkthrough_data': walkthrough_json,
            'created_by': str(created_by),
            'tags': tags_json,
        })

        # Update blueprint content_ids and config.content_ids
        new_content_ids = [content_id]
        config['content_ids'] = new_content_ids
        config_json = json.dumps(config)
        content_ids_json = json.dumps(new_content_ids)

        session.execute(text("""
            UPDATE range_blueprints
            SET content_ids = CAST(:content_ids AS jsonb),
                config = CAST(:config AS jsonb)
            WHERE id = :bp_id
        """), {
            'content_ids': content_ids_json,
            'config': config_json,
            'bp_id': str(bp_id),
        })

        print(f"Migrated blueprint '{bp_name}': created Content {content_id}")

    session.commit()


def downgrade() -> None:
    """Remove migrated content - Note: This doesn't restore original state."""
    bind = op.get_bind()
    session = Session(bind=bind)

    # Delete content with 'migrated' tag
    session.execute(text("""
        DELETE FROM content
        WHERE tags::text LIKE '%migrated%'
        AND tags::text LIKE '%blueprint-walkthrough%'
    """))

    # Clear content_ids from blueprints (can't fully restore original config)
    session.execute(text("""
        UPDATE range_blueprints
        SET content_ids = '[]'::jsonb
        WHERE content_ids IS NOT NULL AND content_ids != '[]'::jsonb
    """))

    session.commit()
