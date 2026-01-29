# Local Docker Registry Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a local Docker registry to enable fast, layer-deduplicated image distribution to DinD range containers.

**Architecture:** Registry service (`registry:2`) on `cyroid-mgmt` network at `172.30.0.16:5000`. Push-on-demand during deployment with automatic fallback to tar transfer. DinD containers configured with `insecure-registries` baked into the image.

**Tech Stack:** Docker Registry 2, FastAPI, React/TypeScript, httpx (async HTTP), docker-py

**Design Document:** `docs/plans/2026-01-29-local-docker-registry-design.md`

---

## Phase 1: Infrastructure & Core Service

### Task 1.1: Add Registry Service to Docker Compose

**Files:**
- Modify: `docker-compose.yml`

**Step 1: Add registry service definition**

Add after the `worker` service definition:

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

**Step 2: Verify compose syntax**

Run: `docker compose -f docker-compose.yml config > /dev/null && echo "Syntax OK"`
Expected: `Syntax OK`

**Step 3: Commit infrastructure change**

```bash
git add docker-compose.yml
git commit -m "feat(infra): add local Docker registry service

- Add registry:2 on cyroid-mgmt network (172.30.0.16:5000)
- Enable storage deletion for future GC
- Bind mount to /data/cyroid/registry/
- Add healthcheck for monitoring

Part of #162"
```

---

### Task 1.2: Update DinD daemon.json

**Files:**
- Modify: `docker/daemon.json`

**Step 1: Add insecure-registries configuration**

Update `docker/daemon.json` to include registry in insecure-registries:

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

**Step 2: Commit daemon.json change**

```bash
git add docker/daemon.json
git commit -m "feat(dind): add insecure-registries for local registry

Allows DinD containers to pull from cyroid-registry:5000 without TLS.

Part of #162"
```

**Note:** DinD image rebuild and push to GHCR will be done in Phase 4 after all code changes are complete.

---

### Task 1.3: Create Registry Service - Core Methods

**Files:**
- Create: `backend/cyroid/services/registry_service.py`
- Create: `backend/tests/unit/test_registry_service.py`

**Step 1: Write the failing test for image_exists**

```python
# backend/tests/unit/test_registry_service.py
"""Tests for RegistryService."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from cyroid.services.registry_service import RegistryService


class TestRegistryService:
    """Test cases for RegistryService."""

    @pytest.fixture
    def registry_service(self):
        return RegistryService()

    @pytest.mark.asyncio
    async def test_image_exists_returns_true_when_tag_found(self, registry_service):
        """Test image_exists returns True when image tag exists in registry."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"tags": ["latest", "v1.0"]}

        with patch.object(registry_service, '_http_client') as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await registry_service.image_exists("myimage:v1.0")

            assert result is True
            mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_image_exists_returns_false_when_no_tags(self, registry_service):
        """Test image_exists returns False when image has no matching tag."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"tags": ["latest"]}

        with patch.object(registry_service, '_http_client') as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await registry_service.image_exists("myimage:v2.0")

            assert result is False

    @pytest.mark.asyncio
    async def test_image_exists_returns_false_on_404(self, registry_service):
        """Test image_exists returns False when image not in registry."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch.object(registry_service, '_http_client') as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await registry_service.image_exists("nonexistent:latest")

            assert result is False
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_registry_service.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'cyroid.services.registry_service'"

**Step 3: Write minimal RegistryService implementation**

```python
# backend/cyroid/services/registry_service.py
"""Service for managing the local Docker registry."""
import logging
from typing import Optional, List, Callable
import httpx
import docker

logger = logging.getLogger(__name__)


class RegistryService:
    """Service for interacting with the local Docker registry."""

    REGISTRY_HOST = "cyroid-registry"
    REGISTRY_PORT = 5000
    REGISTRY_URL = f"http://{REGISTRY_HOST}:{REGISTRY_PORT}"
    REGISTRY_IP = "172.30.0.16"
    REGISTRY_IP_URL = f"http://{REGISTRY_IP}:{REGISTRY_PORT}"

    def __init__(self):
        self._http_client: Optional[httpx.AsyncClient] = None
        self._docker_client: Optional[docker.DockerClient] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    def _get_docker_client(self) -> docker.DockerClient:
        """Get or create Docker client."""
        if self._docker_client is None:
            self._docker_client = docker.from_env()
        return self._docker_client

    async def close(self):
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    def _parse_image_tag(self, image_tag: str) -> tuple[str, str]:
        """Parse image:tag into (image, tag). Default tag is 'latest'."""
        if ':' in image_tag:
            parts = image_tag.rsplit(':', 1)
            return parts[0], parts[1]
        return image_tag, 'latest'

    def get_registry_tag(self, image_tag: str) -> str:
        """Convert image tag to registry-prefixed tag."""
        image, tag = self._parse_image_tag(image_tag)
        # Strip any existing registry prefix
        if '/' in image:
            parts = image.split('/')
            if '.' in parts[0] or ':' in parts[0]:
                # Has registry prefix, remove it
                image = '/'.join(parts[1:])
        return f"{self.REGISTRY_IP}:{self.REGISTRY_PORT}/{image}:{tag}"

    async def image_exists(self, image_tag: str) -> bool:
        """Check if image exists in local registry.

        Args:
            image_tag: Image tag like 'myimage:v1.0'

        Returns:
            True if image exists in registry, False otherwise
        """
        image, tag = self._parse_image_tag(image_tag)

        try:
            client = await self._get_http_client()
            # Query registry API for tags
            response = await client.get(f"{self.REGISTRY_URL}/v2/{image}/tags/list")

            if response.status_code == 404:
                return False

            if response.status_code == 200:
                data = response.json()
                tags = data.get('tags', [])
                return tag in tags if tags else False

            logger.warning(f"Unexpected registry response: {response.status_code}")
            return False

        except httpx.RequestError as e:
            logger.error(f"Failed to check registry: {e}")
            return False

    async def is_healthy(self) -> bool:
        """Check if registry is healthy and accessible."""
        try:
            client = await self._get_http_client()
            response = await client.get(f"{self.REGISTRY_URL}/v2/")
            return response.status_code == 200
        except httpx.RequestError:
            return False


# Singleton instance
_registry_service: Optional[RegistryService] = None


def get_registry_service() -> RegistryService:
    """Get the singleton RegistryService instance."""
    global _registry_service
    if _registry_service is None:
        _registry_service = RegistryService()
    return _registry_service
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_registry_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/cyroid/services/registry_service.py backend/tests/unit/test_registry_service.py
git commit -m "feat(registry): add RegistryService with image_exists method

- Add RegistryService with HTTP client for registry API
- Implement image_exists to check if image is in registry
- Add is_healthy method for registry health checks
- Add get_registry_tag to convert image names to registry format
- Add unit tests

Part of #162"
```

---

### Task 1.4: Add Push Image Method

**Files:**
- Modify: `backend/cyroid/services/registry_service.py`
- Modify: `backend/tests/unit/test_registry_service.py`

**Step 1: Write the failing test for push_image**

Add to `test_registry_service.py`:

```python
    @pytest.mark.asyncio
    async def test_push_image_success(self, registry_service):
        """Test push_image successfully pushes to registry."""
        mock_image = MagicMock()
        mock_image.tag.return_value = True

        mock_docker = MagicMock()
        mock_docker.images.get.return_value = mock_image
        mock_docker.images.push.return_value = iter([
            '{"status": "Pushing"}',
            '{"status": "Pushed"}',
        ])

        with patch.object(registry_service, '_get_docker_client', return_value=mock_docker):
            result = await registry_service.push_image("myimage:latest")

            assert result is True
            mock_image.tag.assert_called_once()
            mock_docker.images.push.assert_called_once()

    @pytest.mark.asyncio
    async def test_push_image_handles_missing_image(self, registry_service):
        """Test push_image returns False when image doesn't exist locally."""
        mock_docker = MagicMock()
        mock_docker.images.get.side_effect = docker.errors.ImageNotFound("not found")

        with patch.object(registry_service, '_get_docker_client', return_value=mock_docker):
            result = await registry_service.push_image("nonexistent:latest")

            assert result is False
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_registry_service.py::TestRegistryService::test_push_image_success -v`
Expected: FAIL with "AttributeError: 'RegistryService' object has no attribute 'push_image'"

**Step 3: Implement push_image method**

Add to `RegistryService` class in `registry_service.py`:

```python
    async def push_image(
        self,
        image_tag: str,
        progress_callback: Optional[Callable[[str, int], None]] = None
    ) -> bool:
        """Push image from host Docker to local registry.

        Args:
            image_tag: Image tag like 'myimage:v1.0'
            progress_callback: Optional callback(status, percent) for progress updates

        Returns:
            True if push succeeded, False otherwise
        """
        try:
            docker_client = self._get_docker_client()

            # Get the image
            try:
                image = docker_client.images.get(image_tag)
            except docker.errors.ImageNotFound:
                logger.error(f"Image not found locally: {image_tag}")
                return False

            # Tag for registry
            registry_tag = self.get_registry_tag(image_tag)
            image.tag(registry_tag)

            if progress_callback:
                progress_callback("Pushing to registry...", 10)

            # Push to registry
            push_output = docker_client.images.push(
                registry_tag,
                stream=True,
                decode=True
            )

            # Process push output for progress
            for line in push_output:
                if 'error' in line:
                    logger.error(f"Push error: {line['error']}")
                    return False
                if progress_callback and 'status' in line:
                    # Estimate progress based on status messages
                    status = line.get('status', '')
                    if 'Pushing' in status:
                        progress_callback(f"Pushing layers...", 50)
                    elif 'Pushed' in status:
                        progress_callback(f"Layer pushed", 80)

            if progress_callback:
                progress_callback("Push complete", 100)

            logger.info(f"Successfully pushed {image_tag} to registry as {registry_tag}")
            return True

        except docker.errors.APIError as e:
            logger.error(f"Docker API error pushing {image_tag}: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to push {image_tag}: {e}")
            return False
```

Also add the import at the top:

```python
import docker.errors
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_registry_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/cyroid/services/registry_service.py backend/tests/unit/test_registry_service.py
git commit -m "feat(registry): add push_image method to RegistryService

- Push images from host Docker to local registry
- Support progress callbacks for UI feedback
- Handle missing images gracefully
- Add unit tests

Part of #162"
```

---

### Task 1.5: Add ensure_image_in_registry (Push-on-Demand)

**Files:**
- Modify: `backend/cyroid/services/registry_service.py`
- Modify: `backend/tests/unit/test_registry_service.py`

**Step 1: Write the failing test**

Add to `test_registry_service.py`:

```python
    @pytest.mark.asyncio
    async def test_ensure_image_skips_push_if_exists(self, registry_service):
        """Test ensure_image_in_registry skips push if image already in registry."""
        with patch.object(registry_service, 'image_exists', new_callable=AsyncMock) as mock_exists:
            mock_exists.return_value = True

            with patch.object(registry_service, 'push_image', new_callable=AsyncMock) as mock_push:
                result = await registry_service.ensure_image_in_registry("myimage:latest")

                assert result is True
                mock_exists.assert_called_once_with("myimage:latest")
                mock_push.assert_not_called()

    @pytest.mark.asyncio
    async def test_ensure_image_pushes_if_not_exists(self, registry_service):
        """Test ensure_image_in_registry pushes if image not in registry."""
        with patch.object(registry_service, 'image_exists', new_callable=AsyncMock) as mock_exists:
            mock_exists.return_value = False

            with patch.object(registry_service, 'push_image', new_callable=AsyncMock) as mock_push:
                mock_push.return_value = True

                result = await registry_service.ensure_image_in_registry("myimage:latest")

                assert result is True
                mock_push.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_registry_service.py::TestRegistryService::test_ensure_image_skips_push_if_exists -v`
Expected: FAIL with "AttributeError"

**Step 3: Implement ensure_image_in_registry**

Add to `RegistryService` class:

```python
    async def ensure_image_in_registry(
        self,
        image_tag: str,
        progress_callback: Optional[Callable[[str, int], None]] = None
    ) -> bool:
        """Ensure image is in registry, pushing if needed (push-on-demand).

        Args:
            image_tag: Image tag like 'myimage:v1.0'
            progress_callback: Optional callback for progress updates

        Returns:
            True if image is in registry (already there or pushed), False on failure
        """
        # Check if already in registry
        if await self.image_exists(image_tag):
            logger.info(f"Image {image_tag} already in registry, skipping push")
            if progress_callback:
                progress_callback("Image already in registry", 100)
            return True

        # Push to registry
        logger.info(f"Image {image_tag} not in registry, pushing...")
        return await self.push_image(image_tag, progress_callback)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_registry_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/cyroid/services/registry_service.py backend/tests/unit/test_registry_service.py
git commit -m "feat(registry): add ensure_image_in_registry for push-on-demand

- Check if image exists before pushing
- Skip push if already in registry (layer caching benefit)
- Add unit tests

Part of #162"
```

---

### Task 1.6: Add list_images and get_stats Methods

**Files:**
- Modify: `backend/cyroid/services/registry_service.py`
- Modify: `backend/tests/unit/test_registry_service.py`

**Step 1: Write the failing tests**

Add to `test_registry_service.py`:

```python
    @pytest.mark.asyncio
    async def test_list_images_returns_catalog(self, registry_service):
        """Test list_images returns images from registry catalog."""
        mock_catalog_response = MagicMock()
        mock_catalog_response.status_code = 200
        mock_catalog_response.json.return_value = {"repositories": ["image1", "image2"]}

        mock_tags_response = MagicMock()
        mock_tags_response.status_code = 200
        mock_tags_response.json.return_value = {"tags": ["latest", "v1.0"]}

        with patch.object(registry_service, '_get_http_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=[mock_catalog_response, mock_tags_response, mock_tags_response])
            mock_get_client.return_value = mock_client

            result = await registry_service.list_images()

            assert len(result) == 2
            assert result[0]['name'] == 'image1'
            assert 'tags' in result[0]

    @pytest.mark.asyncio
    async def test_get_stats_returns_summary(self, registry_service):
        """Test get_stats returns registry statistics."""
        with patch.object(registry_service, 'list_images', new_callable=AsyncMock) as mock_list:
            mock_list.return_value = [
                {'name': 'image1', 'tags': ['latest']},
                {'name': 'image2', 'tags': ['v1', 'v2']},
            ]

            with patch.object(registry_service, 'is_healthy', new_callable=AsyncMock) as mock_healthy:
                mock_healthy.return_value = True

                result = await registry_service.get_stats()

                assert result['image_count'] == 2
                assert result['tag_count'] == 3
                assert result['healthy'] is True
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_registry_service.py::TestRegistryService::test_list_images_returns_catalog -v`
Expected: FAIL

**Step 3: Implement list_images and get_stats**

Add to `RegistryService` class:

```python
    async def list_images(self) -> List[dict]:
        """List all images in the registry.

        Returns:
            List of dicts with 'name' and 'tags' keys
        """
        try:
            client = await self._get_http_client()

            # Get catalog
            response = await client.get(f"{self.REGISTRY_URL}/v2/_catalog")
            if response.status_code != 200:
                logger.warning(f"Failed to get catalog: {response.status_code}")
                return []

            repositories = response.json().get('repositories', [])

            # Get tags for each repository
            images = []
            for repo in repositories:
                tags_response = await client.get(f"{self.REGISTRY_URL}/v2/{repo}/tags/list")
                if tags_response.status_code == 200:
                    tags = tags_response.json().get('tags', [])
                    images.append({
                        'name': repo,
                        'tags': tags or []
                    })
                else:
                    images.append({
                        'name': repo,
                        'tags': []
                    })

            return images

        except httpx.RequestError as e:
            logger.error(f"Failed to list registry images: {e}")
            return []

    async def get_stats(self) -> dict:
        """Get registry statistics.

        Returns:
            Dict with image_count, tag_count, healthy status
        """
        images = await self.list_images()
        healthy = await self.is_healthy()

        tag_count = sum(len(img.get('tags', [])) for img in images)

        return {
            'image_count': len(images),
            'tag_count': tag_count,
            'healthy': healthy,
        }
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_registry_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/cyroid/services/registry_service.py backend/tests/unit/test_registry_service.py
git commit -m "feat(registry): add list_images and get_stats methods

- Query registry catalog API for image list
- Fetch tags for each repository
- Return summary statistics for Admin UI
- Add unit tests

Part of #162"
```

---

## Phase 2: Registry-Based Image Transfer

### Task 2.1: Modify docker_service.py Transfer Flow

**Files:**
- Modify: `backend/cyroid/services/docker_service.py`

**Step 1: Read current transfer_image_to_dind implementation**

Examine lines 2987-3139 to understand current tar-based transfer.

**Step 2: Add registry-based transfer with fallback**

Modify the `transfer_image_to_dind` method to try registry first, fall back to tar:

```python
async def transfer_image_to_dind(
    self,
    range_id: str,
    docker_url: str,
    image: str,
    progress_callback=None
) -> bool:
    """Transfer image to DinD container, preferring registry over tar.

    Flow:
    1. Try to ensure image is in local registry (push-on-demand)
    2. Pull from registry into DinD
    3. Retag to original name inside DinD
    4. If any step fails, fall back to tar transfer
    """
    from cyroid.services.registry_service import get_registry_service

    registry = get_registry_service()

    # Try registry-based transfer
    try:
        if await registry.is_healthy():
            # Step 1: Ensure image is in registry
            if progress_callback:
                progress_callback(f"Checking registry for {image}...")

            if await registry.ensure_image_in_registry(image, progress_callback):
                # Step 2: Pull from registry into DinD
                registry_tag = registry.get_registry_tag(image)

                if progress_callback:
                    progress_callback(f"Pulling {image} from registry...")

                if await self._pull_image_in_dind(range_id, docker_url, registry_tag, progress_callback):
                    # Step 3: Retag to original name
                    if await self._retag_image_in_dind(range_id, docker_url, registry_tag, image):
                        logger.info(f"Successfully transferred {image} via registry")
                        return True
                    else:
                        logger.warning(f"Failed to retag {image} in DinD, falling back to tar")
                else:
                    logger.warning(f"Failed to pull {image} from registry, falling back to tar")
            else:
                logger.warning(f"Failed to push {image} to registry, falling back to tar")
        else:
            logger.info("Registry not healthy, using tar transfer")
    except Exception as e:
        logger.warning(f"Registry transfer failed for {image}, falling back to tar: {e}")

    # Fallback to tar transfer
    if progress_callback:
        progress_callback(f"Transferring {image} via tar...")
    return await self._transfer_image_via_tar(range_id, docker_url, image, progress_callback)
```

**Step 3: Add helper methods for DinD operations**

Add these helper methods to `DockerService`:

```python
async def _pull_image_in_dind(
    self,
    range_id: str,
    docker_url: str,
    registry_image: str,
    progress_callback=None
) -> bool:
    """Pull image from registry inside DinD container."""
    try:
        range_client = docker.DockerClient(base_url=docker_url)

        # Pull from registry
        range_client.images.pull(registry_image)

        logger.info(f"Pulled {registry_image} into DinD for range {range_id}")
        return True

    except docker.errors.APIError as e:
        logger.error(f"Failed to pull {registry_image} in DinD: {e}")
        return False
    except Exception as e:
        logger.error(f"Error pulling {registry_image} in DinD: {e}")
        return False

async def _retag_image_in_dind(
    self,
    range_id: str,
    docker_url: str,
    registry_image: str,
    target_image: str
) -> bool:
    """Retag image inside DinD from registry tag to original name."""
    try:
        range_client = docker.DockerClient(base_url=docker_url)

        image = range_client.images.get(registry_image)

        # Parse target into repo:tag
        if ':' in target_image:
            repo, tag = target_image.rsplit(':', 1)
        else:
            repo, tag = target_image, 'latest'

        image.tag(repo, tag)

        logger.info(f"Retagged {registry_image} to {target_image} in DinD")
        return True

    except docker.errors.ImageNotFound:
        logger.error(f"Image {registry_image} not found in DinD")
        return False
    except docker.errors.APIError as e:
        logger.error(f"Failed to retag image in DinD: {e}")
        return False

async def _transfer_image_via_tar(
    self,
    range_id: str,
    docker_url: str,
    image: str,
    progress_callback=None
) -> bool:
    """Transfer image via tar stream (fallback method)."""
    # This is the existing implementation - extract from current transfer_image_to_dind
    # Keep the existing tar-based logic here
    ...
```

**Step 4: Verify with local testing**

Start services and deploy a range to test the new transfer flow.

**Step 5: Commit**

```bash
git add backend/cyroid/services/docker_service.py
git commit -m "feat(docker): use registry for image transfer with tar fallback

- Try registry-based transfer first (layer caching)
- Automatically fall back to tar if registry fails
- Add _pull_image_in_dind and _retag_image_in_dind helpers
- Extract tar transfer to _transfer_image_via_tar

Part of #162"
```

---

## Phase 3: API Endpoints

### Task 3.1: Create Registry API Router

**Files:**
- Create: `backend/cyroid/api/registry.py`

**Step 1: Create the registry API file**

```python
# backend/cyroid/api/registry.py
"""API endpoints for local Docker registry management."""
import logging
from typing import List
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel

from cyroid.api.auth import get_current_user
from cyroid.models import User
from cyroid.services.registry_service import get_registry_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/registry", tags=["registry"])


class RegistryImage(BaseModel):
    """Registry image info."""
    name: str
    tags: List[str]


class RegistryStats(BaseModel):
    """Registry statistics."""
    image_count: int
    tag_count: int
    healthy: bool


class PushRequest(BaseModel):
    """Request to push image to registry."""
    image_tag: str


class PushResponse(BaseModel):
    """Response from push operation."""
    success: bool
    message: str


@router.get("/images", response_model=List[RegistryImage])
async def list_registry_images(
    current_user: User = Depends(get_current_user)
):
    """List all images in the local registry."""
    registry = get_registry_service()
    images = await registry.list_images()
    return [RegistryImage(**img) for img in images]


@router.get("/stats", response_model=RegistryStats)
async def get_registry_stats(
    current_user: User = Depends(get_current_user)
):
    """Get registry statistics."""
    registry = get_registry_service()
    stats = await registry.get_stats()
    return RegistryStats(**stats)


@router.post("/push", response_model=PushResponse)
async def push_image_to_registry(
    request: PushRequest,
    current_user: User = Depends(get_current_user)
):
    """Manually push an image to the local registry."""
    # Check admin/engineer role
    if not any(role in current_user.roles for role in ['admin', 'engineer']):
        raise HTTPException(status_code=403, detail="Admin or engineer role required")

    registry = get_registry_service()

    if not await registry.is_healthy():
        raise HTTPException(status_code=503, detail="Registry is not healthy")

    success = await registry.push_image(request.image_tag)

    if success:
        return PushResponse(success=True, message=f"Successfully pushed {request.image_tag}")
    else:
        raise HTTPException(status_code=500, detail=f"Failed to push {request.image_tag}")


@router.get("/health")
async def registry_health():
    """Check registry health (no auth required for healthchecks)."""
    registry = get_registry_service()
    healthy = await registry.is_healthy()
    return {"healthy": healthy}
```

**Step 2: Register router in main.py**

Add import and include_router in `backend/cyroid/main.py`:

```python
from cyroid.api.registry import router as registry_router

# In the routers section:
app.include_router(registry_router, prefix="/api/v1")
```

**Step 3: Commit**

```bash
git add backend/cyroid/api/registry.py backend/cyroid/main.py
git commit -m "feat(api): add registry management endpoints

- GET /registry/images - list all registry images
- GET /registry/stats - get registry statistics
- POST /registry/push - manually push image
- GET /registry/health - healthcheck endpoint

Part of #162"
```

---

### Task 3.2: Add Frontend API Client Methods

**Files:**
- Modify: `frontend/src/services/api.ts`

**Step 1: Add registry API types and methods**

Add to `api.ts`:

```typescript
// Registry API
export interface RegistryImage {
  name: string
  tags: string[]
}

export interface RegistryStats {
  image_count: number
  tag_count: number
  healthy: boolean
}

export interface PushResponse {
  success: boolean
  message: string
}

export const registryApi = {
  listImages: () => api.get<RegistryImage[]>('/registry/images'),
  getStats: () => api.get<RegistryStats>('/registry/stats'),
  pushImage: (imageTag: string) => api.post<PushResponse>('/registry/push', { image_tag: imageTag }),
  health: () => api.get<{ healthy: boolean }>('/registry/health'),
}
```

**Step 2: Commit**

```bash
git add frontend/src/services/api.ts
git commit -m "feat(frontend): add registry API client methods

Part of #162"
```

---

## Phase 4: Admin UI

### Task 4.1: Create RegistryTab Component

**Files:**
- Create: `frontend/src/components/admin/RegistryTab.tsx`

**Step 1: Create the Registry tab component**

```tsx
// frontend/src/components/admin/RegistryTab.tsx
import { useState, useEffect } from 'react'
import {
  RefreshCw,
  Database,
  Tag,
  Upload,
  CheckCircle,
  XCircle,
  Loader2,
  Package,
} from 'lucide-react'
import clsx from 'clsx'
import { registryApi, RegistryImage, RegistryStats } from '../../services/api'
import { toast } from '../../stores/toastStore'

export default function RegistryTab() {
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState<RegistryStats | null>(null)
  const [images, setImages] = useState<RegistryImage[]>([])
  const [pushLoading, setPushLoading] = useState(false)
  const [pushImage, setPushImage] = useState('')

  const fetchData = async () => {
    try {
      setLoading(true)
      const [statsRes, imagesRes] = await Promise.all([
        registryApi.getStats(),
        registryApi.listImages(),
      ])
      setStats(statsRes.data)
      setImages(imagesRes.data)
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to load registry data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const handlePush = async () => {
    if (!pushImage.trim()) return

    try {
      setPushLoading(true)
      await registryApi.pushImage(pushImage.trim())
      toast.success(`Successfully pushed ${pushImage}`)
      setPushImage('')
      fetchData()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to push image')
    } finally {
      setPushLoading(false)
    }
  }

  if (loading && !stats) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Stats Card */}
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-medium text-gray-900 flex items-center gap-2">
            <Database className="h-5 w-5" />
            Local Registry Status
          </h3>
          <button
            onClick={fetchData}
            disabled={loading}
            className="inline-flex items-center px-3 py-1.5 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
          >
            <RefreshCw className={clsx('h-4 w-4 mr-2', loading && 'animate-spin')} />
            Refresh
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 bg-gray-50 rounded-lg">
            <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
              <Package className="h-4 w-4" />
              Total Images
            </div>
            <div className="text-2xl font-semibold text-gray-900">
              {stats?.image_count ?? 0}
            </div>
          </div>
          <div className="p-4 bg-gray-50 rounded-lg">
            <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
              <Tag className="h-4 w-4" />
              Total Tags
            </div>
            <div className="text-2xl font-semibold text-gray-900">
              {stats?.tag_count ?? 0}
            </div>
          </div>
          <div className="p-4 bg-gray-50 rounded-lg">
            <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
              Health Status
            </div>
            <div className="flex items-center gap-2">
              {stats?.healthy ? (
                <>
                  <CheckCircle className="h-5 w-5 text-green-500" />
                  <span className="text-green-700 font-medium">Healthy</span>
                </>
              ) : (
                <>
                  <XCircle className="h-5 w-5 text-red-500" />
                  <span className="text-red-700 font-medium">Unhealthy</span>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Manual Push Section */}
      <div className="bg-white shadow rounded-lg p-6">
        <h3 className="text-lg font-medium text-gray-900 flex items-center gap-2 mb-4">
          <Upload className="h-5 w-5" />
          Push Image to Registry
        </h3>
        <div className="flex gap-3">
          <input
            type="text"
            value={pushImage}
            onChange={(e) => setPushImage(e.target.value)}
            placeholder="Enter image:tag (e.g., kalilinux/kali-rolling:latest)"
            className="flex-1 border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-primary-500 focus:border-primary-500"
          />
          <button
            onClick={handlePush}
            disabled={pushLoading || !pushImage.trim()}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-primary-600 hover:bg-primary-700 disabled:opacity-50"
          >
            {pushLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Upload className="h-4 w-4" />
            )}
            <span className="ml-2">Push</span>
          </button>
        </div>
        <p className="mt-2 text-xs text-gray-500">
          Push a local Docker image to the registry for faster deployment to ranges.
        </p>
      </div>

      {/* Images List */}
      <div className="bg-white shadow rounded-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-medium text-gray-900">Registry Images</h3>
        </div>
        {images.length === 0 ? (
          <div className="p-6 text-center text-gray-500">
            No images in registry yet. Images are pushed automatically during range deployment.
          </div>
        ) : (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Image Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Tags
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {images.map((image) => (
                <tr key={image.name}>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="text-sm font-mono text-gray-900">{image.name}</span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-wrap gap-1">
                      {image.tags.map((tag) => (
                        <span
                          key={tag}
                          className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/admin/RegistryTab.tsx
git commit -m "feat(ui): add RegistryTab component for Admin page

- Display registry stats (image count, tag count, health)
- Manual push input for images
- Table of registry contents

Part of #162"
```

---

### Task 4.2: Add Registry Tab to Admin Page

**Files:**
- Modify: `frontend/src/pages/Admin.tsx`
- Modify: `frontend/src/components/admin/index.ts`

**Step 1: Export RegistryTab from admin components**

Create or modify `frontend/src/components/admin/index.ts`:

```typescript
export { default as InfrastructureTab } from './InfrastructureTab'
export { default as CatalogSourcesTab } from './CatalogSourcesTab'
export { default as RegistryTab } from './RegistryTab'
```

**Step 2: Add Registry tab to Admin.tsx**

Update the imports:

```typescript
import { InfrastructureTab, CatalogSourcesTab, RegistryTab } from '../components/admin'
```

Update the TabType:

```typescript
type TabType = 'system' | 'users' | 'infrastructure' | 'registry' | 'catalog'
```

Add the tab button (after Infrastructure, before Catalog):

```tsx
<button
  onClick={() => setActiveTab('registry')}
  className={clsx(
    'flex items-center gap-2 py-4 px-1 border-b-2 font-medium text-sm',
    activeTab === 'registry'
      ? 'border-primary-500 text-primary-600'
      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
  )}
>
  <Database className="h-5 w-5" />
  Registry
</button>
```

Add the tab content (after Infrastructure tab content):

```tsx
{/* Registry Tab */}
{activeTab === 'registry' && (
  <RegistryTab />
)}
```

**Step 3: Commit**

```bash
git add frontend/src/pages/Admin.tsx frontend/src/components/admin/index.ts
git commit -m "feat(ui): add Registry tab to Admin page

Part of #162"
```

---

## Phase 5: User Prompts for Manual Push

### Task 5.1: Add Push-to-Registry Toast on Image Build

**Files:**
- Find and modify the component that handles image build completion

**Step 1: Identify build completion location**

Search for image build completion handling in the frontend.

**Step 2: Add toast with "Push to Registry" action**

After a successful image build, add:

```typescript
toast.info(
  'Image built successfully',
  {
    action: {
      label: 'Push to Registry',
      onClick: async () => {
        try {
          await registryApi.pushImage(imageTag)
          toast.success('Pushed to registry')
        } catch (err) {
          toast.error('Failed to push to registry')
        }
      }
    }
  }
)
```

**Step 3: Commit**

```bash
git add <modified-files>
git commit -m "feat(ui): add push-to-registry prompt on image build

Part of #162"
```

---

### Task 5.2: Add Push Option to Blueprint Import

**Files:**
- Modify: `frontend/src/components/blueprints/ImportBlueprintModal.tsx` (or equivalent)

**Step 1: Add checkbox to import modal**

Add a checkbox option "Push imported images to local registry".

**Step 2: Handle push after import**

If checkbox is checked, push imported images after successful import.

**Step 3: Commit**

```bash
git add <modified-files>
git commit -m "feat(ui): add push-to-registry option in blueprint import

Part of #162"
```

---

## Phase 6: Documentation & Finalization

### Task 6.1: Update README Architecture Section

**Files:**
- Modify: `README.md`

**Step 1: Add registry to architecture diagram**

Update the architecture section to include the registry service.

**Step 2: Add registry to service documentation**

Document the registry service, its purpose, and the static IP allocation.

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add local registry to architecture documentation

Part of #162"
```

---

### Task 6.2: Rebuild and Push DinD Image

**Files:**
- `docker/Dockerfile.dind` (if exists)

**Step 1: Rebuild DinD image with updated daemon.json**

```bash
docker build -t ghcr.io/jongodb/cyroid-dind:latest -f docker/Dockerfile.dind docker/
```

**Step 2: Push to GHCR**

```bash
docker push ghcr.io/jongodb/cyroid-dind:latest
```

**Step 3: Tag and release**

```bash
# Update VERSION file
echo "0.32.0" > VERSION

# Commit and tag
git add VERSION
git commit -m "chore: bump version to 0.32.0"
git tag -a v0.32.0 -m "feat: local Docker registry for fast image distribution (#162)"
git push origin master --tags
```

---

### Task 6.3: Create GitHub Release

**Step 1: Create release notes**

```markdown
## v0.32.0 - Local Docker Registry

### New Features
- **Local Docker Registry** - Added `registry:2` service for fast, layer-deduplicated image distribution to DinD containers
- **Push-on-Demand** - Images are automatically pushed to registry during deployment if not already cached
- **Registry Admin UI** - New "Registry" tab in Admin Settings shows registry status and contents
- **Manual Push** - Engineers can manually push images to registry for pre-caching

### Performance
- Subsequent range deployments are much faster due to layer caching
- Parallel pulls from registry instead of serialized tar exports

### Technical Details
- Registry runs on `cyroid-mgmt` network at 172.30.0.16:5000
- DinD images updated with `insecure-registries` configuration
- Automatic fallback to tar transfer if registry is unavailable

Closes #162
```

**Step 2: Create the release**

```bash
gh release create v0.32.0 --title "v0.32.0 - Local Docker Registry" --notes-file release-notes.md
```

---

## Summary

| Phase | Tasks | Estimated Commits |
|-------|-------|-------------------|
| 1: Infrastructure & Core | 6 tasks | 6 commits |
| 2: Transfer Flow | 1 task | 1 commit |
| 3: API | 2 tasks | 2 commits |
| 4: Admin UI | 2 tasks | 2 commits |
| 5: User Prompts | 2 tasks | 2 commits |
| 6: Documentation | 3 tasks | 3 commits |
| **Total** | **16 tasks** | **16 commits** |
