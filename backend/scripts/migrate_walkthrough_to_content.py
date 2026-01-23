#!/usr/bin/env python3
"""
Migration script to move walkthrough data from MSELs to Content Library.

This script:
1. Finds all MSELs with walkthrough data
2. Creates Content entries from that walkthrough data
3. Links the corresponding range to the new content via student_guide_id
4. Publishes the content automatically

Run with: docker compose exec api python scripts/migrate_walkthrough_to_content.py
"""

import os
import sys

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable not set")
    sys.exit(1)

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
db = Session()

try:
    from cyroid.models.msel import MSEL
    from cyroid.models.range import Range
    from cyroid.models.content import Content, ContentType
    from cyroid.models.user import User

    # Get admin user for created_by
    admin_user = db.query(User).filter(User.username == "admin").first()
    if not admin_user:
        print("ERROR: Admin user not found")
        sys.exit(1)

    print(f"Using admin user: {admin_user.username} (id: {admin_user.id})")

    # Find all MSELs with walkthrough data
    msels_with_walkthrough = db.query(MSEL).filter(MSEL.walkthrough.isnot(None)).all()

    print(f"\nFound {len(msels_with_walkthrough)} MSELs with walkthrough data")

    migrated = 0
    skipped = 0

    for msel in msels_with_walkthrough:
        print(f"\nProcessing MSEL: {msel.name} (range_id: {msel.range_id})")

        # Get the range
        range_obj = db.query(Range).filter(Range.id == msel.range_id).first()
        if not range_obj:
            print(f"  WARNING: Range not found for MSEL, skipping")
            skipped += 1
            continue

        # Check if range already has a student guide
        if range_obj.student_guide_id:
            print(f"  INFO: Range already has a student guide, skipping")
            skipped += 1
            continue

        # Parse walkthrough data
        walkthrough = msel.walkthrough
        if not walkthrough:
            print(f"  WARNING: Walkthrough data is empty, skipping")
            skipped += 1
            continue

        # Create content entry
        content_title = f"{range_obj.name} - Student Guide"

        # Check if content with same title already exists
        existing_content = db.query(Content).filter(
            Content.title == content_title,
            Content.content_type == ContentType.STUDENT_GUIDE
        ).first()

        if existing_content:
            print(f"  INFO: Content '{content_title}' already exists, linking to range")
            range_obj.student_guide_id = existing_content.id
            db.commit()
            migrated += 1
            continue

        # Create new content
        content = Content(
            title=content_title,
            description=f"Migrated from MSEL: {msel.name}",
            content_type=ContentType.STUDENT_GUIDE,
            body_markdown="",
            walkthrough_data=walkthrough,
            tags=["migrated", "student-guide"],
            created_by_id=admin_user.id,
            is_published=True,  # Auto-publish migrated content
        )

        db.add(content)
        db.flush()  # Get the content ID

        print(f"  Created content: {content.title} (id: {content.id})")

        # Link range to content
        range_obj.student_guide_id = content.id
        db.commit()

        print(f"  Linked range '{range_obj.name}' to student guide")
        migrated += 1

    print(f"\n{'='*50}")
    print(f"Migration complete!")
    print(f"  Migrated: {migrated}")
    print(f"  Skipped: {skipped}")
    print(f"  Total MSELs processed: {len(msels_with_walkthrough)}")

except Exception as e:
    db.rollback()
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    db.close()
