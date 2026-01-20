# backend/tests/integration/test_vm_library.py
"""Integration tests for VM Library workflow.

Tests the following VM Library features:
1. Creating VMs from snapshots (snapshot-based VM creation)
2. Promoting Docker images from cache to VM Library
3. Pre-deployment validation for ranges

Note: The first user registered in the system becomes admin automatically.
"""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def auth_headers(client):
    """Register and login the first user (becomes admin automatically)."""
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "testpassword123",
        },
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "testpassword123"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def non_admin_auth_headers(client, auth_headers, db_session):
    """Register and login a non-admin user (second user in the system).

    Depends on auth_headers to ensure admin user is created first.
    The user is manually approved in the database since new users need admin approval.
    """
    from cyroid.models.user import User

    client.post(
        "/api/v1/auth/register",
        json={
            "username": "regularuser",
            "email": "regular@example.com",
            "password": "regularpassword123",
        },
    )

    # Approve the user in the database (normally requires admin approval)
    user = db_session.query(User).filter(User.username == "regularuser").first()
    user.is_approved = True
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"username": "regularuser", "password": "regularpassword123"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_range(client, auth_headers):
    """Create a test range."""
    response = client.post(
        "/api/v1/ranges",
        headers=auth_headers,
        json={"name": "Test Range"},
    )
    return response.json()


@pytest.fixture
def test_network(client, auth_headers, test_range):
    """Create and provision a test network."""
    response = client.post(
        "/api/v1/networks",
        headers=auth_headers,
        json={
            "range_id": test_range["id"],
            "name": "Test Network",
            "subnet": "172.16.1.0/24",
            "gateway": "172.16.1.1",
        },
    )
    network = response.json()
    # Provision the network so VMs can be started
    client.post(f"/api/v1/networks/{network['id']}/provision", headers=auth_headers)
    # Re-fetch to get the updated docker_network_id
    response = client.get(f"/api/v1/networks/{network['id']}", headers=auth_headers)
    return response.json()


@pytest.fixture
def test_snapshot(client, db_session, auth_headers):
    """Create a test snapshot in the VM Library (is_global=True)."""
    from cyroid.models.snapshot import Snapshot

    # Create a snapshot directly in the database
    snapshot = Snapshot(
        name="Test Library Snapshot",
        description="A test snapshot for VM Library",
        docker_image_id="sha256:abc123def456",
        docker_image_tag="alpine:latest",
        os_type="linux",
        vm_type="container",
        default_cpu=1,
        default_ram_mb=512,
        default_disk_gb=10,
        is_global=True,
        tags=["test", "linux"],
    )
    db_session.add(snapshot)
    db_session.commit()
    db_session.refresh(snapshot)

    return {
        "id": str(snapshot.id),
        "name": snapshot.name,
        "description": snapshot.description,
        "docker_image_tag": snapshot.docker_image_tag,
        "is_global": snapshot.is_global,
    }


class TestVMLibrary:
    """Integration tests for VM Library workflow."""

    @pytest.mark.integration
    def test_create_vm_from_snapshot(
        self, client, auth_headers, test_range, test_network, test_snapshot
    ):
        """Test creating a VM using snapshot_id instead of template_id.

        Verifies that:
        - VM can be created with snapshot_id
        - Response has snapshot_id set
        - Response has template_id as None
        """
        response = client.post(
            "/api/v1/vms",
            headers=auth_headers,
            json={
                "range_id": test_range["id"],
                "network_id": test_network["id"],
                "snapshot_id": test_snapshot["id"],
                "hostname": "snapshot-vm-01",
                "ip_address": "172.16.1.10",
                "cpu": 1,
                "ram_mb": 512,
                "disk_gb": 10,
            },
        )

        assert response.status_code == 201, f"Failed to create VM: {response.json()}"
        data = response.json()

        # Verify snapshot-based VM creation
        assert data["snapshot_id"] == test_snapshot["id"]
        assert data["template_id"] is None
        assert data["hostname"] == "snapshot-vm-01"
        assert data["ip_address"] == "172.16.1.10"
        assert data["status"] == "pending"

    @pytest.mark.integration
    def test_create_vm_requires_template_or_snapshot(
        self, client, auth_headers, test_range, test_network
    ):
        """Test that VM creation fails without template_id or snapshot_id."""
        response = client.post(
            "/api/v1/vms",
            headers=auth_headers,
            json={
                "range_id": test_range["id"],
                "network_id": test_network["id"],
                # No template_id or snapshot_id provided
                "hostname": "invalid-vm",
                "ip_address": "172.16.1.11",
                "cpu": 1,
                "ram_mb": 512,
                "disk_gb": 10,
            },
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.integration
    def test_create_vm_cannot_have_both_template_and_snapshot(
        self, client, auth_headers, test_range, test_network, test_snapshot
    ):
        """Test that VM creation fails with both template_id and snapshot_id."""
        # First create a template
        template_response = client.post(
            "/api/v1/templates",
            headers=auth_headers,
            json={
                "name": "Test Template",
                "os_type": "linux",
                "os_variant": "Alpine",
                "base_image": "alpine:latest",
            },
        )
        template_id = template_response.json()["id"]

        response = client.post(
            "/api/v1/vms",
            headers=auth_headers,
            json={
                "range_id": test_range["id"],
                "network_id": test_network["id"],
                "template_id": template_id,
                "snapshot_id": test_snapshot["id"],  # Both provided
                "hostname": "invalid-vm",
                "ip_address": "172.16.1.12",
                "cpu": 1,
                "ram_mb": 512,
                "disk_gb": 10,
            },
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.integration
    def test_promote_image_to_library(self, client, auth_headers):
        """Test promoting a cached Docker image to the VM Library.

        Note: auth_headers is the first user, which is automatically admin.

        Verifies that:
        - POST /api/v1/cache/promote-to-library works
        - Response has name and is_global=True
        """
        # Mock the Docker client to simulate an existing image
        mock_image = MagicMock()
        mock_image.id = "sha256:testimage123456"
        mock_image.tags = ["alpine:latest"]

        with patch('cyroid.api.cache.get_docker_service') as mock_get_docker:
            mock_docker = MagicMock()
            mock_docker.client.images.get.return_value = mock_image
            mock_get_docker.return_value = mock_docker

            response = client.post(
                "/api/v1/cache/promote-to-library",
                headers=auth_headers,  # First user is admin
                json={
                    "image_name": "alpine:latest",
                    "name": "Alpine Linux Library",
                    "description": "Lightweight Alpine Linux container",
                    "os_type": "linux",
                    "vm_type": "container",
                    "default_cpu": 1,
                    "default_ram_mb": 256,
                    "default_disk_gb": 10,
                    "tags": ["linux", "alpine", "minimal"],
                },
            )

        assert response.status_code == 201, f"Failed to promote image: {response.json()}"
        data = response.json()

        # Verify the promoted snapshot
        assert data["name"] == "Alpine Linux Library"
        assert data["is_global"] is True
        assert data["docker_image_tag"] == "alpine:latest"
        assert data["os_type"] == "linux"
        assert data["vm_type"] == "container"

    @pytest.mark.integration
    def test_promote_image_requires_admin(self, client, non_admin_auth_headers):
        """Test that promoting images requires admin role.

        Uses non_admin_auth_headers which creates a second user without admin rights.
        """
        response = client.post(
            "/api/v1/cache/promote-to-library",
            headers=non_admin_auth_headers,  # Non-admin user
            json={
                "image_name": "alpine:latest",
                "name": "Should Fail",
                "os_type": "linux",
                "vm_type": "container",
            },
        )

        assert response.status_code == 403

    @pytest.mark.integration
    def test_deployment_validation(self, client, auth_headers, test_range):
        """Test pre-deployment validation for a range.

        Verifies that:
        - GET /api/v1/ranges/{range_id}/validate works
        - Response contains valid, errors, and warnings fields
        """
        response = client.get(
            f"/api/v1/ranges/{test_range['id']}/validate",
            headers=auth_headers,
        )

        assert response.status_code == 200, f"Validation failed: {response.json()}"
        data = response.json()

        # Verify response structure
        assert "valid" in data
        assert "errors" in data
        assert "warnings" in data
        assert isinstance(data["valid"], bool)
        assert isinstance(data["errors"], list)
        assert isinstance(data["warnings"], list)

    @pytest.mark.integration
    def test_deployment_validation_with_vms(
        self, client, auth_headers, test_range, test_network, test_snapshot
    ):
        """Test deployment validation with VMs in the range."""
        # Create a VM from snapshot
        client.post(
            "/api/v1/vms",
            headers=auth_headers,
            json={
                "range_id": test_range["id"],
                "network_id": test_network["id"],
                "snapshot_id": test_snapshot["id"],
                "hostname": "validation-test-vm",
                "ip_address": "172.16.1.20",
                "cpu": 1,
                "ram_mb": 512,
                "disk_gb": 10,
            },
        )

        response = client.get(
            f"/api/v1/ranges/{test_range['id']}/validate",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Validation should complete (may have warnings about missing images in test env)
        assert "valid" in data
        assert "errors" in data
        assert "warnings" in data

    @pytest.mark.integration
    def test_deployment_validation_nonexistent_range(self, client, auth_headers):
        """Test deployment validation for a non-existent range."""
        fake_range_id = "00000000-0000-0000-0000-000000000000"
        response = client.get(
            f"/api/v1/ranges/{fake_range_id}/validate",
            headers=auth_headers,
        )

        assert response.status_code == 404


class TestVMLibrarySnapshot:
    """Additional tests for snapshot-based VM operations."""

    @pytest.mark.integration
    def test_get_vm_shows_snapshot_info(
        self, client, auth_headers, test_range, test_network, test_snapshot
    ):
        """Test that getting a VM shows its snapshot source."""
        # Create VM from snapshot
        create_response = client.post(
            "/api/v1/vms",
            headers=auth_headers,
            json={
                "range_id": test_range["id"],
                "network_id": test_network["id"],
                "snapshot_id": test_snapshot["id"],
                "hostname": "snapshot-info-vm",
                "ip_address": "172.16.1.30",
                "cpu": 1,
                "ram_mb": 512,
                "disk_gb": 10,
            },
        )
        vm_id = create_response.json()["id"]

        # Get the VM
        response = client.get(f"/api/v1/vms/{vm_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["snapshot_id"] == test_snapshot["id"]
        assert data["template_id"] is None

    @pytest.mark.integration
    def test_list_vms_includes_snapshot_vms(
        self, client, auth_headers, test_range, test_network, test_snapshot
    ):
        """Test that listing VMs includes those created from snapshots."""
        # Create VM from snapshot
        client.post(
            "/api/v1/vms",
            headers=auth_headers,
            json={
                "range_id": test_range["id"],
                "network_id": test_network["id"],
                "snapshot_id": test_snapshot["id"],
                "hostname": "listed-snapshot-vm",
                "ip_address": "172.16.1.40",
                "cpu": 1,
                "ram_mb": 512,
                "disk_gb": 10,
            },
        )

        # List VMs in range
        response = client.get(
            f"/api/v1/vms?range_id={test_range['id']}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

        # Find our snapshot-based VM
        snapshot_vm = next(
            (vm for vm in data if vm["hostname"] == "listed-snapshot-vm"), None
        )
        assert snapshot_vm is not None
        assert snapshot_vm["snapshot_id"] == test_snapshot["id"]
