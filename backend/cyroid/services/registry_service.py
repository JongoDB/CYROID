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
