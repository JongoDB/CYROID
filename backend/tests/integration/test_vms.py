# backend/tests/integration/test_vms.py
import pytest


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
    """Create a test range"""
    response = client.post(
        "/api/v1/ranges",
        headers=auth_headers,
        json={"name": "Test Range"},
    )
    return response.json()


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
    # Provision the network so VMs can be started
    client.post(f"/api/v1/networks/{network['id']}/provision", headers=auth_headers)
    # Re-fetch to get the updated docker_network_id
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


def test_create_vm(client, auth_headers, test_range, test_network, test_template):
    response = client.post(
        "/api/v1/vms",
        headers=auth_headers,
        json={
            "range_id": test_range["id"],
            "network_id": test_network["id"],
            "template_id": test_template["id"],
            "hostname": "web-server-01",
            "ip_address": "172.16.1.10",
            "cpu": 2,
            "ram_mb": 4096,
            "disk_gb": 40,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["hostname"] == "web-server-01"
    assert data["ip_address"] == "172.16.1.10"
    assert data["status"] == "pending"


def test_list_vms(client, auth_headers, test_range, test_network, test_template):
    # Create a VM first
    client.post(
        "/api/v1/vms",
        headers=auth_headers,
        json={
            "range_id": test_range["id"],
            "network_id": test_network["id"],
            "template_id": test_template["id"],
            "hostname": "test-vm",
            "ip_address": "172.16.1.10",
            "cpu": 2,
            "ram_mb": 4096,
            "disk_gb": 40,
        },
    )

    response = client.get(
        f"/api/v1/vms?range_id={test_range['id']}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_get_vm(client, auth_headers, test_range, test_network, test_template):
    # Create a VM
    create_response = client.post(
        "/api/v1/vms",
        headers=auth_headers,
        json={
            "range_id": test_range["id"],
            "network_id": test_network["id"],
            "template_id": test_template["id"],
            "hostname": "test-vm",
            "ip_address": "172.16.1.10",
            "cpu": 2,
            "ram_mb": 4096,
            "disk_gb": 40,
        },
    )
    vm_id = create_response.json()["id"]

    response = client.get(f"/api/v1/vms/{vm_id}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["id"] == vm_id


def test_update_vm(client, auth_headers, test_range, test_network, test_template):
    # Create a VM
    create_response = client.post(
        "/api/v1/vms",
        headers=auth_headers,
        json={
            "range_id": test_range["id"],
            "network_id": test_network["id"],
            "template_id": test_template["id"],
            "hostname": "test-vm",
            "ip_address": "172.16.1.10",
            "cpu": 2,
            "ram_mb": 4096,
            "disk_gb": 40,
        },
    )
    vm_id = create_response.json()["id"]

    # Update it
    response = client.put(
        f"/api/v1/vms/{vm_id}",
        headers=auth_headers,
        json={"hostname": "updated-vm", "cpu": 4, "ram_mb": 8192},
    )

    assert response.status_code == 200
    assert response.json()["hostname"] == "updated-vm"
    assert response.json()["cpu"] == 4
    assert response.json()["ram_mb"] == 8192


def test_delete_vm(client, auth_headers, test_range, test_network, test_template):
    # Create a VM
    create_response = client.post(
        "/api/v1/vms",
        headers=auth_headers,
        json={
            "range_id": test_range["id"],
            "network_id": test_network["id"],
            "template_id": test_template["id"],
            "hostname": "test-vm",
            "ip_address": "172.16.1.10",
            "cpu": 2,
            "ram_mb": 4096,
            "disk_gb": 40,
        },
    )
    vm_id = create_response.json()["id"]

    # Delete it
    response = client.delete(f"/api/v1/vms/{vm_id}", headers=auth_headers)
    assert response.status_code == 204

    # Verify it's gone
    get_response = client.get(f"/api/v1/vms/{vm_id}", headers=auth_headers)
    assert get_response.status_code == 404


def test_duplicate_hostname(client, auth_headers, test_range, test_network, test_template):
    # Create first VM
    client.post(
        "/api/v1/vms",
        headers=auth_headers,
        json={
            "range_id": test_range["id"],
            "network_id": test_network["id"],
            "template_id": test_template["id"],
            "hostname": "test-vm",
            "ip_address": "172.16.1.10",
            "cpu": 2,
            "ram_mb": 4096,
            "disk_gb": 40,
        },
    )

    # Try to create duplicate hostname
    response = client.post(
        "/api/v1/vms",
        headers=auth_headers,
        json={
            "range_id": test_range["id"],
            "network_id": test_network["id"],
            "template_id": test_template["id"],
            "hostname": "test-vm",
            "ip_address": "172.16.1.11",
            "cpu": 2,
            "ram_mb": 4096,
            "disk_gb": 40,
        },
    )

    assert response.status_code == 400
    assert "Hostname already exists" in response.json()["detail"]


def test_duplicate_ip_address(client, auth_headers, test_range, test_network, test_template):
    # Create first VM
    client.post(
        "/api/v1/vms",
        headers=auth_headers,
        json={
            "range_id": test_range["id"],
            "network_id": test_network["id"],
            "template_id": test_template["id"],
            "hostname": "vm-1",
            "ip_address": "172.16.1.10",
            "cpu": 2,
            "ram_mb": 4096,
            "disk_gb": 40,
        },
    )

    # Try to create duplicate IP
    response = client.post(
        "/api/v1/vms",
        headers=auth_headers,
        json={
            "range_id": test_range["id"],
            "network_id": test_network["id"],
            "template_id": test_template["id"],
            "hostname": "vm-2",
            "ip_address": "172.16.1.10",
            "cpu": 2,
            "ram_mb": 4096,
            "disk_gb": 40,
        },
    )

    assert response.status_code == 400
    assert "IP address already exists" in response.json()["detail"]


def test_start_vm(client, auth_headers, test_range, test_network, test_template):
    # Create a VM
    create_response = client.post(
        "/api/v1/vms",
        headers=auth_headers,
        json={
            "range_id": test_range["id"],
            "network_id": test_network["id"],
            "template_id": test_template["id"],
            "hostname": "test-vm",
            "ip_address": "172.16.1.10",
            "cpu": 2,
            "ram_mb": 4096,
            "disk_gb": 40,
        },
    )
    vm_id = create_response.json()["id"]

    # Start it
    response = client.post(f"/api/v1/vms/{vm_id}/start", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["status"] == "running"
