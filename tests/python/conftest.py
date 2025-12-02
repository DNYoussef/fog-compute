"""
Pytest configuration and fixtures for FOG Compute tests.

This file sets up the Python path to allow imports from src/ and backend/ directories.
"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "backend"))

import pytest


def pytest_configure(config):
    """Register custom markers to avoid warnings."""
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "benchmark: mark test as benchmark")


@pytest.fixture(scope="session")
def project_root_path():
    """Return the project root directory path."""
    return project_root


@pytest.fixture(scope="session")
def test_data_dir():
    """Return the test data directory path."""
    return project_root / "tests" / "data"


@pytest.fixture
def mock_config():
    """Provide a mock configuration for tests."""
    return {
        "betanet": {
            "host": "127.0.0.1",
            "port": 9000,
            "api_port": 8443,
        },
        "redis": {
            "host": "127.0.0.1",
            "port": 6379,
        },
        "database": {
            "url": "sqlite:///test.db",
        },
    }
