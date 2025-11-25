"""
Test suite for CSRF middleware
Demonstrates CSRF protection functionality
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from .csrf import CSRFMiddleware


def test_csrf_middleware_basic():
    """Test basic CSRF middleware functionality"""
    # Create test app
    app = FastAPI()
    app.add_middleware(CSRFMiddleware, cookie_secure=False)  # Disable secure for testing

    @app.get("/test")
    async def get_test():
        return {"message": "GET request"}

    @app.post("/test")
    async def post_test():
        return {"message": "POST request"}

    client = TestClient(app)

    # Test 1: GET request should succeed and set CSRF cookie
    response = client.get("/test")
    assert response.status_code == 200
    assert "csrf_token" in response.cookies
    csrf_token = response.cookies["csrf_token"]
    print(f"Test 1 PASSED: GET request succeeded, CSRF token set: {csrf_token[:10]}...")

    # Test 2: POST without CSRF token should fail
    response = client.post("/test")
    assert response.status_code == 403
    assert "CSRF validation failed" in response.json()["error"]
    print("Test 2 PASSED: POST without CSRF token rejected with 403")

    # Test 3: POST with CSRF token should succeed
    response = client.post(
        "/test",
        cookies={"csrf_token": csrf_token},
        headers={"X-CSRF-Token": csrf_token}
    )
    assert response.status_code == 200
    print("Test 3 PASSED: POST with valid CSRF token succeeded")

    # Test 4: POST with mismatched CSRF token should fail
    response = client.post(
        "/test",
        cookies={"csrf_token": csrf_token},
        headers={"X-CSRF-Token": "invalid_token"}
    )
    assert response.status_code == 403
    assert "token mismatch" in response.json()["detail"].lower()
    print("Test 4 PASSED: POST with mismatched CSRF token rejected")


def test_csrf_middleware_bearer_auth_skip():
    """Test that Bearer token authenticated routes skip CSRF check"""
    app = FastAPI()
    app.add_middleware(CSRFMiddleware, cookie_secure=False)

    @app.post("/test")
    async def post_test():
        return {"message": "POST request"}

    client = TestClient(app)

    # POST with Bearer token should skip CSRF check
    response = client.post(
        "/test",
        headers={"Authorization": "Bearer test_token_123"}
    )
    assert response.status_code == 200
    print("Test 5 PASSED: POST with Bearer token skipped CSRF check")


def test_csrf_middleware_safe_methods():
    """Test that safe methods (GET, HEAD, OPTIONS) always succeed"""
    app = FastAPI()
    app.add_middleware(CSRFMiddleware, cookie_secure=False)

    @app.get("/test")
    async def get_test():
        return {"message": "GET"}

    @app.head("/test")
    async def head_test():
        return {"message": "HEAD"}

    @app.options("/test")
    async def options_test():
        return {"message": "OPTIONS"}

    client = TestClient(app)

    # All safe methods should succeed without CSRF token
    assert client.get("/test").status_code == 200
    assert client.head("/test").status_code == 200
    assert client.options("/test").status_code == 200
    print("Test 6 PASSED: Safe methods (GET, HEAD, OPTIONS) succeeded without CSRF token")


if __name__ == "__main__":
    print("Running CSRF Middleware Tests...\n")
    test_csrf_middleware_basic()
    print()
    test_csrf_middleware_bearer_auth_skip()
    print()
    test_csrf_middleware_safe_methods()
    print("\nAll tests passed!")
