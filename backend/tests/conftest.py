# backend/tests/conftest.py
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from cyroid.main import app
from cyroid.database import get_db
from cyroid.models import Base
from cyroid.services.docker_service import get_docker_service


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def mock_dind_service():
    """Mock DinD service for integration tests."""
    import asyncio
    mock_service = MagicMock()

    # Mock async methods - return coroutines
    async def mock_start_range_container(range_id):
        return {
            "container_name": f"cyroid-range-{range_id[:12]}",
            "container_id": "mock-dind-container-id",
            "status": "running",
            "mgmt_ip": "172.30.1.2",
            "docker_url": "tcp://172.30.1.2:2375",
        }

    async def mock_delete_range_container(range_id):
        return None

    mock_service.start_range_container = mock_start_range_container
    mock_service.delete_range_container = mock_delete_range_container
    mock_service.close_range_client.return_value = None
    mock_service.get_range_client.return_value = MagicMock()
    return mock_service


@pytest.fixture
def mock_vyos_service():
    """Mock VyOS service for integration tests."""
    mock_service = MagicMock()
    mock_service.start_router.return_value = True
    mock_service.stop_router.return_value = True
    mock_service.remove_router.return_value = True
    return mock_service


@pytest.fixture
def mock_docker_service(mock_dind_service):
    """Mock Docker service for integration tests."""
    mock_service = MagicMock()
    mock_service.create_network.return_value = "mock-network-id-12345"
    mock_service.create_container.return_value = "mock-container-id-12345"
    mock_service.create_windows_container.return_value = "mock-container-id-12345"
    mock_service.start_container.return_value = True
    mock_service.stop_container.return_value = True
    mock_service.restart_container.return_value = True
    mock_service.remove_container.return_value = True
    mock_service.delete_network.return_value = True
    mock_service.cleanup_range.return_value = {"containers": 0, "networks": 0}
    mock_service.get_container_status.return_value = "running"
    mock_service.exec_command.return_value = (0, "")

    # DinD-related methods
    mock_range_client = MagicMock()
    mock_container = MagicMock()
    mock_range_client.containers.get.return_value = mock_container
    mock_service.get_range_client_sync.return_value = mock_range_client
    mock_service.dind_service = mock_dind_service
    return mock_service


@pytest.fixture
def client(db_session, mock_docker_service, mock_dind_service, mock_vyos_service):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    # Override Docker service dependency (for MSEL API which uses FastAPI dependency injection)
    def override_get_docker_service():
        return mock_docker_service

    app.dependency_overrides[get_docker_service] = override_get_docker_service

    # Patch Docker service, DinD service, and VyOS service in APIs that call them directly
    with patch('cyroid.api.vms.get_docker_service', return_value=mock_docker_service), \
         patch('cyroid.api.networks.get_docker_service', return_value=mock_docker_service), \
         patch('cyroid.api.ranges.get_docker_service', return_value=mock_docker_service), \
         patch('cyroid.api.ranges.get_dind_service', return_value=mock_dind_service), \
         patch('cyroid.api.ranges.get_vyos_service', return_value=mock_vyos_service):
        with TestClient(app) as test_client:
            yield test_client
    app.dependency_overrides.clear()
