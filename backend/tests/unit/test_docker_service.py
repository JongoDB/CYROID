# tests/unit/test_docker_service.py
"""Unit tests for Docker service using mocks."""
import pytest
from unittest.mock import Mock, MagicMock, patch


class TestDockerService:
    """Test Docker service methods with mocked Docker client."""
    
    @patch('docker.from_env')
    def test_create_network(self, mock_docker):
        """Test network creation."""
        from cyroid.services.docker_service import DockerService
        
        # Setup mock
        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_network = MagicMock()
        mock_network.id = "net123456789"
        mock_client.networks.create.return_value = mock_network
        
        # Create service and call method
        service = DockerService()
        network_id = service.create_network(
            name="test-network",
            subnet="10.0.1.0/24",
            gateway="10.0.1.1",
            internal=True
        )
        
        assert network_id == "net123456789"
        mock_client.networks.create.assert_called_once()
    
    @patch('docker.from_env')
    def test_delete_network(self, mock_docker):
        """Test network deletion."""
        from cyroid.services.docker_service import DockerService
        
        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_network = MagicMock()
        mock_client.networks.get.return_value = mock_network
        
        service = DockerService()
        result = service.delete_network("net123")
        
        assert result is True
        mock_network.remove.assert_called_once()
    
    @patch('docker.from_env')
    def test_create_container(self, mock_docker):
        """Test container creation."""
        from cyroid.services.docker_service import DockerService
        
        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_client.api.create_container.return_value = {"Id": "container123"}
        mock_network = MagicMock()
        mock_network.name = "test-net"
        mock_client.networks.get.return_value = mock_network
        
        service = DockerService()
        container_id = service.create_container(
            name="test-vm",
            image="ubuntu:22.04",
            network_id="net123",
            ip_address="10.0.1.10",
            cpu_limit=2,
            memory_limit_mb=2048
        )
        
        assert container_id == "container123"
    
    @patch('docker.from_env')
    def test_start_container(self, mock_docker):
        """Test starting a container."""
        from cyroid.services.docker_service import DockerService
        
        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        
        service = DockerService()
        result = service.start_container("container123")
        
        assert result is True
        mock_client.api.start.assert_called_once_with("container123")
    
    @patch('docker.from_env')
    def test_stop_container(self, mock_docker):
        """Test stopping a container."""
        from cyroid.services.docker_service import DockerService
        
        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        
        service = DockerService()
        result = service.stop_container("container123", timeout=10)
        
        assert result is True
        mock_client.api.stop.assert_called_once_with("container123", timeout=10)
    
    @patch('docker.from_env')
    def test_remove_container(self, mock_docker):
        """Test removing a container."""
        from cyroid.services.docker_service import DockerService
        
        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        
        service = DockerService()
        result = service.remove_container("container123", force=True)
        
        assert result is True
        mock_client.api.remove_container.assert_called_once_with("container123", force=True, v=True)
    
    @patch('docker.from_env')
    def test_get_container_status(self, mock_docker):
        """Test getting container status."""
        from cyroid.services.docker_service import DockerService
        
        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_container = MagicMock()
        mock_container.status = "running"
        mock_client.containers.get.return_value = mock_container
        
        service = DockerService()
        status = service.get_container_status("container123")
        
        assert status == "running"
    
    @patch('docker.from_env')
    def test_exec_command(self, mock_docker):
        """Test executing command in container."""
        from cyroid.services.docker_service import DockerService
        
        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_container = MagicMock()
        mock_container.exec_run.return_value = MagicMock(
            exit_code=0,
            output=(b"Hello World", b"")
        )
        mock_client.containers.get.return_value = mock_container
        
        service = DockerService()
        exit_code, output = service.exec_command("container123", "echo 'Hello World'")
        
        assert exit_code == 0
        assert "Hello World" in output
    
    @patch('docker.from_env')
    def test_create_snapshot(self, mock_docker):
        """Test creating a snapshot."""
        from cyroid.services.docker_service import DockerService
        
        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_container = MagicMock()
        mock_image = MagicMock()
        mock_image.id = "image123456"
        mock_container.commit.return_value = mock_image
        mock_client.containers.get.return_value = mock_container
        
        service = DockerService()
        image_id = service.create_snapshot("container123", "my-snapshot")
        
        assert image_id == "image123456"
        mock_container.commit.assert_called_once()
    
    @patch('docker.from_env')
    def test_get_system_info(self, mock_docker):
        """Test getting Docker system info."""
        from cyroid.services.docker_service import DockerService
        
        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_client.info.return_value = {
            "Containers": 5,
            "ContainersRunning": 3,
            "ContainersPaused": 0,
            "ContainersStopped": 2,
            "Images": 10,
            "ServerVersion": "24.0.0",
            "OperatingSystem": "Ubuntu 22.04",
            "Architecture": "x86_64",
            "NCPU": 8,
            "MemTotal": 16000000000
        }
        
        service = DockerService()
        info = service.get_system_info()
        
        assert info["containers"] == 5
        assert info["containers_running"] == 3
        assert info["docker_version"] == "24.0.0"
        assert info["cpus"] == 8


class TestImageTransfer:
    """Tests for enhanced image transfer functionality with progress reporting."""

    @pytest.mark.asyncio
    @patch('cyroid.services.docker_service.docker.from_env')
    async def test_transfer_image_with_progress_callback(self, mock_docker):
        """Transfer should report progress via callback."""
        from cyroid.services.docker_service import DockerService
        import docker as docker_pkg

        # Setup mock host Docker client
        mock_client = MagicMock()
        mock_docker.return_value = mock_client

        # Mock image with known size
        mock_image = MagicMock()
        mock_image.attrs = {'Size': 1024 * 1024 * 100}  # 100MB
        mock_image.save.return_value = iter([b'image_data_chunk'])
        mock_client.images.get.return_value = mock_image

        # Track progress calls
        progress_updates = []

        def progress_callback(transferred: int, total: int, status: str):
            progress_updates.append({'transferred': transferred, 'total': total, 'status': status})

        # Mock DinD service and range client
        mock_dind_service = MagicMock()
        mock_range_client = MagicMock()
        mock_dind_service.get_range_client.return_value = mock_range_client

        # Image doesn't exist in DinD (need to transfer) - use correct exception type
        mock_range_client.images.get.side_effect = docker_pkg.errors.ImageNotFound("not found")
        mock_range_client.images.load.return_value = [mock_image]

        # Create service with mocked DinD service
        service = DockerService(dind_service=mock_dind_service)

        # Execute transfer
        result = await service.transfer_image_to_dind(
            range_id='test-range',
            docker_url='tcp://172.30.1.1:2375',
            image='ubuntu:22.04',
            progress_callback=progress_callback
        )

        assert result is True
        assert len(progress_updates) >= 2  # At least start and complete
        assert progress_updates[0]['status'] == 'starting'
        assert progress_updates[-1]['status'] == 'complete'

    @pytest.mark.asyncio
    @patch('cyroid.services.docker_service.docker.from_env')
    async def test_transfer_image_already_exists_in_dind(self, mock_docker):
        """Transfer should report 'already_exists' when image is in DinD."""
        from cyroid.services.docker_service import DockerService

        # Setup mock host Docker client
        mock_client = MagicMock()
        mock_docker.return_value = mock_client

        # Mock image on host
        mock_image = MagicMock()
        mock_image.attrs = {'Size': 1024 * 1024 * 50}  # 50MB
        mock_client.images.get.return_value = mock_image

        # Track progress calls
        progress_updates = []

        def progress_callback(transferred: int, total: int, status: str):
            progress_updates.append({'transferred': transferred, 'total': total, 'status': status})

        # Mock DinD service and range client
        mock_dind_service = MagicMock()
        mock_range_client = MagicMock()
        mock_dind_service.get_range_client.return_value = mock_range_client

        # Image already exists in DinD
        mock_range_client.images.get.return_value = mock_image

        # Create service with mocked DinD service
        service = DockerService(dind_service=mock_dind_service)

        # Execute transfer
        result = await service.transfer_image_to_dind(
            range_id='test-range',
            docker_url='tcp://172.30.1.1:2375',
            image='ubuntu:22.04',
            progress_callback=progress_callback
        )

        assert result is True
        # Should have starting and already_exists
        statuses = [p['status'] for p in progress_updates]
        assert 'starting' in statuses
        assert 'already_exists' in statuses

    @pytest.mark.asyncio
    @patch('cyroid.services.docker_service.docker.from_env')
    async def test_transfer_image_pulls_if_missing(self, mock_docker):
        """Transfer should report 'pulling_to_host' and 'pulled_to_host' when pulling."""
        from cyroid.services.docker_service import DockerService
        import docker as docker_pkg

        # Setup mock host Docker client
        mock_client = MagicMock()
        mock_docker.return_value = mock_client

        # Mock image not found initially, then found after pull
        mock_image = MagicMock()
        mock_image.attrs = {'Size': 1024 * 1024 * 75}  # 75MB
        mock_image.save.return_value = iter([b'image_data_chunk'])
        mock_client.images.get.side_effect = docker_pkg.errors.ImageNotFound("not found")
        mock_client.images.pull.return_value = mock_image

        # Track progress calls
        progress_updates = []

        def progress_callback(transferred: int, total: int, status: str):
            progress_updates.append({'transferred': transferred, 'total': total, 'status': status})

        # Mock DinD service and range client
        mock_dind_service = MagicMock()
        mock_range_client = MagicMock()
        mock_dind_service.get_range_client.return_value = mock_range_client

        # Image doesn't exist in DinD - use correct exception type
        mock_range_client.images.get.side_effect = docker_pkg.errors.ImageNotFound("not found")
        mock_range_client.images.load.return_value = [mock_image]

        # Create service with mocked DinD service
        service = DockerService(dind_service=mock_dind_service)

        # Execute transfer
        result = await service.transfer_image_to_dind(
            range_id='test-range',
            docker_url='tcp://172.30.1.1:2375',
            image='nginx:latest',
            progress_callback=progress_callback
        )

        assert result is True
        statuses = [p['status'] for p in progress_updates]
        assert 'starting' in statuses
        assert 'pulling_to_host' in statuses
        assert 'pulled_to_host' in statuses
        assert 'complete' in statuses

    @pytest.mark.asyncio
    @patch('cyroid.services.docker_service.docker.from_env')
    async def test_transfer_image_error_reports_status(self, mock_docker):
        """Transfer should report 'error' status on failure."""
        from cyroid.services.docker_service import DockerService
        import docker as docker_pkg

        # Setup mock host Docker client
        mock_client = MagicMock()
        mock_docker.return_value = mock_client

        # Image not found and pull fails
        mock_client.images.get.side_effect = docker_pkg.errors.ImageNotFound("not found")
        mock_client.images.pull.side_effect = Exception("Network error")

        # Track progress calls
        progress_updates = []

        def progress_callback(transferred: int, total: int, status: str):
            progress_updates.append({'transferred': transferred, 'total': total, 'status': status})

        # Mock DinD service
        mock_dind_service = MagicMock()

        # Create service with mocked DinD service
        service = DockerService(dind_service=mock_dind_service)

        # Execute transfer
        result = await service.transfer_image_to_dind(
            range_id='test-range',
            docker_url='tcp://172.30.1.1:2375',
            image='nonexistent:image',
            progress_callback=progress_callback
        )

        assert result is False
        statuses = [p['status'] for p in progress_updates]
        assert 'starting' in statuses
        assert 'error' in statuses

    @pytest.mark.asyncio
    @patch('cyroid.services.docker_service.docker.from_env')
    async def test_transfer_image_without_callback(self, mock_docker):
        """Transfer should work without progress callback (backward compatible)."""
        from cyroid.services.docker_service import DockerService
        import docker as docker_pkg

        # Setup mock host Docker client
        mock_client = MagicMock()
        mock_docker.return_value = mock_client

        # Mock image
        mock_image = MagicMock()
        mock_image.attrs = {'Size': 1024 * 1024 * 100}
        mock_image.save.return_value = iter([b'image_data_chunk'])
        mock_client.images.get.return_value = mock_image

        # Mock DinD service and range client
        mock_dind_service = MagicMock()
        mock_range_client = MagicMock()
        mock_dind_service.get_range_client.return_value = mock_range_client

        # Image doesn't exist in DinD - use correct exception type
        mock_range_client.images.get.side_effect = docker_pkg.errors.ImageNotFound("not found")
        mock_range_client.images.load.return_value = [mock_image]

        # Create service with mocked DinD service
        service = DockerService(dind_service=mock_dind_service)

        # Execute transfer without callback (should not raise)
        result = await service.transfer_image_to_dind(
            range_id='test-range',
            docker_url='tcp://172.30.1.1:2375',
            image='ubuntu:22.04'
        )

        assert result is True
