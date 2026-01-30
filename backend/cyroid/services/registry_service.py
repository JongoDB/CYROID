"""Service for managing the local Docker registry."""
import logging
from typing import Optional, List, Callable
import httpx
import docker
import docker.errors

logger = logging.getLogger(__name__)


class RegistryPushError(Exception):
    """Raised when pushing to registry fails."""
    pass


class RegistryService:
    """Service for interacting with the local Docker registry."""

    REGISTRY_HOST = "registry"  # Docker Compose service name
    REGISTRY_PORT = 5000
    REGISTRY_URL = f"http://{REGISTRY_HOST}:{REGISTRY_PORT}"
    REGISTRY_IP = "172.30.0.16"  # Internal IP for DinD containers to pull
    REGISTRY_IP_URL = f"http://{REGISTRY_IP}:{REGISTRY_PORT}"
    REGISTRY_LOCALHOST = "127.0.0.1"  # For host Docker daemon to push (no insecure-registries needed)

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

    def get_registry_tag(self, image_tag: str, for_host: bool = False) -> str:
        """Convert image tag to registry-prefixed tag.

        Args:
            image_tag: Image tag like 'myimage:v1.0'
            for_host: If True, use localhost (for host Docker push).
                      If False, use internal IP (for DinD pull).

        Returns:
            Registry-prefixed tag
        """
        image, tag = self._parse_image_tag(image_tag)
        # Strip any existing registry prefix
        if '/' in image:
            parts = image.split('/')
            if '.' in parts[0] or ':' in parts[0]:
                # Has registry prefix, remove it
                image = '/'.join(parts[1:])
        host = self.REGISTRY_LOCALHOST if for_host else self.REGISTRY_IP
        return f"{host}:{self.REGISTRY_PORT}/{image}:{tag}"

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

            # Tag for registry - use localhost for host Docker to push
            push_tag = self.get_registry_tag(image_tag, for_host=True)
            image.tag(push_tag)

            if progress_callback:
                progress_callback("Pushing to registry...", 10)

            # Push to registry via localhost
            push_output = docker_client.images.push(
                push_tag,
                stream=True,
                decode=True
            )

            # Process push output for progress
            for line in push_output:
                if 'error' in line:
                    logger.error(f"Push error: {line['error']}")
                    return False
                if progress_callback and 'status' in line:
                    status = line.get('status', '')
                    if 'Pushing' in status:
                        progress_callback("Pushing layers...", 50)
                    elif 'Pushed' in status:
                        progress_callback("Layer pushed", 80)

            if progress_callback:
                progress_callback("Push complete", 100)

            # Log both the push tag (localhost) and what DinD will use (internal IP)
            pull_tag = self.get_registry_tag(image_tag, for_host=False)
            logger.info(f"Successfully pushed {image_tag} to registry as {push_tag} (DinD can pull as {pull_tag})")
            return True

        except docker.errors.APIError as e:
            logger.error(f"Docker API error pushing {image_tag}: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to push {image_tag}: {e}")
            return False

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

    async def push_and_cleanup(
        self,
        image_tag: str,
        progress_callback: Optional[Callable[[str, int], None]] = None
    ) -> bool:
        """Push image to registry and remove from host Docker.

        This method pushes the image to the local registry, verifies it exists
        in the registry, then removes it from the host Docker daemon to free
        disk space.

        Args:
            image_tag: Image tag like 'myimage:v1.0'
            progress_callback: Optional callback(status, percent) for progress updates

        Returns:
            True if image is in registry (push succeeded or already there)

        Raises:
            RegistryPushError: If push to registry fails
        """
        if progress_callback:
            progress_callback("Pushing to registry...", 10)

        # Push to registry
        push_result = await self.push_image(image_tag, progress_callback)
        if not push_result:
            raise RegistryPushError(f"Failed to push image {image_tag} to registry")

        if progress_callback:
            progress_callback("Verifying in registry...", 70)

        # Verify image is in registry
        if not await self.image_exists(image_tag):
            raise RegistryPushError(
                f"Image {image_tag} not found in registry after push"
            )

        if progress_callback:
            progress_callback("Cleaning up host...", 85)

        # Remove from host Docker - the registry tag we created
        try:
            docker_client = self._get_docker_client()
            push_tag = self.get_registry_tag(image_tag, for_host=True)

            # Remove the registry-tagged version first (localhost:5000/...)
            try:
                docker_client.images.remove(push_tag, force=False)
                logger.info(f"Removed registry tag {push_tag} from host")
            except docker.errors.ImageNotFound:
                logger.debug(f"Registry tag {push_tag} not found on host (already removed)")
            except docker.errors.APIError as e:
                logger.warning(f"Could not remove registry tag {push_tag}: {e}")

            # Remove the original image tag
            try:
                docker_client.images.remove(image_tag, force=False)
                logger.info(f"Removed original image {image_tag} from host")
            except docker.errors.ImageNotFound:
                logger.debug(f"Image {image_tag} not found on host (already removed)")
            except docker.errors.APIError as e:
                # Image might be in use or have other tags - log warning but don't fail
                logger.warning(f"Could not remove image {image_tag} from host: {e}")

        except Exception as e:
            # Cleanup failure is not critical - image is already in registry
            logger.warning(f"Host cleanup failed for {image_tag}, but image is in registry: {e}")

        if progress_callback:
            progress_callback("Push and cleanup complete", 100)

        return True

    async def image_needs_push(self, image_tag: str) -> bool:
        """Check if image exists on host but not in registry.

        Args:
            image_tag: Image tag like 'myimage:v1.0'

        Returns:
            True if image exists on host but not in registry, False otherwise
        """
        # Check if image exists in registry
        in_registry = await self.image_exists(image_tag)
        if in_registry:
            return False

        # Check if image exists on host
        try:
            docker_client = self._get_docker_client()
            docker_client.images.get(image_tag)
            return True
        except docker.errors.ImageNotFound:
            return False
        except docker.errors.APIError as e:
            logger.warning(f"Error checking host for image {image_tag}: {e}")
            return False

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


# Singleton instance
_registry_service: Optional[RegistryService] = None


def get_registry_service() -> RegistryService:
    """Get the singleton RegistryService instance."""
    global _registry_service
    if _registry_service is None:
        _registry_service = RegistryService()
    return _registry_service
