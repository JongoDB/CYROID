# backend/tests/integration/test_events.py
import pytest
from uuid import uuid4


@pytest.fixture
def auth_headers(client):
    # Register and login
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
def test_range(client, auth_headers):
    response = client.post(
        "/api/v1/ranges",
        headers=auth_headers,
        json={"name": "Test Range", "description": "A test range"},
    )
    return response.json()


def test_get_events_requires_auth(client):
    response = client.get(f"/api/v1/events/{uuid4()}")
    assert response.status_code == 401  # No auth header


def test_get_events_empty(client, auth_headers, test_range):
    response = client.get(
        f"/api/v1/events/{test_range['id']}",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["events"] == []
    assert data["total"] == 0


@pytest.fixture
def test_network(client, auth_headers, test_range):
    """Create and provision a test network"""
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
    # Provision the network
    client.post(f"/api/v1/networks/{network['id']}/provision", headers=auth_headers)
    # Re-fetch
    response = client.get(f"/api/v1/networks/{network['id']}", headers=auth_headers)
    return response.json()


@pytest.fixture
def test_template(client, auth_headers):
    """Create a test template"""
    response = client.post(
        "/api/v1/templates",
        headers=auth_headers,
        json={
            "name": "Ubuntu Server",
            "os_type": "linux",
            "os_variant": "Ubuntu 22.04",
            "base_image": "ubuntu:22.04",
        },
    )
    return response.json()


@pytest.fixture
def test_vm(client, auth_headers, test_range, test_network, test_template):
    """Create a test VM"""
    response = client.post(
        "/api/v1/vms",
        headers=auth_headers,
        json={
            "range_id": test_range["id"],
            "network_id": test_network["id"],
            "template_id": test_template["id"],
            "hostname": "test-vm-01",
            "ip_address": "172.16.1.10",
            "cpu": 2,
            "ram_mb": 2048,
            "disk_gb": 20,
        },
    )
    return response.json()


def test_vm_start_creates_event(client, auth_headers, test_range, test_vm):
    # Start the VM
    response = client.post(
        f"/api/v1/vms/{test_vm['id']}/start",
        headers=auth_headers
    )
    assert response.status_code == 200

    # Check event was logged
    response = client.get(
        f"/api/v1/events/{test_range['id']}",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(e["event_type"] == "vm_started" for e in data["events"])
