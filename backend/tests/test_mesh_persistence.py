"""
Tests for Mesh Persistence Service
PHASE0-SEC-001 (lg03): Token Persistence in SQLite

Tests:
- Token storage and validation
- Token expiry and revocation
- Device persistence
- Cache initialization from DB
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from backend.server.services.mesh_persistence import (
    MeshPersistenceService,
    hash_token,
    generate_token,
)
from backend.server.schemas.device_mesh import (
    DeviceProfile,
    DeviceRole,
    DeviceStatus,
    DeviceCapability,
)


class TestTokenHashing:
    """Test token hashing functions"""

    def test_hash_token_deterministic(self):
        """Same token should produce same hash"""
        token = "test_token_123"
        hash1 = hash_token(token)
        hash2 = hash_token(token)
        assert hash1 == hash2

    def test_hash_token_different_inputs(self):
        """Different tokens should produce different hashes"""
        hash1 = hash_token("token_a")
        hash2 = hash_token("token_b")
        assert hash1 != hash2

    def test_hash_token_length(self):
        """Hash should be 64 characters (SHA-256 hex)"""
        token_hash = hash_token("any_token")
        assert len(token_hash) == 64

    def test_generate_token_returns_tuple(self):
        """generate_token should return (plaintext, hash) tuple"""
        token, token_hash = generate_token()
        assert isinstance(token, str)
        assert isinstance(token_hash, str)
        assert len(token) > 20  # URL-safe base64 is ~43 chars for 32 bytes
        assert len(token_hash) == 64  # SHA-256 hex

    def test_generate_token_hash_matches(self):
        """Generated hash should match hashing the token"""
        token, token_hash = generate_token()
        assert hash_token(token) == token_hash

    def test_generate_token_unique(self):
        """Each call should generate unique tokens"""
        tokens = set()
        for _ in range(100):
            token, _ = generate_token()
            tokens.add(token)
        assert len(tokens) == 100


class TestMeshPersistenceServiceTokens:
    """Test token operations in MeshPersistenceService"""

    @pytest.fixture
    def persistence(self):
        """Create a fresh persistence service instance"""
        return MeshPersistenceService()

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session"""
        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)
        return session

    @pytest.mark.asyncio
    async def test_store_token_creates_record(self, persistence, mock_session):
        """store_token should create a MeshToken record"""
        with patch('backend.server.services.mesh_persistence.AsyncSessionLocal', return_value=mock_session):
            result = await persistence.store_token(
                device_id="test-device-001",
                token_hash="abc123" * 10 + "abcd",  # 64 chars
                token_type="mesh_auth",
                expires_in_hours=24
            )

            # Verify session.add was called
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_token_returns_device_id(self, persistence, mock_session):
        """validate_token should return device_id for valid token"""
        from backend.server.models.mesh import MeshToken

        # Create a mock token record
        mock_token = MagicMock(spec=MeshToken)
        mock_token.device_id = "test-device-001"
        mock_token.is_valid = True
        mock_token.last_used_at = None
        mock_token.use_count = 0

        # Mock the query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_token
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch('backend.server.services.mesh_persistence.AsyncSessionLocal', return_value=mock_session):
            device_id = await persistence.validate_token("test_token")

            assert device_id == "test-device-001"
            assert mock_token.use_count == 1

    @pytest.mark.asyncio
    async def test_validate_token_returns_none_for_invalid(self, persistence, mock_session):
        """validate_token should return None for invalid/revoked token"""
        from backend.server.models.mesh import MeshToken

        mock_token = MagicMock(spec=MeshToken)
        mock_token.is_valid = False  # Token is invalid
        mock_token.device_id = "test-device-001"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_token
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch('backend.server.services.mesh_persistence.AsyncSessionLocal', return_value=mock_session):
            device_id = await persistence.validate_token("expired_token")

            assert device_id is None

    @pytest.mark.asyncio
    async def test_validate_token_returns_none_for_missing(self, persistence, mock_session):
        """validate_token should return None for non-existent token"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch('backend.server.services.mesh_persistence.AsyncSessionLocal', return_value=mock_session):
            device_id = await persistence.validate_token("nonexistent_token")

            assert device_id is None


class TestMeshPersistenceServiceDevices:
    """Test device operations in MeshPersistenceService"""

    @pytest.fixture
    def persistence(self):
        return MeshPersistenceService()

    @pytest.fixture
    def sample_profile(self):
        return DeviceProfile(
            hostname="test-desktop",
            cpu_cores=8,
            ram_gb=16.0,
            storage_gb=500.0,
            capabilities=[DeviceCapability.CPU, DeviceCapability.GPU],
            max_concurrent_tasks=4
        )

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)
        return session

    @pytest.mark.asyncio
    async def test_store_device_creates_record(self, persistence, sample_profile, mock_session):
        """store_device should create a MeshDevice record"""
        with patch('backend.server.services.mesh_persistence.AsyncSessionLocal', return_value=mock_session):
            result = await persistence.store_device(
                device_id="mesh-wor-abc123",
                device_name="Test Desktop",
                profile=sample_profile,
                role=DeviceRole.WORKER,
                zone="default"
            )

            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_device_heartbeat(self, persistence, mock_session):
        """update_device_heartbeat should update device state"""
        from backend.server.models.mesh import MeshDevice

        mock_device = MagicMock(spec=MeshDevice)
        mock_device.device_id = "test-device"
        mock_device.consecutive_successes = 5
        mock_device.consecutive_misses = 0
        mock_device.avg_latency_ms = 50.0

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_device
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch('backend.server.services.mesh_persistence.AsyncSessionLocal', return_value=mock_session):
            acknowledged = await persistence.update_device_heartbeat(
                device_id="test-device",
                status=DeviceStatus.ONLINE,
                current_load=0.5,
                active_tasks=["task-1", "task-2"],
                pending_sync_count=0,
                latency_ms=45.0
            )

            assert acknowledged is True
            mock_session.commit.assert_called_once()


class TestMeshTokenModel:
    """Test MeshToken model properties"""

    def test_is_valid_true_for_fresh_token(self):
        """Fresh token should be valid"""
        from backend.server.models.mesh import MeshToken

        token = MeshToken(
            token_hash="abc" * 21 + "a",
            device_id="test-device",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            revoked_at=None
        )

        assert token.is_valid is True

    def test_is_valid_false_for_expired_token(self):
        """Expired token should be invalid"""
        from backend.server.models.mesh import MeshToken

        token = MeshToken(
            token_hash="abc" * 21 + "a",
            device_id="test-device",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),  # Expired
            revoked_at=None
        )

        assert token.is_valid is False

    def test_is_valid_false_for_revoked_token(self):
        """Revoked token should be invalid"""
        from backend.server.models.mesh import MeshToken

        token = MeshToken(
            token_hash="abc" * 21 + "a",
            device_id="test-device",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            revoked_at=datetime.now(timezone.utc)  # Revoked
        )

        assert token.is_valid is False


class TestMeshDeviceModel:
    """Test MeshDevice model properties"""

    def test_is_healthy_true_for_good_device(self):
        """Device with few misses should be healthy"""
        from backend.server.models.mesh import MeshDevice

        device = MeshDevice(
            device_id="test-device",
            device_name="Test",
            role="worker",
            status="online",
            zone="default",
            profile_json={},
            consecutive_misses=0
        )

        assert device.is_healthy is True

    def test_is_healthy_false_for_many_misses(self):
        """Device with many misses should be unhealthy"""
        from backend.server.models.mesh import MeshDevice

        device = MeshDevice(
            device_id="test-device",
            device_name="Test",
            role="worker",
            status="online",
            zone="default",
            profile_json={},
            consecutive_misses=5  # More than 3
        )

        assert device.is_healthy is False

    def test_is_healthy_false_for_offline(self):
        """Offline device should be unhealthy"""
        from backend.server.models.mesh import MeshDevice

        device = MeshDevice(
            device_id="test-device",
            device_name="Test",
            role="worker",
            status="offline",
            zone="default",
            profile_json={},
            consecutive_misses=0
        )

        assert device.is_healthy is False
