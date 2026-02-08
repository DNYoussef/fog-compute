"""
Tests for Task Timeout Service

PHASE2-TASK-004 (s74b): Timeout Enforcement
- Coordinator-side timeout for task execution
- Kill runaway tasks
- Return FAILED status with timeout reason
"""
import pytest
import asyncio
import os
from datetime import datetime, timedelta, UTC

# Set test environment before imports
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-timeout-testing')
os.environ.setdefault('TESTING', 'true')

from backend.server.services.task_timeout import (
    TaskTimeoutService,
    TaskExecution,
    TaskExecutionStatus,
    TimeoutResult,
    get_task_timeout_service,
)
from backend.server.services.command_idempotency import (
    CommandIdempotencyService,
    generate_command_id,
)


@pytest.fixture
def timeout_service():
    """Create a fresh TaskTimeoutService for each test"""
    return TaskTimeoutService(
        default_timeout_sec=10,
        check_interval_sec=1,
        warning_threshold_percent=80,
    )


@pytest.fixture
def idempotency_service():
    """Create fresh idempotency service"""
    return CommandIdempotencyService(
        dedupe_window_seconds=60,
        max_cache_size=100,
    )


class TestExecutionRegistration:
    """Tests for execution registration"""

    def test_register_execution(self, timeout_service):
        """Should register new execution"""
        cmd_id = generate_command_id()

        execution = timeout_service.register_execution(
            command_id=cmd_id,
            device_id="device-1",
            task_type="compute",
        )

        assert execution is not None
        assert execution.command_id == cmd_id
        assert execution.device_id == "device-1"
        assert execution.status == TaskExecutionStatus.QUEUED
        assert execution.timeout_sec > 0

    def test_register_with_custom_timeout(self, timeout_service):
        """Should accept custom timeout"""
        cmd_id = generate_command_id()

        execution = timeout_service.register_execution(
            command_id=cmd_id,
            device_id="device-1",
            task_type="compute",
            timeout_sec=60,
        )

        assert execution.timeout_sec == 60

    def test_register_uses_task_security_timeout(self, timeout_service):
        """Should use timeout from security constraints"""
        cmd_id = generate_command_id()

        execution = timeout_service.register_execution(
            command_id=cmd_id,
            device_id="device-1",
            task_type="gpu_compute",  # Has longer timeout in TASK_ALLOWLIST
        )

        # GPU compute has 1800s (30 min) timeout
        assert execution.timeout_sec == 1800

    def test_execution_id_unique(self, timeout_service):
        """Each execution should have unique ID"""
        cmd_id1 = generate_command_id()
        cmd_id2 = generate_command_id()

        exec1 = timeout_service.register_execution(
            command_id=cmd_id1,
            device_id="device-1",
            task_type="compute",
        )
        exec2 = timeout_service.register_execution(
            command_id=cmd_id2,
            device_id="device-1",
            task_type="compute",
        )

        assert exec1.execution_id != exec2.execution_id


class TestExecutionLifecycle:
    """Tests for execution lifecycle"""

    def test_start_execution(self, timeout_service):
        """Should start execution and set deadline"""
        cmd_id = generate_command_id()

        execution = timeout_service.register_execution(
            command_id=cmd_id,
            device_id="device-1",
            task_type="compute",
        )

        success = timeout_service.start_execution(execution.execution_id)

        assert success is True
        assert execution.status == TaskExecutionStatus.RUNNING
        assert execution.started_at is not None
        assert execution.deadline is not None

    def test_cannot_start_twice(self, timeout_service):
        """Should not start already running execution"""
        cmd_id = generate_command_id()

        execution = timeout_service.register_execution(
            command_id=cmd_id,
            device_id="device-1",
            task_type="compute",
        )

        timeout_service.start_execution(execution.execution_id)
        success = timeout_service.start_execution(execution.execution_id)

        assert success is False

    def test_complete_execution(self, timeout_service):
        """Should complete execution"""
        cmd_id = generate_command_id()

        execution = timeout_service.register_execution(
            command_id=cmd_id,
            device_id="device-1",
            task_type="compute",
        )
        timeout_service.start_execution(execution.execution_id)

        result_data = {"answer": 42}
        success = timeout_service.complete_execution(
            execution.execution_id,
            result=result_data
        )

        assert success is True
        assert execution.status == TaskExecutionStatus.COMPLETED
        assert execution.result == result_data
        assert execution.completed_at is not None

    def test_fail_execution(self, timeout_service):
        """Should fail execution with error message"""
        cmd_id = generate_command_id()

        execution = timeout_service.register_execution(
            command_id=cmd_id,
            device_id="device-1",
            task_type="compute",
        )
        timeout_service.start_execution(execution.execution_id)

        success = timeout_service.fail_execution(
            execution.execution_id,
            error_message="Out of memory"
        )

        assert success is True
        assert execution.status == TaskExecutionStatus.FAILED
        assert execution.error_message == "Out of memory"

    def test_cancel_execution(self, timeout_service):
        """Should cancel execution"""
        cmd_id = generate_command_id()

        execution = timeout_service.register_execution(
            command_id=cmd_id,
            device_id="device-1",
            task_type="compute",
        )
        timeout_service.start_execution(execution.execution_id)

        success = timeout_service.cancel_execution(execution.execution_id)

        assert success is True
        assert execution.status == TaskExecutionStatus.CANCELLED


class TestTimeoutCheck:
    """Tests for timeout checking"""

    def test_check_running_execution(self, timeout_service):
        """Should check running execution"""
        cmd_id = generate_command_id()

        execution = timeout_service.register_execution(
            command_id=cmd_id,
            device_id="device-1",
            task_type="compute",
            timeout_sec=60,
        )
        timeout_service.start_execution(execution.execution_id)

        result = timeout_service.check_timeout(execution.execution_id)

        assert result.timed_out is False
        assert result.remaining_sec > 0
        assert result.remaining_sec <= 60

    def test_check_nonexistent_execution(self, timeout_service):
        """Should handle nonexistent execution"""
        result = timeout_service.check_timeout("nonexistent-id")

        assert result.timed_out is False
        assert "not found" in result.message.lower()

    def test_check_completed_execution(self, timeout_service):
        """Should handle completed execution"""
        cmd_id = generate_command_id()

        execution = timeout_service.register_execution(
            command_id=cmd_id,
            device_id="device-1",
            task_type="compute",
        )
        timeout_service.start_execution(execution.execution_id)
        timeout_service.complete_execution(execution.execution_id)

        result = timeout_service.check_timeout(execution.execution_id)

        assert result.timed_out is False
        assert "not running" in result.message.lower()


class TestTimeoutEnforcement:
    """Tests for timeout enforcement"""

    @pytest.mark.asyncio
    async def test_timeout_execution(self, timeout_service):
        """Should timeout execution"""
        cmd_id = generate_command_id()

        execution = timeout_service.register_execution(
            command_id=cmd_id,
            device_id="device-1",
            task_type="compute",
        )
        timeout_service.start_execution(execution.execution_id)

        success = await timeout_service.timeout_execution(execution.execution_id)

        assert success is True
        assert execution.status == TaskExecutionStatus.TIMEOUT
        assert "timed out" in execution.error_message.lower()

    @pytest.mark.asyncio
    async def test_timeout_callback(self, timeout_service):
        """Should call timeout callback"""
        callback_called = False
        callback_execution = None

        async def on_timeout(execution):
            nonlocal callback_called, callback_execution
            callback_called = True
            callback_execution = execution

        timeout_service.set_timeout_callback(on_timeout)

        cmd_id = generate_command_id()
        execution = timeout_service.register_execution(
            command_id=cmd_id,
            device_id="device-1",
            task_type="compute",
        )
        timeout_service.start_execution(execution.execution_id)

        await timeout_service.timeout_execution(execution.execution_id)

        assert callback_called is True
        assert callback_execution.execution_id == execution.execution_id

    @pytest.mark.asyncio
    async def test_cannot_timeout_completed(self, timeout_service):
        """Should not timeout completed execution"""
        cmd_id = generate_command_id()

        execution = timeout_service.register_execution(
            command_id=cmd_id,
            device_id="device-1",
            task_type="compute",
        )
        timeout_service.start_execution(execution.execution_id)
        timeout_service.complete_execution(execution.execution_id)

        success = await timeout_service.timeout_execution(execution.execution_id)

        assert success is False
        assert execution.status == TaskExecutionStatus.COMPLETED


class TestTimeoutExtension:
    """Tests for timeout extension"""

    def test_extend_timeout(self, timeout_service):
        """Should extend timeout"""
        cmd_id = generate_command_id()

        execution = timeout_service.register_execution(
            command_id=cmd_id,
            device_id="device-1",
            task_type="compute",
            timeout_sec=60,
        )
        timeout_service.start_execution(execution.execution_id)

        original_deadline = execution.deadline

        success = timeout_service.extend_timeout(execution.execution_id, 30)

        assert success is True
        assert execution.deadline > original_deadline
        assert execution.timeout_sec == 90
        assert execution.extension_count == 1

    def test_max_extensions_enforced(self, timeout_service):
        """Should enforce max extensions limit"""
        cmd_id = generate_command_id()

        execution = timeout_service.register_execution(
            command_id=cmd_id,
            device_id="device-1",
            task_type="compute",
        )
        timeout_service.start_execution(execution.execution_id)

        # Max is 2 by default
        timeout_service.extend_timeout(execution.execution_id, 10)
        timeout_service.extend_timeout(execution.execution_id, 10)
        success = timeout_service.extend_timeout(execution.execution_id, 10)

        assert success is False
        assert execution.extension_count == 2

    def test_cannot_extend_completed(self, timeout_service):
        """Should not extend completed execution"""
        cmd_id = generate_command_id()

        execution = timeout_service.register_execution(
            command_id=cmd_id,
            device_id="device-1",
            task_type="compute",
        )
        timeout_service.start_execution(execution.execution_id)
        timeout_service.complete_execution(execution.execution_id)

        success = timeout_service.extend_timeout(execution.execution_id, 30)

        assert success is False


class TestBackgroundMonitoring:
    """Tests for background timeout monitoring"""

    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self, timeout_service):
        """Should start and stop monitoring"""
        await timeout_service.start()
        assert timeout_service._is_running is True

        await timeout_service.stop()
        assert timeout_service._is_running is False

    @pytest.mark.asyncio
    async def test_auto_timeout_on_deadline(self):
        """Should auto-timeout when deadline reached"""
        # Use very short timeout for test
        service = TaskTimeoutService(
            default_timeout_sec=1,
            check_interval_sec=0.5,
        )

        cmd_id = generate_command_id()
        execution = service.register_execution(
            command_id=cmd_id,
            device_id="device-1",
            task_type="compute",
            timeout_sec=1,
        )
        service.start_execution(execution.execution_id)

        await service.start()

        # Wait for timeout to occur
        await asyncio.sleep(2)

        await service.stop()

        # Should have been timed out by monitor
        assert execution.status == TaskExecutionStatus.TIMEOUT


class TestExecutionQueries:
    """Tests for execution queries"""

    def test_get_execution(self, timeout_service):
        """Should get execution by ID"""
        cmd_id = generate_command_id()

        execution = timeout_service.register_execution(
            command_id=cmd_id,
            device_id="device-1",
            task_type="compute",
        )

        retrieved = timeout_service.get_execution(execution.execution_id)

        assert retrieved is not None
        assert retrieved.execution_id == execution.execution_id

    def test_get_execution_by_command(self, timeout_service):
        """Should get execution by command ID"""
        cmd_id = generate_command_id()

        execution = timeout_service.register_execution(
            command_id=cmd_id,
            device_id="device-1",
            task_type="compute",
        )

        retrieved = timeout_service.get_execution_by_command(cmd_id)

        assert retrieved is not None
        assert retrieved.command_id == cmd_id

    def test_get_running_executions(self, timeout_service):
        """Should get running executions"""
        for i in range(3):
            cmd_id = generate_command_id()
            execution = timeout_service.register_execution(
                command_id=cmd_id,
                device_id="device-1",
                task_type="compute",
            )
            if i < 2:  # Start only 2 of 3
                timeout_service.start_execution(execution.execution_id)

        running = timeout_service.get_running_executions()

        assert len(running) == 2

    def test_get_running_by_device(self, timeout_service):
        """Should filter running by device"""
        for device_id in ["device-1", "device-1", "device-2"]:
            cmd_id = generate_command_id()
            execution = timeout_service.register_execution(
                command_id=cmd_id,
                device_id=device_id,
                task_type="compute",
            )
            timeout_service.start_execution(execution.execution_id)

        running = timeout_service.get_running_executions(device_id="device-1")

        assert len(running) == 2


class TestStatistics:
    """Tests for service statistics"""

    def test_stats_tracking(self, timeout_service):
        """Should track statistics"""
        cmd_id = generate_command_id()

        execution = timeout_service.register_execution(
            command_id=cmd_id,
            device_id="device-1",
            task_type="compute",
        )
        timeout_service.start_execution(execution.execution_id)
        timeout_service.complete_execution(execution.execution_id)

        stats = timeout_service.get_stats()

        assert stats["total_executions"] == 1
        assert stats["completions"] == 1

    def test_stats_fields(self, timeout_service):
        """Should have all expected stats fields"""
        stats = timeout_service.get_stats()

        assert "total_executions" in stats
        assert "timeouts" in stats
        assert "completions" in stats
        assert "failures" in stats
        assert "extensions_granted" in stats
        assert "currently_running" in stats
        assert "default_timeout_sec" in stats


class TestCleanup:
    """Tests for cleanup of old executions"""

    def test_cleanup_completed(self, timeout_service):
        """Should clean up old completed executions"""
        cmd_id = generate_command_id()

        execution = timeout_service.register_execution(
            command_id=cmd_id,
            device_id="device-1",
            task_type="compute",
        )
        timeout_service.start_execution(execution.execution_id)
        timeout_service.complete_execution(execution.execution_id)

        # Artificially age the completion
        execution.completed_at = datetime.now(UTC) - timedelta(hours=2)

        removed = timeout_service.cleanup_completed(max_age_sec=3600)

        assert removed == 1
        assert timeout_service.get_execution(execution.execution_id) is None

    def test_does_not_cleanup_running(self, timeout_service):
        """Should not clean up running executions"""
        cmd_id = generate_command_id()

        execution = timeout_service.register_execution(
            command_id=cmd_id,
            device_id="device-1",
            task_type="compute",
        )
        timeout_service.start_execution(execution.execution_id)

        removed = timeout_service.cleanup_completed(max_age_sec=0)

        assert removed == 0
        assert timeout_service.get_execution(execution.execution_id) is not None


class TestGlobalInstance:
    """Tests for global service instance"""

    def test_get_task_timeout_service(self):
        """Should return TaskTimeoutService instance"""
        service = get_task_timeout_service()

        assert service is not None
        assert isinstance(service, TaskTimeoutService)

    def test_singleton_pattern(self):
        """Should return same instance on multiple calls"""
        service1 = get_task_timeout_service()
        service2 = get_task_timeout_service()

        assert service1 is service2


class TestWarningThreshold:
    """Tests for warning threshold"""

    def test_warning_triggered(self, timeout_service):
        """Should trigger warning at threshold"""
        cmd_id = generate_command_id()

        # Create execution with 10 second timeout, 80% threshold = warn at 8s
        execution = timeout_service.register_execution(
            command_id=cmd_id,
            device_id="device-1",
            task_type="compute",
            timeout_sec=10,
        )
        timeout_service.start_execution(execution.execution_id)

        # Artificially set deadline to be nearly reached
        execution.deadline = datetime.now(UTC) + timedelta(seconds=1)

        # Check should trigger warning
        result = timeout_service.check_timeout(execution.execution_id)

        assert result.timed_out is False
        assert execution.timeout_warned is True
