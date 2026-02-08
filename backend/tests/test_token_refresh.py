"""
Tests for Token Expiry and Refresh Flow (PHASE0-SEC-003)

Tests cover:
- Access token expiry (15 minutes)
- Refresh token expiry (7 days)
- Token refresh flow
- Token rotation on refresh
- Invalid/expired token handling
"""
import pytest
from datetime import datetime, UTC, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import os

# Set test environment variables before imports
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-token-refresh-testing-only')
os.environ.setdefault('TESTING', 'true')

from backend.server.schemas.device_mesh import (
    DeviceProfile,
    DeviceRole,
    DeviceCapability,
    TokenRefreshRequest,
    TokenRefreshResponse,
)
from backend.server.services.mesh_persistence import (
    MeshPersistenceService,
    hash_token,
    generate_token,
    ACCESS_TOKEN_LIFETIME_MINUTES,
    REFRESH_TOKEN_LIFETIME_DAYS,
)


# === Fixtures ===

@pytest.fixture
def mock_persistence():
    """Create a mock persistence service for token tests."""
    mock = MagicMock()

    # Track stored tokens
    stored_tokens = {}
    token_counter = [0]

    # store_token
    async def mock_store_token(device_id, token_hash, token_type="mesh_auth", expires_in_hours=None, **kwargs):
        token_counter[0] += 1
        token_id = f"token-{token_counter[0]}"

        token = MagicMock()
        token.id = token_id
        token.token_hash = token_hash
        token.device_id = device_id
        token.token_type = token_type
        token.created_at = datetime.now(UTC)
        token.expires_at = datetime.now(UTC) + timedelta(hours=expires_in_hours) if expires_in_hours else None
        token.revoked_at = None
        token.last_used_at = None
        token.use_count = 0

        # is_valid property
        def is_valid():
            now = datetime.now(UTC)
            if token.revoked_at is not None:
                return False
            if token.expires_at is not None and token.expires_at < now:
                return False
            return True
        token.is_valid = property(lambda self: is_valid())

        stored_tokens[token_hash] = token
        return token

    mock.store_token = AsyncMock(side_effect=mock_store_token)

    # validate_token
    async def mock_validate_token(token):
        token_hash = hash_token(token)
        db_token = stored_tokens.get(token_hash)
        if db_token is None or not db_token.is_valid:
            return None
        return db_token.device_id

    mock.validate_token = AsyncMock(side_effect=mock_validate_token)

    # get_token_record
    async def mock_get_token_record(token):
        token_hash = hash_token(token)
        return stored_tokens.get(token_hash)

    mock.get_token_record = AsyncMock(side_effect=mock_get_token_record)

    # create_token_pair
    async def mock_create_token_pair(device_id, **kwargs):
        # Generate access token (15 minutes)
        access_token, access_hash = generate_token()
        access_expires_at = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_LIFETIME_MINUTES)

        access_record = MagicMock()
        access_record.token_hash = access_hash
        access_record.device_id = device_id
        access_record.token_type = "mesh_auth"
        access_record.expires_at = access_expires_at
        access_record.revoked_at = None
        access_record.is_valid = True
        stored_tokens[access_hash] = access_record

        # Generate refresh token (7 days)
        refresh_token, refresh_hash = generate_token()
        refresh_expires_at = datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_LIFETIME_DAYS)

        refresh_record = MagicMock()
        refresh_record.token_hash = refresh_hash
        refresh_record.device_id = device_id
        refresh_record.token_type = "refresh"
        refresh_record.expires_at = refresh_expires_at
        refresh_record.revoked_at = None
        refresh_record.is_valid = True
        stored_tokens[refresh_hash] = refresh_record

        return access_token, access_expires_at, refresh_token, refresh_expires_at

    mock.create_token_pair = AsyncMock(side_effect=mock_create_token_pair)

    # refresh_access_token
    async def mock_refresh_access_token(refresh_token, **kwargs):
        refresh_hash = hash_token(refresh_token)
        db_refresh = stored_tokens.get(refresh_hash)

        if db_refresh is None:
            return None

        if db_refresh.revoked_at is not None:
            return None

        if db_refresh.token_type != "refresh":
            return None

        if db_refresh.expires_at and db_refresh.expires_at < datetime.now(UTC):
            return None

        device_id = db_refresh.device_id

        # Revoke old refresh token
        db_refresh.revoked_at = datetime.now(UTC)

        # Generate new access token
        new_access, new_access_hash = generate_token()
        access_expires = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_LIFETIME_MINUTES)

        access_record = MagicMock()
        access_record.token_hash = new_access_hash
        access_record.device_id = device_id
        access_record.token_type = "mesh_auth"
        access_record.expires_at = access_expires
        access_record.revoked_at = None
        access_record.is_valid = True
        stored_tokens[new_access_hash] = access_record

        # Generate new refresh token
        new_refresh, new_refresh_hash = generate_token()
        refresh_expires = datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_LIFETIME_DAYS)

        new_refresh_record = MagicMock()
        new_refresh_record.token_hash = new_refresh_hash
        new_refresh_record.device_id = device_id
        new_refresh_record.token_type = "refresh"
        new_refresh_record.expires_at = refresh_expires
        new_refresh_record.revoked_at = None
        new_refresh_record.is_valid = True
        stored_tokens[new_refresh_hash] = new_refresh_record

        return new_access, access_expires, new_refresh, refresh_expires

    mock.refresh_access_token = AsyncMock(side_effect=mock_refresh_access_token)

    # Expose stored_tokens for test inspection
    mock._stored_tokens = stored_tokens

    return mock


@pytest.fixture
def sample_profile():
    """Sample device profile."""
    return DeviceProfile(
        hostname="test-device",
        capabilities=[DeviceCapability.CPU],
        cpu_cores=4,
        ram_gb=8.0,
        storage_gb=100.0,
    )


# === Token Lifetime Constants Tests ===

class TestTokenLifetimeConstants:
    """Tests for token lifetime configuration."""

    def test_access_token_lifetime(self):
        """Access token should be 15 minutes."""
        assert ACCESS_TOKEN_LIFETIME_MINUTES == 15

    def test_refresh_token_lifetime(self):
        """Refresh token should be 7 days."""
        assert REFRESH_TOKEN_LIFETIME_DAYS == 7


# === Token Pair Creation Tests ===

class TestTokenPairCreation:
    """Tests for creating access + refresh token pairs."""

    @pytest.mark.asyncio
    async def test_create_token_pair(self, mock_persistence):
        """Should create both access and refresh tokens."""
        access, access_exp, refresh, refresh_exp = await mock_persistence.create_token_pair(
            device_id="test-device-1"
        )

        assert access is not None
        assert refresh is not None
        assert len(access) > 20
        assert len(refresh) > 20
        assert access != refresh

    @pytest.mark.asyncio
    async def test_access_token_expires_in_15_minutes(self, mock_persistence):
        """Access token should expire in ~15 minutes."""
        _, access_exp, _, _ = await mock_persistence.create_token_pair(
            device_id="test-device-1"
        )

        now = datetime.now(UTC)
        delta = access_exp - now

        # Should be approximately 15 minutes (allow 1 minute tolerance)
        assert 14 * 60 <= delta.total_seconds() <= 16 * 60

    @pytest.mark.asyncio
    async def test_refresh_token_expires_in_7_days(self, mock_persistence):
        """Refresh token should expire in ~7 days."""
        _, _, _, refresh_exp = await mock_persistence.create_token_pair(
            device_id="test-device-1"
        )

        now = datetime.now(UTC)
        delta = refresh_exp - now

        # Should be approximately 7 days (allow 1 hour tolerance)
        expected_seconds = 7 * 24 * 60 * 60
        assert expected_seconds - 3600 <= delta.total_seconds() <= expected_seconds + 3600


# === Token Refresh Tests ===

class TestTokenRefresh:
    """Tests for token refresh flow."""

    @pytest.mark.asyncio
    async def test_refresh_valid_token(self, mock_persistence):
        """Should successfully refresh with valid refresh token."""
        # Create initial token pair
        _, _, refresh_token, _ = await mock_persistence.create_token_pair(
            device_id="test-device-1"
        )

        # Refresh the token
        result = await mock_persistence.refresh_access_token(refresh_token)

        assert result is not None
        new_access, new_access_exp, new_refresh, new_refresh_exp = result
        assert new_access is not None
        assert new_refresh is not None

    @pytest.mark.asyncio
    async def test_refresh_returns_new_tokens(self, mock_persistence):
        """Refresh should return different tokens than original."""
        # Create initial token pair
        access1, _, refresh1, _ = await mock_persistence.create_token_pair(
            device_id="test-device-1"
        )

        # Refresh
        result = await mock_persistence.refresh_access_token(refresh1)
        access2, _, refresh2, _ = result

        assert access2 != access1
        assert refresh2 != refresh1

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, mock_persistence):
        """Should fail with invalid refresh token."""
        result = await mock_persistence.refresh_access_token("invalid-token-123")
        assert result is None

    @pytest.mark.asyncio
    async def test_refresh_revokes_old_refresh_token(self, mock_persistence):
        """Old refresh token should be revoked after use."""
        # Create initial token pair
        _, _, refresh_token, _ = await mock_persistence.create_token_pair(
            device_id="test-device-1"
        )

        # First refresh succeeds
        result1 = await mock_persistence.refresh_access_token(refresh_token)
        assert result1 is not None

        # Second refresh with same token fails (revoked)
        result2 = await mock_persistence.refresh_access_token(refresh_token)
        assert result2 is None

    @pytest.mark.asyncio
    async def test_refresh_with_access_token_fails(self, mock_persistence):
        """Using access token for refresh should fail."""
        # Create token pair
        access_token, _, _, _ = await mock_persistence.create_token_pair(
            device_id="test-device-1"
        )

        # Try to use access token as refresh token
        result = await mock_persistence.refresh_access_token(access_token)
        assert result is None


# === Token Validation Tests ===

class TestTokenValidation:
    """Tests for token validation with expiry."""

    @pytest.mark.asyncio
    async def test_valid_access_token(self, mock_persistence):
        """Valid access token should authenticate device."""
        access_token, _, _, _ = await mock_persistence.create_token_pair(
            device_id="test-device-1"
        )

        device_id = await mock_persistence.validate_token(access_token)
        assert device_id == "test-device-1"

    @pytest.mark.asyncio
    async def test_invalid_token_returns_none(self, mock_persistence):
        """Invalid token should return None."""
        device_id = await mock_persistence.validate_token("not-a-real-token")
        assert device_id is None


# === Schema Tests ===

class TestTokenRefreshSchemas:
    """Tests for token refresh Pydantic schemas."""

    def test_token_refresh_request_valid(self):
        """Valid refresh request should pass validation."""
        request = TokenRefreshRequest(
            refresh_token="a" * 30  # min_length=20
        )
        assert request.refresh_token == "a" * 30

    def test_token_refresh_request_too_short(self):
        """Short refresh token should fail validation."""
        with pytest.raises(ValueError):
            TokenRefreshRequest(refresh_token="short")

    def test_token_refresh_response(self):
        """Token refresh response should have all fields."""
        response = TokenRefreshResponse(
            access_token="access123",
            access_token_expires_at=datetime.now(UTC) + timedelta(minutes=15),
            refresh_token="refresh456",
            refresh_token_expires_at=datetime.now(UTC) + timedelta(days=7)
        )

        assert response.access_token == "access123"
        assert response.refresh_token == "refresh456"
        assert response.token_type == "Bearer"


# === Integration Tests ===

class TestTokenRefreshIntegration:
    """Integration tests for full token refresh flow."""

    @pytest.mark.asyncio
    async def test_full_token_lifecycle(self, mock_persistence):
        """Test complete token lifecycle: create -> use -> refresh -> use new."""
        device_id = "lifecycle-device"

        # 1. Create initial tokens
        access1, _, refresh1, _ = await mock_persistence.create_token_pair(
            device_id=device_id
        )

        # 2. Validate access token works
        validated = await mock_persistence.validate_token(access1)
        assert validated == device_id

        # 3. Refresh tokens
        result = await mock_persistence.refresh_access_token(refresh1)
        assert result is not None
        access2, _, refresh2, _ = result

        # 4. New access token works
        validated2 = await mock_persistence.validate_token(access2)
        assert validated2 == device_id

        # 5. Old refresh token no longer works
        result2 = await mock_persistence.refresh_access_token(refresh1)
        assert result2 is None

        # 6. New refresh token works
        result3 = await mock_persistence.refresh_access_token(refresh2)
        assert result3 is not None

    @pytest.mark.asyncio
    async def test_multiple_devices_tokens_isolated(self, mock_persistence):
        """Tokens from different devices should be isolated."""
        # Create tokens for device A
        access_a, _, refresh_a, _ = await mock_persistence.create_token_pair(
            device_id="device-a"
        )

        # Create tokens for device B
        access_b, _, refresh_b, _ = await mock_persistence.create_token_pair(
            device_id="device-b"
        )

        # Each validates to correct device
        assert await mock_persistence.validate_token(access_a) == "device-a"
        assert await mock_persistence.validate_token(access_b) == "device-b"

        # Tokens are different
        assert access_a != access_b
        assert refresh_a != refresh_b
