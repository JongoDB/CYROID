# Walkthrough Export/Import Design

**Date**: 2026-01-23
**Status**: Approved
**Author**: Claude + Steven

## Overview

Add walkthrough (Content Library student guide) export/import support to the range export service, enabling fully portable labs with training materials included.

## Requirements

1. Export range with linked walkthrough includes full Content Library entry
2. Import supports content reuse via title + content hash matching
3. If title exists but content differs, create new entry with modified title

## Schema Changes

### New Schema (`schemas/export.py`)

```python
class WalkthroughExportData(BaseModel):
    """Student guide/walkthrough for export."""
    title: str
    description: Optional[str] = None
    content_type: str = "student_guide"
    body_markdown: str = ""
    walkthrough_data: Optional[dict] = None
    version: str = "1.0"
    tags: List[str] = []
    content_hash: str  # SHA256 of walkthrough_data JSON
```

### Updated Schemas

**ExportComponents**: Add `walkthrough: bool = False`

**ExportRequest**: Add `include_walkthrough: bool = True`

**RangeExportFull**: Add `walkthrough: Optional[WalkthroughExportData] = None`

**ImportOptions**: Add `skip_walkthrough: bool = False`

**ImportSummary**: Add `walkthrough_status: Optional[str] = None`

**ImportResult**: Add `walkthrough_imported: bool = False`, `walkthrough_reused: bool = False`

## Export Logic

In `_build_export_data()`:

1. Check if `range_obj.student_guide_id` is set
2. Load the Content entry from database
3. Compute SHA256 hash of `walkthrough_data` (JSON with sorted keys)
4. Create `WalkthroughExportData` with all fields + hash
5. Include in `RangeExportFull.walkthrough`

## Import Logic

In `import_range()`:

1. If `export_data.walkthrough` exists and not `skip_walkthrough`:
2. Query for existing Content by title + content_type=STUDENT_GUIDE
3. If found:
   - Compute hash of existing walkthrough_data
   - If hashes match: reuse existing Content (set `content_id = existing.id`)
   - If hashes differ: create new with title suffix "(imported YYYY-MM-DD HH:MM)"
4. If not found: create new Content entry
5. Set `new_range.student_guide_id = content_id`

## Validation

In `validate_import()`:

1. Check for existing walkthrough by title
2. Compare hashes to determine status
3. Add warning if title exists with different content
4. Set `walkthrough_status` in ImportSummary: "reuse_existing", "create_new", "create_renamed", or None

## Testing

1. Export with walkthrough - verify JSON structure and hash
2. Export without walkthrough - verify null
3. Import no existing - creates new Content
4. Import exact match - reuses existing (no duplicate)
5. Import title match, content differs - creates renamed
6. Import with skip_walkthrough - ignores walkthrough
7. Round-trip - export → import → verify Student Lab works

## Files to Modify

- `backend/cyroid/schemas/export.py` - Add schemas
- `backend/cyroid/services/export_service.py` - Export/import logic
- `backend/cyroid/models/content.py` - Import for ContentType enum
