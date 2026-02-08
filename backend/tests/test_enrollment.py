"""
Tests for Enrollment Code API (PHASE0-SEC-002)

Tests cover:
- Create enrollment codes (primary only)
- List enrollment codes (primary only)
- Revoke enrollment codes (primary only)
- Enroll device using code
- Code expiration and validation
"""
import pytest
from datetime import datetime, UTC, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import os

# Set test environment variables before imports
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-enrollment-testing-only')
os.environ.setdefault('TESTING', 'true')

from backend.server.schemas.device_mesh import (
    DeviceProfile,
    DeviceRole,
    DeviceStatus,
    DeviceCapability,
    EnrollmentCodeCreateRequest,
    EnrollmentCodeResponse,
    EnrollmentCodeStatus,
    EnrollmentRequest,
    EnrollmentResponse,
)
from backend.server.services.mesh_persistence import (
    MeshPersistenceService,
    hash_token,
    generate_token,
)


# === Fixtures ===

@pytest.fixture
def mock_persistence():
    """Create a mock persistence service for unit tests."""
    mock = MagicMock()

    # Track stored data
    stored_devices = {}
    stored_tokens = {}
    stored_enrollment_codes = {}
    code_counter = [0]

    # store_device
    async def mock_store_device(device_id, device_name, profile, role, zone, **kwargs):
        mock_device = MagicMock()
        mock_device.device_id = device_id
        mock_device.device_name = device_name
        mock_device.profile_json = profile.model_dump()
        mock_device.role = role.value
        mock_device.zone = zone
        mock_device.status = DeviceStatus.ONLINE.value
        mock_device.joined_at = datetime.now(UTC)
        mock_device.last_heartbeat = datetime.now(UTC)
        mock_device.current_load = 0.0
        mock_device.active_tasks_json = []
        mock_device.pending_sync_count = 0
        mock_device.consecutive_misses = 0
        mock_device.consecutive_successes = 0
        mock_device.left_at = None
        mock_device.avg_latency_ms = 0.0
        mock_device.last_heartbeat_latency_ms = 0.0
        stored_devices[device_id] = mock_device
        return mock_device

    mock.store_device = AsyncMock(side_effect=mock_store_device)

    # store_token
    async def mock_store_token(device_id, token_hash, **kwargs):
        stored_tokens[token_hash] = device_id
        return MagicMock()

    mock.store_token = AsyncMock(side_effect=mock_store_token)

    # validate_token
    async def mock_validate_token(token):
        token_hash = hash_token(token)
        return stored_tokens.get(token_hash)

    mock.validate_token = AsyncMock(side_effect=mock_validate_token)

    # list_devices
    mock.list_devices = AsyncMock(return_value=[])

    # update_device_heartbeat
    mock.update_device_heartbeat = AsyncMock(return_value=True)

    # remove_device
    mock.remove_device = AsyncMock(return_value=True)

    # revoke_device_tokens
    mock.revoke_device_tokens = AsyncMock(return_value=0)

    # get_device
    async def mock_get_device(device_id):
        return stored_devices.get(device_id)

    mock.get_device = AsyncMock(side_effect=mock_get_device)

    # update_device
    mock.update_device = AsyncMock(return_value=MagicMock())

    # mark_device_missed_heartbeat
    mock.mark_device_missed_heartbeat = AsyncMock(return_value=1)

    # get_device_state
    mock.get_device_state = AsyncMock(return_value=None)

    # create_enrollment_code
    async def mock_create_enrollment(created_by_device_id, intended_device_name=None, intended_role=DeviceRole.WORKER, expires_in_hours=24.0):
        code_counter[0] += 1
        code_id = f"code-{code_counter[0]}"
        plaintext_code, code_hash = generate_token()

        enrollment = MagicMock()
        enrollment.id = code_id
        enrollment.code_hash = code_hash
        enrollment.intended_device_name = intended_device_name
        enrollment.intended_role = intended_role.value
        enrollment.created_at = datetime.now(UTC)
        enrollment.expires_at = datetime.now(UTC) + timedelta(hours=expires_in_hours)
        enrollment.used_at = None
        enrollment.used_by_device_id = None
        enrollment.created_by_device_id = created_by_device_id
        enrollment.is_valid = True

        stored_enrollment_codes[code_hash] = enrollment
        return plaintext_code, enrollment

    mock.create_enrollment_code = AsyncMock(side_effect=mock_create_enrollment)

    # validate_enrollment_code
    async def mock_validate_enrollment(code):
        code_hash = hash_token(code)
        enrollment = stored_enrollment_codes.get(code_hash)
        if enrollment and enrollment.is_valid and enrollment.used_at is None:
            return enrollment
        return None

    mock.validate_enrollment_code = AsyncMock(side_effect=mock_validate_enrollment)

    # use_enrollment_code
    async def mock_use_enrollment(code, used_by_device_id):
        code_hash = hash_token(code)
        enrollment = stored_enrollment_codes.get(code_hash)
        if enrollment and enrollment.used_at is None:
            enrollment.used_at = datetime.now(UTC)
            enrollment.used_by_device_id = used_by_device_id
            return True
        return False

    mock.use_enrollment_code = AsyncMock(side_effect=mock_use_enrollment)

    # list_enrollment_codes
    async def mock_list_codes(include_used=False, include_expired=False):
        codes = []
        now = datetime.now(UTC)
        for enrollment in stored_enrollment_codes.values():
            is_used = enrollment.used_at is not None
            is_expired = enrollment.expires_at < now
            if (not is_used or include_used) and (not is_expired or include_expired):
                codes.append(enrollment)
        return codes

    mock.list_enrollment_codes = AsyncMock(side_effect=mock_list_codes)

    # revoke_enrollment_code
    async def mock_revoke_code(code_id):
        for enrollment in stored_enrollment_codes.values():
            if str(enrollment.id) == code_id:
                enrollment.used_at = datetime.now(UTC)
                enrollment.used_by_device_id = "REVOKED"
                return True
        return False

    mock.revoke_enrollment_code = AsyncMock(side_effect=mock_revoke_code)

    return mock


@pytest.fixture
def mesh_service(mock_persistence):
    """Create a MeshService with mocked persistence."""
    with patch('backend.server.services.mesh_service.get_mesh_persistence') as mock_get_persistence:
        mock_get_persistence.return_value = mock_persistence
        from backend.server.services.mesh_service import MeshService
        service = MeshService()
        yield service


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


# === Enrollment Code Creation Tests ===

class TestEnrollmentCodeCreation:
    """Tests for enrollment code creation."""

    @pytest.mark.asyncio
    async def test_create_enrollment_code(self, mock_persistence):
        """Should create a new enrollment code."""
        plaintext_code, enrollment = await mock_persistence.create_enrollment_code(
            created_by_device_id="primary-device",
            intended_device_name="New Worker",
            intended_role=DeviceRole.WORKER,
            expires_in_hours=0.1  # 6 minutes
        )

        assert plaintext_code is not None
        assert len(plaintext_code) > 20
        assert enrollment.intended_device_name == "New Worker"
        assert enrollment.intended_role == DeviceRole.WORKER.value

    @pytest.mark.asyncio
    async def test_enrollment_code_expires(self, mock_persistence):
        """Enrollment code should have expiration time."""
        _, enrollment = await mock_persistence.create_enrollment_code(
            created_by_device_id="primary-device",
            intended_role=DeviceRole.WORKER,
            expires_in_hours=1.0
        )

        assert enrollment.expires_at > datetime.now(UTC)
        assert enrollment.expires_at < datetime.now(UTC) + timedelta(hours=2)


class TestEnrollmentCodeValidation:
    """Tests for enrollment code validation."""

    @pytest.mark.asyncio
    async def test_validate_valid_code(self, mock_persistence):
        """Valid code should pass validation."""
        plaintext_code, _ = await mock_persistence.create_enrollment_code(
            created_by_device_id="primary",
            intended_role=DeviceRole.WORKER,
            expires_in_hours=1.0
        )

        enrollment = await mock_persistence.validate_enrollment_code(plaintext_code)
        assert enrollment is not None
        assert enrollment.intended_role == DeviceRole.WORKER.value

    @pytest.mark.asyncio
    async def test_validate_invalid_code(self, mock_persistence):
        """Invalid code should fail validation."""
        enrollment = await mock_persistence.validate_enrollment_code("invalid-code-123")
        assert enrollment is None

    @pytest.mark.asyncio
    async def test_validate_used_code(self, mock_persistence):
        """Used code should fail validation."""
        plaintext_code, _ = await mock_persistence.create_enrollment_code(
            created_by_device_id="primary",
            intended_role=DeviceRole.WORKER,
            expires_in_hours=1.0
        )

        # Use the code
        await mock_persistence.use_enrollment_code(plaintext_code, "new-device")

        # Try to validate again
        enrollment = await mock_persistence.validate_enrollment_code(plaintext_code)
        assert enrollment is None


class TestEnrollmentCodeUsage:
    """Tests for using enrollment codes."""

    @pytest.mark.asyncio
    async def test_use_enrollment_code(self, mock_persistence):
        """Should mark code as used."""
        plaintext_code, _ = await mock_persistence.create_enrollment_code(
            created_by_device_id="primary",
            intended_role=DeviceRole.WORKER,
            expires_in_hours=1.0
        )

        success = await mock_persistence.use_enrollment_code(plaintext_code, "new-device")
        assert success is True

    @pytest.mark.asyncio
    async def test_cannot_reuse_code(self, mock_persistence):
        """Code should not be usable twice."""
        plaintext_code, _ = await mock_persistence.create_enrollment_code(
            created_by_device_id="primary",
            intended_role=DeviceRole.WORKER,
            expires_in_hours=1.0
        )

        # First use succeeds
        success1 = await mock_persistence.use_enrollment_code(plaintext_code, "device-1")
        assert success1 is True

        # Second use fails
        success2 = await mock_persistence.use_enrollment_code(plaintext_code, "device-2")
        assert success2 is False


class TestEnrollmentCodeListing:
    """Tests for listing enrollment codes."""

    @pytest.mark.asyncio
    async def test_list_active_codes(self, mock_persistence):
        """Should list only active codes by default."""
        # Create two codes
        await mock_persistence.create_enrollment_code(
            created_by_device_id="primary",
            intended_device_name="Device 1",
            intended_role=DeviceRole.WORKER,
            expires_in_hours=1.0
        )
        code2, _ = await mock_persistence.create_enrollment_code(
            created_by_device_id="primary",
            intended_device_name="Device 2",
            intended_role=DeviceRole.WORKER,
            expires_in_hours=1.0
        )

        # Use second code
        await mock_persistence.use_enrollment_code(code2, "some-device")

        # List should only show first code
        codes = await mock_persistence.list_enrollment_codes()
        assert len(codes) == 1
        assert codes[0].intended_device_name == "Device 1"

    @pytest.mark.asyncio
    async def test_list_including_used(self, mock_persistence):
        """Should include used codes when requested."""
        await mock_persistence.create_enrollment_code(
            created_by_device_id="primary",
            intended_role=DeviceRole.WORKER,
            expires_in_hours=1.0
        )
        code2, _ = await mock_persistence.create_enrollment_code(
            created_by_device_id="primary",
            intended_role=DeviceRole.WORKER,
            expires_in_hours=1.0
        )

        await mock_persistence.use_enrollment_code(code2, "some-device")

        codes = await mock_persistence.list_enrollment_codes(include_used=True)
        assert len(codes) == 2


class TestEnrollmentCodeRevocation:
    """Tests for revoking enrollment codes."""

    @pytest.mark.asyncio
    async def test_revoke_code(self, mock_persistence):
        """Should revoke a code by ID."""
        _, enrollment = await mock_persistence.create_enrollment_code(
            created_by_device_id="primary",
            intended_role=DeviceRole.WORKER,
            expires_in_hours=1.0
        )

        success = await mock_persistence.revoke_enrollment_code(str(enrollment.id))
        assert success is True

    @pytest.mark.asyncio
    async def test_revoke_nonexistent_code(self, mock_persistence):
        """Should return False for nonexistent code."""
        success = await mock_persistence.revoke_enrollment_code("nonexistent-id")
        assert success is False


class TestEnrollmentFlow:
    """Integration tests for the full enrollment flow."""

    @pytest.mark.asyncio
    async def test_full_enrollment_flow(self, mesh_service, mock_persistence, sample_profile):
        """Test complete enrollment: create code -> join -> verify."""
        # 1. Primary joins first (to have a primary)
        primary_id, _, role, _ = await mesh_service.join_mesh(
            device_name="Primary Device",
            profile=sample_profile,
            preferred_role=DeviceRole.PRIMARY
        )
        assert role == DeviceRole.PRIMARY

        # 2. Create enrollment code
        plaintext_code, enrollment = await mock_persistence.create_enrollment_code(
            created_by_device_id=primary_id,
            intended_device_name="Worker Device",
            intended_role=DeviceRole.WORKER,
            expires_in_hours=0.1
        )
        assert plaintext_code is not None

        # 3. Validate the code
        validated = await mock_persistence.validate_enrollment_code(plaintext_code)
        assert validated is not None

        # 4. Join using the code
        worker_id, token, worker_role, zone = await mesh_service.join_mesh(
            device_name="Worker Device",
            profile=sample_profile,
            preferred_role=DeviceRole(validated.intended_role)
        )

        # 5. Mark code as used
        used = await mock_persistence.use_enrollment_code(plaintext_code, worker_id)
        assert used is True

        # 6. Verify worker joined
        assert worker_id is not None
        assert token is not None
        assert worker_role == DeviceRole.WORKER

        # 7. Code should no longer be valid
        revalidated = await mock_persistence.validate_enrollment_code(plaintext_code)
        assert revalidated is None
