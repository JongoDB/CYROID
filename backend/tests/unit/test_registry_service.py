"""Tests for RegistryService."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
import docker.errors

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

    @pytest.mark.asyncio
    async def test_image_exists_returns_false_on_request_error(self, registry_service):
        """Test image_exists returns False when registry is unreachable."""
        with patch.object(registry_service, '_http_client') as mock_client:
            mock_client.get = AsyncMock(side_effect=httpx.RequestError("Connection failed"))

            result = await registry_service.image_exists("myimage:latest")

            assert result is False

    @pytest.mark.asyncio
    async def test_image_exists_defaults_to_latest_tag(self, registry_service):
        """Test image_exists uses 'latest' tag when none specified."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"tags": ["latest", "v1.0"]}

        with patch.object(registry_service, '_http_client') as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await registry_service.image_exists("myimage")

            assert result is True

    @pytest.mark.asyncio
    async def test_is_healthy_returns_true_when_registry_responds(self, registry_service):
        """Test is_healthy returns True when registry is accessible."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(registry_service, '_http_client') as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await registry_service.is_healthy()

            assert result is True

    @pytest.mark.asyncio
    async def test_is_healthy_returns_false_on_error(self, registry_service):
        """Test is_healthy returns False when registry is unreachable."""
        with patch.object(registry_service, '_http_client') as mock_client:
            mock_client.get = AsyncMock(side_effect=httpx.RequestError("Connection failed"))

            result = await registry_service.is_healthy()

            assert result is False

    def test_parse_image_tag_with_tag(self, registry_service):
        """Test _parse_image_tag correctly parses image:tag."""
        image, tag = registry_service._parse_image_tag("myimage:v1.0")
        assert image == "myimage"
        assert tag == "v1.0"

    def test_parse_image_tag_without_tag(self, registry_service):
        """Test _parse_image_tag defaults to 'latest' when no tag."""
        image, tag = registry_service._parse_image_tag("myimage")
        assert image == "myimage"
        assert tag == "latest"

    def test_parse_image_tag_with_path(self, registry_service):
        """Test _parse_image_tag handles image paths."""
        image, tag = registry_service._parse_image_tag("library/myimage:v1.0")
        assert image == "library/myimage"
        assert tag == "v1.0"

    def test_get_registry_tag_basic(self, registry_service):
        """Test get_registry_tag converts simple image to registry format."""
        result = registry_service.get_registry_tag("myimage:v1.0")
        assert result == "172.30.0.16:5000/myimage:v1.0"

    def test_get_registry_tag_strips_existing_registry(self, registry_service):
        """Test get_registry_tag strips existing registry prefix."""
        result = registry_service.get_registry_tag("docker.io/library/myimage:v1.0")
        assert result == "172.30.0.16:5000/library/myimage:v1.0"

    def test_get_registry_tag_defaults_to_latest(self, registry_service):
        """Test get_registry_tag uses 'latest' when no tag specified."""
        result = registry_service.get_registry_tag("myimage")
        assert result == "172.30.0.16:5000/myimage:latest"

    def test_parse_image_tag_with_registry_port(self, registry_service):
        """Test parsing image tag with registry port (edge case)."""
        image, tag = registry_service._parse_image_tag("registry.example.com:5000/myimage:v1.0")
        assert image == "registry.example.com:5000/myimage"
        assert tag == "v1.0"

    def test_get_registry_tag_with_localhost(self, registry_service):
        """Test converting localhost registry image tag."""
        result = registry_service.get_registry_tag("localhost/myimage:v1.0")
        # localhost has no dot, so not stripped - this is expected behavior
        assert result == "172.30.0.16:5000/localhost/myimage:v1.0"

    @pytest.mark.asyncio
    async def test_push_image_success(self, registry_service):
        """Test push_image successfully pushes to registry."""
        mock_image = MagicMock()
        mock_image.tag.return_value = True

        mock_docker = MagicMock()
        mock_docker.images.get.return_value = mock_image
        mock_docker.images.push.return_value = iter([
            {"status": "Pushing"},
            {"status": "Pushed"},
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


class TestRegistryServiceSingleton:
    """Test cases for the singleton pattern."""

    def test_get_registry_service_returns_instance(self):
        """Test get_registry_service returns a RegistryService instance."""
        from cyroid.services.registry_service import get_registry_service

        service = get_registry_service()
        assert isinstance(service, RegistryService)

    def test_get_registry_service_returns_same_instance(self):
        """Test get_registry_service returns the same instance on multiple calls."""
        from cyroid.services.registry_service import get_registry_service

        service1 = get_registry_service()
        service2 = get_registry_service()
        assert service1 is service2
