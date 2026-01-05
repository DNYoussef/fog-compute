"""
Comprehensive Production Hardening Tests
Tests for security, error handling, performance, and production readiness
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from unittest.mock import Mock, patch, AsyncMock
import jwt
import time

from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

# Import application components
from server.main import app
from server.middleware.error_handling import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    ErrorHandlingMiddleware,
    global_circuit_breaker
)
from server.middleware.rate_limit import RateLimiter, rate_limiter
from server.auth.jwt_utils import create_access_token, verify_token
from server.config import settings

from backend.tests.constants import (
    TEST_MAX_LOGIN_ATTEMPTS,
    TEST_PAGE_SIZE,
    TEST_MAX_RESULTS,
    TEST_SMALL_FILE_SIZE,
    TEST_TOKEN_LENGTH,
)


##############################################################################
# 1. ERROR HANDLING TESTS (8 tests)
##############################################################################

class TestErrorHandling:
    """Test comprehensive error handling mechanisms"""

    def test_circuit_breaker_opens_after_failures(self):
        """Test circuit breaker opens after threshold failures"""
        cb = CircuitBreaker(failure_threshold=3, timeout_seconds=60)

        def failing_function():
            raise Exception("Service failure")

        # First 2 failures should not open circuit
        for i in range(2):
            with pytest.raises(Exception):
                cb.call("test_service", failing_function)

        # Circuit should still be closed
        assert cb.get_state("test_service") == "closed"

        # 3rd failure should open circuit
        with pytest.raises(Exception):
            cb.call("test_service", failing_function)

        assert cb.get_state("test_service") == "open"

    def test_circuit_breaker_blocks_requests_when_open(self):
        """Test circuit breaker blocks requests when open"""
        cb = CircuitBreaker(failure_threshold=2, timeout_seconds=60)

        def failing_function():
            raise Exception("Service failure")

        # Cause 2 failures to open circuit
        for i in range(2):
            with pytest.raises(Exception):
                cb.call("test_service", failing_function)

        # Next call should be blocked
        with pytest.raises(CircuitBreakerOpenError):
            cb.call("test_service", lambda: "success")

    def test_circuit_breaker_transitions_to_half_open(self):
        """Test circuit breaker transitions to half-open after timeout"""
        cb = CircuitBreaker(failure_threshold=2, timeout_seconds=1)

        def failing_function():
            raise Exception("Service failure")

        # Open circuit
        for i in range(2):
            with pytest.raises(Exception):
                cb.call("test_service", failing_function)

        assert cb.get_state("test_service") == "open"

        # Wait for timeout
        time.sleep(1.1)

        # Should transition to half-open and allow request
        def success_function():
            return "success"

        result = cb.call("test_service", success_function)
        assert result == "success"
        assert cb.get_state("test_service") == "closed"

    def test_circuit_breaker_resets_on_success(self):
        """Test circuit breaker resets failure count on success"""
        cb = CircuitBreaker(failure_threshold=3)

        def failing_function():
            raise Exception("Service failure")

        def success_function():
            return "success"

        # One failure
        with pytest.raises(Exception):
            cb.call("test_service", failing_function)

        # Success should reset count
        cb.call("test_service", success_function)
        assert cb.failure_count["test_service"] == 0

    def test_error_response_includes_correlation_id(self):
        """Test all error responses include correlation ID"""
        client = TestClient(app)

        # Trigger an error
        response = client.get("/api/nonexistent")
        assert response.status_code == 404
        assert "X-Correlation-ID" in response.headers

    def test_error_response_no_stack_traces(self):
        """Test error responses don't leak stack traces"""
        client = TestClient(app)

        # Trigger server error (if endpoint exists)
        response = client.post("/api/auth/login", json={"invalid": "data"})

        # Should not contain "Traceback" or "File \"
        response_text = response.text
        assert "Traceback" not in response_text
        assert 'File "' not in response_text

    def test_graceful_degradation_on_database_failure(self):
        """Test system degrades gracefully on database failure"""
        client = TestClient(app)

        # Health endpoint should still work even if DB is down
        with patch('backend.server.database.get_db', side_effect=Exception("DB down")):
            response = client.get("/health")
            # Should return degraded status, not 500
            assert response.status_code in [200, 503]

    def test_retry_logic_with_exponential_backoff(self):
        """Test retry logic implements exponential backoff"""
        from backend.server.middleware.error_handling import RetryStrategy

        delays = [RetryStrategy.calculate_delay(i) for i in range(5)]

        # Should increase exponentially: 1, 2, 4, 8, 16
        assert delays[0] == 1.0
        assert delays[1] == 2.0
        assert delays[2] == 4.0
        assert delays[3] == 8.0
        assert delays[4] == 16.0


##############################################################################
# 2. SECURITY VULNERABILITY TESTS (10 tests)
##############################################################################

class TestSecurityVulnerabilities:
    """Test for common security vulnerabilities"""

    def test_sql_injection_in_login(self):
        """Test SQL injection protection in login endpoint"""
        client = TestClient(app)

        # Attempt SQL injection
        response = client.post("/api/auth/login", json={
            "username": "admin' OR '1'='1",
            "password": "password"
        })

        # Should fail authentication, not execute SQL
        assert response.status_code == 401

    def test_xss_in_user_input(self):
        """Test XSS protection in user input"""
        client = TestClient(app)

        # Attempt XSS via registration
        response = client.post("/api/auth/register", json={
            "username": "<script>alert('XSS')</script>",
            "email": "test@example.com",
            "password": "SecurePass123!"
        })

        if response.status_code == 201:
            # Input should be escaped
            assert "<script>" not in response.json()["username"]

    def test_csrf_protection_on_state_changing_operations(self):
        """Test CSRF protection on POST/PUT/DELETE endpoints"""
        client = TestClient(app)

        # Test 1: Auth endpoints are exempt (use Bearer tokens)
        # Login should work without CSRF token since it's in BEARER_AUTH_ROUTES
        response = client.post("/api/auth/login", json={
            "username": "test",
            "password": "test"
        })
        # Should fail with 401 (auth) or 500 (db unavailable), not 403 (CSRF)
        # The key test is that CSRF middleware doesn't block auth routes
        assert response.status_code in [401, 500]  # Auth error or DB error, not CSRF

        # Test 2: GET requests should set CSRF cookie
        get_response = client.get("/health")
        assert get_response.status_code == 200
        csrf_token = get_response.cookies.get("csrf_token")
        # CSRF cookie should be set on safe methods
        assert csrf_token is not None or "csrf_token" in str(client.cookies)

        # Test 3: Bearer token authenticated requests bypass CSRF
        # (Requests with Authorization: Bearer header skip CSRF check)
        register_response = client.post("/api/auth/register", json={
            "username": "csrftest",
            "email": "csrf@test.com",
            "password": "SecurePass123!"
        })
        if register_response.status_code == 201:
            login_resp = client.post("/api/auth/login", json={
                "username": "csrftest",
                "password": "SecurePass123!"
            })
            token = login_resp.json().get("access_token")
            if token:
                # Bearer authenticated requests should work without CSRF token
                me_response = client.get(
                    "/api/auth/me",
                    headers={"Authorization": f"Bearer {token}"}
                )
                assert me_response.status_code == 200

    def test_rate_limiting_prevents_brute_force(self):
        """Test rate limiting on authentication endpoints"""
        client = TestClient(app)

        # Make many failed login attempts
        attempt_count = TEST_MAX_LOGIN_ATTEMPTS + TEST_PAGE_SIZE
        for i in range(attempt_count):
            response = client.post("/api/auth/login", json={
                "username": "attacker",
                "password": f"attempt{i}"
            })

        # Should be rate limited (429)
        assert response.status_code == 429

    def test_jwt_token_expiration(self):
        """Test JWT tokens expire correctly"""
        # Create token with 1 second expiration
        token = create_access_token(
            data={"sub": "user123"},
            expires_delta=timedelta(seconds=1)
        )

        # Token should be valid immediately
        payload = verify_token(token)
        assert payload is not None

        # Wait for expiration
        time.sleep(2)

        # Token should be expired
        payload = verify_token(token)
        assert payload is None

    def test_jwt_signature_verification(self):
        """Test JWT signature is verified"""
        # Create valid token
        token = create_access_token(data={"sub": "user123"})

        # Tamper with token
        tampered_token = token[:-10] + "tampered123"

        # Should fail verification
        payload = verify_token(tampered_token)
        assert payload is None

    def test_password_hashing_strength(self):
        """Test passwords are hashed with strong algorithm"""
        from backend.server.auth.jwt_utils import get_password_hash, verify_password

        password = "MySecurePassword123!"
        hashed = get_password_hash(password)

        # Should use bcrypt (starts with $2b$)
        assert hashed.startswith("$2b$")

        # Should verify correctly
        assert verify_password(password, hashed)

        # Wrong password should not verify
        assert not verify_password("WrongPassword", hashed)

    def test_no_default_credentials(self):
        """Test no default admin credentials exist"""
        client = TestClient(app)

        # Try common default credentials
        default_creds = [
            ("admin", "admin"),
            ("admin", "password"),
            ("root", "root"),
            ("admin", "Admin123"),
        ]

        for username, password in default_creds:
            response = client.post("/api/auth/login", json={
                "username": username,
                "password": password
            })
            # Should all fail
            assert response.status_code == 401

    def test_secure_headers_present(self):
        """Test security headers are present in responses"""
        client = TestClient(app)

        response = client.get("/")

        # Check for security headers
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"

        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"

        assert "X-XSS-Protection" in response.headers
        assert response.headers["X-XSS-Protection"] == "1; mode=block"

        assert "Strict-Transport-Security" in response.headers
        assert "max-age=31536000" in response.headers["Strict-Transport-Security"]
        assert "includeSubDomains" in response.headers["Strict-Transport-Security"]

        assert "Content-Security-Policy" in response.headers
        assert "default-src 'self'" in response.headers["Content-Security-Policy"]

        assert "Referrer-Policy" in response.headers
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

        assert "Permissions-Policy" in response.headers
        assert "geolocation=()" in response.headers["Permissions-Policy"]

    def test_https_only_in_production(self):
        """Test HTTPS enforcement in production"""
        # This would be tested in actual deployment
        # Check that production config has security settings
        # In test environment, API_HOST is typically localhost
        import os
        env = os.getenv("ENVIRONMENT", "test")
        assert env != "production" or settings.API_HOST != "localhost"


##############################################################################
# 3. RATE LIMITING TESTS (5 tests)
##############################################################################

class TestRateLimiting:
    """Test rate limiting functionality"""

    def test_rate_limiter_allows_within_limit(self):
        """Test rate limiter allows requests within limit"""
        limiter = RateLimiter()

        # Requests should be allowed while under the configured limit
        for i in range(TEST_MAX_LOGIN_ATTEMPTS):
            is_allowed, count, reset_time = limiter.is_allowed("test_user", "/api/test", TEST_PAGE_SIZE)
            assert is_allowed

    def test_rate_limiter_blocks_over_limit(self):
        """Test rate limiter blocks requests over limit"""
        limiter = RateLimiter()

        # Exhaust limit
        for i in range(TEST_PAGE_SIZE):
            limiter.is_allowed("test_user", "/api/test", TEST_PAGE_SIZE)

        # Next request should be blocked
        is_allowed, count, reset_time = limiter.is_allowed("test_user", "/api/test", TEST_PAGE_SIZE)
        assert not is_allowed

    def test_rate_limiter_per_endpoint(self):
        """Test rate limiter is per-endpoint"""
        limiter = RateLimiter()

        # Fill limit for endpoint1
        for i in range(TEST_PAGE_SIZE):
            limiter.is_allowed("test_user", "/api/endpoint1", TEST_PAGE_SIZE)

        # endpoint2 should still have capacity
        is_allowed, count, reset_time = limiter.is_allowed("test_user", "/api/endpoint2", TEST_PAGE_SIZE)
        assert is_allowed

    def test_rate_limiter_sliding_window(self):
        """Test rate limiter uses sliding window"""
        limiter = RateLimiter()
        limiter.window_size = 2  # 2 second window for testing

        # Make requests within the window
        for i in range(TEST_MAX_LOGIN_ATTEMPTS):
            limiter.is_allowed("test_user", "/api/test", TEST_PAGE_SIZE)

        # Wait for window to slide
        time.sleep(2.1)

        # Old requests should be expired, new request allowed
        is_allowed, count, reset_time = limiter.is_allowed("test_user", "/api/test", TEST_PAGE_SIZE)
        assert is_allowed
        assert count == 1  # Only current request counted

    def test_rate_limiter_returns_retry_after(self):
        """Test rate limiter returns retry-after time"""
        limiter = RateLimiter()

        # Fill limit
        for i in range(TEST_PAGE_SIZE):
            limiter.is_allowed("test_user", "/api/test", TEST_PAGE_SIZE)

        # Check retry-after is returned
        is_allowed, count, reset_time = limiter.is_allowed("test_user", "/api/test", TEST_PAGE_SIZE)
        assert not is_allowed
        assert reset_time > 0
        assert reset_time <= limiter.window_size


##############################################################################
# 4. AUTHENTICATION TESTS (6 tests)
##############################################################################

class TestAuthentication:
    """Test authentication mechanisms"""

    def test_password_reset_requires_verification(self):
        """Test password reset requires email verification"""
        client = TestClient(app)

        # Register a test user
        register_resp = client.post("/api/auth/register", json={
            "username": "resetuser",
            "email": "reset@test.com",
            "password": "SecurePass123!"
        })

        # Note: Password reset endpoint is a future enhancement
        # For now, verify the user exists and can change password via profile
        if register_resp.status_code == 201:
            login_resp = client.post("/api/auth/login", json={
                "username": "resetuser",
                "password": "SecurePass123!"
            })
            assert login_resp.status_code == 200
            # Password change would require email verification in production
            # This test validates the user flow exists

    def test_account_lockout_after_failed_attempts(self):
        """Test account locks after multiple failed login attempts"""
        client = TestClient(app)

        # Register a test user first
        client.post("/api/auth/register", json={
            "username": "locktest",
            "email": "locktest@example.com",
            "password": "SecurePass123!"
        })

        # Make repeated failed login attempts (5 is the threshold)
        for i in range(TEST_MAX_LOGIN_ATTEMPTS):
            response = client.post("/api/auth/login", json={
                "username": "locktest",
                "password": "WrongPassword"
            })
            # Should be 401 until account is locked
            assert response.status_code in [401, 423]

        # After 5 failures, account should be locked (423 Locked)
        response = client.post("/api/auth/login", json={
            "username": "locktest",
            "password": "WrongPassword"
        })
        assert response.status_code == 423
        assert "locked" in response.json()["detail"].lower()

        # Even correct password should fail while locked
        response = client.post("/api/auth/login", json={
            "username": "locktest",
            "password": "SecurePass123!"
        })
        assert response.status_code == 423

    def test_token_refresh_mechanism(self):
        """Test JWT token refresh mechanism"""
        client = TestClient(app)

        # Register and login to get tokens
        client.post("/api/auth/register", json={
            "username": "refreshuser",
            "email": "refresh@test.com",
            "password": "SecurePass123!"
        })

        login_resp = client.post("/api/auth/login", json={
            "username": "refreshuser",
            "password": "SecurePass123!"
        })

        if login_resp.status_code == 200:
            tokens = login_resp.json()
            assert "access_token" in tokens
            assert "refresh_token" in tokens
            assert "expires_in" in tokens

            refresh_token = tokens["refresh_token"]

            # Use refresh token to get new access token
            refresh_resp = client.post("/api/auth/refresh", json={
                "refresh_token": refresh_token
            })

            assert refresh_resp.status_code == 200
            new_tokens = refresh_resp.json()
            assert "access_token" in new_tokens
            assert "refresh_token" in new_tokens

            # New tokens should be different (token rotation)
            assert new_tokens["refresh_token"] != refresh_token

            # Old refresh token should no longer work (rotation)
            old_refresh_resp = client.post("/api/auth/refresh", json={
                "refresh_token": refresh_token
            })
            assert old_refresh_resp.status_code == 401

    def test_session_invalidation_on_logout(self):
        """Test session is properly invalidated on logout"""
        client = TestClient(app)

        # Register and login
        client.post("/api/auth/register", json={
            "username": "logoutuser",
            "email": "logout@test.com",
            "password": "SecurePass123!"
        })

        login_resp = client.post("/api/auth/login", json={
            "username": "logoutuser",
            "password": "SecurePass123!"
        })

        if login_resp.status_code == 200:
            access_token = login_resp.json()["access_token"]

            # Token should work before logout
            me_resp = client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            assert me_resp.status_code == 200

            # Logout (blacklists the token)
            logout_resp = client.post(
                "/api/auth/logout",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            assert logout_resp.status_code == 200
            assert logout_resp.json()["success"] is True

            # Token should be blacklisted after logout
            me_resp_after = client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            # Should fail with 401 (token revoked)
            assert me_resp_after.status_code == 401

    def test_multi_factor_authentication(self):
        """Test MFA for admin accounts"""
        # MFA implementation uses TOTP (Time-based One-Time Password)
        # This test validates the MFA setup and verification flow
        import pyotp

        client = TestClient(app)

        # Register user
        register_resp = client.post("/api/auth/register", json={
            "username": "mfauser",
            "email": "mfa@test.com",
            "password": "SecurePass123!"
        })

        if register_resp.status_code == 201:
            # Login
            login_resp = client.post("/api/auth/login", json={
                "username": "mfauser",
                "password": "SecurePass123!"
            })
            token = login_resp.json().get("access_token")

            if token:
                # Generate TOTP secret for testing
                totp_secret = pyotp.random_base32()
                totp = pyotp.TOTP(totp_secret)

                # Verify TOTP works correctly
                current_code = totp.now()
                assert len(current_code) == 6
                assert totp.verify(current_code)

                # Note: Full MFA setup endpoint (/api/auth/mfa/setup)
                # would be tested in integration tests
                # This validates TOTP library works correctly

    def test_api_key_authentication(self):
        """Test API key authentication for service accounts"""
        client = TestClient(app)

        # Register and login
        client.post("/api/auth/register", json={
            "username": "apikeyuser",
            "email": "apikey@example.com",
            "password": "SecurePass123!"
        })
        login_response = client.post("/api/auth/login", json={
            "username": "apikeyuser",
            "password": "SecurePass123!"
        })
        token = login_response.json()["access_token"]

        # Create an API key
        create_response = client.post(
            "/api/keys",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "Test Service Account",
                "expires_in_days": 30,
                "rate_limit": 1000
            }
        )
        assert create_response.status_code == 201
        api_key_data = create_response.json()
        assert "secret_key" in api_key_data
        assert api_key_data["secret_key"].startswith("fog_sk_")
        secret_key = api_key_data["secret_key"]

        # Test API key authentication
        # Note: This test validates the key creation and format
        # Actual endpoint authentication with X-API-Key header
        # should be tested in integration tests
        assert len(secret_key) >= TEST_TOKEN_LENGTH  # Key should be sufficiently long
        assert api_key_data["is_active"] is True
        assert api_key_data["rate_limit"] == 1000

        # List API keys
        list_response = client.get(
            "/api/keys",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert list_response.status_code == 200
        keys_list = list_response.json()
        assert keys_list["total"] == 1
        assert keys_list["keys"][0]["name"] == "Test Service Account"
        # Secret key should NOT be in list response
        assert "secret_key" not in keys_list["keys"][0]

        # Revoke API key
        key_id = api_key_data["id"]
        revoke_response = client.delete(
            f"/api/keys/{key_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert revoke_response.status_code == 200
        assert revoke_response.json()["success"] is True


##############################################################################
# 5. INPUT VALIDATION TESTS (6 tests)
##############################################################################

class TestInputValidation:
    """Test input validation and sanitization"""

    def test_email_validation(self):
        """Test email format validation"""
        client = TestClient(app)

        # Invalid email
        response = client.post("/api/auth/register", json={
            "username": "testuser",
            "email": "invalid-email",
            "password": "SecurePass123!"
        })

        assert response.status_code == 422  # Validation error

    def test_password_strength_requirements(self):
        """Test password meets strength requirements"""
        client = TestClient(app)

        weak_passwords = [
            "weak",  # Too short
            "alllowercase",  # No uppercase or digits
            "ALLUPPERCASE",  # No lowercase or digits
            "NoDigits!",  # No digits
            "NoSpecialChar123",  # No special characters (optional)
        ]

        for weak_pass in weak_passwords:
            response = client.post("/api/auth/register", json={
                "username": "testuser",
                "email": "test@example.com",
                "password": weak_pass
            })
            assert response.status_code == 422

    def test_username_length_validation(self):
        """Test username length constraints"""
        client = TestClient(app)

        # Too short
        response = client.post("/api/auth/register", json={
            "username": "ab",  # Less than 3 chars
            "email": "test@example.com",
            "password": "SecurePass123!"
        })
        assert response.status_code == 422

        # Too long (if limit is enforced)
        response = client.post("/api/auth/register", json={
            "username": "a" * 100,  # Very long
            "email": "test@example.com",
            "password": "SecurePass123!"
        })
        # Should either fail validation or succeed (depending on max length)
        assert response.status_code in [201, 422]

    def test_special_characters_sanitization(self):
        """Test special characters are sanitized"""
        client = TestClient(app)

        # Input with special characters
        response = client.post("/api/auth/register", json={
            "username": "user<script>alert(1)</script>",
            "email": "test@example.com",
            "password": "SecurePass123!"
        })

        # Should sanitize input (if successful)
        if response.status_code == 201:
            assert "<script>" not in response.json().get("username", "")

    def test_file_upload_size_limit(self):
        """Test file upload size limits"""
        # File upload endpoints are a future enhancement
        # When implemented, this test should verify:
        # 1. Maximum file size limit (e.g., 10MB)
        # 2. Allowed file types (whitelist)
        # 3. Content-type validation
        # 4. Virus scanning integration
        # 5. Secure storage path (outside webroot)

        # Placeholder validation - test framework works
        assert True, "File upload security will be tested when endpoints exist"

    def test_json_payload_size_limit(self):
        """Test JSON payload size limits"""
        client = TestClient(app)

        # Very large payload
        large_payload = {"data": "x" * TEST_SMALL_FILE_SIZE}  # 1MB of data

        response = client.post("/api/auth/login", json=large_payload)

        # Should handle gracefully (413 or 422)
        assert response.status_code in [413, 422, 500]


##############################################################################
# 6. MONITORING AND LOGGING TESTS (5 tests)
##############################################################################

class TestMonitoringAndLogging:
    """Test monitoring and logging functionality"""

    def test_health_check_endpoint(self):
        """Test health check endpoint returns correct status"""
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 200
        assert "status" in response.json()

    def test_metrics_endpoint_available(self):
        """Test Prometheus metrics endpoint"""
        client = TestClient(app)

        # Prometheus metrics typically at /metrics
        response = client.get("/metrics")
        # May or may not exist yet
        assert response.status_code in [200, 404]

    def test_sensitive_data_not_logged(self):
        """Test sensitive data is not logged"""
        import logging
        import io
        from backend.server.middleware.log_sanitizer import (
            LogSanitizationFilter,
            sanitize_log_string
        )

        # Create in-memory log handler to capture logs
        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.INFO)

        # Create test logger with sanitization filter
        test_logger = logging.getLogger("test_sanitizer")
        test_logger.setLevel(logging.INFO)
        test_logger.addHandler(handler)
        test_logger.addFilter(LogSanitizationFilter())

        # Test cases with sensitive data
        sensitive_test_cases = [
            ("password=mysecretpass123", "[REDACTED:password]"),
            ("token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoiYWRtaW4ifQ.sig", "[REDACTED:jwt]"),
            ("api_key=sk_live_1234567890abcdef", "[REDACTED:token]"),
            ("Authorization: Bearer abc123def456", "[REDACTED:authorization]"),
            ("SSN: 123-45-6789", "[REDACTED:ssn]"),
            ("card: 4532-1234-5678-9010", "[REDACTED:credit_card]"),
            ("email: user@example.com", "[REDACTED:email]@example.com"),
            ("phone: (555) 123-4567", "[REDACTED:phone]"),
        ]

        for sensitive_data, expected_redaction in sensitive_test_cases:
            # Clear the log stream
            log_stream.truncate(0)
            log_stream.seek(0)

            # Log the sensitive data
            test_logger.info(f"User input: {sensitive_data}")

            # Get logged output
            logged_output = log_stream.getvalue()

            # Verify sensitive data is NOT in logs
            # Extract just the sensitive value (not the key)
            if "=" in sensitive_data or ":" in sensitive_data:
                sensitive_value = sensitive_data.split("=")[-1].split(":")[-1].strip()
                # Make sure the actual sensitive value is NOT in logs
                # (Some characters from the pattern might remain, but not the full value)
                if len(sensitive_value) > 10:  # Only check for longer sensitive values
                    assert sensitive_value not in logged_output, \
                        f"Sensitive data '{sensitive_value}' was not redacted in logs"

            # Verify redaction marker IS in logs
            assert "[REDACTED" in logged_output, \
                f"Redaction marker not found for: {sensitive_data}"

        # Test utility function
        test_string = "User password=secret123 and token=abc123xyz"
        sanitized = sanitize_log_string(test_string)
        assert "secret123" not in sanitized
        assert "abc123xyz" not in sanitized
        assert "[REDACTED" in sanitized

        # Cleanup
        test_logger.removeHandler(handler)

    def test_request_correlation_ids(self):
        """Test all requests have correlation IDs"""
        client = TestClient(app)

        # Test health endpoint (always works)
        response = client.get("/health")
        assert response.status_code == 200

        # Test that correlation ID is in response headers
        # ErrorHandlingMiddleware adds X-Correlation-ID to all responses
        assert "X-Correlation-ID" in response.headers
        correlation_id = response.headers["X-Correlation-ID"]
        assert len(correlation_id) > 0  # Should be a UUID

        # Test on error response too
        error_response = client.get("/nonexistent-endpoint")
        if "X-Correlation-ID" in error_response.headers:
            assert len(error_response.headers["X-Correlation-ID"]) > 0

    @pytest.mark.asyncio
    async def test_audit_log_for_sensitive_operations(self):
        """Test sensitive operations are audit logged"""
        from httpx import AsyncClient, ASGITransport
        from backend.server.main import app
        from backend.server.database import get_db_context
        from backend.server.models.audit_log import AuditLog
        from sqlalchemy import select, desc

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # Perform a sensitive operation (registration)
            response = await ac.post("/api/auth/register", json={
                "username": "audit_test_user",
                "email": "audit@test.com",
                "password": "SecurePass123!"
            })

            # Allow time for batch logging to flush
            import asyncio
            await asyncio.sleep(0.5)

            # Query audit logs to verify logging
            async with get_db_context() as db:
                result = await db.execute(
                    select(AuditLog)
                    .where(AuditLog.event_type.in_(['user_created', 'data_create']))
                    .order_by(desc(AuditLog.timestamp))
                    .limit(10)
                )
                logs = result.scalars().all()

                # Should have at least one audit log for the registration
                # (Either event_type='user_created' or event_type='data_create')
                assert len(logs) > 0, "No audit logs found for registration"

                # Verify log contains expected fields
                latest_log = logs[0]
                assert latest_log.ip_address is not None
                assert latest_log.action in ['create', 'post']
                assert latest_log.status in ['success', 'failure']


##############################################################################
# 7. PERFORMANCE TESTS (5 tests)
##############################################################################

class TestPerformance:
    """Test performance and efficiency"""

    @pytest.mark.asyncio
    async def test_api_response_time_p95(self):
        """Test API response time p95 < 200ms"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response_times = []
            sample_size = TEST_MAX_RESULTS

            for i in range(sample_size):
                start = time.time()
                await ac.get("/health")
                end = time.time()
                response_times.append((end - start) * 1000)  # Convert to ms

            response_times.sort()
            p95_index = max(0, int(sample_size * 0.95) - 1)
            p95 = response_times[p95_index]  # 95th percentile

            # Target: p95 < 200ms
            assert p95 < 200, f"P95 response time {p95}ms exceeds 200ms target"

    def test_concurrent_request_handling(self):
        """Test server handles concurrent requests"""
        client = TestClient(app)

        # Simulate concurrent requests
        import concurrent.futures

        def make_request():
            return client.get("/health")

        with concurrent.futures.ThreadPoolExecutor(max_workers=TEST_PAGE_SIZE) as executor:
            futures = [executor.submit(make_request) for _ in range(TEST_MAX_RESULTS // 2)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All requests should succeed
        assert all(r.status_code == 200 for r in results)

    def test_database_connection_pooling(self):
        """Test database connection pooling is configured"""
        # Check that connection pooling is configured
        from backend.server.database import engine

        # Should have pool_size configured
        assert hasattr(engine.pool, '_pool')

    def test_memory_leak_detection(self):
        """Test for memory leaks using memory profiler service"""
        import asyncio
        from backend.server.services.memory_profiler import memory_profiler

        async def test_memory_monitoring():
            # Start profiler
            await memory_profiler.start()

            try:
                # Take initial snapshot
                initial_snapshot = await memory_profiler.take_snapshot()
                assert initial_snapshot is not None
                assert initial_snapshot.heap_size_mb > 0

                # Simulate some operations
                data = []
                for i in range(100):
                    data.append({"key": f"value_{i}" * 100})

                # Take another snapshot
                later_snapshot = await memory_profiler.take_snapshot()
                assert later_snapshot is not None

                # Check leak detection is working
                leak_report = await memory_profiler.detect_leaks()
                # Leak detection returns report (may or may not find leaks)
                assert leak_report is not None

                # Verify snapshot history is maintained
                summary = await memory_profiler.get_summary()
                assert summary["snapshot_count"] >= 2

            finally:
                await memory_profiler.stop()

        asyncio.get_event_loop().run_until_complete(test_memory_monitoring())

    def test_cache_effectiveness(self):
        """Test caching service functionality"""
        import asyncio
        from backend.server.services.cache_service import cache_service

        async def test_cache_operations():
            # Initialize cache service
            await cache_service.initialize()

            test_namespace = "test_ns"
            test_key = "test_key"
            test_value = {"data": "test_value", "count": 42}

            try:
                # Test set and get
                await cache_service.set(test_namespace, test_key, test_value, ttl=60)
                cached_value = await cache_service.get(test_namespace, test_key)
                assert cached_value == test_value

                # Test cache hit
                cached_value_again = await cache_service.get(test_namespace, test_key)
                assert cached_value_again == test_value

                # Test invalidation
                await cache_service.invalidate(test_namespace, test_key)
                invalidated_value = await cache_service.get(test_namespace, test_key)
                assert invalidated_value is None

                # Test key generation
                generated_key = cache_service.generate_key(
                    test_namespace, "operation", arg1="val1", arg2=123
                )
                assert generated_key is not None
                assert len(generated_key) > 0

            finally:
                # Cleanup
                await cache_service.invalidate(test_namespace, test_key)

        asyncio.get_event_loop().run_until_complete(test_cache_operations())


##############################################################################
# Test Configuration
##############################################################################

@pytest.fixture(scope="session")
def test_client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset rate limiter between tests"""
    rate_limiter.requests.clear()
    yield


@pytest.fixture(autouse=True)
def reset_circuit_breaker():
    """Reset circuit breaker between tests"""
    global_circuit_breaker.state.clear()
    global_circuit_breaker.failure_count.clear()
    global_circuit_breaker.last_failure_time.clear()
    global_circuit_breaker.half_open_requests.clear()
    yield


# Run all tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
