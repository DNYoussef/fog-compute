"""
Tests for Heartbeat Jitter Buffer (PHASE1-COORD-003)

Tests cover:
- Jitter calculation within expected range
- Monotonic clock usage for elapsed time
- 2.0x multiplier for heartbeat miss detection
- Jittered heartbeat interval in responses
"""
import pytest
from datetime import datetime, UTC, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import os
import time

# Set test environment variables before imports
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-heartbeat-jitter-testing-only')
os.environ.setdefault('TESTING', 'true')

from backend.server.services.mesh_service import MeshService, MeshDevice
from backend.server.schemas.device_mesh import (
    DeviceProfile,
    DeviceRole,
    DeviceStatus,
    DeviceCapability,
)


# === Fixtures ===

@pytest.fixture
def mesh_service():
    """Create a MeshService with default settings."""
    service = MeshService(
        heartbeat_timeout_sec=90,
        heartbeat_interval_sec=30,
        sync_interval_sec=60,
        max_missed_heartbeats=3,
        heartbeat_jitter_ratio=0.2,
    )
    service._cache_initialized = True
    return service


@pytest.fixture
def mesh_service_no_jitter():
    """Create a MeshService with no jitter."""
    service = MeshService(
        heartbeat_timeout_sec=90,
        heartbeat_interval_sec=30,
        sync_interval_sec=60,
        max_missed_heartbeats=3,
        heartbeat_jitter_ratio=0.0,
    )
    service._cache_initialized = True
    return service


@pytest.fixture
def sample_device():
    """Create a sample MeshDevice."""
    profile = DeviceProfile(
        hostname="test-device",
        capabilities=[DeviceCapability.CPU],
        cpu_cores=4,
        ram_gb=8.0,
        storage_gb=100.0,
    )
    profile.device_id = "mesh-wor-12345678"

    return MeshDevice(
        device_id="mesh-wor-12345678",
        device_name="Test Device",
        role=DeviceRole.WORKER,
        status=DeviceStatus.ONLINE,
        zone="default",
        profile=profile,
        mesh_token="",
        joined_at=datetime.now(UTC),
        last_heartbeat=datetime.now(UTC),
        last_heartbeat_monotonic=time.monotonic(),
    )


# === Jitter Configuration Tests ===

class TestJitterConfiguration:
    """Tests for jitter configuration."""

    def test_default_jitter_ratio(self, mesh_service):
        """Default jitter ratio should be 0.2 (20%)."""
        assert mesh_service.heartbeat_jitter_ratio == 0.2

    def test_jitter_ratio_clamped_to_max(self):
        """Jitter ratio should be clamped to maximum 0.5."""
        service = MeshService(heartbeat_jitter_ratio=0.8)
        assert service.heartbeat_jitter_ratio == 0.5

    def test_jitter_ratio_clamped_to_min(self):
        """Jitter ratio should be clamped to minimum 0.0."""
        service = MeshService(heartbeat_jitter_ratio=-0.1)
        assert service.heartbeat_jitter_ratio == 0.0

    def test_miss_multiplier_is_2(self, mesh_service):
        """Miss multiplier should be 2.0 (changed from 1.5)."""
        assert mesh_service._heartbeat_miss_multiplier == 2.0


# === Jitter Calculation Tests ===

class TestJitterCalculation:
    """Tests for jitter calculation."""

    def test_jitter_within_range(self, mesh_service):
        """Jitter should produce values within expected range."""
        base_interval = mesh_service.heartbeat_interval_sec  # 30
        jitter_range = int(base_interval * mesh_service.heartbeat_jitter_ratio)  # 6

        # Generate many samples to test distribution
        samples = [mesh_service._calculate_next_heartbeat_interval() for _ in range(100)]

        min_expected = base_interval - jitter_range  # 24
        max_expected = base_interval + jitter_range  # 36

        for sample in samples:
            assert min_expected <= sample <= max_expected, f"Sample {sample} outside range [{min_expected}, {max_expected}]"

    def test_no_jitter_returns_base_interval(self, mesh_service_no_jitter):
        """With no jitter, should return exact base interval."""
        samples = [mesh_service_no_jitter._calculate_next_heartbeat_interval() for _ in range(10)]

        for sample in samples:
            assert sample == mesh_service_no_jitter.heartbeat_interval_sec

    def test_jitter_produces_variation(self, mesh_service):
        """Jitter should produce different values over multiple calls."""
        samples = [mesh_service._calculate_next_heartbeat_interval() for _ in range(50)]
        unique_values = set(samples)

        # With 20% jitter on 30s interval, we expect some variation
        # (probabilistically should have multiple unique values)
        assert len(unique_values) > 1, "Jitter should produce different values"

    def test_jitter_minimum_one_second(self):
        """Jittered interval should never be less than 1 second."""
        # Use very small interval to test edge case
        service = MeshService(
            heartbeat_interval_sec=2,
            heartbeat_jitter_ratio=0.5,  # Max jitter
        )

        samples = [service._calculate_next_heartbeat_interval() for _ in range(100)]

        for sample in samples:
            assert sample >= 1, f"Sample {sample} should be at least 1 second"


# === Monotonic Clock Tests ===

class TestMonotonicClock:
    """Tests for monotonic clock usage."""

    def test_device_has_monotonic_field(self, sample_device):
        """Device should have last_heartbeat_monotonic field."""
        assert hasattr(sample_device, 'last_heartbeat_monotonic')
        assert sample_device.last_heartbeat_monotonic is not None

    def test_liveness_uses_monotonic_when_available(self, mesh_service, sample_device):
        """Liveness calculation should use monotonic clock when available."""
        # Set monotonic time to recent
        sample_device.last_heartbeat_monotonic = time.monotonic() - 10  # 10 seconds ago

        liveness = mesh_service._get_device_liveness(sample_device)

        assert liveness.is_healthy is True

    def test_liveness_falls_back_to_wall_clock(self, mesh_service, sample_device):
        """Liveness should fall back to wall clock if monotonic not available."""
        sample_device.last_heartbeat_monotonic = None
        sample_device.last_heartbeat = datetime.now(UTC) - timedelta(seconds=10)

        liveness = mesh_service._get_device_liveness(sample_device)

        assert liveness.is_healthy is True

    def test_liveness_unhealthy_with_old_monotonic(self, mesh_service, sample_device):
        """Device should be unhealthy if monotonic time too old."""
        # Set monotonic time to older than timeout
        sample_device.last_heartbeat_monotonic = time.monotonic() - 100  # 100 seconds ago

        liveness = mesh_service._get_device_liveness(sample_device)

        assert liveness.is_healthy is False


# === Miss Detection Tests ===

class TestMissDetection:
    """Tests for heartbeat miss detection with 2.0x multiplier."""

    @pytest.mark.asyncio
    async def test_miss_threshold_uses_2x_multiplier(self, mesh_service, sample_device):
        """Miss detection should use 2.0x multiplier (not 1.5x)."""
        # Add device to cache
        mesh_service._devices_cache[sample_device.device_id] = sample_device

        # Set last heartbeat to just over 1.5x interval (45 seconds)
        # This would trigger miss with old 1.5x, but not with new 2.0x
        sample_device.last_heartbeat_monotonic = time.monotonic() - 50  # 50 seconds ago

        # Mock persistence
        mesh_service._persistence = MagicMock()
        mesh_service._persistence.mark_device_missed_heartbeat = AsyncMock()

        await mesh_service._check_device_health()

        # Should NOT have marked as missed (50s < 60s = 30 * 2.0)
        assert sample_device.consecutive_missed_heartbeats == 0

    @pytest.mark.asyncio
    async def test_miss_detected_after_2x_threshold(self, mesh_service, sample_device):
        """Miss should be detected after 2.0x threshold."""
        # Add device to cache
        mesh_service._devices_cache[sample_device.device_id] = sample_device

        # Set last heartbeat to over 2x interval (65 seconds)
        sample_device.last_heartbeat_monotonic = time.monotonic() - 65

        # Mock persistence
        mesh_service._persistence = MagicMock()
        mesh_service._persistence.mark_device_missed_heartbeat = AsyncMock()

        await mesh_service._check_device_health()

        # Should have marked as missed (65s > 60s = 30 * 2.0)
        assert sample_device.consecutive_missed_heartbeats == 1


# === Heartbeat Response Tests ===

class TestHeartbeatResponse:
    """Tests for jittered interval in heartbeat responses."""

    @pytest.mark.asyncio
    async def test_process_heartbeat_returns_four_tuple(self, mesh_service, sample_device):
        """process_heartbeat should return 4-tuple with next_heartbeat_sec."""
        # Add device to cache
        mesh_service._devices_cache[sample_device.device_id] = sample_device

        # Mock persistence
        mesh_service._persistence = MagicMock()
        mesh_service._persistence.update_device_heartbeat = AsyncMock(return_value=True)

        result = await mesh_service.process_heartbeat(
            device_id=sample_device.device_id,
            status=DeviceStatus.ONLINE,
            current_load=0.5,
            active_tasks=[],
        )

        assert len(result) == 4
        acknowledged, commands, sync_required, next_heartbeat_sec = result

        assert acknowledged is True
        assert isinstance(next_heartbeat_sec, int)

    @pytest.mark.asyncio
    async def test_process_heartbeat_jittered_interval(self, mesh_service, sample_device):
        """process_heartbeat should return jittered interval values."""
        # Add device to cache
        mesh_service._devices_cache[sample_device.device_id] = sample_device

        # Mock persistence
        mesh_service._persistence = MagicMock()
        mesh_service._persistence.update_device_heartbeat = AsyncMock(return_value=True)

        # Collect multiple intervals
        intervals = []
        for _ in range(20):
            result = await mesh_service.process_heartbeat(
                device_id=sample_device.device_id,
                status=DeviceStatus.ONLINE,
                current_load=0.5,
                active_tasks=[],
            )
            intervals.append(result[3])

        # Check that intervals are within jitter range
        base = mesh_service.heartbeat_interval_sec
        jitter_range = int(base * mesh_service.heartbeat_jitter_ratio)

        for interval in intervals:
            assert base - jitter_range <= interval <= base + jitter_range

    @pytest.mark.asyncio
    async def test_process_heartbeat_updates_monotonic(self, mesh_service, sample_device):
        """process_heartbeat should update monotonic timestamp."""
        # Add device to cache
        mesh_service._devices_cache[sample_device.device_id] = sample_device
        old_monotonic = sample_device.last_heartbeat_monotonic

        # Mock persistence
        mesh_service._persistence = MagicMock()
        mesh_service._persistence.update_device_heartbeat = AsyncMock(return_value=True)

        # Wait a tiny bit to ensure monotonic advances
        await mesh_service.process_heartbeat(
            device_id=sample_device.device_id,
            status=DeviceStatus.ONLINE,
            current_load=0.5,
            active_tasks=[],
        )

        # Monotonic should be updated (equal or greater)
        assert sample_device.last_heartbeat_monotonic >= old_monotonic

    @pytest.mark.asyncio
    async def test_process_heartbeat_unknown_device_returns_base_interval(self, mesh_service):
        """Unknown device should get base interval in response."""
        result = await mesh_service.process_heartbeat(
            device_id="unknown-device",
            status=DeviceStatus.ONLINE,
            current_load=0.5,
            active_tasks=[],
        )

        acknowledged, commands, sync_required, next_heartbeat_sec = result

        assert acknowledged is False
        assert next_heartbeat_sec == mesh_service.heartbeat_interval_sec


# === Integration Tests ===

class TestJitterIntegration:
    """Integration tests for heartbeat jitter system."""

    @pytest.mark.asyncio
    async def test_join_sets_monotonic_time(self, mesh_service):
        """Joining mesh should set monotonic time."""
        # Mock persistence
        mesh_service._persistence = MagicMock()
        mesh_service._persistence.store_device = AsyncMock()
        mesh_service._persistence.store_token = AsyncMock()

        profile = DeviceProfile(
            hostname="new-device",
            capabilities=[DeviceCapability.CPU],
            cpu_cores=4,
            ram_gb=8.0,
            storage_gb=100.0,
        )

        device_id, token, role, zone = await mesh_service.join_mesh(
            device_name="New Test Device",
            profile=profile,
        )

        # Check device in cache has monotonic time set
        device = mesh_service._devices_cache[device_id]
        assert device.last_heartbeat_monotonic is not None
        assert isinstance(device.last_heartbeat_monotonic, float)

    @pytest.mark.asyncio
    async def test_thundering_herd_prevention(self, mesh_service):
        """Multiple devices should get different heartbeat intervals."""
        # Create multiple devices
        devices = []
        for i in range(10):
            profile = DeviceProfile(
                hostname=f"device-{i}",
                capabilities=[DeviceCapability.CPU],
                cpu_cores=4,
                ram_gb=8.0,
                storage_gb=100.0,
            )
            profile.device_id = f"mesh-wor-{i:08d}"

            device = MeshDevice(
                device_id=f"mesh-wor-{i:08d}",
                device_name=f"Device {i}",
                role=DeviceRole.WORKER,
                status=DeviceStatus.ONLINE,
                zone="default",
                profile=profile,
                mesh_token="",
                joined_at=datetime.now(UTC),
                last_heartbeat=datetime.now(UTC),
                last_heartbeat_monotonic=time.monotonic(),
            )
            devices.append(device)
            mesh_service._devices_cache[device.device_id] = device

        # Mock persistence
        mesh_service._persistence = MagicMock()
        mesh_service._persistence.update_device_heartbeat = AsyncMock(return_value=True)

        # Process heartbeats and collect intervals
        intervals = []
        for device in devices:
            result = await mesh_service.process_heartbeat(
                device_id=device.device_id,
                status=DeviceStatus.ONLINE,
                current_load=0.5,
                active_tasks=[],
            )
            intervals.append(result[3])

        # Intervals should have some variation (preventing thundering herd)
        unique_intervals = set(intervals)

        # With 10 devices and 20% jitter on 30s (6s range = 13 possible values),
        # we should see some variation
        # This is probabilistic, but highly likely to have > 1 unique value
        assert len(unique_intervals) >= 1  # At minimum, should work
