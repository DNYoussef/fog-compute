"""
Security Integration Tests
Tests for authentication, authorization, and rate limiting
"""
import pytest
import httpx
import asyncio
import time
from datetime import datetime


# Test configuration
BASE_URL = "http://localhost:8000"

# Generate unique username using timestamp to allow multiple test runs
def get_test_user():
    """Generate unique test user for each test run"""
    timestamp = int(time.time())
    return {
        "username": f"testuser{timestamp}",
        "email": f"test{timestamp}@example.com",
        "password": "TestPassword123"
    }

TEST_USER = get_test_user()


async def test_user_registration():
    """Test user registration endpoint"""
    async with httpx.AsyncClient() as client:
        # Register new user
        response = await client.post(
            f"{BASE_URL}/api/auth/register",
            json=TEST_USER
        )

        assert response.status_code == 201
        data = response.json()
        assert data["username"] == TEST_USER["username"].lower()
        assert data["email"] == TEST_USER["email"].lower()
        assert "hashed_password" not in data  # Password should not be in response
        assert data["is_active"] is True
        assert data["is_admin"] is False
        print(f"[PASS] User registration successful: {data['username']}")


async def test_user_login():
    """Test user login endpoint"""
    async with httpx.AsyncClient() as client:
        # Login
        response = await client.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "username": TEST_USER["username"],
                "password": TEST_USER["password"]
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
        print(f"[PASS] User login successful. Token expires in {data['expires_in']}s")
        return data["access_token"]


async def test_protected_endpoint(token: str):
    """Test accessing protected endpoint with JWT"""
    async with httpx.AsyncClient() as client:
        # Access /me endpoint with token
        response = await client.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == TEST_USER["username"].lower()
        print(f"[PASS] Protected endpoint access successful: {data['username']}")


async def test_protected_endpoint_no_token():
    """Test accessing protected endpoint without token (should fail)"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/auth/me")

        assert response.status_code == 403  # Forbidden without token
        print("[PASS] Protected endpoint correctly rejects unauthenticated requests")


async def test_invalid_token():
    """Test accessing protected endpoint with invalid token"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": "Bearer invalid_token_12345"}
        )

        assert response.status_code == 401  # Unauthorized
        print("[PASS] Protected endpoint correctly rejects invalid tokens")


async def test_rate_limiting():
    """Test rate limiting middleware"""
    async with httpx.AsyncClient() as client:
        # Auth endpoint has 10 req/min limit
        # Try to exceed it
        failed_attempts = 0
        for i in range(15):
            response = await client.post(
                f"{BASE_URL}/api/auth/login",
                json={
                    "username": "nonexistent",
                    "password": "wrong"
                }
            )

            if response.status_code == 429:  # Too Many Requests
                failed_attempts += 1
                data = response.json()
                assert "Rate limit exceeded" in data["error"]
                assert "retry_after" in data
                print(f"[PASS] Rate limiting activated after {i} requests")
                print(f"       Retry after: {data['retry_after']} seconds")
                break

        assert failed_attempts > 0, "Rate limiting should have activated"


async def test_password_validation():
    """Test password complexity requirements"""
    async with httpx.AsyncClient() as client:
        # Weak password (no uppercase)
        response = await client.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "username": "weakuser",
                "email": "weak@example.com",
                "password": "weakpassword123"  # No uppercase
            }
        )

        assert response.status_code == 422  # Validation error
        print("[PASS] Weak passwords are rejected (no uppercase)")

        # Weak password (no numbers)
        response = await client.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "username": "weakuser2",
                "email": "weak2@example.com",
                "password": "WeakPassword"  # No numbers
            }
        )

        assert response.status_code == 422
        print("[PASS] Weak passwords are rejected (no numbers)")


async def test_duplicate_username():
    """Test that duplicate usernames are rejected"""
    async with httpx.AsyncClient() as client:
        # Try to register the same user that was already registered in test_user_registration
        response = await client.post(
            f"{BASE_URL}/api/auth/register",
            json=TEST_USER  # Same user as registered in first test
        )

        assert response.status_code == 400  # Bad Request (already exists)
        assert "already registered" in response.json()["detail"]
        print("[PASS] Duplicate usernames are rejected")


async def run_all_tests():
    """Run all security tests in sequence"""
    print("\n[SECURITY] Starting Security Integration Tests...\n")

    try:
        # Test 1: Registration
        await test_user_registration()

        # Test 2: Login
        token = await test_user_login()

        # Test 3: Protected endpoint with valid token
        await test_protected_endpoint(token)

        # Test 4: Protected endpoint without token
        await test_protected_endpoint_no_token()

        # Test 5: Invalid token
        await test_invalid_token()

        # Test 6: Rate limiting
        await test_rate_limiting()

        # Test 7: Password validation
        await test_password_validation()

        # Test 8: Duplicate username
        await test_duplicate_username()

        print("\n[PASS] All security tests passed!\n")

    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}\n")
        raise
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}\n")
        raise


if __name__ == "__main__":
    asyncio.run(run_all_tests())
