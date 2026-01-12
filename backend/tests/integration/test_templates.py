# backend/tests/integration/test_templates.py
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


def test_create_template(client, auth_headers):
    response = client.post(
        "/api/v1/templates",
        headers=auth_headers,
        json={
            "name": "Ubuntu Server",
            "description": "Ubuntu 22.04 LTS Server",
            "os_type": "linux",
            "os_variant": "Ubuntu 22.04",
            "base_image": "ubuntu:22.04",
            "default_cpu": 2,
            "default_ram_mb": 4096,
            "default_disk_gb": 40,
            "tags": ["linux", "server", "ubuntu"],
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Ubuntu Server"
    assert data["os_type"] == "linux"
    assert "id" in data


def test_list_templates(client, auth_headers):
    # Create a template first
    client.post(
        "/api/v1/templates",
        headers=auth_headers,
        json={
            "name": "Test Template",
            "os_type": "linux",
            "os_variant": "Ubuntu 22.04",
            "base_image": "ubuntu:22.04",
        },
    )

    response = client.get("/api/v1/templates", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_get_template(client, auth_headers):
    # Create a template
    create_response = client.post(
        "/api/v1/templates",
        headers=auth_headers,
        json={
            "name": "Test Template",
            "os_type": "linux",
            "os_variant": "Ubuntu 22.04",
            "base_image": "ubuntu:22.04",
        },
    )
    template_id = create_response.json()["id"]

    response = client.get(f"/api/v1/templates/{template_id}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["id"] == template_id


def test_update_template(client, auth_headers):
    # Create a template
    create_response = client.post(
        "/api/v1/templates",
        headers=auth_headers,
        json={
            "name": "Test Template",
            "os_type": "linux",
            "os_variant": "Ubuntu 22.04",
            "base_image": "ubuntu:22.04",
        },
    )
    template_id = create_response.json()["id"]

    # Update it
    response = client.put(
        f"/api/v1/templates/{template_id}",
        headers=auth_headers,
        json={"name": "Updated Template", "default_cpu": 4},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated Template"
    assert response.json()["default_cpu"] == 4


def test_delete_template(client, auth_headers):
    # Create a template
    create_response = client.post(
        "/api/v1/templates",
        headers=auth_headers,
        json={
            "name": "Test Template",
            "os_type": "linux",
            "os_variant": "Ubuntu 22.04",
            "base_image": "ubuntu:22.04",
        },
    )
    template_id = create_response.json()["id"]

    # Delete it
    response = client.delete(f"/api/v1/templates/{template_id}", headers=auth_headers)
    assert response.status_code == 204

    # Verify it's gone
    get_response = client.get(f"/api/v1/templates/{template_id}", headers=auth_headers)
    assert get_response.status_code == 404


def test_clone_template(client, auth_headers):
    # Create a template
    create_response = client.post(
        "/api/v1/templates",
        headers=auth_headers,
        json={
            "name": "Original Template",
            "os_type": "windows",
            "os_variant": "Windows Server 2022",
            "base_image": "dockurr/windows:server2022",
            "tags": ["windows", "server"],
        },
    )
    template_id = create_response.json()["id"]

    # Clone it
    response = client.post(f"/api/v1/templates/{template_id}/clone", headers=auth_headers)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Original Template (Copy)"
    assert data["id"] != template_id
    assert data["tags"] == ["windows", "server"]
