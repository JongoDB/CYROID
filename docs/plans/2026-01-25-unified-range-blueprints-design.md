# Unified Range Blueprints System Design

**Issue**: #131
**Date**: 2026-01-25
**Status**: Approved

## Overview

Consolidate Range Export and Blueprint Export into a single unified Range Blueprints system. This reduces code duplication, simplifies sharing, and provides users modular control over what to include in exports.

## Current State

Two overlapping export systems:
- **Range Export** (v2.0): Modular checkboxes, Docker images, background jobs, artifacts
- **Blueprint Export** (v3.0): Dockerfiles, Content Library assets, simpler format

## Design Decisions

1. **Enhance Blueprint Export** with Range Export's modular approach
2. **Retire Range Export** endpoints
3. **Single "Range Blueprints"** naming convention
4. **v4.0 format** combining best of both systems

## User Flow

1. Range → "Save as Blueprint" → Creates DB record
2. Blueprints page → Click blueprint → "Export" button
3. Export modal → Checkboxes for what to include → ZIP download

---

## Database Changes

### Keep
- `RangeBlueprint` model
- Training Event's `blueprint_id` reference

### Remove from RangeBlueprint
- `base_subnet_prefix` (no longer used)
- `next_offset` (no longer used)

---

## API Changes

### Keep
- `POST /blueprints` - Save range as blueprint
- `GET /blueprints` - List blueprints
- `GET /blueprints/{id}` - Get blueprint details
- `DELETE /blueprints/{id}` - Delete blueprint

### Modify
```
GET /blueprints/{id}/export
  Query params:
    ?include_msel=true
    &include_dockerfiles=true
    &include_docker_images=true
    &include_content=true
    &include_artifacts=true
  Returns: ZIP file (or job ID for large exports)
```

### Remove (Phase 3)
- `GET /ranges/{id}/export`
- `POST /ranges/{id}/export/full`
- `GET /ranges/export/jobs/{job_id}`
- `GET /ranges/export/jobs/{job_id}/download`
- `POST /ranges/import`
- `POST /ranges/import/validate`
- `POST /ranges/import/execute`

### Import Endpoints (Consolidated)
- `POST /blueprints/import/validate` - Validate any format (v2.0, v3.0, v4.0)
- `POST /blueprints/import` - Execute import with conflict strategies
- `POST /blueprints/import/load-images` - Load Docker images (background job)

---

## Export Package Format (v4.0)

```
blueprint-{name}-{timestamp}.zip
├── manifest.json
├── blueprint.json
├── msel/
│   └── scenario.yaml
├── dockerfiles/
│   └── {project}/
│       ├── Dockerfile
│       └── [build context]
├── content/
│   ├── content.json
│   └── assets/
│       └── {hash}_{filename}
├── artifacts/
│   └── {hash}_{filename}
└── docker-images/
    └── {image}.tar
```

### manifest.json
```json
{
  "format_version": "4.0",
  "name": "Blueprint Name",
  "description": "...",
  "created_at": "2026-01-25T12:00:00Z",
  "cyroid_version": "0.27.12",
  "includes": {
    "networks": true,
    "vms": true,
    "msel": true,
    "dockerfiles": ["custom-kali"],
    "content": ["content-id-1"],
    "artifacts": ["artifact-id-1"],
    "docker_images": ["image:tag"]
  },
  "checksums": {
    "blueprint.json": "sha256:...",
    "msel/scenario.yaml": "sha256:..."
  }
}
```

---

## Frontend Changes

### Range Detail Page
- Keep "Save as Blueprint" button
- Remove "Export Range" button

### Blueprints Page
- Rename to "Range Blueprints"
- List view with Export/Delete actions

### Export Blueprint Modal (New)
```
Export Blueprint
────────────────
Include in package:
☑ Network configuration     (always included)
☑ VM definitions            (always included)
☑ MSEL / Scenario injects
☐ Dockerfiles               (2 available)
☐ Content Library items     (1 available)
☐ Artifacts                 (3 available)
☐ Docker images (offline)   ⚠️ ~2.4 GB

[Cancel]  [Export]
```

### Import Blueprint Modal (Enhanced)
- Accept v2.0, v3.0, v4.0 formats
- Show validation results
- Conflict resolution options (Skip/Overwrite/Rename)
- Optional Docker image loading

### Remove
- `ExportRangeDialog.tsx`
- `ImportRangeWizard.tsx`

---

## Implementation Phases

### Phase 1: Backend Consolidation
- [ ] Add query params to `GET /blueprints/{id}/export`
- [ ] Create unified export service
- [ ] Update manifest to v4.0 format
- [ ] Add legacy format detection in import (v2.0, v3.0)
- [ ] Remove `base_subnet_prefix`, `next_offset` columns
- [ ] Mark Range export endpoints as deprecated

### Phase 2: Frontend Consolidation
- [ ] Create `ExportBlueprintModal.tsx` with checkboxes
- [ ] Update `ImportBlueprintModal.tsx` for all formats
- [ ] Remove "Export Range" from Range Detail
- [ ] Remove `ExportRangeDialog.tsx`, `ImportRangeWizard.tsx`
- [ ] Update Blueprints page UI

### Phase 3: Cleanup (Future Release)
- [ ] Remove deprecated Range export endpoints
- [ ] Remove old export service code
- [ ] Update documentation

---

## Files to Modify

### Backend
- `backend/cyroid/api/blueprints.py` - Export params, unified logic
- `backend/cyroid/api/ranges.py` - Deprecate export endpoints
- `backend/cyroid/services/blueprint_service.py` - Enhanced export
- `backend/cyroid/services/range_export_service.py` - Merge into blueprint service
- `backend/cyroid/models/blueprint.py` - Remove unused columns
- `backend/cyroid/schemas/blueprint.py` - v4.0 manifest schema

### Frontend
- `frontend/src/components/blueprints/ExportBlueprintModal.tsx` (new)
- `frontend/src/components/blueprints/ImportBlueprintModal.tsx` (enhance)
- `frontend/src/pages/RangeDetail.tsx` - Remove export button
- `frontend/src/pages/Blueprints.tsx` - UI updates
- `frontend/src/services/api.ts` - Update API methods

### Remove
- `frontend/src/components/export/ExportRangeDialog.tsx`
- `frontend/src/components/import/ImportRangeWizard.tsx`

---

## Backwards Compatibility

- v3.0 Blueprint ZIPs: Importable (auto-detected)
- v2.0 Range Export ZIPs: Importable (converted to blueprint)
- Range export endpoints: Return 410 Gone after Phase 3

---

## Success Criteria

- [ ] Single "Save as Blueprint" → "Export" flow
- [ ] Modular export with checkboxes
- [ ] Single v4.0 ZIP format
- [ ] Import validates and shows conflicts
- [ ] Legacy formats still importable
- [ ] Training Events continue working
- [ ] Range export endpoints deprecated/removed
