# backend/tests/integration/test_msel.py
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


SAMPLE_MSEL = """# Test MSEL

## T+0:00 - Setup
Initial setup.

**Actions:**
- Run command on test-vm: echo hello
"""


def test_import_msel(client, auth_headers, test_range):
    response = client.post(
        f"/api/v1/msel/{test_range['id']}/import",
        headers=auth_headers,
        json={"name": "Test MSEL", "content": SAMPLE_MSEL}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test MSEL"
    assert len(data["injects"]) == 1


def test_get_msel(client, auth_headers, test_range):
    # First import
    client.post(
        f"/api/v1/msel/{test_range['id']}/import",
        headers=auth_headers,
        json={"name": "Test MSEL", "content": SAMPLE_MSEL}
    )

    # Then get
    response = client.get(
        f"/api/v1/msel/{test_range['id']}",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test MSEL"
    assert "content" in data


def test_import_msel_replaces_existing(client, auth_headers, test_range):
    # First import
    client.post(
        f"/api/v1/msel/{test_range['id']}/import",
        headers=auth_headers,
        json={"name": "First MSEL", "content": SAMPLE_MSEL}
    )

    # Second import (should replace)
    new_msel = """# New MSEL

## T+0:05 - New Event
New event.

**Actions:**
- Run command on vm1: date
"""
    response = client.post(
        f"/api/v1/msel/{test_range['id']}/import",
        headers=auth_headers,
        json={"name": "Second MSEL", "content": new_msel}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Second MSEL"
    assert data["injects"][0]["inject_time_minutes"] == 5


def test_get_msel_not_found(client, auth_headers, test_range):
    response = client.get(
        f"/api/v1/msel/{test_range['id']}",
        headers=auth_headers
    )
    assert response.status_code == 404


def test_import_msel_unauthorized_range(client, auth_headers, db_session):
    from uuid import uuid4
    fake_range_id = uuid4()
    response = client.post(
        f"/api/v1/msel/{fake_range_id}/import",
        headers=auth_headers,
        json={"name": "Test MSEL", "content": SAMPLE_MSEL}
    )
    assert response.status_code == 404


def test_import_msel_requires_auth(client, test_range):
    response = client.post(
        f"/api/v1/msel/{test_range['id']}/import",
        json={"name": "Test MSEL", "content": SAMPLE_MSEL}
    )
    assert response.status_code == 401


def test_execute_inject(client, auth_headers, test_range):
    # Import MSEL first
    response = client.post(
        f"/api/v1/msel/{test_range['id']}/import",
        headers=auth_headers,
        json={"name": "Test MSEL", "content": SAMPLE_MSEL}
    )
    assert response.status_code == 201
    inject_id = response.json()["injects"][0]["id"]

    # Execute inject (will fail because no VM exists, but endpoint works)
    response = client.post(
        f"/api/v1/msel/inject/{inject_id}/execute",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
    assert data["inject_id"] == inject_id
    # success=False because VM doesn't exist
    assert data["success"] == False


def test_execute_inject_not_found(client, auth_headers):
    fake_inject_id = uuid4()
    response = client.post(
        f"/api/v1/msel/inject/{fake_inject_id}/execute",
        headers=auth_headers
    )
    assert response.status_code == 404


def test_skip_inject(client, auth_headers, test_range):
    # Import MSEL first
    response = client.post(
        f"/api/v1/msel/{test_range['id']}/import",
        headers=auth_headers,
        json={"name": "Test MSEL", "content": SAMPLE_MSEL}
    )
    inject_id = response.json()["injects"][0]["id"]

    # Skip the inject
    response = client.post(
        f"/api/v1/msel/inject/{inject_id}/skip",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "skipped"

    # Verify inject is now skipped
    response = client.get(
        f"/api/v1/msel/{test_range['id']}",
        headers=auth_headers
    )
    assert response.json()["injects"][0]["status"] == "skipped"


def test_cannot_skip_non_pending_inject(client, auth_headers, test_range):
    # Import MSEL and execute
    response = client.post(
        f"/api/v1/msel/{test_range['id']}/import",
        headers=auth_headers,
        json={"name": "Test MSEL", "content": SAMPLE_MSEL}
    )
    inject_id = response.json()["injects"][0]["id"]

    # Execute it first
    client.post(
        f"/api/v1/msel/inject/{inject_id}/execute",
        headers=auth_headers
    )

    # Try to skip (should fail)
    response = client.post(
        f"/api/v1/msel/inject/{inject_id}/skip",
        headers=auth_headers
    )
    assert response.status_code == 400
