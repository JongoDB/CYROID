# Self-Contained Blueprints Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:writing-plans to create the implementation plan after this design is approved.

**Goal:** Make blueprints fully self-contained and reproducible - when imported, automatically acquire any missing images via registry pull, Dockerfile build, or ISO download.

**Problem:** Catalog/Storefront blueprints reference images that may not exist locally, with no way to acquire them automatically.

**Solution:** Explicit image manifest in blueprints declaring how to acquire each image, with interactive import flow.

---

## Image Manifest Schema

Each blueprint includes an `images` array declaring every required image:

```json
{
  "images": [
    {
      "name": "kali-linux",
      "source": "registry",
      "registry_image": "docker.io/kalilinux/kali-rolling:latest",
      "description": "Kali Linux for penetration testing"
    },
    {
      "name": "custom-webapp",
      "source": "dockerfile",
      "project_name": "vulnerable-webapp",
      "dockerfile_path": "dockerfiles/vulnerable-webapp/",
      "description": "Custom vulnerable web application"
    },
    {
      "name": "windows-server-2022",
      "source": "iso",
      "iso_name": "Windows Server 2022",
      "iso_filename": "windows_server_2022.iso",
      "vm_type": "dockur",
      "description": "Windows Server 2022 for AD exercises"
    }
  ],

  "vms": [
    {
      "hostname": "attacker",
      "image_ref": "kali-linux",
      "ip_address": "10.0.0.10",
      "network_name": "range-net"
    }
  ]
}
```

### Source Types

| Source | Description | Data Location |
|--------|-------------|---------------|
| `registry` | Pull from Docker registry | `registry_image` field |
| `dockerfile` | Build from embedded Dockerfile | `dockerfiles/{project_name}/` in archive |
| `iso` | Download ISO via ISO manager | `iso_name` references known ISO |

### VM References

VMs reference images by `image_ref` name (string) instead of UUIDs. This enables:
- Cross-environment portability
- Clear mapping to image manifest
- No UUID conflicts on import

---

## Import Flow

### Step 1: Validation & Analysis

```python
# ImageResolver.analyze(blueprint) returns:
{
  "available": [
    {"name": "kali-linux", "source": "registry", "status": "exists"}
  ],
  "missing": [
    {"name": "ubuntu-server", "source": "registry", "size_bytes": 1200000000},
    {"name": "vulnerable-webapp", "source": "dockerfile", "estimated_build_time": 300},
    {"name": "Windows Server 2022", "source": "iso", "size_bytes": 5400000000}
  ],
  "total_download_bytes": 6600000000,
  "estimated_time_seconds": 900
}
```

### Step 2: Interactive Prompt

UI displays acquisition plan before proceeding:

```
┌─────────────────────────────────────────────────────────┐
│  Import: Red Team Training Lab                          │
├─────────────────────────────────────────────────────────┤
│  This blueprint requires the following:                 │
│                                                         │
│  ✅ kali-linux          (already available)             │
│  ⬇️  ubuntu-server       Pull from Docker Hub  [1.2 GB] │
│  🔨 vulnerable-webapp   Build from Dockerfile  [~5 min] │
│  💿 Windows Server 2022 Download ISO          [5.4 GB]  │
│                                                         │
│  Total download: ~6.6 GB                                │
│  Estimated time: ~15 minutes                            │
│                                                         │
│  [Cancel]                      [Import & Build Images]  │
└─────────────────────────────────────────────────────────┘
```

### Step 3: Acquisition (Background Tasks)

Each missing image triggers appropriate acquisition:

```python
# Registry pull
docker pull docker.io/kalilinux/kali-rolling:latest

# Dockerfile build
docker build -t cyroid/vulnerable-webapp:latest ./dockerfiles/vulnerable-webapp/

# ISO download (via existing ISO manager)
iso_manager.ensure_iso("Windows Server 2022")
```

Progress updates via WebSocket to frontend.

### Step 4: Completion

- All images resolved and registered in BaseImage table
- Blueprint saved with image references
- Ready to deploy as range

---

## Backend Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Blueprint Import API                    │
│                 POST /blueprints/import                  │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│              ImageResolverService                        │
│  - Parse image manifest                                 │
│  - Check local availability                             │
│  - Return acquisition plan                              │
└─────────────────┬───────────────────────────────────────┘
                  │
        ┌─────────┼─────────┐
        ▼         ▼         ▼
┌───────────┐ ┌───────────┐ ┌───────────┐
│ Registry  │ │Dockerfile │ │    ISO    │
│  Puller   │ │  Builder  │ │  Manager  │
│           │ │           │ │ (existing)│
│ docker    │ │ docker    │ │           │
│ pull      │ │ build     │ │ download/ │
└───────────┘ └───────────┘ │ cache     │
                            └───────────┘
```

### New Services

**ImageResolverService** (`backend/cyroid/services/image_resolver_service.py`)
- `analyze(blueprint) -> AcquisitionPlan`
- `check_registry_image(image_tag) -> bool`
- `check_dockerfile_project(project_name) -> bool`
- `check_iso_available(iso_name) -> bool`

**RegistryPullerService** (`backend/cyroid/services/registry_puller_service.py`)
- `pull_image(registry_image, progress_callback) -> str`
- `get_image_size(registry_image) -> int`
- Supports Docker Hub, GHCR, private registries

### Modified Services

**BlueprintExportService** - Add image manifest generation
**DockerfileBuilder** - Already exists, minor enhancements
**ISOManager** - Already exists, add `ensure_iso()` method

---

## Export Changes

### Manifest Generation

On export, scan VMs and generate image manifest:

```python
def generate_image_manifest(range_obj, db):
    images = []
    seen = set()

    for vm in range_obj.vms:
        base_image = get_base_image(vm, db)
        if base_image.id in seen:
            continue
        seen.add(base_image.id)

        if base_image.image_project_name:
            # Has Dockerfile project
            images.append({
                "name": base_image.name,
                "source": "dockerfile",
                "project_name": base_image.image_project_name,
                "dockerfile_path": f"dockerfiles/{base_image.image_project_name}/"
            })
        elif base_image.vm_type in ("qemu", "dockur"):
            # ISO-based VM
            images.append({
                "name": base_image.name,
                "source": "iso",
                "iso_name": base_image.iso_name,
                "vm_type": base_image.vm_type
            })
        else:
            # Registry image
            images.append({
                "name": base_image.name,
                "source": "registry",
                "registry_image": base_image.docker_image_tag
            })

    return images
```

### Archive Structure

```
blueprint.cyrbp (ZIP)
├── blueprint.json          # Config + images manifest
├── manifest.json           # Metadata, checksums
├── dockerfiles/
│   ├── vulnerable-webapp/
│   │   ├── Dockerfile
│   │   ├── app/
│   │   └── README.md
│   └── custom-router/
│       ├── Dockerfile
│       └── config/
├── content/                # Student guides
└── artifacts/              # Tools, scripts
```

### Export Validation

Before allowing export:
- Verify all Dockerfile projects exist in `/data/images/`
- Verify registry images are resolvable
- Warn on any missing components

---

## Frontend Changes

### ImportBlueprintModal Enhancement

Add acquisition plan display:

```tsx
interface AcquisitionPlan {
  available: ImageStatus[];
  missing: ImageStatus[];
  totalDownloadBytes: number;
  estimatedTimeSeconds: number;
}

interface ImageStatus {
  name: string;
  source: 'registry' | 'dockerfile' | 'iso';
  status: 'exists' | 'missing';
  sizeBytes?: number;
  estimatedBuildTime?: number;
}
```

### Progress Component

Real-time progress during acquisition:

```tsx
<ImageAcquisitionProgress
  images={missingImages}
  onComplete={() => setImportComplete(true)}
  onError={(error) => setError(error)}
/>
```

---

## API Changes

### POST /blueprints/import/analyze

New endpoint to analyze blueprint before import:

```python
@router.post("/blueprints/import/analyze")
async def analyze_blueprint(file: UploadFile) -> AcquisitionPlan:
    """Analyze blueprint and return acquisition plan."""
    pass
```

### POST /blueprints/import

Enhanced to accept acquisition confirmation:

```python
@router.post("/blueprints/import")
async def import_blueprint(
    file: UploadFile,
    acquire_missing: bool = True,  # Trigger image acquisition
    conflict_strategy: str = "skip"
) -> BlueprintImportResult:
    pass
```

### WebSocket /ws/import/{task_id}

Progress updates during acquisition:

```json
{
  "type": "progress",
  "image": "ubuntu-server",
  "source": "registry",
  "progress": 45,
  "status": "pulling",
  "bytes_downloaded": 540000000,
  "bytes_total": 1200000000
}
```

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `backend/cyroid/schemas/blueprint.py` | Modify | Add `ImageManifestEntry`, `AcquisitionPlan` schemas |
| `backend/cyroid/services/image_resolver_service.py` | Create | Analyze blueprints, check image availability |
| `backend/cyroid/services/registry_puller_service.py` | Create | Docker registry pull with progress |
| `backend/cyroid/services/blueprint_export_service.py` | Modify | Generate image manifest on export |
| `backend/cyroid/api/blueprints.py` | Modify | Add analyze endpoint, enhance import |
| `backend/cyroid/tasks/image_acquisition.py` | Create | Background tasks for pull/build |
| `frontend/src/components/blueprints/ImportBlueprintModal.tsx` | Modify | Add acquisition plan UI |
| `frontend/src/components/blueprints/ImageAcquisitionProgress.tsx` | Create | Progress component |

---

## Migration & Compatibility

### Existing Blueprints

Blueprints without `images` manifest use fallback behavior:
1. Resolve VMs by existing `base_image_id` / `base_image_tag` fields
2. If missing, show error with manual resolution options
3. No breaking changes to existing exports

### Catalog Integration

Catalog blueprints must include:
- Complete `images` manifest
- All Dockerfile projects embedded
- Valid ISO references

Catalog validation enforces completeness before publishing.

---

*Created: 2026-01-29*
