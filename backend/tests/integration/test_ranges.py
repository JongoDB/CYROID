# backend/tests/integration/test_ranges.py
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


def test_create_range(client, auth_headers):
    response = client.post(
        "/api/v1/ranges",
        headers=auth_headers,
        json={
            "name": "Test Range",
            "description": "A test cyber range",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Range"
    assert data["status"] == "draft"
    assert "id" in data


def test_list_ranges(client, auth_headers):
    # Create a range first
    client.post(
        "/api/v1/ranges",
        headers=auth_headers,
        json={"name": "Test Range"},
    )

    response = client.get("/api/v1/ranges", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_get_range(client, auth_headers):
    # Create a range
    create_response = client.post(
        "/api/v1/ranges",
        headers=auth_headers,
        json={"name": "Test Range"},
    )
    range_id = create_response.json()["id"]

    response = client.get(f"/api/v1/ranges/{range_id}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["id"] == range_id
    assert "networks" in response.json()
    assert "vms" in response.json()


def test_update_range(client, auth_headers):
    # Create a range
    create_response = client.post(
        "/api/v1/ranges",
        headers=auth_headers,
        json={"name": "Test Range"},
    )
    range_id = create_response.json()["id"]

    # Update it
    response = client.put(
        f"/api/v1/ranges/{range_id}",
        headers=auth_headers,
        json={"name": "Updated Range", "description": "New description"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated Range"
    assert response.json()["description"] == "New description"


def test_delete_range(client, auth_headers):
    # Create a range
    create_response = client.post(
        "/api/v1/ranges",
        headers=auth_headers,
        json={"name": "Test Range"},
    )
    range_id = create_response.json()["id"]

    # Delete it
    response = client.delete(f"/api/v1/ranges/{range_id}", headers=auth_headers)
    assert response.status_code == 204

    # Verify it's gone
    get_response = client.get(f"/api/v1/ranges/{range_id}", headers=auth_headers)
    assert get_response.status_code == 404


def test_deploy_range(client, auth_headers):
    # Create a range
    create_response = client.post(
        "/api/v1/ranges",
        headers=auth_headers,
        json={"name": "Test Range"},
    )
    range_id = create_response.json()["id"]

    # Deploy it (synchronous - completes immediately with mocked Docker)
    response = client.post(f"/api/v1/ranges/{range_id}/deploy", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_stop_running_range(client, auth_headers):
    # Create and deploy a range
    create_response = client.post(
        "/api/v1/ranges",
        headers=auth_headers,
        json={"name": "Test Range"},
    )
    range_id = create_response.json()["id"]

    # Deploy it (now completes synchronously)
    client.post(f"/api/v1/ranges/{range_id}/deploy", headers=auth_headers)

    # Stop the running range
    response = client.post(f"/api/v1/ranges/{range_id}/stop", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "stopped"


def test_teardown_range(client, auth_headers):
    # Create a range
    create_response = client.post(
        "/api/v1/ranges",
        headers=auth_headers,
        json={"name": "Test Range"},
    )
    range_id = create_response.json()["id"]

    # Teardown from draft status
    response = client.post(f"/api/v1/ranges/{range_id}/teardown", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["status"] == "draft"
