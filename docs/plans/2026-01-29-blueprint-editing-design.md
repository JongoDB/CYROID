# Blueprint Editing Feature Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable editing blueprints through two paths: updating from modified range instances, and direct config editing.

**Architecture:** Three-phase approach - (1) Update Blueprint via Range button, (2) JSON config editor modal, (3) Full visual editor page. Each phase is independently useful.

**Tech Stack:** React, FastAPI, Pydantic validation, optional Monaco editor for JSON editing.

---

## Phase 1: Update Blueprint via Range

### Overview
When a range was deployed from a blueprint (tracked via `RangeInstance`), show an "Update Blueprint" button that pushes the current range configuration back to the source blueprint.

### UI Changes

**RangeDetail.tsx:**
- Add state to track if range is a blueprint instance
- Fetch instance info via new API field or separate call
- Show "Update Blueprint" button when `blueprintInstanceInfo` exists
- Keep existing "Save as Blueprint" for creating new blueprints

**New Component - UpdateBlueprintModal.tsx:**
```
┌─────────────────────────────────────────────┐
│ Update Blueprint                            │
├─────────────────────────────────────────────┤
│                                             │
│ Update "Red Team Lab" to version 3?         │
│                                             │
│ Current instances will remain on their      │
│ original versions until redeployed.         │
│                                             │
│ Changes:                                    │
│ • 3 networks (was 2)                        │
│ • 5 VMs (was 4)                             │
│                                             │
│              [Cancel]  [Update Blueprint]   │
└─────────────────────────────────────────────┘
```

### API Changes

**New endpoint:**
```
PUT /blueprints/{blueprint_id}/update-from-range/{range_id}
```

Request: (empty body - uses range state)

Response:
```json
{
  "id": "uuid",
  "name": "Red Team Lab",
  "version": 3,
  "previous_version": 2,
  "updated_at": "2026-01-29T..."
}
```

**Extend Range response:**
Add `blueprint_instance` field to `RangeDetailResponse`:
```python
class BlueprintInstanceInfo(BaseModel):
    instance_id: UUID
    blueprint_id: UUID
    blueprint_name: str
    blueprint_version: int
    current_blueprint_version: int  # To show if outdated

class RangeDetailResponse(BaseModel):
    # ... existing fields ...
    blueprint_instance: Optional[BlueprintInstanceInfo] = None
```

### Backend Implementation

**api/blueprints.py - new endpoint:**
```python
@router.put("/{blueprint_id}/update-from-range/{range_id}")
def update_blueprint_from_range(
    blueprint_id: UUID,
    range_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    # Verify blueprint exists and user has permission
    blueprint = db.query(RangeBlueprint).filter(RangeBlueprint.id == blueprint_id).first()
    if not blueprint:
        raise HTTPException(404, "Blueprint not found")

    # Verify range exists and is an instance of this blueprint
    instance = db.query(RangeInstance).filter(
        RangeInstance.blueprint_id == blueprint_id,
        RangeInstance.range_id == range_id,
    ).first()
    if not instance:
        raise HTTPException(400, "Range is not an instance of this blueprint")

    # Extract new config from range
    new_config = extract_config_from_range(db, range_id)

    # Update blueprint
    blueprint.config = new_config.model_dump()
    blueprint.version += 1
    blueprint.updated_at = datetime.utcnow()

    db.commit()
    return {...}
```

---

## Phase 2: JSON Config Editor

### Overview
Add an "Edit" button on BlueprintDetail that opens a modal with a JSON/YAML editor for direct config modification.

### UI Changes

**BlueprintDetail.tsx:**
- Add "Edit" button in header actions
- Add state for edit modal

**New Component - EditBlueprintConfigModal.tsx:**
```
┌─────────────────────────────────────────────────────┐
│ Edit Blueprint Configuration                    [X] │
├─────────────────────────────────────────────────────┤
│ [JSON] [YAML]                        [Validate]     │
├─────────────────────────────────────────────────────┤
│ {                                                   │
│   "networks": [                                     │
│     {                                               │
│       "name": "Corporate",                          │
│       "subnet": "10.100.1.0/24",                    │
│       "gateway": "10.100.1.1",                      │
│       "is_isolated": false                          │
│     }                                               │
│   ],                                                │
│   "vms": [                                          │
│     {                                               │
│       "hostname": "dc01",                           │
│       "ip_address": "10.100.1.10",                  │
│       ...                                           │
│                                                     │
├─────────────────────────────────────────────────────┤
│ ✓ Configuration valid                               │
│                                                     │
│                    [Cancel]  [Save & Increment Ver] │
└─────────────────────────────────────────────────────┘
```

### Dependencies
- `@monaco-editor/react` or `react-simple-code-editor` for syntax highlighting
- `js-yaml` for JSON/YAML conversion

### API Changes

**New validation endpoint:**
```
POST /blueprints/validate-config
```

Request:
```json
{
  "config": { ... BlueprintConfig ... }
}
```

Response:
```json
{
  "valid": true,
  "errors": [],
  "warnings": [
    "base_image_id 'abc-123' not found - will need to exist on import"
  ]
}
```

**Extend existing update endpoint:**
```
PUT /blueprints/{id}
```

Add `config` to `BlueprintUpdate` schema:
```python
class BlueprintUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    content_ids: Optional[List[str]] = None
    config: Optional[BlueprintConfig] = None  # NEW
```

When config is updated, increment version.

### Validation Rules

**Networks:**
- Valid CIDR format for subnet
- Valid IP for gateway (within subnet)
- Unique network names

**VMs:**
- Required: hostname, at least one network reference
- IP addresses within referenced network subnet
- Valid resource values (cpu > 0, ram_mb > 0, disk_gb > 0)

**References (warnings, not errors):**
- base_image_id exists in database
- base_image_name/tag can be resolved
- network_name references exist in networks list

---

## Phase 3: Visual Blueprint Editor (Future)

### Overview
Full visual editor at `/blueprints/{id}/edit` with canvas-based network topology, similar to RangeDetail but operating on config JSON instead of live resources.

### Page Structure
```
┌─────────────────────────────────────────────────────────────┐
│ ← Back to Blueprint    "Red Team Lab" (Editing)    [Save]   │
├─────────────────────────────────────────────────────────────┤
│ [Networks] [VMs] [MSEL] [Raw Config]                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐   │
│  │ Corporate   │     │ DMZ         │     │ Attack      │   │
│  │ 10.100.1.0  │     │ 10.100.2.0  │     │ 10.100.3.0  │   │
│  │ [Edit][Del] │     │ [Edit][Del] │     │ [Edit][Del] │   │
│  └─────────────┘     └─────────────┘     └─────────────┘   │
│                                                             │
│  [+ Add Network]                                            │
│                                                             │
│  VMs:                                                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ dc01          10.100.1.10    Windows Server  [Edit]  │  │
│  │ web01         10.100.2.10    Ubuntu 22.04    [Edit]  │  │
│  │ kali          10.100.3.10    Kali Linux      [Edit]  │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  [+ Add VM]                                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Reusable Components from RangeDetail
- Network display cards (adapt for config editing)
- VM display cards (adapt for config editing)
- Multi-NIC editor modal
- Canvas positioning (if used)

### New Components
- `BlueprintEditor.tsx` - Main page
- `BlueprintNetworkEditor.tsx` - Add/edit network in config
- `BlueprintVMEditor.tsx` - Add/edit VM in config
- State management for unsaved changes

### Key Differences from RangeDetail
| Aspect | RangeDetail | BlueprintEditor |
|--------|-------------|-----------------|
| Data source | DB records (Range, Network, VM) | JSON config |
| Actions | Deploy, Start, Stop, Console | Save config only |
| Validation | Live Docker checks | Schema validation |
| Status | Container states | N/A |
| Save | Immediate to DB | Batch save to config |

---

## Implementation Order

| Task | Phase | Description | Files |
|------|-------|-------------|-------|
| 1 | 1 | Add blueprint_instance to Range response | api/ranges.py, schemas/range.py |
| 2 | 1 | Create update-from-range endpoint | api/blueprints.py |
| 3 | 1 | Add UpdateBlueprintModal component | components/blueprints/ |
| 4 | 1 | Integrate into RangeDetail | pages/RangeDetail.tsx |
| 5 | 2 | Add config to BlueprintUpdate schema | schemas/blueprint.py |
| 6 | 2 | Create validate-config endpoint | api/blueprints.py |
| 7 | 2 | Create EditBlueprintConfigModal | components/blueprints/ |
| 8 | 2 | Integrate into BlueprintDetail | pages/BlueprintDetail.tsx |
| 9 | 3 | Create BlueprintEditor page | pages/BlueprintEditor.tsx |
| 10 | 3 | Create network/VM editor components | components/blueprint-editor/ |

---

## Test Plan

### Phase 1 Tests
- [ ] Deploy instance from blueprint
- [ ] Modify range (add network, add VM, change IPs)
- [ ] Click "Update Blueprint"
- [ ] Verify blueprint version incremented
- [ ] Verify new config matches range
- [ ] Deploy new instance - verify it has updated config

### Phase 2 Tests
- [ ] Open JSON editor on blueprint
- [ ] Modify config (change IP, add VM)
- [ ] Click Validate - verify success
- [ ] Save - verify version incremented
- [ ] Introduce invalid config - verify validation errors shown
- [ ] Test YAML toggle

### Phase 3 Tests
- [ ] Navigate to visual editor
- [ ] Add/edit/remove network
- [ ] Add/edit/remove VM
- [ ] Save changes
- [ ] Verify config updated correctly

---

*Created: 2026-01-29*
