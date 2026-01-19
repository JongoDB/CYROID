# backend/tests/unit/test_vnc_proxy_service.py
"""Unit tests for VNC proxy service for DinD console access."""
import pytest
from unittest.mock import MagicMock


class TestVNCProxyService:
    """Tests for VNC proxy deployment inside DinD."""

    @pytest.fixture
    def vnc_proxy_service(self):
        """Create VNC proxy service with mocked docker service."""
        from cyroid.services.vnc_proxy_service import VNCProxyService
        mock_docker_service = MagicMock()
        return VNCProxyService(docker_service=mock_docker_service)

    @pytest.mark.asyncio
    async def test_deploy_vnc_proxy_creates_container(self, vnc_proxy_service):
        """VNC proxy should be deployed inside DinD with correct port mappings."""
        mock_range_client = MagicMock()
        vnc_proxy_service.docker_service.get_range_client_sync.return_value = mock_range_client

        # Mock container creation
        mock_container = MagicMock()
        mock_container.id = 'proxy-container-123'
        mock_range_client.containers.run.return_value = mock_container

        vm_ports = [
            {'vm_id': 'vm-1', 'hostname': 'dc01', 'vnc_port': 8006, 'container_name': 'cyroid-dc01-vm-1'},
            {'vm_id': 'vm-2', 'hostname': 'web01', 'vnc_port': 6901, 'container_name': 'cyroid-web01-vm-2'},
        ]

        result = await vnc_proxy_service.deploy_vnc_proxy(
            range_id='range-123',
            docker_url='tcp://172.30.1.5:2375',
            dind_mgmt_ip='172.30.1.5',
            vm_ports=vm_ports
        )

        assert result['container_id'] == 'proxy-container-123'
        assert 'nginx' in mock_range_client.containers.run.call_args[1]['image']

    @pytest.mark.asyncio
    async def test_deploy_vnc_proxy_generates_correct_port_mappings(self, vnc_proxy_service):
        """Port mappings should use base port 15900 and increment."""
        mock_range_client = MagicMock()
        vnc_proxy_service.docker_service.get_range_client_sync.return_value = mock_range_client

        mock_container = MagicMock()
        mock_container.id = 'proxy-container-456'
        mock_range_client.containers.run.return_value = mock_container

        vm_ports = [
            {'vm_id': 'vm-1', 'hostname': 'dc01', 'vnc_port': 8006, 'container_name': 'cyroid-dc01-vm-1'},
            {'vm_id': 'vm-2', 'hostname': 'web01', 'vnc_port': 6901, 'container_name': 'cyroid-web01-vm-2'},
            {'vm_id': 'vm-3', 'hostname': 'db01', 'vnc_port': 8006, 'container_name': 'cyroid-db01-vm-3'},
        ]

        result = await vnc_proxy_service.deploy_vnc_proxy(
            range_id='range-456',
            docker_url='tcp://172.30.1.10:2375',
            dind_mgmt_ip='172.30.1.10',
            vm_ports=vm_ports
        )

        # Should have port mappings for each VM
        assert 'port_mappings' in result
        assert len(result['port_mappings']) == 3

        # Check port assignments
        assert result['port_mappings']['vm-1']['proxy_port'] == 15900
        assert result['port_mappings']['vm-2']['proxy_port'] == 15901
        assert result['port_mappings']['vm-3']['proxy_port'] == 15902

        # Check proxy host is the DinD management IP
        for vm_id, mapping in result['port_mappings'].items():
            assert mapping['proxy_host'] == '172.30.1.10'

    @pytest.mark.asyncio
    async def test_deploy_vnc_proxy_injects_nginx_config_via_command(self, vnc_proxy_service):
        """Nginx config should be injected via command (not volume mount) for DinD compatibility."""
        mock_range_client = MagicMock()
        vnc_proxy_service.docker_service.get_range_client_sync.return_value = mock_range_client

        mock_container = MagicMock()
        mock_container.id = 'proxy-container-789'
        mock_range_client.containers.run.return_value = mock_container

        vm_ports = [
            {'vm_id': 'vm-1', 'hostname': 'dc01', 'vnc_port': 8006, 'container_name': 'cyroid-dc01-vm-1'},
        ]

        await vnc_proxy_service.deploy_vnc_proxy(
            range_id='range-789',
            docker_url='tcp://172.30.1.15:2375',
            dind_mgmt_ip='172.30.1.15',
            vm_ports=vm_ports
        )

        # Check that containers.run was called with command (not volumes)
        call_kwargs = mock_range_client.containers.run.call_args[1]

        # Should NOT have volumes (DinD can't see host paths)
        assert 'volumes' not in call_kwargs

        # Should have command that injects config via shell
        assert 'command' in call_kwargs
        command = call_kwargs['command']
        assert command[0] == 'sh'
        assert command[1] == '-c'
        # Command should write config to nginx.conf and start nginx
        assert '/etc/nginx/nginx.conf' in command[2]
        assert 'nginx -g' in command[2]
        # Should contain nginx stream config
        assert 'stream {' in command[2]

    @pytest.mark.asyncio
    async def test_remove_vnc_proxy_removes_container(self, vnc_proxy_service):
        """Remove should stop and delete the proxy container."""
        mock_range_client = MagicMock()
        vnc_proxy_service.docker_service.get_range_client_sync.return_value = mock_range_client

        mock_container = MagicMock()
        mock_range_client.containers.get.return_value = mock_container

        await vnc_proxy_service.remove_vnc_proxy(
            range_id='range-123',
            docker_url='tcp://172.30.1.5:2375'
        )

        mock_range_client.containers.get.assert_called_once()
        mock_container.stop.assert_called_once()
        mock_container.remove.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_vnc_proxy_redeploys(self, vnc_proxy_service):
        """Update should remove old proxy and deploy new one."""
        mock_range_client = MagicMock()
        vnc_proxy_service.docker_service.get_range_client_sync.return_value = mock_range_client

        # Mock existing container removal
        mock_old_container = MagicMock()
        mock_range_client.containers.get.return_value = mock_old_container

        # Mock new container creation
        mock_new_container = MagicMock()
        mock_new_container.id = 'new-proxy-container'
        mock_range_client.containers.run.return_value = mock_new_container

        vm_ports = [
            {'vm_id': 'vm-1', 'hostname': 'dc01', 'vnc_port': 8006, 'container_name': 'cyroid-dc01-vm-1'},
        ]

        result = await vnc_proxy_service.update_vnc_proxy(
            range_id='range-123',
            docker_url='tcp://172.30.1.5:2375',
            dind_mgmt_ip='172.30.1.5',
            vm_ports=vm_ports
        )

        # Should have attempted to remove old container
        mock_old_container.stop.assert_called_once()
        mock_old_container.remove.assert_called_once()

        # Should have created new container
        assert result['container_id'] == 'new-proxy-container'

    def test_get_vnc_url_for_vm(self, vnc_proxy_service):
        """Helper should construct proper VNC URL."""
        port_mappings = {
            'vm-1': {'proxy_port': 15900, 'proxy_host': '172.30.1.5', 'original_port': 8006},
            'vm-2': {'proxy_port': 15901, 'proxy_host': '172.30.1.5', 'original_port': 6901},
        }

        url = vnc_proxy_service.get_vnc_url_for_vm('vm-1', port_mappings)
        assert url == 'http://172.30.1.5:15900'

        url2 = vnc_proxy_service.get_vnc_url_for_vm('vm-2', port_mappings)
        assert url2 == 'http://172.30.1.5:15901'

    def test_get_vnc_url_for_vm_not_found(self, vnc_proxy_service):
        """Helper should return None for unknown VM."""
        port_mappings = {
            'vm-1': {'proxy_port': 15900, 'proxy_host': '172.30.1.5', 'original_port': 8006},
        }

        url = vnc_proxy_service.get_vnc_url_for_vm('vm-unknown', port_mappings)
        assert url is None

    @pytest.mark.asyncio
    async def test_deploy_vnc_proxy_with_empty_vm_list(self, vnc_proxy_service):
        """Deploy with no VMs should still create container but with no upstream proxies."""
        mock_range_client = MagicMock()
        vnc_proxy_service.docker_service.get_range_client_sync.return_value = mock_range_client

        mock_container = MagicMock()
        mock_container.id = 'empty-proxy-container'
        mock_range_client.containers.run.return_value = mock_container

        result = await vnc_proxy_service.deploy_vnc_proxy(
            range_id='range-empty',
            docker_url='tcp://172.30.1.20:2375',
            dind_mgmt_ip='172.30.1.20',
            vm_ports=[]
        )

        assert result['container_id'] == 'empty-proxy-container'
        assert result['port_mappings'] == {}

    @pytest.mark.asyncio
    async def test_deploy_vnc_proxy_labels_container(self, vnc_proxy_service):
        """Proxy container should have CYROID labels for identification."""
        mock_range_client = MagicMock()
        vnc_proxy_service.docker_service.get_range_client_sync.return_value = mock_range_client

        mock_container = MagicMock()
        mock_container.id = 'labeled-proxy-container'
        mock_range_client.containers.run.return_value = mock_container

        vm_ports = [
            {'vm_id': 'vm-1', 'hostname': 'dc01', 'vnc_port': 8006, 'container_name': 'cyroid-dc01-vm-1'},
        ]

        await vnc_proxy_service.deploy_vnc_proxy(
            range_id='range-labeled',
            docker_url='tcp://172.30.1.25:2375',
            dind_mgmt_ip='172.30.1.25',
            vm_ports=vm_ports
        )

        call_kwargs = mock_range_client.containers.run.call_args[1]
        assert 'labels' in call_kwargs
        labels = call_kwargs['labels']
        assert labels.get('cyroid.type') == 'vnc-proxy'
        assert 'cyroid.range_id' in labels


class TestVNCProxyNginxConfig:
    """Tests for nginx configuration generation."""

    @pytest.fixture
    def vnc_proxy_service(self):
        """Create VNC proxy service with mocked docker service."""
        from cyroid.services.vnc_proxy_service import VNCProxyService
        mock_docker_service = MagicMock()
        return VNCProxyService(docker_service=mock_docker_service)

    def test_generate_nginx_config_stream_blocks(self, vnc_proxy_service):
        """Generated config should have stream blocks for each VM."""
        vm_ports = [
            {'vm_id': 'vm-1', 'hostname': 'dc01', 'vnc_port': 8006, 'container_name': 'cyroid-dc01-vm-1'},
            {'vm_id': 'vm-2', 'hostname': 'web01', 'vnc_port': 6901, 'container_name': 'cyroid-web01-vm-2'},
        ]

        config, _ = vnc_proxy_service._generate_nginx_config(vm_ports)

        # Should contain stream directive
        assert 'stream {' in config

        # Should contain upstream blocks for each VM
        assert 'upstream vnc_vm1' in config or 'upstream vnc_' in config
        assert 'cyroid-dc01-vm-1:8006' in config
        assert 'cyroid-web01-vm-2:6901' in config

        # Should have server blocks listening on proxy ports
        assert 'listen 15900' in config
        assert 'listen 15901' in config

        # Should have proxy_timeout
        assert 'proxy_timeout' in config

    def test_generate_nginx_config_returns_port_mappings(self, vnc_proxy_service):
        """Config generation should return port mapping dict."""
        vm_ports = [
            {'vm_id': 'vm-1', 'hostname': 'dc01', 'vnc_port': 8006, 'container_name': 'cyroid-dc01-vm-1'},
        ]

        _, port_mappings = vnc_proxy_service._generate_nginx_config(vm_ports)

        assert 'vm-1' in port_mappings
        assert port_mappings['vm-1']['proxy_port'] == 15900
        assert port_mappings['vm-1']['original_port'] == 8006
