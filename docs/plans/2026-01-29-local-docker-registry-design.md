# Local Docker Registry for DinD Image Distribution

**Issue:** #162
**Version:** 0.32.0
**Date:** 2026-01-29
**Status:** Approved

## Summary

Replace the current tar-based image transfer mechanism with a local Docker registry (`registry:2`) to enable fast, layer-deduplicated image distribution to DinD range containers.

## Problem

Currently, deploying a range transfers images from the host Docker daemon to each DinD container via tar stream (`docker save` → TCP → `docker load`). This is:

- **Slow**: Full serialized image transfer per deployment (multi-GB for Windows/macOS VMs)
- **No layer dedup**: Every deployment transfers the full image, even if layers are shared
- **Sequential bottleneck**: Blocks on host daemon's export stream
- **Scales poorly**: Each new range re-transfers identical images

## Solution

Add a local Docker registry to the CYROID stack as the primary image distribution mechanism for DinD containers.

### Architecture

```
Image Build/Import/Promote
        ↓
  (Optional) Push to local registry (cyroid-registry:5000)
        ↓
  On Deploy: Push-on-demand if not in registry
        ↓
  DinD containers pull from registry
  (layer-level caching — only missing layers transferred)
        ↓
  Fallback to tar transfer if registry fails
```

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Registry network | `cyroid-mgmt` only (172.30.0.16) | DinD already has connectivity to mgmt network |
| Push strategy | Push-on-demand + optional user prompts | Keeps registry lean; user controls eager pushing |
| Storage location | Bind mount `/data/cyroid/registry/` | Consistent with other CYROID data directories |
| Fallback behavior | Automatic fallback to tar transfer | Deployments stay resilient if registry fails |
| Garbage collection | Deferred to future release | Focus on core functionality first (see #177) |
| Management UI | Basic UI in Admin Settings | Gives users visibility into registry contents |
| DinD config | Baked into DinD image | Simpler than runtime configuration |

## Infrastructure Changes

### Registry Service (docker-compose.yml)

```yaml
registry:
  image: registry:2
  restart: unless-stopped
  environment:
    REGISTRY_STORAGE_DELETE_ENABLED: "true"
  volumes:
    - ${CYROID_DATA_DIR:-/data/cyroid}/registry:/var/lib/registry
  networks:
    cyroid-mgmt:
      ipv4_address: 172.30.0.16
  healthcheck:
    test: ["CMD", "wget", "-q", "--spider", "http://localhost:5000/v2/"]
    interval: 10s
    timeout: 5s
    retries: 3
```

### DinD daemon.json

```json
{
  "hosts": ["unix:///var/run/docker.sock", "tcp://0.0.0.0:2375"],
  "storage-driver": "overlay2",
  "insecure-registries": ["cyroid-registry:5000", "172.30.0.16:5000"],
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" },
  "live-restore": true,
  "userland-proxy": false
}
```

### Static IP Allocation (cyroid-mgmt network)

| IP | Service |
|----|---------|
| 172.30.0.10 | api |
| 172.30.0.11 | db |
| 172.30.0.12 | redis |
| 172.30.0.13 | minio |
| 172.30.0.14 | traefik |
| 172.30.0.15 | worker |
| 172.30.0.16 | **registry** (new) |
| 172.30.0.20 | frontend |

## Backend Service Layer

### RegistryService (`backend/cyroid/services/registry_service.py`)

```python
class RegistryService:
    REGISTRY_URL = "cyroid-registry:5000"
    REGISTRY_IP = "172.30.0.16:5000"

    async def push_image(self, image_tag: str, progress_callback=None) -> bool:
        """Push image from host Docker to local registry."""

    async def image_exists(self, image_tag: str) -> bool:
        """Check if image exists in registry via HTTP API."""

    async def ensure_image_in_registry(self, image_tag: str) -> bool:
        """Push image to registry if not already there (push-on-demand)."""

    async def list_images(self) -> List[dict]:
        """List all images in registry via catalog API."""

    async def get_stats(self) -> dict:
        """Get registry storage usage stats."""
```

## Modified Image Transfer Flow

### Current Flow
```
host docker save → tar stream → DinD docker load
```

### New Flow
```
1. Ensure image in registry (push-on-demand if needed)
2. DinD pulls from registry (layer caching)
3. Retag to original name inside DinD
4. If any step fails → fallback to tar transfer
```

### Code Structure
```python
async def transfer_image_to_dind(self, range_id, docker_url, image, progress_callback=None):
    registry = get_registry_service()

    try:
        # Ensure image is in registry (push-on-demand)
        if await registry.ensure_image_in_registry(image, progress_callback):
            # Pull from registry into DinD
            registry_image = registry.get_registry_tag(image)
            if await self._pull_image_in_dind(range_id, docker_url, registry_image, progress_callback):
                # Retag to original name inside DinD
                await self._retag_image_in_dind(range_id, docker_url, registry_image, image)
                return True
    except Exception as e:
        logger.warning(f"Registry transfer failed, falling back to tar: {e}")

    # Fallback to existing tar transfer
    return await self._transfer_image_via_tar(range_id, docker_url, image, progress_callback)
```

## API Endpoints

### Registry Management (`/api/v1/registry/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/images` | List all images in registry |
| GET | `/stats` | Storage usage, image count, health |
| POST | `/push` | Manually push image to registry |

## Admin UI

New "Registry" tab in Admin Settings:

- **Stats card**: Total images, storage used, registry health status
- **Image list table**: Image name, tags, size
- **Manual push**: Dropdown of host images + "Push to Registry" button

## User Prompts

For build/import/promote operations, add optional "Push to Registry" prompts:

- **Image build completion**: Toast with [Push to Registry] [Skip]
- **Blueprint import**: Checkbox "Push imported images to local registry"
- **Promote to VM Library**: Toast with [Push to Registry] [Skip]

These are non-blocking; if skipped, push-on-demand handles it during deployment.

## Implementation Files

### New Files
| File | Purpose |
|------|---------|
| `backend/cyroid/services/registry_service.py` | Registry operations |
| `backend/cyroid/api/registry.py` | API endpoints |
| `frontend/src/pages/AdminRegistry.tsx` | Admin UI tab |

### Modified Files
| File | Changes |
|------|---------|
| `docker-compose.yml` | Add registry service |
| `docker/daemon.json` | Add insecure-registries |
| `backend/cyroid/services/docker_service.py` | Registry-based transfer |
| `backend/cyroid/api/__init__.py` | Register router |
| `frontend/src/pages/AdminSettings.tsx` | Add Registry tab |
| `frontend/src/services/api.ts` | Registry API calls |
| `README.md` | Architecture documentation |
| Build/import/promote components | Push prompts |

### DinD Image
- Rebuild with updated `daemon.json`
- Push to `ghcr.io/jongodb/cyroid-dind:latest`

## Expected Benefits

| Metric | Current (tar) | With Registry |
|--------|--------------|---------------|
| First deployment | Full transfer | Full pull (comparable) |
| Subsequent deployments | Full transfer again | Layer cache hit — near-instant |
| Concurrent ranges | Serialized exports | Parallel pulls |
| Shared base layers | Re-transferred each time | Pulled once, cached |

## Future Work

- **Registry garbage collection** (#177) - Clean up unused layers
- **Delete image from registry** - UI button to remove specific images
- **Auto-push setting** - Global toggle to always push on build/import/promote
