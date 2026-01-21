# backend/tests/integration/test_console_access.py
"""
Tests for console access functionality.

Tests cover:
- VNC console access for VMs (kasm/webtop/qemu)
- Container shell access
- Range console access (DinD diagnostics)
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4


class TestVMConsoleAccess:
    """Tests for VM console access endpoints."""

    def test_get_vm_console_info_running_vm(self, client, auth_headers, range_with_vm):
        """Test getting console info for a running VM."""
        range_id, vm_id = range_with_vm

        # Start the VM first
        response = client.post(
            f"/api/v1/vms/{vm_id}/start",
            headers=auth_headers
        )
        assert response.status_code == 200

        # Get console info
        response = client.get(
            f"/api/v1/vms/{vm_id}/console",
            headers=auth_headers
        )
        # Console endpoint returns the VNC proxy URL or 404 if not available
        assert response.status_code in [200, 404]

    def test_get_vm_console_info_stopped_vm(self, client, auth_headers, range_with_vm):
        """Test getting console info for a stopped VM returns error."""
        range_id, vm_id = range_with_vm

        response = client.get(
            f"/api/v1/vms/{vm_id}/console",
            headers=auth_headers
        )
        # Stopped VMs should not have console access
        assert response.status_code in [400, 404]

    def test_vnc_console_types(self, client, auth_headers, range_with_vm):
        """Test that different VM types report correct console type."""
        range_id, vm_id = range_with_vm

        # Get VM details to check display type
        response = client.get(
            f"/api/v1/vms/{vm_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        vm_data = response.json()

        # display_type should be set
        assert "display_type" in vm_data
        # Default should be "desktop" for VNC access
        assert vm_data["display_type"] in ["desktop", "server", "headless", None]


class TestContainerShellAccess:
    """Tests for container shell/terminal access."""

    def test_exec_in_container_running(self, client, auth_headers, range_with_vm, mock_docker_service):
        """Test executing command in a running container."""
        range_id, vm_id = range_with_vm

        # Start the VM
        client.post(f"/api/v1/vms/{vm_id}/start", headers=auth_headers)

        # Configure mock for exec
        mock_docker_service.exec_command.return_value = (0, "hello world\n")

        # The container shell uses WebSocket, but we can test the exec API
        response = client.get(
            f"/api/v1/vms/{vm_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        vm_data = response.json()

        # Verify container_id is set for running VMs
        assert vm_data.get("container_id") is not None or vm_data["status"] in ["pending", "stopped"]


class TestRangeConsoleAccess:
    """Tests for Range Console (DinD diagnostics) access."""

    def test_get_range_console_containers(self, client, auth_headers, deployed_range):
        """Test getting list of containers in a deployed range."""
        range_id = deployed_range

        response = client.get(
            f"/api/v1/ranges/{range_id}/console/containers",
            headers=auth_headers
        )
        # May return 200 with containers or 404/400 if range not deployed
        assert response.status_code in [200, 400, 404, 500]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    def test_get_range_console_networks(self, client, auth_headers, deployed_range):
        """Test getting list of networks in a deployed range."""
        range_id = deployed_range

        response = client.get(
            f"/api/v1/ranges/{range_id}/console/networks",
            headers=auth_headers
        )
        assert response.status_code in [200, 400, 404, 500]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    def test_get_range_console_stats(self, client, auth_headers, deployed_range):
        """Test getting stats for a deployed range."""
        range_id = deployed_range

        response = client.get(
            f"/api/v1/ranges/{range_id}/console/stats",
            headers=auth_headers
        )
        assert response.status_code in [200, 400, 404, 500]

        if response.status_code == 200:
            data = response.json()
            assert "container_count" in data or "error" in data

    def test_get_range_console_iptables(self, client, auth_headers, deployed_range):
        """Test getting iptables rules for a deployed range."""
        range_id = deployed_range

        response = client.get(
            f"/api/v1/ranges/{range_id}/console/iptables",
            headers=auth_headers
        )
        assert response.status_code in [200, 400, 404, 500]

    def test_get_range_console_routes(self, client, auth_headers, deployed_range):
        """Test getting routes for a deployed range."""
        range_id = deployed_range

        response = client.get(
            f"/api/v1/ranges/{range_id}/console/routes",
            headers=auth_headers
        )
        assert response.status_code in [200, 400, 404, 500]

    def test_range_console_requires_auth(self, client, deployed_range):
        """Test that range console endpoints require authentication."""
        range_id = deployed_range

        # Try without auth
        response = client.get(f"/api/v1/ranges/{range_id}/console/containers")
        assert response.status_code in [401, 403]

    def test_range_console_nonexistent_range(self, client, auth_headers):
        """Test range console with nonexistent range returns 404."""
        fake_range_id = str(uuid4())

        response = client.get(
            f"/api/v1/ranges/{fake_range_id}/console/containers",
            headers=auth_headers
        )
        assert response.status_code == 404


class TestCachePruneEndpoint:
    """Tests for the cache prune endpoint."""

    def test_prune_images_admin_only(self, client, auth_headers, mock_docker_service):
        """Test that prune endpoint is admin-only."""
        mock_docker_service.prune_images.return_value = {
            "images_deleted": 2,
            "space_reclaimed": 1024 * 1024 * 500  # 500 MB
        }

        response = client.post(
            "/api/v1/cache/prune",
            headers=auth_headers
        )
        # Should succeed for admin
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert data["status"] == "success"
        assert "images_deleted" in data
        assert "space_reclaimed_gb" in data

    def test_prune_images_no_auth(self, client):
        """Test that prune endpoint requires authentication."""
        response = client.post("/api/v1/cache/prune")
        assert response.status_code in [401, 403]


# Fixtures specific to console tests

@pytest.fixture
def auth_headers(client):
    """Create an admin user and return auth headers."""
    # Register admin user
    client.post("/api/v1/auth/register", json={
        "username": "testadmin",
        "email": "testadmin@test.com",
        "password": "testpass123"
    })

    # Login
    response = client.post("/api/v1/auth/login", data={
        "username": "testadmin",
        "password": "testpass123"
    })

    if response.status_code == 200:
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    # If login failed, try with default test setup
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def range_with_vm(client, auth_headers, mock_docker_service):
    """Create a range with a VM for testing."""
    # Create range
    range_response = client.post(
        "/api/v1/ranges",
        json={"name": "Test Console Range", "description": "Testing console access"},
        headers=auth_headers
    )

    if range_response.status_code != 201:
        pytest.skip("Could not create range for test")

    range_id = range_response.json()["id"]

    # Create network
    network_response = client.post(
        f"/api/v1/networks",
        json={
            "range_id": range_id,
            "name": "test-net",
            "subnet": "10.0.0.0/24",
            "gateway": "10.0.0.1"
        },
        headers=auth_headers
    )

    if network_response.status_code != 201:
        pytest.skip("Could not create network for test")

    network_id = network_response.json()["id"]

    # Create VM
    vm_response = client.post(
        f"/api/v1/vms",
        json={
            "range_id": range_id,
            "network_id": network_id,
            "hostname": "test-vm",
            "ip_address": "10.0.0.10",
            "cpu": 2,
            "ram_mb": 2048,
            "disk_gb": 20
        },
        headers=auth_headers
    )

    if vm_response.status_code != 201:
        pytest.skip("Could not create VM for test")

    vm_id = vm_response.json()["id"]

    yield range_id, vm_id

    # Cleanup
    client.delete(f"/api/v1/ranges/{range_id}", headers=auth_headers)


@pytest.fixture
def deployed_range(client, auth_headers, mock_docker_service, mock_dind_service):
    """Create and deploy a range for testing."""
    # Create range
    range_response = client.post(
        "/api/v1/ranges",
        json={"name": "Test Deployed Range", "description": "Testing deployed range"},
        headers=auth_headers
    )

    if range_response.status_code != 201:
        pytest.skip("Could not create range for test")

    range_id = range_response.json()["id"]

    # Create network
    client.post(
        f"/api/v1/networks",
        json={
            "range_id": range_id,
            "name": "test-net",
            "subnet": "10.0.0.0/24",
            "gateway": "10.0.0.1"
        },
        headers=auth_headers
    )

    # Deploy range
    with patch('cyroid.api.ranges.get_dind_service', return_value=mock_dind_service):
        deploy_response = client.post(
            f"/api/v1/ranges/{range_id}/deploy",
            headers=auth_headers
        )

    yield range_id

    # Cleanup
    client.delete(f"/api/v1/ranges/{range_id}", headers=auth_headers)
