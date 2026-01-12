# backend/tests/integration/test_networks.py
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


def test_create_network(client, auth_headers, test_range):
    response = client.post(
        "/api/v1/networks",
        headers=auth_headers,
        json={
            "range_id": test_range["id"],
            "name": "Corporate Network",
            "subnet": "172.16.1.0/24",
            "gateway": "172.16.1.1",
            "dns_servers": "8.8.8.8,8.8.4.4",
            "isolation_level": "complete",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Corporate Network"
    assert data["subnet"] == "172.16.1.0/24"
    assert data["gateway"] == "172.16.1.1"


def test_list_networks(client, auth_headers, test_range):
    # Create a network first
    client.post(
        "/api/v1/networks",
        headers=auth_headers,
        json={
            "range_id": test_range["id"],
            "name": "Test Network",
            "subnet": "172.16.1.0/24",
            "gateway": "172.16.1.1",
        },
    )

    response = client.get(
        f"/api/v1/networks?range_id={test_range['id']}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_get_network(client, auth_headers, test_range):
    # Create a network
    create_response = client.post(
        "/api/v1/networks",
        headers=auth_headers,
        json={
            "range_id": test_range["id"],
            "name": "Test Network",
            "subnet": "172.16.1.0/24",
            "gateway": "172.16.1.1",
        },
    )
    network_id = create_response.json()["id"]

    response = client.get(f"/api/v1/networks/{network_id}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["id"] == network_id


def test_update_network(client, auth_headers, test_range):
    # Create a network
    create_response = client.post(
        "/api/v1/networks",
        headers=auth_headers,
        json={
            "range_id": test_range["id"],
            "name": "Test Network",
            "subnet": "172.16.1.0/24",
            "gateway": "172.16.1.1",
        },
    )
    network_id = create_response.json()["id"]

    # Update it
    response = client.put(
        f"/api/v1/networks/{network_id}",
        headers=auth_headers,
        json={"name": "Updated Network", "dns_servers": "1.1.1.1"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated Network"
    assert response.json()["dns_servers"] == "1.1.1.1"


def test_delete_network(client, auth_headers, test_range):
    # Create a network
    create_response = client.post(
        "/api/v1/networks",
        headers=auth_headers,
        json={
            "range_id": test_range["id"],
            "name": "Test Network",
            "subnet": "172.16.1.0/24",
            "gateway": "172.16.1.1",
        },
    )
    network_id = create_response.json()["id"]

    # Delete it
    response = client.delete(f"/api/v1/networks/{network_id}", headers=auth_headers)
    assert response.status_code == 204

    # Verify it's gone
    get_response = client.get(f"/api/v1/networks/{network_id}", headers=auth_headers)
    assert get_response.status_code == 404


def test_create_duplicate_subnet(client, auth_headers, test_range):
    # Create first network
    client.post(
        "/api/v1/networks",
        headers=auth_headers,
        json={
            "range_id": test_range["id"],
            "name": "Network 1",
            "subnet": "172.16.1.0/24",
            "gateway": "172.16.1.1",
        },
    )

    # Try to create duplicate subnet
    response = client.post(
        "/api/v1/networks",
        headers=auth_headers,
        json={
            "range_id": test_range["id"],
            "name": "Network 2",
            "subnet": "172.16.1.0/24",
            "gateway": "172.16.1.1",
        },
    )

    assert response.status_code == 400
    assert "Subnet already exists" in response.json()["detail"]
