"""Tests for registry auto-push behavior.

This module tests the automatic push-to-registry functionality including:
- push_and_cleanup: Push image to registry and remove from host
- image_needs_push: Check if image exists on host but not in registry
- delete_image: Remove image from registry via manifest digest
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
import docker.errors
import httpx

from cyroid.services.registry_service import RegistryService, RegistryPushError


class TestPushAndCleanup:
    """Tests for push_and_cleanup method."""

    @pytest.fixture
    def registry_service(self):
        """Create a fresh RegistryService instance for each test."""
        return RegistryService()

    @pytest.mark.asyncio
    async def test_push_and_cleanup_removes_host_image(self, registry_service):
        """Test that push_and_cleanup removes image from host after push."""
        mock_docker = MagicMock()
        mock_docker.images.remove.return_value = None

        with patch.object(registry_service, 'push_image', new_callable=AsyncMock) as mock_push:
            mock_push.return_value = True

            with patch.object(registry_service, 'image_exists', new_callable=AsyncMock) as mock_exists:
                mock_exists.return_value = True

                with patch.object(registry_service, '_get_docker_client', return_value=mock_docker):
                    result = await registry_service.push_and_cleanup("myimage:v1.0")

                    # Verify image was pushed to registry
                    mock_push.assert_called_once()
                    push_call_args = mock_push.call_args
                    assert push_call_args[0][0] == "myimage:v1.0"

                    # Verify image existence was checked
                    mock_exists.assert_called_once_with("myimage:v1.0")

                    # Verify image was removed from host (both registry tag and original)
                    assert mock_docker.images.remove.call_count == 2
                    remove_calls = mock_docker.images.remove.call_args_list
                    # First call removes registry tag (127.0.0.1:5000/myimage:v1.0)
                    assert "127.0.0.1:5000/myimage:v1.0" in str(remove_calls[0])
                    # Second call removes original tag
                    assert "myimage:v1.0" in str(remove_calls[1])

                    assert result is True

    @pytest.mark.asyncio
    async def test_push_and_cleanup_raises_on_push_failure(self, registry_service):
        """Test that push_and_cleanup raises RegistryPushError on failure."""
        with patch.object(registry_service, 'push_image', new_callable=AsyncMock) as mock_push:
            mock_push.return_value = False  # Simulate push failure

            with pytest.raises(RegistryPushError) as exc_info:
                await registry_service.push_and_cleanup("myimage:latest")

            assert "Failed to push image myimage:latest to registry" in str(exc_info.value)
            mock_push.assert_called_once()

    @pytest.mark.asyncio
    async def test_push_and_cleanup_raises_on_verification_failure(self, registry_service):
        """Test that push_and_cleanup raises RegistryPushError when verification fails."""
        with patch.object(registry_service, 'push_image', new_callable=AsyncMock) as mock_push:
            mock_push.return_value = True

            with patch.object(registry_service, 'image_exists', new_callable=AsyncMock) as mock_exists:
                mock_exists.return_value = False  # Image not found in registry after push

                with pytest.raises(RegistryPushError) as exc_info:
                    await registry_service.push_and_cleanup("myimage:latest")

                assert "not found in registry after push" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_push_and_cleanup_succeeds_if_cleanup_fails(self, registry_service):
        """Test that push_and_cleanup still succeeds if host cleanup fails."""
        mock_docker = MagicMock()
        mock_docker.images.remove.side_effect = docker.errors.APIError("Image in use by container")

        with patch.object(registry_service, 'push_image', new_callable=AsyncMock) as mock_push:
            mock_push.return_value = True

            with patch.object(registry_service, 'image_exists', new_callable=AsyncMock) as mock_exists:
                mock_exists.return_value = True

                with patch.object(registry_service, '_get_docker_client', return_value=mock_docker):
                    # Should not raise - cleanup failure is not critical
                    result = await registry_service.push_and_cleanup("myimage:latest")

                    assert result is True

    @pytest.mark.asyncio
    async def test_push_and_cleanup_handles_image_not_found_on_cleanup(self, registry_service):
        """Test that push_and_cleanup handles ImageNotFound during cleanup gracefully."""
        mock_docker = MagicMock()
        mock_docker.images.remove.side_effect = docker.errors.ImageNotFound("Image already removed")

        with patch.object(registry_service, 'push_image', new_callable=AsyncMock) as mock_push:
            mock_push.return_value = True

            with patch.object(registry_service, 'image_exists', new_callable=AsyncMock) as mock_exists:
                mock_exists.return_value = True

                with patch.object(registry_service, '_get_docker_client', return_value=mock_docker):
                    result = await registry_service.push_and_cleanup("myimage:latest")

                    # Should succeed - image already removed is fine
                    assert result is True

    @pytest.mark.asyncio
    async def test_push_and_cleanup_with_progress_callback(self, registry_service):
        """Test that push_and_cleanup calls progress callback at each stage."""
        mock_docker = MagicMock()
        mock_docker.images.remove.return_value = None
        progress_calls = []

        def track_progress(status, percent):
            progress_calls.append((status, percent))

        with patch.object(registry_service, 'push_image', new_callable=AsyncMock) as mock_push:
            mock_push.return_value = True

            with patch.object(registry_service, 'image_exists', new_callable=AsyncMock) as mock_exists:
                mock_exists.return_value = True

                with patch.object(registry_service, '_get_docker_client', return_value=mock_docker):
                    await registry_service.push_and_cleanup(
                        "myimage:latest",
                        progress_callback=track_progress
                    )

                    # Verify progress was tracked at key stages
                    assert len(progress_calls) >= 4
                    statuses = [call[0] for call in progress_calls]
                    assert "Pushing to registry..." in statuses
                    assert "Verifying in registry..." in statuses
                    assert "Cleaning up host..." in statuses
                    assert "Push and cleanup complete" in statuses
                    # Final call should be 100%
                    assert progress_calls[-1][1] == 100


class TestImageNeedsPush:
    """Tests for image_needs_push method."""

    @pytest.fixture
    def registry_service(self):
        """Create a fresh RegistryService instance for each test."""
        return RegistryService()

    @pytest.mark.asyncio
    async def test_image_needs_push_when_on_host_only(self, registry_service):
        """Test image_needs_push returns True when image is on host but not registry."""
        mock_docker = MagicMock()
        mock_docker.images.get.return_value = MagicMock()  # Image exists on host

        with patch.object(registry_service, 'image_exists', new_callable=AsyncMock) as mock_exists:
            mock_exists.return_value = False  # Not in registry

            with patch.object(registry_service, '_get_docker_client', return_value=mock_docker):
                result = await registry_service.image_needs_push("myimage:latest")

                assert result is True
                mock_exists.assert_called_once_with("myimage:latest")
                mock_docker.images.get.assert_called_once_with("myimage:latest")

    @pytest.mark.asyncio
    async def test_image_needs_push_false_when_in_registry(self, registry_service):
        """Test image_needs_push returns False when image is in registry."""
        with patch.object(registry_service, 'image_exists', new_callable=AsyncMock) as mock_exists:
            mock_exists.return_value = True  # Image is in registry

            result = await registry_service.image_needs_push("myimage:latest")

            assert result is False
            mock_exists.assert_called_once_with("myimage:latest")
            # Should NOT check host Docker since image is already in registry

    @pytest.mark.asyncio
    async def test_image_needs_push_false_when_not_on_host(self, registry_service):
        """Test image_needs_push returns False when image is not on host."""
        mock_docker = MagicMock()
        mock_docker.images.get.side_effect = docker.errors.ImageNotFound("not found")

        with patch.object(registry_service, 'image_exists', new_callable=AsyncMock) as mock_exists:
            mock_exists.return_value = False  # Not in registry

            with patch.object(registry_service, '_get_docker_client', return_value=mock_docker):
                result = await registry_service.image_needs_push("myimage:latest")

                assert result is False

    @pytest.mark.asyncio
    async def test_image_needs_push_false_on_docker_api_error(self, registry_service):
        """Test image_needs_push returns False on Docker API error."""
        mock_docker = MagicMock()
        mock_docker.images.get.side_effect = docker.errors.APIError("Connection refused")

        with patch.object(registry_service, 'image_exists', new_callable=AsyncMock) as mock_exists:
            mock_exists.return_value = False

            with patch.object(registry_service, '_get_docker_client', return_value=mock_docker):
                result = await registry_service.image_needs_push("myimage:latest")

                # Should return False on error, not raise
                assert result is False

    @pytest.mark.asyncio
    async def test_image_needs_push_with_tag(self, registry_service):
        """Test image_needs_push works with specific tag."""
        mock_docker = MagicMock()
        mock_docker.images.get.return_value = MagicMock()

        with patch.object(registry_service, 'image_exists', new_callable=AsyncMock) as mock_exists:
            mock_exists.return_value = False

            with patch.object(registry_service, '_get_docker_client', return_value=mock_docker):
                result = await registry_service.image_needs_push("myimage:v2.5.1")

                assert result is True
                mock_exists.assert_called_once_with("myimage:v2.5.1")


class TestDeleteImage:
    """Tests for delete_image method."""

    @pytest.fixture
    def registry_service(self):
        """Create a fresh RegistryService instance for each test."""
        return RegistryService()

    @pytest.mark.asyncio
    async def test_delete_image_calls_registry_api(self, registry_service):
        """Test delete_image properly calls registry DELETE endpoint."""
        mock_head_response = MagicMock()
        mock_head_response.status_code = 200
        mock_head_response.headers = {
            'Docker-Content-Digest': 'sha256:abc123def456'
        }

        mock_delete_response = MagicMock()
        mock_delete_response.status_code = 202

        with patch.object(registry_service, '_get_http_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.head = AsyncMock(return_value=mock_head_response)
            mock_client.delete = AsyncMock(return_value=mock_delete_response)
            mock_get_client.return_value = mock_client

            result = await registry_service.delete_image("myimage:v1.0")

            assert result is True
            # Verify HEAD request was made to get manifest digest
            mock_client.head.assert_called_once()
            head_call_args = mock_client.head.call_args
            assert "/v2/myimage/manifests/v1.0" in str(head_call_args)
            assert 'Accept' in head_call_args[1]['headers']

            # Verify DELETE request was made with digest
            mock_client.delete.assert_called_once()
            delete_call_args = mock_client.delete.call_args
            assert "/v2/myimage/manifests/sha256:abc123def456" in str(delete_call_args)

    @pytest.mark.asyncio
    async def test_delete_image_returns_false_on_404(self, registry_service):
        """Test delete_image returns False when image not found."""
        mock_head_response = MagicMock()
        mock_head_response.status_code = 404

        with patch.object(registry_service, '_get_http_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.head = AsyncMock(return_value=mock_head_response)
            mock_get_client.return_value = mock_client

            result = await registry_service.delete_image("nonexistent:latest")

            assert result is False
            mock_client.head.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_image_returns_false_on_no_digest_header(self, registry_service):
        """Test delete_image returns False when no digest header in response."""
        mock_head_response = MagicMock()
        mock_head_response.status_code = 200
        mock_head_response.headers = {}  # No Docker-Content-Digest header

        with patch.object(registry_service, '_get_http_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.head = AsyncMock(return_value=mock_head_response)
            mock_get_client.return_value = mock_client

            result = await registry_service.delete_image("myimage:latest")

            assert result is False

    @pytest.mark.asyncio
    async def test_delete_image_returns_false_on_delete_failure(self, registry_service):
        """Test delete_image returns False when DELETE request fails."""
        mock_head_response = MagicMock()
        mock_head_response.status_code = 200
        mock_head_response.headers = {
            'Docker-Content-Digest': 'sha256:abc123def456'
        }

        mock_delete_response = MagicMock()
        mock_delete_response.status_code = 405  # Method not allowed

        with patch.object(registry_service, '_get_http_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.head = AsyncMock(return_value=mock_head_response)
            mock_client.delete = AsyncMock(return_value=mock_delete_response)
            mock_get_client.return_value = mock_client

            result = await registry_service.delete_image("myimage:latest")

            assert result is False

    @pytest.mark.asyncio
    async def test_delete_image_handles_request_error(self, registry_service):
        """Test delete_image handles HTTP request errors gracefully."""
        with patch.object(registry_service, '_get_http_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.head = AsyncMock(side_effect=httpx.RequestError("Connection refused"))
            mock_get_client.return_value = mock_client

            result = await registry_service.delete_image("myimage:latest")

            assert result is False

    @pytest.mark.asyncio
    async def test_delete_image_with_path_in_name(self, registry_service):
        """Test delete_image works with image names containing paths."""
        mock_head_response = MagicMock()
        mock_head_response.status_code = 200
        mock_head_response.headers = {
            'Docker-Content-Digest': 'sha256:abc123'
        }

        mock_delete_response = MagicMock()
        mock_delete_response.status_code = 202

        with patch.object(registry_service, '_get_http_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.head = AsyncMock(return_value=mock_head_response)
            mock_client.delete = AsyncMock(return_value=mock_delete_response)
            mock_get_client.return_value = mock_client

            result = await registry_service.delete_image("cyroid/kali:latest")

            assert result is True
            # Verify the path is preserved in the API call
            head_call_args = mock_client.head.call_args
            assert "/v2/cyroid/kali/manifests/latest" in str(head_call_args)

    @pytest.mark.asyncio
    async def test_delete_image_uses_default_tag(self, registry_service):
        """Test delete_image uses 'latest' as default tag."""
        mock_head_response = MagicMock()
        mock_head_response.status_code = 200
        mock_head_response.headers = {
            'Docker-Content-Digest': 'sha256:abc123'
        }

        mock_delete_response = MagicMock()
        mock_delete_response.status_code = 202

        with patch.object(registry_service, '_get_http_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.head = AsyncMock(return_value=mock_head_response)
            mock_client.delete = AsyncMock(return_value=mock_delete_response)
            mock_get_client.return_value = mock_client

            result = await registry_service.delete_image("myimage")

            assert result is True
            # Verify 'latest' tag is used
            head_call_args = mock_client.head.call_args
            assert "/v2/myimage/manifests/latest" in str(head_call_args)


class TestRegistryPushError:
    """Tests for RegistryPushError exception."""

    def test_registry_push_error_is_exception(self):
        """Test RegistryPushError is an Exception subclass."""
        assert issubclass(RegistryPushError, Exception)

    def test_registry_push_error_stores_message(self):
        """Test RegistryPushError stores and returns error message."""
        error = RegistryPushError("Failed to push image myimage:latest")
        assert str(error) == "Failed to push image myimage:latest"

    def test_registry_push_error_can_be_raised_and_caught(self):
        """Test RegistryPushError can be raised and caught properly."""
        with pytest.raises(RegistryPushError) as exc_info:
            raise RegistryPushError("Push failed due to network error")

        assert "network error" in str(exc_info.value)
