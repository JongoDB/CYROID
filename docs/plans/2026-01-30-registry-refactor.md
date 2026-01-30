# Registry Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the local registry the central image store for all DinD ranges, with auto-push on all image operations and pull-through caching.

**Architecture:** Host Docker daemon holds only CYROID services + DinD containers. Registry holds all VM/container images. Images are auto-pushed to registry and auto-removed from host after successful push.

**Tech Stack:** Docker Registry v2, Python/FastAPI, React/TypeScript

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         HOST DOCKER                                  │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │
│  │   api   │ │frontend │ │   db    │ │  redis  │ │  minio  │ ...   │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘       │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐                                │
│  │ DinD-1  │ │ DinD-2  │ │ DinD-N  │  (Range containers)           │
│  └────┬────┘ └────┬────┘ └────┬────┘                                │
│       │           │           │                                      │
│       └───────────┼───────────┘                                      │
│                   ▼                                                  │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                    LOCAL REGISTRY (172.30.0.16:5000)           │ │
│  │  ┌──────────────────────────────────────────────────────────┐  │ │
│  │  │  All VM/Container Images (cyroid/*, catalog images, etc) │  │ │
│  │  └──────────────────────────────────────────────────────────┘  │ │
│  │  ┌──────────────────────────────────────────────────────────┐  │ │
│  │  │  Pull-Through Cache (docker.io/*, ghcr.io/*)             │  │ │
│  │  └──────────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ (pull-through only)
                        ┌───────────────────────┐
                        │  Docker Hub / GHCR    │
                        └───────────────────────┘
```

## New Behavior Summary

| Operation | Current Behavior | New Behavior |
|-----------|-----------------|--------------|
| Docker Pull (cache) | Stays on host | Push to registry → remove from host |
| Custom Build | Stays on host, prompt to push | Push to registry → remove from host |
| Catalog Install | Stays on host | Push to registry → remove from host |
| Blueprint Import (tar) | Load to host | Push to registry → remove from host |
| Blueprint Import (Dockerfile) | Build on host | Push to registry → remove from host |
| DinD Image Pull | Registry or tar transfer | Registry only (pull-through if needed) |
| DinD Internet Pull | Allowed, no tracking | Allowed, notify user, auto-cache |

---

## Phase 1: Registry Pull-Through Cache Configuration

### Task 1.1: Create Registry Configuration File

**Files:**
- Create: `config/registry-config.yml`

**Step 1: Create registry configuration with pull-through proxy**

```yaml
version: 0.1
log:
  level: info
storage:
  filesystem:
    rootdirectory: /var/lib/registry
  delete:
    enabled: true
http:
  addr: :5000
  headers:
    X-Content-Type-Options: [nosniff]
proxy:
  remoteurl: https://registry-1.docker.io
  username: ""
  password: ""
```

**Step 2: Commit**

```bash
git add config/registry-config.yml
git commit -m "feat(registry): add registry configuration for pull-through cache"
```

### Task 1.2: Update Docker Compose for Registry Config

**Files:**
- Modify: `docker-compose.yml`

**Step 1: Update registry service to use config**

Find the registry service and add config volume mount:

```yaml
registry:
  image: registry:2
  ports:
    - "127.0.0.1:5000:5000"
  volumes:
    - ${CYROID_DATA_DIR:-/data/cyroid}/registry:/var/lib/registry
    - ./config/registry-config.yml:/etc/docker/registry/config.yml:ro
  networks:
    cyroid-mgmt:
      ipv4_address: 172.30.0.16
  restart: unless-stopped
```

**Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(registry): configure registry with pull-through cache support"
```

---

## Phase 2: Registry Service Enhancements

### Task 2.1: Add Host Image Cleanup Method

**Files:**
- Modify: `backend/cyroid/services/registry_service.py`

**Step 1: Add method to remove image from host after push**

```python
async def push_and_cleanup(
    self,
    image_tag: str,
    progress_callback: Optional[Callable[[str, int], None]] = None
) -> bool:
    """Push image to registry and remove from host Docker.

    Args:
        image_tag: Image tag like 'cyroid/kali:latest'
        progress_callback: Optional callback for progress updates

    Returns:
        True if push succeeded and host cleanup completed

    Raises:
        RegistryPushError: If push fails (image kept on host)
    """
    # Push to registry
    success = await self.push_image(image_tag, progress_callback)

    if not success:
        raise RegistryPushError(f"Failed to push {image_tag} to registry")

    # Verify image is in registry before cleanup
    if not await self.image_exists(image_tag):
        raise RegistryPushError(f"Image {image_tag} not found in registry after push")

    # Remove from host Docker
    try:
        docker_client = self._get_docker_client()
        docker_client.images.remove(image_tag, force=False)
        logger.info(f"Removed {image_tag} from host Docker after registry push")

        if progress_callback:
            progress_callback("Cleaned up host image", 100)

        return True
    except docker.errors.APIError as e:
        # Log but don't fail - image is in registry which is the goal
        logger.warning(f"Failed to remove {image_tag} from host: {e}")
        return True
```

**Step 2: Add custom exception class**

```python
class RegistryPushError(Exception):
    """Raised when pushing to registry fails."""
    pass
```

**Step 3: Add method to check if image needs push**

```python
async def image_needs_push(self, image_tag: str) -> bool:
    """Check if image exists on host but not in registry.

    Returns:
        True if image is on host but not in registry
    """
    # Check if in registry
    if await self.image_exists(image_tag):
        return False

    # Check if on host
    try:
        docker_client = self._get_docker_client()
        docker_client.images.get(image_tag)
        return True  # On host, not in registry
    except docker.errors.ImageNotFound:
        return False  # Not on host either
```

**Step 4: Run tests**

```bash
pytest backend/tests/unit/test_registry_service.py -v
```

**Step 5: Commit**

```bash
git add backend/cyroid/services/registry_service.py
git commit -m "feat(registry): add push_and_cleanup and image_needs_push methods"
```

### Task 2.2: Add Registry Status Endpoint

**Files:**
- Modify: `backend/cyroid/api/registry.py`

**Step 1: Add endpoint to get image registry status**

```python
@router.get("/status/{image_tag:path}")
async def get_image_registry_status(
    image_tag: str,
    current_user: CurrentUser
):
    """Check if image is in registry, on host, or both."""
    registry = get_registry_service()

    in_registry = await registry.image_exists(image_tag)

    # Check host
    on_host = False
    try:
        docker_client = docker.from_env()
        docker_client.images.get(image_tag)
        on_host = True
    except docker.errors.ImageNotFound:
        pass

    return {
        "image_tag": image_tag,
        "in_registry": in_registry,
        "on_host": on_host,
        "needs_push": on_host and not in_registry,
    }
```

**Step 2: Commit**

```bash
git add backend/cyroid/api/registry.py
git commit -m "feat(registry): add image status endpoint"
```

---

## Phase 3: Auto-Push on Docker Pull

### Task 3.1: Modify Docker Pull to Auto-Push

**Files:**
- Modify: `backend/cyroid/api/cache.py`

**Step 1: Update `_pull_docker_image_async` to push after pull**

Find the function around line 350 and modify the success path:

```python
# After successful pull, push to registry and cleanup
try:
    from ..services.registry_service import get_registry_service

    registry = get_registry_service()
    if await registry.is_healthy():
        _active_docker_pulls[pull_key]["status"] = "pushing_to_registry"
        _active_docker_pulls[pull_key]["current_step_name"] = "Pushing to registry..."

        await registry.push_and_cleanup(image)

        _active_docker_pulls[pull_key]["pushed_to_registry"] = True
        logger.info(f"Pushed {image} to registry and cleaned up host")
    else:
        logger.warning(f"Registry not healthy, keeping {image} on host")
        _active_docker_pulls[pull_key]["pushed_to_registry"] = False
except Exception as e:
    logger.error(f"Failed to push {image} to registry: {e}")
    _active_docker_pulls[pull_key]["pushed_to_registry"] = False
    _active_docker_pulls[pull_key]["registry_error"] = str(e)
    raise  # Fail the operation
```

**Step 2: Update status response to include registry info**

```python
# In get_docker_pull_status, add:
"pushed_to_registry": pull_info.get("pushed_to_registry", False),
"registry_error": pull_info.get("registry_error"),
```

**Step 3: Run tests**

```bash
pytest backend/tests/unit/test_cache_api.py -v -k pull
```

**Step 4: Commit**

```bash
git add backend/cyroid/api/cache.py
git commit -m "feat(cache): auto-push pulled images to registry"
```

---

## Phase 4: Auto-Push on Custom Build

### Task 4.1: Modify Custom Build to Auto-Push

**Files:**
- Modify: `backend/cyroid/api/cache.py`

**Step 1: Update `_build_docker_image_async` to push after build**

Find the success path in `_build_docker_image_async` (around line 740) and add:

```python
# After successful build (in the "aux" handler or final check)
logger.info(f"Docker build completed: {full_tag} ({image_id})")

# Push to registry and cleanup host
try:
    from ..services.registry_service import get_registry_service

    registry = get_registry_service()
    if await registry.is_healthy():
        _active_docker_builds[build_key]["current_step_name"] = "Pushing to registry..."

        # Use sync wrapper for async call in thread
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(registry.push_and_cleanup(full_tag))
        finally:
            loop.close()

        _active_docker_builds[build_key]["pushed_to_registry"] = True
        logger.info(f"Pushed {full_tag} to registry and cleaned up host")
    else:
        logger.warning(f"Registry not healthy, keeping {full_tag} on host")
        _active_docker_builds[build_key]["pushed_to_registry"] = False
except Exception as e:
    logger.error(f"Failed to push {full_tag} to registry: {e}")
    _active_docker_builds[build_key].update({
        "status": "failed",
        "error": f"Build succeeded but registry push failed: {e}",
        "current_step_name": f"Registry push failed: {e}",
    })
    return  # Fail the operation
```

**Step 2: Commit**

```bash
git add backend/cyroid/api/cache.py
git commit -m "feat(cache): auto-push built images to registry"
```

---

## Phase 5: Auto-Push on Catalog Install

### Task 5.1: Modify Catalog Service to Auto-Push

**Files:**
- Modify: `backend/cyroid/services/catalog_service.py`

**Step 1: Update `_build_docker_image` to push after build**

```python
def _build_docker_image(self, image_tag: str, project_dir: Path) -> bool:
    """Build a Docker image and push to registry."""
    try:
        import docker
        client = docker.from_env()

        # Check if image already exists in registry
        from .registry_service import get_registry_service
        import asyncio

        registry = get_registry_service()
        loop = asyncio.new_event_loop()
        try:
            in_registry = loop.run_until_complete(registry.image_exists(image_tag))
            if in_registry:
                logger.info(f"Image {image_tag} already in registry, skipping build")
                return True
        finally:
            loop.close()

        # Build the image
        logger.info(f"Building image {image_tag} from {project_dir}")
        image, build_logs = client.images.build(
            path=str(project_dir),
            tag=image_tag,
            rm=True,
            forcerm=True,
        )

        for log_line in build_logs:
            if "stream" in log_line:
                logger.debug(log_line["stream"].strip())

        logger.info(f"Successfully built image {image_tag}")

        # Push to registry and cleanup
        loop = asyncio.new_event_loop()
        try:
            if loop.run_until_complete(registry.is_healthy()):
                loop.run_until_complete(registry.push_and_cleanup(image_tag))
                logger.info(f"Pushed {image_tag} to registry")
            else:
                logger.warning(f"Registry not healthy, keeping {image_tag} on host")
        finally:
            loop.close()

        return True

    except Exception as e:
        logger.error(f"Failed to build image {image_tag}: {e}")
        raise  # Propagate error to fail the operation
```

**Step 2: Commit**

```bash
git add backend/cyroid/services/catalog_service.py
git commit -m "feat(catalog): auto-push built images to registry"
```

---

## Phase 6: Blueprint Import Registry Integration

### Task 6.1: Update Blueprint Import to Push Images

**Files:**
- Modify: `backend/cyroid/services/blueprint_export_service.py`

**Step 1: Add method to load tar image and push to registry**

```python
async def _load_image_to_registry(
    self,
    tar_path: Path,
    progress_callback: Optional[Callable[[str, int], None]] = None
) -> List[str]:
    """Load image from tar file and push to registry.

    Args:
        tar_path: Path to the image tar file
        progress_callback: Optional progress callback

    Returns:
        List of image tags that were loaded and pushed
    """
    from .registry_service import get_registry_service

    registry = get_registry_service()
    docker_client = docker.from_env()

    if progress_callback:
        progress_callback("Loading image from tar...", 10)

    # Load image to host temporarily
    with open(tar_path, 'rb') as f:
        loaded_images = docker_client.images.load(f)

    tags = []
    for image in loaded_images:
        for tag in (image.tags or []):
            tags.append(tag)

    if progress_callback:
        progress_callback(f"Loaded {len(tags)} image(s), pushing to registry...", 50)

    # Push each tag to registry and cleanup
    for tag in tags:
        if await registry.is_healthy():
            await registry.push_and_cleanup(tag)
            logger.info(f"Pushed {tag} to registry from blueprint import")
        else:
            raise RegistryPushError(f"Registry not healthy, cannot import {tag}")

    if progress_callback:
        progress_callback("Images pushed to registry", 100)

    return tags
```

**Step 2: Update `_extract_docker_images` to use registry**

Modify the method to call `_load_image_to_registry` instead of just loading to host.

**Step 3: Update `_build_and_register_images` to push to registry**

The catalog service changes should handle this, but ensure the import flow uses the updated build method.

**Step 4: Commit**

```bash
git add backend/cyroid/services/blueprint_export_service.py
git commit -m "feat(blueprint): push imported images to registry"
```

---

## Phase 7: DinD Internet Pull Tracking

### Task 7.1: Add Pull Source Tracking to DinD

**Files:**
- Modify: `backend/cyroid/services/docker_service.py`

**Step 1: Update `pull_image_to_dind` to track pull source**

```python
async def pull_image_to_dind(
    self,
    range_id: UUID,
    image: str,
    progress_callback: Optional[Callable] = None
) -> Dict[str, Any]:
    """Pull image into DinD container, tracking source.

    Returns:
        Dict with:
            - success: bool
            - source: 'registry' | 'internet' | 'error'
            - cached_to_registry: bool (if pulled from internet)
    """
    result = {
        "success": False,
        "source": None,
        "cached_to_registry": False,
        "image": image,
    }

    registry = get_registry_service()

    # Try registry first
    if await registry.image_exists(image):
        result["source"] = "registry"
        # ... existing registry pull logic ...
        result["success"] = True
        return result

    # Not in registry - will need to pull from internet
    result["source"] = "internet"

    # Pull into DinD from internet
    range_client = self.dind_service.get_range_client(range_id)
    range_client.images.pull(image)

    # Cache to registry for future use
    try:
        # Export from DinD, load to host, push to registry
        await self._cache_dind_image_to_registry(range_id, image)
        result["cached_to_registry"] = True
        logger.info(f"Cached internet pull {image} to registry")
    except Exception as e:
        logger.warning(f"Failed to cache {image} to registry: {e}")
        result["cached_to_registry"] = False

    result["success"] = True
    return result
```

**Step 2: Add method to cache DinD image to registry**

```python
async def _cache_dind_image_to_registry(
    self,
    range_id: UUID,
    image: str
) -> None:
    """Export image from DinD and push to registry."""
    registry = get_registry_service()
    range_client = self.dind_service.get_range_client(range_id)
    host_client = docker.from_env()

    # Export from DinD
    dind_image = range_client.images.get(image)
    image_data = dind_image.save(named=True)

    # Load to host temporarily
    loaded = host_client.images.load(image_data)

    # Push to registry and cleanup host
    for img in loaded:
        for tag in (img.tags or []):
            await registry.push_and_cleanup(tag)
```

**Step 3: Commit**

```bash
git add backend/cyroid/services/docker_service.py
git commit -m "feat(dind): track pull source and auto-cache internet pulls"
```

### Task 7.2: Add WebSocket Notification for Internet Pulls

**Files:**
- Modify: `backend/cyroid/api/ranges.py` (or wherever deployment progress is reported)

**Step 1: Add notification when pulling from internet**

```python
# During VM deployment, when pull_image_to_dind returns source='internet':
if pull_result["source"] == "internet":
    await notify_user(
        user_id=current_user.id,
        type="warning",
        title="Image Pulled from Internet",
        message=f"Image {image} was pulled from the internet (not cached). "
                f"{'Cached to registry for future use.' if pull_result['cached_to_registry'] else 'Failed to cache.'}",
    )
```

**Step 2: Commit**

```bash
git add backend/cyroid/api/ranges.py
git commit -m "feat(ranges): notify user when DinD pulls from internet"
```

---

## Phase 8: Frontend Updates

### Task 8.1: Update Image Cache to Show Registry Status

**Files:**
- Modify: `frontend/src/pages/ImageCache.tsx`
- Modify: `frontend/src/services/api.ts`

**Step 1: Add API call for image registry status**

```typescript
// In api.ts registryApi:
getImageStatus: (imageTag: string) =>
  api.get<{ image_tag: string; in_registry: boolean; on_host: boolean; needs_push: boolean }>(
    `/registry/status/${encodeURIComponent(imageTag)}`
  ),
```

**Step 2: Add registry status indicator to cached images**

Show badge/icon for each cached image:
- Green checkmark: In registry
- Yellow warning: On host only (needs push)
- "Push to Registry" button for images not in registry

**Step 3: Remove manual push prompt after build**

Remove the toast with "Push to Registry" action since it's now automatic.

**Step 4: Add error handling for registry push failures**

Show clear error message if registry push fails during build/pull.

**Step 5: Commit**

```bash
git add frontend/src/pages/ImageCache.tsx frontend/src/services/api.ts
git commit -m "feat(ui): show registry status for cached images"
```

### Task 8.2: Update Registry Admin Tab

**Files:**
- Modify: `frontend/src/components/admin/RegistryTab.tsx`

**Step 1: Add delete image functionality**

```typescript
const handleDeleteImage = async (imageTag: string) => {
  if (!confirm(`Delete ${imageTag} from registry? This cannot be undone.`)) {
    return;
  }
  try {
    await registryApi.deleteImage(imageTag);
    toast.success(`Deleted ${imageTag} from registry`);
    await fetchAll();
  } catch (err) {
    toast.error('Failed to delete image');
  }
};
```

**Step 2: Show storage usage**

Display registry storage stats if available.

**Step 3: Add "Push All Missing" button**

Button to push all images that are on host but not in registry.

**Step 4: Commit**

```bash
git add frontend/src/components/admin/RegistryTab.tsx
git commit -m "feat(ui): enhance registry admin with delete and bulk push"
```

### Task 8.3: Add Internet Pull Notification UI

**Files:**
- Modify: `frontend/src/pages/RangeDetail.tsx` (deployment progress)

**Step 1: Show warning when image pulled from internet**

During deployment progress, highlight images pulled from internet vs registry.

**Step 2: Commit**

```bash
git add frontend/src/pages/RangeDetail.tsx
git commit -m "feat(ui): show internet pull warnings during deployment"
```

---

## Phase 9: Registry Delete Endpoint

### Task 9.1: Add Registry Delete API

**Files:**
- Modify: `backend/cyroid/services/registry_service.py`
- Modify: `backend/cyroid/api/registry.py`

**Step 1: Add delete method to registry service**

```python
async def delete_image(self, image_tag: str) -> bool:
    """Delete image from registry.

    Note: Requires registry garbage collection to reclaim space.
    """
    # Parse image_tag to get name and tag
    if ':' in image_tag:
        name, tag = image_tag.rsplit(':', 1)
    else:
        name, tag = image_tag, 'latest'

    # Get manifest digest
    client = await self._get_client()
    try:
        resp = await client.head(
            f"{self.REGISTRY_URL}/v2/{name}/manifests/{tag}",
            headers={"Accept": "application/vnd.docker.distribution.manifest.v2+json"}
        )
        digest = resp.headers.get("Docker-Content-Digest")

        if not digest:
            return False

        # Delete by digest
        resp = await client.delete(f"{self.REGISTRY_URL}/v2/{name}/manifests/{digest}")
        return resp.status_code == 202
    except Exception as e:
        logger.error(f"Failed to delete {image_tag}: {e}")
        return False
```

**Step 2: Add delete endpoint**

```python
@router.delete("/images/{image_tag:path}")
async def delete_registry_image(
    image_tag: str,
    current_user: AdminUser
):
    """Delete image from registry (admin only)."""
    registry = get_registry_service()

    success = await registry.delete_image(image_tag)

    if success:
        return {"success": True, "message": f"Deleted {image_tag}"}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to delete {image_tag}")
```

**Step 3: Commit**

```bash
git add backend/cyroid/services/registry_service.py backend/cyroid/api/registry.py
git commit -m "feat(registry): add image delete endpoint"
```

---

## Phase 10: Testing & Migration

### Task 10.1: Write Tests for New Registry Behavior

**Files:**
- Create: `backend/tests/unit/test_registry_auto_push.py`

**Step 1: Write tests for push_and_cleanup**

```python
@pytest.mark.asyncio
async def test_push_and_cleanup_removes_host_image():
    """Test that push_and_cleanup removes image from host after push."""
    # ... test implementation
```

**Step 2: Write tests for auto-push on pull**

**Step 3: Write tests for auto-push on build**

**Step 4: Run all tests**

```bash
pytest backend/tests/ -v
```

**Step 5: Commit**

```bash
git add backend/tests/
git commit -m "test(registry): add tests for auto-push behavior"
```

### Task 10.2: Create Migration Script

**Files:**
- Create: `scripts/migrate-images-to-registry.sh`

**Step 1: Write migration script**

```bash
#!/bin/bash
# Migrate existing cached images to registry

echo "Migrating cached images to registry..."

# Get list of cyroid/* images on host
images=$(docker images --format "{{.Repository}}:{{.Tag}}" | grep "^cyroid/")

for image in $images; do
    echo "Pushing $image to registry..."
    docker tag "$image" "127.0.0.1:5000/$image"
    docker push "127.0.0.1:5000/$image"
    docker rmi "$image" "127.0.0.1:5000/$image"
done

echo "Migration complete!"
```

**Step 2: Commit**

```bash
git add scripts/migrate-images-to-registry.sh
git commit -m "chore: add migration script for existing images"
```

---

## Implementation Order

1. **Phase 1** - Registry pull-through config (foundation)
2. **Phase 2** - Registry service enhancements (methods needed by other phases)
3. **Phase 9** - Registry delete endpoint (admin needs this)
4. **Phase 3** - Auto-push on Docker pull
5. **Phase 4** - Auto-push on custom build
6. **Phase 5** - Auto-push on catalog install
7. **Phase 6** - Blueprint import registry integration
8. **Phase 7** - DinD internet pull tracking
9. **Phase 8** - Frontend updates
10. **Phase 10** - Testing & migration

---

## Rollback Plan

If issues arise:
1. Remove registry config volume mount (disables pull-through)
2. Comment out auto-push calls (images stay on host)
3. Revert frontend changes

The system will fall back to tar-based transfers which still work.

---

## Success Criteria

- [ ] All image pulls auto-push to registry
- [ ] All image builds auto-push to registry
- [ ] All catalog installs auto-push to registry
- [ ] All blueprint imports push to registry
- [ ] Host Docker only has CYROID services + DinD containers
- [ ] DinD pulls from registry by default
- [ ] Internet pulls are tracked and cached
- [ ] Admin can delete images from registry
- [ ] Frontend shows registry status for images
- [ ] All existing tests pass
- [ ] Migration script works for existing installations
