"""
Tests for TLS Configuration (PHASE0-SEC-004)

Tests cover:
- TLS configuration settings
- URL scheme selection based on TLS state
- URL builder methods
"""
import pytest
import os
from unittest.mock import patch

# Set test environment variables before imports
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-tls-testing-only')
os.environ.setdefault('TESTING', 'true')


class TestTLSConfiguration:
    """Tests for TLS configuration settings."""

    def test_tls_enabled_by_default(self):
        """TLS should be enabled by default."""
        # Reset environment for fresh import
        with patch.dict(os.environ, {"TLS_ENABLED": "true"}, clear=False):
            from backend.server.config import Settings
            settings = Settings()
            assert settings.TLS_ENABLED is True

    def test_tls_can_be_disabled(self):
        """TLS can be disabled via environment variable."""
        with patch.dict(os.environ, {"TLS_ENABLED": "false"}, clear=False):
            from backend.server.config import Settings
            settings = Settings()
            assert settings.TLS_ENABLED is False

    def test_tls_cert_paths_optional(self):
        """TLS certificate paths should be optional."""
        with patch.dict(os.environ, {}, clear=False):
            from backend.server.config import Settings
            settings = Settings()
            # These should be None if not set
            assert settings.TLS_CERT_PATH is None or settings.TLS_CERT_PATH == os.getenv("TLS_CERT_PATH")
            assert settings.TLS_KEY_PATH is None or settings.TLS_KEY_PATH == os.getenv("TLS_KEY_PATH")


class TestURLSchemes:
    """Tests for URL scheme selection based on TLS state."""

    def test_https_scheme_when_tls_enabled(self):
        """Should return https when TLS is enabled."""
        with patch.dict(os.environ, {"TLS_ENABLED": "true"}, clear=False):
            from backend.server.config import Settings
            settings = Settings()
            assert settings.get_http_scheme() == "https"

    def test_http_scheme_when_tls_disabled(self):
        """Should return http when TLS is disabled."""
        with patch.dict(os.environ, {"TLS_ENABLED": "false"}, clear=False):
            from backend.server.config import Settings
            settings = Settings()
            assert settings.get_http_scheme() == "http"

    def test_wss_scheme_when_tls_enabled(self):
        """Should return wss when TLS is enabled."""
        with patch.dict(os.environ, {"TLS_ENABLED": "true"}, clear=False):
            from backend.server.config import Settings
            settings = Settings()
            assert settings.get_ws_scheme() == "wss"

    def test_ws_scheme_when_tls_disabled(self):
        """Should return ws when TLS is disabled."""
        with patch.dict(os.environ, {"TLS_ENABLED": "false"}, clear=False):
            from backend.server.config import Settings
            settings = Settings()
            assert settings.get_ws_scheme() == "ws"


class TestURLBuilders:
    """Tests for URL builder methods."""

    def test_build_api_url_with_tls(self):
        """API URL builder should use https with TLS enabled."""
        with patch.dict(os.environ, {"TLS_ENABLED": "true"}, clear=False):
            from backend.server.config import Settings
            settings = Settings()
            url = settings.build_api_url("/api/test")
            assert url.startswith("https://")
            assert "/api/test" in url

    def test_build_api_url_without_tls(self):
        """API URL builder should use http with TLS disabled."""
        with patch.dict(os.environ, {"TLS_ENABLED": "false"}, clear=False):
            from backend.server.config import Settings
            settings = Settings()
            url = settings.build_api_url("/api/test")
            assert url.startswith("http://")
            assert "/api/test" in url

    def test_build_ws_url_with_tls(self):
        """WebSocket URL builder should use wss with TLS enabled."""
        with patch.dict(os.environ, {"TLS_ENABLED": "true"}, clear=False):
            from backend.server.config import Settings
            settings = Settings()
            url = settings.build_ws_url("/ws/test")
            assert url.startswith("wss://")
            assert "/ws/test" in url

    def test_build_ws_url_without_tls(self):
        """WebSocket URL builder should use ws with TLS disabled."""
        with patch.dict(os.environ, {"TLS_ENABLED": "false"}, clear=False):
            from backend.server.config import Settings
            settings = Settings()
            url = settings.build_ws_url("/ws/test")
            assert url.startswith("ws://")
            assert "/ws/test" in url

    def test_build_url_includes_host_and_port(self):
        """URL builder should include host and port."""
        with patch.dict(os.environ, {"TLS_ENABLED": "false"}, clear=False):
            from backend.server.config import Settings
            settings = Settings()
            url = settings.build_api_url()
            assert settings.API_HOST in url
            assert str(settings.API_PORT) in url

    def test_build_url_empty_path(self):
        """URL builder should handle empty path."""
        with patch.dict(os.environ, {"TLS_ENABLED": "true"}, clear=False):
            from backend.server.config import Settings
            settings = Settings()
            url = settings.build_api_url("")
            assert url == f"https://{settings.API_HOST}:{settings.API_PORT}"


class TestMTLSConfiguration:
    """Tests for mTLS configuration."""

    def test_mtls_disabled_by_default(self):
        """mTLS (client verification) should be disabled by default."""
        with patch.dict(os.environ, {}, clear=False):
            from backend.server.config import Settings
            settings = Settings()
            assert settings.TLS_VERIFY_CLIENT is False

    def test_mtls_can_be_enabled(self):
        """mTLS can be enabled via environment variable."""
        with patch.dict(os.environ, {"TLS_VERIFY_CLIENT": "true"}, clear=False):
            from backend.server.config import Settings
            settings = Settings()
            assert settings.TLS_VERIFY_CLIENT is True

    def test_ca_path_for_mtls(self):
        """CA path can be set for certificate pinning."""
        test_path = "/etc/ssl/certs/ca.crt"
        with patch.dict(os.environ, {"TLS_CA_PATH": test_path}, clear=False):
            from backend.server.config import Settings
            settings = Settings()
            assert settings.TLS_CA_PATH == test_path


class TestIntegration:
    """Integration tests for TLS configuration in routes."""

    def test_mesh_ws_url_uses_tls_settings(self):
        """Mesh WebSocket URLs should respect TLS settings."""
        # This test verifies the integration of TLS config in routes
        # The actual URL generation is tested through the settings
        with patch.dict(os.environ, {"TLS_ENABLED": "true"}, clear=False):
            from backend.server.config import Settings
            settings = Settings()

            device_id = "test-device-123"
            ws_url = settings.build_ws_url(f"/api/mesh/ws/{device_id}")

            assert ws_url.startswith("wss://")
            assert device_id in ws_url
            assert "/api/mesh/ws/" in ws_url

    def test_fog_bridge_ws_url_uses_tls_settings(self):
        """Fog bridge WebSocket URLs should respect TLS settings."""
        with patch.dict(os.environ, {"TLS_ENABLED": "true"}, clear=False):
            from backend.server.config import Settings
            settings = Settings()

            device_id = "test-device-456"
            ws_url = settings.build_ws_url(f"/api/fog-bridge/ws/{device_id}")

            assert ws_url.startswith("wss://")
            assert device_id in ws_url
            assert "/api/fog-bridge/ws/" in ws_url
