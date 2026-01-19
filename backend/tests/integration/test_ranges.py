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


# ============================================================================
# DinD-Aware Lifecycle Endpoint Tests
# ============================================================================

def test_start_range_requires_stopped_status(client, auth_headers):
    """Test that start_range requires the range to be in STOPPED status."""
    # Create a range (draft status)
    create_response = client.post(
        "/api/v1/ranges",
        headers=auth_headers,
        json={"name": "Test Range"},
    )
    range_id = create_response.json()["id"]

    # Try to start a draft range - should fail
    response = client.post(f"/api/v1/ranges/{range_id}/start", headers=auth_headers)
    assert response.status_code == 400
    assert "Cannot start range" in response.json()["detail"]


def test_stop_range_requires_running_status(client, auth_headers):
    """Test that stop_range requires the range to be in RUNNING status."""
    # Create a range (draft status)
    create_response = client.post(
        "/api/v1/ranges",
        headers=auth_headers,
        json={"name": "Test Range"},
    )
    range_id = create_response.json()["id"]

    # Try to stop a draft range - should fail
    response = client.post(f"/api/v1/ranges/{range_id}/stop", headers=auth_headers)
    assert response.status_code == 400
    assert "Cannot stop range" in response.json()["detail"]


def test_start_stopped_range(client, auth_headers):
    """Test starting a stopped DinD-based range."""
    # Create and deploy a range
    create_response = client.post(
        "/api/v1/ranges",
        headers=auth_headers,
        json={"name": "Test Range"},
    )
    range_id = create_response.json()["id"]

    # Deploy it
    deploy_response = client.post(f"/api/v1/ranges/{range_id}/deploy", headers=auth_headers)
    assert deploy_response.status_code == 200
    assert deploy_response.json()["status"] == "running"

    # Stop it
    stop_response = client.post(f"/api/v1/ranges/{range_id}/stop", headers=auth_headers)
    assert stop_response.status_code == 200
    assert stop_response.json()["status"] == "stopped"

    # Start it again
    start_response = client.post(f"/api/v1/ranges/{range_id}/start", headers=auth_headers)
    assert start_response.status_code == 200
    assert start_response.json()["status"] == "running"
    assert "started_at" in start_response.json()


def test_stop_running_range_with_dind(client, auth_headers):
    """Test stopping a running DinD-based range."""
    # Create and deploy a range
    create_response = client.post(
        "/api/v1/ranges",
        headers=auth_headers,
        json={"name": "Test Range"},
    )
    range_id = create_response.json()["id"]

    # Deploy it
    deploy_response = client.post(f"/api/v1/ranges/{range_id}/deploy", headers=auth_headers)
    assert deploy_response.status_code == 200

    # Stop it
    stop_response = client.post(f"/api/v1/ranges/{range_id}/stop", headers=auth_headers)
    assert stop_response.status_code == 200
    assert stop_response.json()["status"] == "stopped"
    assert "stopped_at" in stop_response.json()


def test_delete_range_not_found(client, auth_headers):
    """Test deleting a non-existent range returns 404."""
    import uuid
    fake_id = str(uuid.uuid4())
    response = client.delete(f"/api/v1/ranges/{fake_id}", headers=auth_headers)
    assert response.status_code == 404


def test_delete_deployed_range(client, auth_headers):
    """Test deleting a deployed range cleans up DinD resources."""
    # Create and deploy a range
    create_response = client.post(
        "/api/v1/ranges",
        headers=auth_headers,
        json={"name": "Test Range"},
    )
    range_id = create_response.json()["id"]

    # Deploy it
    client.post(f"/api/v1/ranges/{range_id}/deploy", headers=auth_headers)

    # Delete it
    response = client.delete(f"/api/v1/ranges/{range_id}", headers=auth_headers)
    assert response.status_code == 204

    # Verify it's gone
    get_response = client.get(f"/api/v1/ranges/{range_id}", headers=auth_headers)
    assert get_response.status_code == 404


def test_start_range_not_found(client, auth_headers):
    """Test starting a non-existent range returns 404."""
    import uuid
    fake_id = str(uuid.uuid4())
    response = client.post(f"/api/v1/ranges/{fake_id}/start", headers=auth_headers)
    assert response.status_code == 404


def test_stop_range_not_found(client, auth_headers):
    """Test stopping a non-existent range returns 404."""
    import uuid
    fake_id = str(uuid.uuid4())
    response = client.post(f"/api/v1/ranges/{fake_id}/stop", headers=auth_headers)
    assert response.status_code == 404
