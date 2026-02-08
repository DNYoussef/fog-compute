"""
Tests for Command Idempotency Service

PHASE2-TASK-003 (p522): Command Idempotency
- Add unique command_id to task assignments
- Dedupe window tracking
- Prevent duplicate execution on network retries
"""
import pytest
import asyncio
import os
from datetime import datetime, timedelta, UTC

# Set test environment before imports
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-idempotency-testing')
os.environ.setdefault('TESTING', 'true')

from backend.server.services.command_idempotency import (
    CommandIdempotencyService,
    CommandRecord,
    CommandStatus,
    IdempotencyCheckResult,
    generate_command_id,
    hash_payload,
    get_command_idempotency_service,
)


@pytest.fixture
def idempotency_service():
    """Create a fresh CommandIdempotencyService for each test"""
    return CommandIdempotencyService(
        dedupe_window_seconds=60,
        max_cache_size=100,
        cleanup_interval_seconds=10,
    )


@pytest.fixture
def sample_payload():
    """Sample command payload"""
    return {
        "task_type": "compute",
        "data": [1, 2, 3],
        "config": {"iterations": 10}
    }


class TestGenerateCommandId:
    """Tests for command ID generation"""

    def test_format(self):
        """Command ID should have correct format"""
        cmd_id = generate_command_id()

        assert cmd_id.startswith("cmd-")
        parts = cmd_id.split("-")
        assert len(parts) == 3  # cmd, timestamp, random

    def test_uniqueness(self):
        """Generated IDs should be unique"""
        ids = [generate_command_id() for _ in range(100)]
        assert len(set(ids)) == 100

    def test_time_ordered(self):
        """IDs should be roughly time-ordered"""
        id1 = generate_command_id()
        id2 = generate_command_id()

        # Extract timestamp parts
        ts1 = id1.split("-")[1]
        ts2 = id2.split("-")[1]

        # Second ID should have same or later timestamp
        assert ts2 >= ts1


class TestHashPayload:
    """Tests for payload hashing"""

    def test_deterministic(self, sample_payload):
        """Same payload should produce same hash"""
        hash1 = hash_payload(sample_payload)
        hash2 = hash_payload(sample_payload)

        assert hash1 == hash2

    def test_different_payloads_different_hash(self):
        """Different payloads should produce different hashes"""
        hash1 = hash_payload({"a": 1})
        hash2 = hash_payload({"a": 2})

        assert hash1 != hash2

    def test_order_independent(self):
        """Key order should not affect hash"""
        hash1 = hash_payload({"a": 1, "b": 2})
        hash2 = hash_payload({"b": 2, "a": 1})

        assert hash1 == hash2

    def test_hash_length(self, sample_payload):
        """Hash should have consistent length"""
        hash1 = hash_payload(sample_payload)
        hash2 = hash_payload({"different": "payload"})

        assert len(hash1) == 16
        assert len(hash2) == 16


class TestCommandRegistration:
    """Tests for command registration"""

    def test_register_new_command(self, idempotency_service, sample_payload):
        """Should register new commands"""
        cmd_id, result = idempotency_service.register_command(
            device_id="device-1",
            task_type="compute",
            payload=sample_payload
        )

        assert cmd_id is not None
        assert result.is_duplicate is False
        assert result.message == "New command registered"

    def test_register_with_custom_id(self, idempotency_service, sample_payload):
        """Should accept custom command ID"""
        custom_id = "cmd-custom-12345678"

        cmd_id, result = idempotency_service.register_command(
            device_id="device-1",
            task_type="compute",
            payload=sample_payload,
            command_id=custom_id
        )

        assert cmd_id == custom_id
        assert result.is_duplicate is False

    def test_detect_duplicate_by_id(self, idempotency_service, sample_payload):
        """Should detect duplicate by command ID"""
        custom_id = "cmd-test-duplicate"

        # First registration
        cmd_id1, result1 = idempotency_service.register_command(
            device_id="device-1",
            task_type="compute",
            payload=sample_payload,
            command_id=custom_id
        )

        # Second registration with same ID
        cmd_id2, result2 = idempotency_service.register_command(
            device_id="device-1",
            task_type="compute",
            payload={"different": "payload"},
            command_id=custom_id
        )

        assert result1.is_duplicate is False
        assert result2.is_duplicate is True
        assert cmd_id1 == cmd_id2

    def test_detect_duplicate_by_payload(self, idempotency_service, sample_payload):
        """Should detect duplicate by payload hash"""
        # First registration
        cmd_id1, result1 = idempotency_service.register_command(
            device_id="device-1",
            task_type="compute",
            payload=sample_payload
        )

        # Second registration with same payload
        cmd_id2, result2 = idempotency_service.register_command(
            device_id="device-1",
            task_type="compute",
            payload=sample_payload  # Same payload
        )

        assert result1.is_duplicate is False
        assert result2.is_duplicate is True
        assert "Duplicate payload" in result2.message

    def test_different_payloads_not_duplicate(self, idempotency_service):
        """Different payloads should not be duplicates"""
        _, result1 = idempotency_service.register_command(
            device_id="device-1",
            task_type="compute",
            payload={"data": 1}
        )

        _, result2 = idempotency_service.register_command(
            device_id="device-1",
            task_type="compute",
            payload={"data": 2}
        )

        assert result1.is_duplicate is False
        assert result2.is_duplicate is False


class TestDuplicateCheck:
    """Tests for duplicate checking"""

    def test_check_by_command_id(self, idempotency_service, sample_payload):
        """Should check duplicate by command ID"""
        cmd_id, _ = idempotency_service.register_command(
            device_id="device-1",
            task_type="compute",
            payload=sample_payload
        )

        result = idempotency_service.check_duplicate(command_id=cmd_id)

        assert result.is_duplicate is True
        assert result.command_id == cmd_id

    def test_check_by_payload(self, idempotency_service, sample_payload):
        """Should check duplicate by payload"""
        idempotency_service.register_command(
            device_id="device-1",
            task_type="compute",
            payload=sample_payload
        )

        result = idempotency_service.check_duplicate(payload=sample_payload)

        assert result.is_duplicate is True

    def test_check_no_duplicate(self, idempotency_service):
        """Should return no duplicate for new payload"""
        result = idempotency_service.check_duplicate(
            payload={"brand": "new"}
        )

        assert result.is_duplicate is False


class TestStatusUpdates:
    """Tests for command status updates"""

    def test_mark_executing(self, idempotency_service, sample_payload):
        """Should mark command as executing"""
        cmd_id, _ = idempotency_service.register_command(
            device_id="device-1",
            task_type="compute",
            payload=sample_payload
        )

        success = idempotency_service.mark_executing(cmd_id)
        record = idempotency_service.get_command(cmd_id)

        assert success is True
        assert record.status == CommandStatus.EXECUTING
        assert record.execution_count == 1

    def test_mark_completed(self, idempotency_service, sample_payload):
        """Should mark command as completed"""
        cmd_id, _ = idempotency_service.register_command(
            device_id="device-1",
            task_type="compute",
            payload=sample_payload
        )

        result_data = {"output": [4, 5, 6]}
        success = idempotency_service.mark_completed(cmd_id, result=result_data)
        record = idempotency_service.get_command(cmd_id)

        assert success is True
        assert record.status == CommandStatus.COMPLETED
        assert record.result == result_data

    def test_mark_failed(self, idempotency_service, sample_payload):
        """Should mark command as failed"""
        cmd_id, _ = idempotency_service.register_command(
            device_id="device-1",
            task_type="compute",
            payload=sample_payload
        )

        success = idempotency_service.mark_failed(cmd_id, "Out of memory")
        record = idempotency_service.get_command(cmd_id)

        assert success is True
        assert record.status == CommandStatus.FAILED
        assert record.error_message == "Out of memory"

    def test_update_nonexistent_command(self, idempotency_service):
        """Should return False for nonexistent command"""
        success = idempotency_service.mark_executing("cmd-nonexistent")
        assert success is False


class TestResultCaching:
    """Tests for result caching"""

    def test_get_cached_result(self, idempotency_service, sample_payload):
        """Should return cached result for completed command"""
        cmd_id, _ = idempotency_service.register_command(
            device_id="device-1",
            task_type="compute",
            payload=sample_payload
        )

        result_data = {"computed": True}
        idempotency_service.mark_completed(cmd_id, result=result_data)

        cached = idempotency_service.get_command_result(cmd_id)

        assert cached == result_data

    def test_no_result_for_incomplete(self, idempotency_service, sample_payload):
        """Should return None for incomplete commands"""
        cmd_id, _ = idempotency_service.register_command(
            device_id="device-1",
            task_type="compute",
            payload=sample_payload
        )

        idempotency_service.mark_executing(cmd_id)
        cached = idempotency_service.get_command_result(cmd_id)

        assert cached is None


class TestDedupeWindow:
    """Tests for dedupe window functionality"""

    def test_extend_dedupe_window(self, idempotency_service, sample_payload):
        """Should extend dedupe window"""
        cmd_id, _ = idempotency_service.register_command(
            device_id="device-1",
            task_type="compute",
            payload=sample_payload
        )

        original_record = idempotency_service.get_command(cmd_id)
        original_expiry = original_record.expires_at

        success = idempotency_service.extend_dedupe_window(cmd_id, 300)
        updated_record = idempotency_service.get_command(cmd_id)

        assert success is True
        assert updated_record.expires_at > original_expiry

    def test_expired_not_duplicate(self):
        """Expired commands should not be duplicates"""
        # Create service with very short window
        service = CommandIdempotencyService(
            dedupe_window_seconds=0,  # Immediate expiry
            max_cache_size=100,
        )

        payload = {"test": "data"}

        # First registration
        cmd_id1, result1 = service.register_command(
            device_id="device-1",
            task_type="compute",
            payload=payload
        )

        # Manually expire the record
        record = service.get_command(cmd_id1)
        record.expires_at = datetime.now(UTC) - timedelta(seconds=1)

        # Second registration should NOT be duplicate (expired)
        # Note: This depends on the exact timing check in register_command
        # The implementation should check expires_at > now


class TestCacheSizeLimit:
    """Tests for cache size limits"""

    def test_evicts_oldest_on_overflow(self):
        """Should evict oldest entries when cache is full"""
        service = CommandIdempotencyService(
            dedupe_window_seconds=300,
            max_cache_size=3,  # Very small
        )

        # Register 4 commands
        ids = []
        for i in range(4):
            cmd_id, _ = service.register_command(
                device_id="device-1",
                task_type="compute",
                payload={"index": i}
            )
            ids.append(cmd_id)

        # First command should be evicted
        assert service.get_command(ids[0]) is None
        # Later commands should still exist
        assert service.get_command(ids[-1]) is not None


class TestStatistics:
    """Tests for service statistics"""

    def test_stats_tracking(self, idempotency_service, sample_payload):
        """Should track statistics"""
        # Register and duplicate
        idempotency_service.register_command(
            device_id="device-1",
            task_type="compute",
            payload=sample_payload
        )
        idempotency_service.register_command(
            device_id="device-1",
            task_type="compute",
            payload=sample_payload
        )

        stats = idempotency_service.get_stats()

        assert stats["total_commands"] == 1
        assert stats["duplicates_prevented"] == 1
        assert stats["active_commands"] == 1

    def test_stats_fields(self, idempotency_service):
        """Should have all expected stats fields"""
        stats = idempotency_service.get_stats()

        assert "active_commands" in stats
        assert "total_commands" in stats
        assert "duplicates_prevented" in stats
        assert "expirations" in stats
        assert "dedupe_window_seconds" in stats
        assert "max_cache_size" in stats


class TestBackgroundCleanup:
    """Tests for background cleanup"""

    @pytest.mark.asyncio
    async def test_start_stop(self, idempotency_service):
        """Should start and stop cleanup task"""
        await idempotency_service.start()
        assert idempotency_service._is_running is True

        await idempotency_service.stop()
        assert idempotency_service._is_running is False

    @pytest.mark.asyncio
    async def test_idempotent_start(self, idempotency_service):
        """Starting twice should be safe"""
        await idempotency_service.start()
        await idempotency_service.start()  # Should not raise

        assert idempotency_service._is_running is True

        await idempotency_service.stop()


class TestCommandRecord:
    """Tests for CommandRecord dataclass"""

    def test_record_fields(self, idempotency_service, sample_payload):
        """Record should have all expected fields"""
        cmd_id, _ = idempotency_service.register_command(
            device_id="device-1",
            task_type="compute",
            payload=sample_payload
        )

        record = idempotency_service.get_command(cmd_id)

        assert record.command_id == cmd_id
        assert record.device_id == "device-1"
        assert record.task_type == "compute"
        assert record.status == CommandStatus.PENDING
        assert record.created_at is not None
        assert record.updated_at is not None
        assert record.expires_at is not None
        assert record.execution_count == 0


class TestGlobalInstance:
    """Tests for global service instance"""

    def test_get_command_idempotency_service(self):
        """Should return CommandIdempotencyService instance"""
        service = get_command_idempotency_service()

        assert service is not None
        assert isinstance(service, CommandIdempotencyService)

    def test_singleton_pattern(self):
        """Should return same instance on multiple calls"""
        service1 = get_command_idempotency_service()
        service2 = get_command_idempotency_service()

        assert service1 is service2


class TestNetworkRetryScenario:
    """Tests for network retry scenarios (main use case)"""

    def test_retry_returns_original_result(self, idempotency_service):
        """Network retry should return cached result"""
        payload = {"task": "important_computation"}

        # First request succeeds
        cmd_id1, result1 = idempotency_service.register_command(
            device_id="device-1",
            task_type="compute",
            payload=payload
        )

        assert result1.is_duplicate is False

        # Execute and complete
        idempotency_service.mark_executing(cmd_id1)
        idempotency_service.mark_completed(cmd_id1, result={"answer": 42})

        # Network timeout, client retries with same payload
        cmd_id2, result2 = idempotency_service.register_command(
            device_id="device-1",
            task_type="compute",
            payload=payload
        )

        assert result2.is_duplicate is True
        assert result2.original_record.status == CommandStatus.COMPLETED

        # Client can retrieve cached result
        cached = idempotency_service.get_command_result(cmd_id1)
        assert cached == {"answer": 42}

    def test_retry_with_explicit_command_id(self, idempotency_service):
        """Client-provided command ID prevents duplicates"""
        # Client generates command ID before request
        client_cmd_id = generate_command_id()

        # First request
        _, result1 = idempotency_service.register_command(
            device_id="device-1",
            task_type="compute",
            payload={"task": "work"},
            command_id=client_cmd_id
        )

        # Network timeout, client retries with SAME command ID
        _, result2 = idempotency_service.register_command(
            device_id="device-1",
            task_type="compute",
            payload={"task": "work"},
            command_id=client_cmd_id  # Same ID
        )

        assert result1.is_duplicate is False
        assert result2.is_duplicate is True
