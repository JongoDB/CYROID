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
def mock_docker_service():
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
    return mock_service


@pytest.fixture
def client(db_session, mock_docker_service):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    # Patch Docker service in all API modules
    with patch('cyroid.api.vms.get_docker_service', return_value=mock_docker_service), \
         patch('cyroid.api.networks.get_docker_service', return_value=mock_docker_service), \
         patch('cyroid.api.ranges.get_docker_service', return_value=mock_docker_service):
        with TestClient(app) as test_client:
            yield test_client
    app.dependency_overrides.clear()
