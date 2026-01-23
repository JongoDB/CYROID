# Design: Link Content Library to Ranges for Student Lab

**Date:** 2026-01-23
**Status:** Approved
**Issue:** #96

## Overview

Enable range builders to associate content from the Content Library with ranges, so that the selected student guide is displayed in the Student Lab view.

## Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Where to select guide | Both creation wizard AND settings page | Maximum flexibility |
| Data relationship | Single guide per range | Simple, Student Lab shows one walkthrough |
| Backward compatibility | None - migrate existing data | Only one existing walkthrough, clean break |
| UI location | New "Training" tab in Range Detail | Room to grow, separation of concerns |
| Content structure | Add JSON field to Content model | Explicit, no parsing magic |
| Editor UX | Hybrid visual builder + YAML toggle | Approachable for instructors, power mode for devs |

## Future Enhancements (Out of Scope)

- Multiple content items per range (instructor notes, reference materials, etc.)
- VM dropdown in editor populated from actual range VMs

---

## Data Model Changes

### Content Model

Add `walkthrough_data` JSON field for structured walkthrough content:

```python
# backend/cyroid/models/content.py
class Content(Base, UUIDMixin, TimestampMixin):
    # ... existing fields ...

    # Structured walkthrough data (for student_guide type)
    walkthrough_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
```

**Walkthrough data structure:**

```json
{
  "title": "Lab Title",
  "phases": [
    {
      "id": "phase1",
      "name": "Phase Name",
      "steps": [
        {
          "id": "step1_1",
          "title": "Step Title",
          "vm": "kali",
          "hints": ["Optional hint 1"],
          "content": "Markdown content..."
        }
      ]
    }
  ]
}
```

### Range Model

Add `student_guide_id` foreign key to Content:

```python
# backend/cyroid/models/range.py
class Range(Base, UUIDMixin, TimestampMixin):
    # ... existing fields ...

    # Training content link
    student_guide_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("content.id", ondelete="SET NULL"), nullable=True
    )
    student_guide = relationship("Content", foreign_keys=[student_guide_id])
```

### Database Migration

```python
# alembic migration
def upgrade():
    # Add walkthrough_data to content table
    op.add_column('content', sa.Column('walkthrough_data', sa.JSON(), nullable=True))

    # Add student_guide_id to ranges table
    op.add_column('ranges', sa.Column('student_guide_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_ranges_student_guide_id',
        'ranges', 'content',
        ['student_guide_id'], ['id'],
        ondelete='SET NULL'
    )
```

---

## API Changes

### Update Walkthrough API

Change from MSEL-based to Content Library-based:

```python
# backend/cyroid/api/walkthrough.py

@router.get("/{range_id}/walkthrough", response_model=WalkthroughResponse)
def get_walkthrough(
    range_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the walkthrough content for a range from Content Library."""
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(status_code=404, detail="Range not found")

    # Fetch from Content Library via student_guide relationship
    if range_obj.student_guide_id:
        content = db.query(Content).filter(Content.id == range_obj.student_guide_id).first()
        if content and content.walkthrough_data:
            return WalkthroughResponse(walkthrough=content.walkthrough_data)

    return WalkthroughResponse(walkthrough=None)
```

### Update Range API

Add endpoint to set/update student guide:

```python
# backend/cyroid/api/ranges.py

class SetStudentGuideRequest(BaseModel):
    student_guide_id: Optional[UUID] = None

@router.patch("/{range_id}/student-guide")
def set_student_guide(
    range_id: UUID,
    data: SetStudentGuideRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Associate a student guide from Content Library with this range."""
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(status_code=404, detail="Range not found")

    # Validate content exists and is published student_guide type
    if data.student_guide_id:
        content = db.query(Content).filter(Content.id == data.student_guide_id).first()
        if not content:
            raise HTTPException(status_code=404, detail="Content not found")
        if content.content_type != ContentType.STUDENT_GUIDE:
            raise HTTPException(status_code=400, detail="Content must be student_guide type")

    range_obj.student_guide_id = data.student_guide_id
    db.commit()

    return {"student_guide_id": data.student_guide_id}
```

Also update Range response schema to include `student_guide_id`.

### Update Content API

Add endpoint to list published student guides:

```python
# backend/cyroid/api/content.py

@router.get("/student-guides/available", response_model=List[ContentListResponse])
def list_available_student_guides(
    db: DBSession,
    current_user: CurrentUser,
):
    """List published student guides for range assignment."""
    return db.query(Content).filter(
        Content.content_type == ContentType.STUDENT_GUIDE,
        Content.is_published == True
    ).order_by(Content.title).all()
```

---

## Frontend Changes

### New Component: TrainingTab

Location: `frontend/src/components/range/TrainingTab.tsx`

```typescript
interface TrainingTabProps {
  rangeId: string
  studentGuideId: string | null
  onUpdate: () => void
}

export function TrainingTab({ rangeId, studentGuideId, onUpdate }: TrainingTabProps) {
  const [guides, setGuides] = useState<Content[]>([])
  const [selectedGuideId, setSelectedGuideId] = useState(studentGuideId)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    contentApi.listStudentGuides().then(res => {
      setGuides(res.data)
      setLoading(false)
    })
  }, [])

  useEffect(() => {
    setSelectedGuideId(studentGuideId)
  }, [studentGuideId])

  const handleSave = async () => {
    setSaving(true)
    try {
      await rangesApi.setStudentGuide(rangeId, selectedGuideId)
      onUpdate()
      toast.success('Student guide updated')
    } catch (err) {
      toast.error('Failed to update student guide')
    } finally {
      setSaving(false)
    }
  }

  const hasChanges = selectedGuideId !== studentGuideId

  return (
    <div className="p-6 space-y-6">
      <div>
        <h3 className="text-lg font-medium text-gray-900">Student Lab Guide</h3>
        <p className="text-sm text-gray-500 mt-1">
          Select content from the Content Library to display in the Student Lab view.
        </p>
      </div>

      <div className="max-w-md">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Student Guide
        </label>
        <select
          value={selectedGuideId || ''}
          onChange={(e) => setSelectedGuideId(e.target.value || null)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-primary-500"
          disabled={loading}
        >
          <option value="">None selected</option>
          {guides.map(guide => (
            <option key={guide.id} value={guide.id}>
              {guide.title} (v{guide.version})
            </option>
          ))}
        </select>
      </div>

      <div className="flex items-center gap-4">
        <button
          onClick={handleSave}
          disabled={!hasChanges || saving}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save'}
        </button>
        <Link
          to="/content/new?type=student_guide"
          className="text-primary-600 hover:underline text-sm"
        >
          + Create new guide
        </Link>
      </div>

      {/* Preview section */}
      {selectedGuideId && (
        <div className="border rounded-lg p-4 bg-gray-50 mt-6">
          <h4 className="font-medium text-gray-900 mb-2">Preview</h4>
          <WalkthroughPreview contentId={selectedGuideId} />
        </div>
      )}
    </div>
  )
}
```

### Update RangeDetail.tsx

Add Training tab:

```typescript
// Update tab type
const [activeTab, setActiveTab] = useState<'builder' | 'training' | 'diagnostics' | 'activity'>('builder')

// Add tab button in tab bar
<button
  onClick={() => setActiveTab('training')}
  className={clsx(
    'flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-t-lg',
    activeTab === 'training'
      ? 'bg-white text-primary-600 border-t border-l border-r'
      : 'text-gray-500 hover:text-gray-700'
  )}
>
  <BookOpen className="w-4 h-4" />
  Training
</button>

// Add tab content
{activeTab === 'training' && (
  <TrainingTab
    rangeId={id!}
    studentGuideId={range.student_guide_id}
    onUpdate={loadRange}
  />
)}
```

### New Component: WalkthroughEditor

Location: `frontend/src/components/content/WalkthroughEditor.tsx`

Hybrid visual builder with YAML toggle for student_guide content type.

**Main component:**
- Mode toggle (Visual / YAML)
- Visual mode: drag-drop phases/steps with inline markdown editors
- YAML mode: CodeMirror/Monaco editor with live validation

**Sub-components:**
- `PhaseEditor` - Collapsible phase with step list
- `StepEditor` - Step with title, VM selector, markdown content
- `YamlEditor` - YAML editing with parse error display

### Update ContentEditor.tsx

Show WalkthroughEditor when content_type is student_guide:

```typescript
{contentType === 'student_guide' && (
  <div className="mt-6">
    <label className="block text-sm font-medium text-gray-700 mb-2">
      Walkthrough Structure
    </label>
    <WalkthroughEditor
      value={walkthroughData}
      onChange={setWalkthroughData}
    />
  </div>
)}
```

### Update API Service

Add new API calls:

```typescript
// frontend/src/services/api.ts

export const contentApi = {
  // ... existing methods ...

  listStudentGuides: () =>
    api.get<Content[]>('/content/student-guides/available'),
}

export const rangesApi = {
  // ... existing methods ...

  setStudentGuide: (rangeId: string, studentGuideId: string | null) =>
    api.patch(`/ranges/${rangeId}/student-guide`, { student_guide_id: studentGuideId }),
}
```

### Update Types

```typescript
// frontend/src/types/index.ts

export interface Range {
  // ... existing fields ...
  student_guide_id?: string | null
}

export interface WalkthroughData {
  title: string
  phases: WalkthroughPhase[]
}

export interface WalkthroughPhase {
  id: string
  name: string
  steps: WalkthroughStep[]
}

export interface WalkthroughStep {
  id: string
  title: string
  vm?: string
  hints?: string[]
  content: string
}
```

---

## Migration Plan

### Migration Script

```python
# scripts/migrate_walkthrough_to_content.py

from cyroid.models.content import Content, ContentType
from cyroid.models.msel import MSEL
from cyroid.models.range import Range

def migrate_msel_walkthrough_to_content(db):
    """Migrate existing MSEL walkthroughs to Content Library."""

    msels_with_walkthrough = db.query(MSEL).filter(
        MSEL.walkthrough.isnot(None)
    ).all()

    migrated = 0
    for msel in msels_with_walkthrough:
        range_obj = msel.range
        if not range_obj:
            continue

        # Create Content entry
        content = Content(
            title=f"{range_obj.name} - Student Guide",
            description=f"Migrated walkthrough from {range_obj.name}",
            content_type=ContentType.STUDENT_GUIDE,
            body_markdown="",
            walkthrough_data=msel.walkthrough,
            is_published=True,
            created_by_id=range_obj.created_by,
        )
        db.add(content)
        db.flush()

        # Link to range
        range_obj.student_guide_id = content.id
        migrated += 1

        print(f"Migrated: {range_obj.name} -> Content '{content.title}'")

    db.commit()
    print(f"Migration complete: {migrated} walkthroughs migrated")

if __name__ == "__main__":
    from cyroid.api.deps import get_db
    db = next(get_db())
    migrate_msel_walkthrough_to_content(db)
```

### Post-Migration

1. Run migration script
2. Verify Content Library shows migrated guides
3. Verify Student Lab loads correctly
4. Remove `msel.walkthrough` fallback from walkthrough API
5. Update blueprint import to create Content entry (separate task)

---

## Implementation Order

1. **Database migration** - Add columns to content and ranges tables
2. **Backend models** - Update Content and Range models
3. **Backend API** - Update walkthrough, ranges, and content endpoints
4. **Frontend types** - Update TypeScript interfaces
5. **Frontend API service** - Add new API calls
6. **TrainingTab component** - Build the range settings UI
7. **WalkthroughEditor component** - Build the content editor
8. **Update RangeDetail** - Add Training tab
9. **Update ContentEditor** - Show WalkthroughEditor for student_guide
10. **Migration script** - Migrate existing data
11. **Testing** - End-to-end verification

---

## Testing Checklist

- [ ] Can create student_guide content with walkthrough structure
- [ ] Visual editor allows adding/editing/deleting phases and steps
- [ ] YAML mode parses and validates correctly
- [ ] Can assign student guide to range via Training tab
- [ ] Student Lab displays selected guide content
- [ ] Preview in Training tab shows guide correctly
- [ ] Removing guide (set to None) works
- [ ] Migration script migrates existing walkthrough
- [ ] Published filter works (only published guides in dropdown)
