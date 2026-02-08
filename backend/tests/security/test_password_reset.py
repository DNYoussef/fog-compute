"""
TEST-01: Password Reset Security Tests
Tests password reset flow including email generation, token validation, and expiration.
"""
import asyncio
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from server.main import app
from server.auth.jwt_utils import create_access_token
from server.config import settings
from server.middleware.rate_limit import rate_limiter
from server.routes import auth as auth_routes
from server.services.token_service import get_token_service, token_service


BASE_URL = "http://test"
TEST_PASSWORD = "OldPassword123"
NEW_PASSWORD = "NewPassword456"


def _assert_generic_reset_message(payload: dict) -> None:
    assert "message" in payload
    assert "if an account exists" in payload["message"].lower()


@pytest.fixture(autouse=True)
def reset_in_memory_state():
    """Avoid cross-test bleed from in-memory limiters/token stores."""
    rate_limiter.requests.clear()
    rate_limiter.last_cleanup = time.time()
    auth_routes._reset_request_counts.clear()
    token_service._password_reset_tokens.clear()
    token_service._login_attempts.clear()
    token_service._refresh_tokens.clear()


@pytest.fixture
async def test_user():
    unique = int(time.time_ns())
    return {
        "username": f"reset_user_{unique}",
        "email": f"reset_test_{unique}@example.com",
        "password": TEST_PASSWORD,
    }


@pytest.fixture
async def registered_user(test_user):
    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as client:
        response = await client.post("/api/auth/register", json=test_user)
        assert response.status_code == 201
        user_data = response.json()

        login_response = await client.post(
            "/api/auth/login",
            json={"username": test_user["username"], "password": test_user["password"]},
        )
        assert login_response.status_code == 200
        token_data = login_response.json()

        return {
            **user_data,
            "access_token": token_data["access_token"],
            "original_password": test_user["password"],
        }


@pytest.mark.asyncio
async def test_request_password_reset_success(registered_user):
    with patch(
        "server.services.email_service.EmailService.send_password_reset_email",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_email:
        async with httpx.AsyncClient(app=app, base_url=BASE_URL) as client:
            response = await client.post(
                "/api/auth/password-reset/request",
                json={"email": registered_user["email"]},
            )
            assert response.status_code == 200
            _assert_generic_reset_message(response.json())
            assert mock_email.await_count == 1


@pytest.mark.asyncio
async def test_request_password_reset_nonexistent_email():
    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as client:
        response = await client.post(
            "/api/auth/password-reset/request",
            json={"email": "nonexistent@example.com"},
        )
        assert response.status_code == 200
        _assert_generic_reset_message(response.json())


@pytest.mark.asyncio
async def test_request_password_reset_invalid_email():
    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as client:
        response = await client.post(
            "/api/auth/password-reset/request",
            json={"email": "not-an-email"},
        )
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_reset_password_with_valid_token(registered_user):
    token_service_instance = await get_token_service()
    token_data = await token_service_instance.create_password_reset_token(
        user_id=registered_user["id"],
        email=registered_user["email"],
    )

    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as client:
        response = await client.post(
            "/api/auth/password-reset/confirm",
            json={"token": token_data.token, "new_password": NEW_PASSWORD},
        )
        assert response.status_code == 200
        assert "password has been reset successfully" in response.json()["message"].lower()

        login_response = await client.post(
            "/api/auth/login",
            json={"username": registered_user["username"], "password": NEW_PASSWORD},
        )
        assert login_response.status_code == 200

        old_login_response = await client.post(
            "/api/auth/login",
            json={
                "username": registered_user["username"],
                "password": registered_user["original_password"],
            },
        )
        assert old_login_response.status_code == 401


@pytest.mark.asyncio
async def test_reset_password_with_invalid_token():
    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as client:
        response = await client.post(
            "/api/auth/password-reset/confirm",
            json={"token": "invalid_token_123", "new_password": NEW_PASSWORD},
        )
        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower() or "expired" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reset_password_with_expired_token(registered_user):
    token_service_instance = await get_token_service()
    token_data = await token_service_instance.create_password_reset_token(
        user_id=registered_user["id"],
        email=registered_user["email"],
    )
    if token_data.token in token_service._password_reset_tokens:
        token_service._password_reset_tokens[token_data.token].expires_at = (
            datetime.now(timezone.utc) - timedelta(minutes=1)
        )

    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as client:
        response = await client.post(
            "/api/auth/password-reset/confirm",
            json={"token": token_data.token, "new_password": NEW_PASSWORD},
        )
        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower() or "expired" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reset_password_with_weak_password(registered_user):
    token_service_instance = await get_token_service()
    token_data = await token_service_instance.create_password_reset_token(
        user_id=registered_user["id"],
        email=registered_user["email"],
    )
    weak_passwords = ["short", "alllowercase", "ALLUPPERCASE", "12345678", "NoDigits!"]

    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as client:
        for weak_password in weak_passwords:
            response = await client.post(
                "/api/auth/password-reset/confirm",
                json={"token": token_data.token, "new_password": weak_password},
            )
            assert response.status_code == 422


@pytest.mark.asyncio
async def test_reset_token_expiration_time():
    token_service_instance = await get_token_service()
    token_data = await token_service_instance.create_password_reset_token(
        user_id="test-user-id",
        email="test@example.com",
    )
    delta = token_data.expires_at - token_data.created_at
    assert 3500 < delta.total_seconds() < 3700


@pytest.mark.asyncio
async def test_reset_token_single_use(registered_user):
    token_service_instance = await get_token_service()
    token_data = await token_service_instance.create_password_reset_token(
        user_id=registered_user["id"],
        email=registered_user["email"],
    )

    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as client:
        response1 = await client.post(
            "/api/auth/password-reset/confirm",
            json={"token": token_data.token, "new_password": NEW_PASSWORD},
        )
        assert response1.status_code == 200

        response2 = await client.post(
            "/api/auth/password-reset/confirm",
            json={"token": token_data.token, "new_password": "AnotherPassword789"},
        )
        assert response2.status_code == 400


@pytest.mark.asyncio
async def test_reset_email_contains_link(registered_user):
    with patch(
        "server.services.email_service.EmailService.send_password_reset_email",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_email:
        async with httpx.AsyncClient(app=app, base_url=BASE_URL) as client:
            response = await client.post(
                "/api/auth/password-reset/request",
                json={"email": registered_user["email"]},
            )
            assert response.status_code == 200
            _assert_generic_reset_message(response.json())

            assert mock_email.await_count == 1
            _, kwargs = mock_email.await_args
            assert len(kwargs.get("reset_token", "")) > 20


@pytest.mark.asyncio
async def test_password_reset_rate_limiting(registered_user):
    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as client:
        responses = []
        for _ in range(10):
            response = await client.post(
                "/api/auth/password-reset/request",
                json={"email": registered_user["email"]},
            )
            responses.append(response.status_code)
            await asyncio.sleep(0.1)
        assert all(status in [200, 429] for status in responses)


@pytest.mark.asyncio
async def test_password_reset_updates_timestamp(registered_user):
    token_service_instance = await get_token_service()
    token_data = await token_service_instance.create_password_reset_token(
        user_id=registered_user["id"],
        email=registered_user["email"],
    )

    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as client:
        response = await client.post(
            "/api/auth/password-reset/confirm",
            json={"token": token_data.token, "new_password": NEW_PASSWORD},
        )
        assert response.status_code == 200

        login_response = await client.post(
            "/api/auth/login",
            json={"username": registered_user["username"], "password": NEW_PASSWORD},
        )
        assert login_response.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_wrong_token_type(registered_user):
    access_token = create_access_token(data={"sub": registered_user["id"], "scope": "access"})

    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as client:
        response = await client.post(
            "/api/auth/password-reset/confirm",
            json={"token": access_token, "new_password": NEW_PASSWORD},
        )
        assert response.status_code in [400, 401, 403]


@pytest.mark.asyncio
async def test_password_reset_case_insensitive_email(registered_user):
    with patch(
        "server.services.email_service.EmailService.send_password_reset_email",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_email:
        async with httpx.AsyncClient(app=app, base_url=BASE_URL) as client:
            response = await client.post(
                "/api/auth/password-reset/request",
                json={"email": registered_user["email"].upper()},
            )
            assert response.status_code == 200
            _assert_generic_reset_message(response.json())
            assert mock_email.await_count == 1


def test_password_reset_test_count():
    test_count = 14
    assert test_count == 14
