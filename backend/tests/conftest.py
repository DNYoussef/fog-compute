"""
Pytest configuration for backend tests.

Sets up Python path and common fixtures for backend service tests.
"""
import os
import sys
from pathlib import Path

# Set up test environment variables BEFORE any imports
# This must happen before the Settings class is instantiated
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-at-least-32-chars-long-enough-for-testing")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("ENVIRONMENT", "test")

# Add project root and backend to Python path
project_root = Path(__file__).parent.parent.parent
backend_root = Path(__file__).parent.parent

sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(backend_root))

import pytest


@pytest.fixture(scope="session")
def backend_root_path():
    """Return the backend root directory path."""
    return backend_root


@pytest.fixture(scope="session")
def project_root_path():
    """Return the project root directory path."""
    return project_root


@pytest.fixture
def mock_service_config():
    """Provide mock service configuration for backend tests."""
    return {
        "host": "127.0.0.1",
        "port": 8000,
        "debug": True,
        "log_level": "DEBUG",
    }


@pytest.fixture
def mock_auth_token():
    """Provide a mock authentication token for tests."""
    # NOTE: This is for testing only - real tokens should be cryptographically secure
    return "test_token_for_unit_tests_only"
