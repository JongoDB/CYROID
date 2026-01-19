# backend/tests/unit/test_dind_service.py
"""Unit tests for DinD service using mocks."""
import pytest
from unittest.mock import MagicMock, patch, call


class TestDinDIptables:
    """Tests for iptables isolation inside DinD containers."""

    @pytest.mark.asyncio
    @patch('cyroid.services.dind_service.docker.from_env')
    async def test_setup_network_isolation_in_dind(self, mock_docker):
        """Should apply iptables rules inside DinD container."""
        from cyroid.services.dind_service import DinDService

        # Setup mock host Docker client
        mock_client = MagicMock()
        mock_docker.return_value = mock_client

        # Mock the DinD container that runs on the host
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (0, b'')
        mock_client.containers.get.return_value = mock_container

        service = DinDService()

        await service.setup_network_isolation_in_dind(
            range_id='range-123-abc-456',
            networks=['lan', 'dmz'],
            allow_internet=['lan'],  # Only LAN can reach internet
        )

        # Verify iptables commands were executed
        exec_calls = mock_container.exec_run.call_args_list
        assert len(exec_calls) >= 2  # At least isolation rules

        # Verify key rules were applied
        commands_executed = [str(c) for c in exec_calls]
        commands_str = ' '.join(commands_executed)

        # Should set default FORWARD policy to DROP
        assert 'FORWARD DROP' in commands_str or '-P FORWARD DROP' in commands_str

        # Should allow established connections
        assert 'ESTABLISHED' in commands_str

    @pytest.mark.asyncio
    @patch('cyroid.services.dind_service.docker.from_env')
    async def test_setup_network_isolation_allows_internet_for_specified_networks(self, mock_docker):
        """Should allow internet access only for specified networks."""
        from cyroid.services.dind_service import DinDService

        mock_client = MagicMock()
        mock_docker.return_value = mock_client

        mock_container = MagicMock()
        mock_container.exec_run.return_value = (0, b'')
        mock_client.containers.get.return_value = mock_container

        service = DinDService()

        await service.setup_network_isolation_in_dind(
            range_id='range-123-abc-456',
            networks=['lan', 'dmz', 'management'],
            allow_internet=['lan', 'management'],
        )

        exec_calls = mock_container.exec_run.call_args_list
        commands_str = ' '.join(str(c) for c in exec_calls)

        # Should have NAT/MASQUERADE for internet access
        assert 'MASQUERADE' in commands_str or 'nat' in commands_str

    @pytest.mark.asyncio
    @patch('cyroid.services.dind_service.docker.from_env')
    async def test_setup_network_isolation_no_internet(self, mock_docker):
        """Should work with no internet access for any network."""
        from cyroid.services.dind_service import DinDService

        mock_client = MagicMock()
        mock_docker.return_value = mock_client

        mock_container = MagicMock()
        mock_container.exec_run.return_value = (0, b'')
        mock_client.containers.get.return_value = mock_container

        service = DinDService()

        # Call with no internet access (air-gapped mode)
        await service.setup_network_isolation_in_dind(
            range_id='range-123-abc-456',
            networks=['lan', 'dmz'],
            allow_internet=[],  # No internet for anyone
        )

        exec_calls = mock_container.exec_run.call_args_list
        # Should still apply basic isolation rules
        assert len(exec_calls) >= 2

    @pytest.mark.asyncio
    @patch('cyroid.services.dind_service.docker.from_env')
    async def test_setup_network_isolation_handles_container_not_found(self, mock_docker):
        """Should handle missing DinD container gracefully."""
        from cyroid.services.dind_service import DinDService
        from docker.errors import NotFound

        mock_client = MagicMock()
        mock_docker.return_value = mock_client

        # Container not found
        mock_client.containers.get.side_effect = NotFound("Container not found")

        service = DinDService()

        # Should not raise, just log and return
        await service.setup_network_isolation_in_dind(
            range_id='nonexistent-range',
            networks=['lan'],
            allow_internet=[],
        )

    @pytest.mark.asyncio
    @patch('cyroid.services.dind_service.docker.from_env')
    async def test_setup_network_isolation_logs_failed_rules(self, mock_docker):
        """Should log warning when iptables rule fails but continue."""
        from cyroid.services.dind_service import DinDService

        mock_client = MagicMock()
        mock_docker.return_value = mock_client

        mock_container = MagicMock()
        # First rule succeeds, second fails, third succeeds
        mock_container.exec_run.side_effect = [
            (0, b''),
            (1, b'iptables: Bad rule'),
            (0, b''),
        ]
        mock_client.containers.get.return_value = mock_container

        service = DinDService()

        # Should not raise even with failed rules
        await service.setup_network_isolation_in_dind(
            range_id='range-123-abc-456',
            networks=['lan'],
            allow_internet=[],
        )

        # Should have attempted all rules despite failure
        assert mock_container.exec_run.call_count >= 2

    @pytest.mark.asyncio
    @patch('cyroid.services.dind_service.docker.from_env')
    async def test_teardown_network_isolation_in_dind(self, mock_docker):
        """Teardown should be a no-op (rules removed with container)."""
        from cyroid.services.dind_service import DinDService

        mock_client = MagicMock()
        mock_docker.return_value = mock_client

        service = DinDService()

        # Should complete without error
        await service.teardown_network_isolation_in_dind(range_id='range-123')

        # Should not try to do anything (container destruction handles cleanup)


class TestDinDContainerManagement:
    """Tests for DinD container lifecycle management."""

    @pytest.mark.asyncio
    @patch('cyroid.services.dind_service.docker.from_env')
    async def test_get_dind_container_name_format(self, mock_docker):
        """Container name should use first 12 chars of range_id without dashes."""
        from cyroid.services.dind_service import DinDService

        mock_client = MagicMock()
        mock_docker.return_value = mock_client

        # Mock container not found to verify the name being looked up
        from docker.errors import NotFound
        mock_client.containers.get.side_effect = NotFound("not found")

        service = DinDService()

        # Try to set up isolation - will fail but we can check the container name
        await service.setup_network_isolation_in_dind(
            range_id='abc12345-6789-def0-1234-567890abcdef',
            networks=['lan'],
            allow_internet=[],
        )

        # Check the container name that was looked up
        # Range ID without dashes: abc1234567890def01234567890abcdef
        # First 12 chars: abc123456789
        mock_client.containers.get.assert_called_once()
        container_name = mock_client.containers.get.call_args[0][0]
        assert container_name == 'cyroid-range-abc123456789'
