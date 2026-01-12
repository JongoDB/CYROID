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
