"""
Security integration tests for auth and rate limiting.
"""
import time

import httpx
import pytest

from server.main import app
from server.middleware.rate_limit import rate_limiter


BASE_URL = "http://testserver"


@pytest.fixture(autouse=True)
def reset_rate_limit_state():
    """Prevent cross-test rate-limit bleed-through."""
    rate_limiter.requests.clear()
    rate_limiter.last_cleanup = time.time()
    yield


@pytest.fixture
def test_user():
    """Generate a unique test user per test."""
    unique = int(time.time_ns())
    return {
        "username": f"testuser_{unique}",
        "email": f"test_{unique}@example.com",
        "password": "TestPassword123",
    }


@pytest.fixture
async def registered_user(test_user):
    """Register and return a user payload."""
    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as client:
        response = await client.post(
            f"{BASE_URL}/api/auth/register",
            json=test_user,
        )
        assert response.status_code == 201
        return test_user


@pytest.fixture
async def token(registered_user):
    """Login and return an access token."""
    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as client:
        response = await client.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "username": registered_user["username"],
                "password": registered_user["password"],
            },
        )
        assert response.status_code == 200
        return response.json()["access_token"]


@pytest.mark.asyncio
async def test_user_registration(test_user):
    """Test user registration endpoint."""
    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as client:
        response = await client.post(
            f"{BASE_URL}/api/auth/register",
            json=test_user,
        )

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == test_user["username"].lower()
    assert data["email"] == test_user["email"].lower()
    assert "hashed_password" not in data
    assert data["is_active"] is True
    assert data["is_admin"] is False


@pytest.mark.asyncio
async def test_user_login(registered_user):
    """Test user login endpoint."""
    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as client:
        response = await client.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "username": registered_user["username"],
                "password": registered_user["password"],
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "expires_in" in data


@pytest.mark.asyncio
async def test_protected_endpoint(token: str, registered_user):
    """Test accessing protected endpoint with JWT."""
    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as client:
        response = await client.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == registered_user["username"].lower()


@pytest.mark.asyncio
async def test_protected_endpoint_no_token():
    """Test accessing protected endpoint without token."""
    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as client:
        response = await client.get(f"{BASE_URL}/api/auth/me")

    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_invalid_token():
    """Test accessing protected endpoint with invalid token."""
    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as client:
        response = await client.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": "Bearer invalid_token_12345"},
        )

    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_rate_limiting():
    """Test rate limiting middleware on auth endpoints."""
    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as client:
        saw_rate_limit = False
        for _ in range(20):
            response = await client.post(
                f"{BASE_URL}/api/auth/login",
                json={
                    "username": "nonexistent",
                    "password": "wrong",
                },
            )
            if response.status_code == 429:
                data = response.json()
                assert "Rate limit exceeded" in data["error"]
                assert "retry_after" in data
                saw_rate_limit = True
                break

    assert saw_rate_limit


@pytest.mark.asyncio
async def test_password_validation():
    """Test password complexity requirements."""
    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as client:
        # Weak password (no uppercase)
        weak_1 = int(time.time_ns())
        response = await client.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "username": f"weakuser_{weak_1}",
                "email": f"weak_{weak_1}@example.com",
                "password": "weakpassword123",
            },
        )
        assert response.status_code == 422

        # Weak password (no numbers)
        weak_2 = int(time.time_ns())
        response = await client.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "username": f"weakuser_{weak_2}",
                "email": f"weak_{weak_2}@example.com",
                "password": "WeakPassword",
            },
        )
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_username(test_user):
    """Test that duplicate usernames are rejected."""
    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as client:
        first = await client.post(
            f"{BASE_URL}/api/auth/register",
            json=test_user,
        )
        assert first.status_code == 201

        second = await client.post(
            f"{BASE_URL}/api/auth/register",
            json=test_user,
        )
        assert second.status_code == 400
        assert "already registered" in second.json()["detail"]
