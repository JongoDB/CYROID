# backend/tests/unit/conftest.py
"""Conftest for unit tests - minimal fixtures without app imports."""
import pytest
from unittest.mock import MagicMock


# Override parent conftest by not importing the app
# Unit tests should mock all dependencies


@pytest.fixture
def mock_docker_service():
    """Mock Docker service for unit tests."""
    mock_service = MagicMock()
    mock_service.get_range_client_sync.return_value = MagicMock()
    return mock_service
