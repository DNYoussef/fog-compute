"""
Tests for mock guard (SIN-032).

Verifies that mock fallbacks are blocked in production mode.
"""
import os
import pytest
from unittest import mock


class TestMockGuard:
    """Ensure mock guard enforces ALLOW_MOCKS policy."""

    def test_allow_mock_in_development(self):
        with mock.patch.dict(os.environ, {"APP_ENV": "development", "ALLOW_MOCKS": "true"}):
            # Reimport to pick up patched env
            import importlib
            import backend.server.mock_guard as mg
            importlib.reload(mg)
            assert mg.allow_mock_fallback() is True

    def test_block_mock_in_production(self):
        with mock.patch.dict(os.environ, {"APP_ENV": "production", "ALLOW_MOCKS": "false"}):
            import importlib
            import backend.server.mock_guard as mg
            importlib.reload(mg)
            assert mg.allow_mock_fallback() is False

    def test_guard_raises_in_production(self):
        with mock.patch.dict(os.environ, {"APP_ENV": "production", "ALLOW_MOCKS": "false"}):
            import importlib
            import backend.server.mock_guard as mg
            importlib.reload(mg)
            with pytest.raises(mg.MockNotAllowedError, match="production"):
                mg.guard_mock("test context")

    def test_guard_noop_in_development(self):
        with mock.patch.dict(os.environ, {"APP_ENV": "development", "ALLOW_MOCKS": "true"}):
            import importlib
            import backend.server.mock_guard as mg
            importlib.reload(mg)
            mg.guard_mock("test context")  # Should not raise

    def test_production_with_mocks_true_is_blocked(self):
        """Even if ALLOW_MOCKS=true, production mode blocks it."""
        with mock.patch.dict(os.environ, {"APP_ENV": "production", "ALLOW_MOCKS": "true"}):
            import importlib
            import backend.server.mock_guard as mg
            importlib.reload(mg)
            assert mg.allow_mock_fallback() is False
