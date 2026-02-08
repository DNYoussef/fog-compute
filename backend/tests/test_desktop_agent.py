"""
Tests for Desktop Agent

PHASE3-AGENT-001 (bw09): Cross-Platform Compatibility
PHASE3-AGENT-002 (9ql3): Sandboxed Task Execution
PHASE3-AGENT-003 (is5m): Auto-Discovery + Manual Fallback
PHASE3-AGENT-004 (35dm): Resource Limits Enforcement
"""
import pytest
import asyncio
import os
import platform
import tempfile
from datetime import datetime, UTC
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

# Set test environment before imports
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-desktop-agent-testing')
os.environ.setdefault('TESTING', 'true')

from backend.desktop_agent.config import (
    AgentConfig,
    get_platform,
    get_config_dir,
    get_data_dir,
    get_cache_dir,
    get_log_dir,
    ensure_directories,
)
from backend.desktop_agent.resource_monitor import (
    ResourceMonitor,
    ResourceStatus,
    ResourceThresholds,
    ResourceMetrics,
)
from backend.desktop_agent.discovery import (
    CoordinatorDiscovery,
    CoordinatorInfo,
    DiscoveryMethod,
    RetryWithBackoff,
)
from backend.desktop_agent.executor import (
    TaskExecutor,
    TaskAssignment,
    ExecutionResult,
    ExecutionStatus,
    TaskQueue,
)
from backend.desktop_agent.agent import (
    DesktopAgent,
    AgentStatus,
)


class TestPlatformCompatibility:
    """
    Tests for PHASE3-AGENT-001: Cross-Platform Compatibility
    """

    def test_get_platform_normalized(self):
        """Platform name should be normalized"""
        plat = get_platform()

        assert plat in ("windows", "macos", "linux")
        assert plat.islower()

    def test_config_dir_uses_pathlib(self):
        """Config dir should use pathlib.Path"""
        config_dir = get_config_dir()

        assert isinstance(config_dir, Path)
        assert "fogburst" in str(config_dir)

    def test_data_dir_uses_pathlib(self):
        """Data dir should use pathlib.Path"""
        data_dir = get_data_dir()

        assert isinstance(data_dir, Path)

    def test_cache_dir_platform_specific(self):
        """Cache dir should be platform-specific"""
        cache_dir = get_cache_dir()

        assert isinstance(cache_dir, Path)
        if platform.system() == "Windows":
            assert "AppData" in str(cache_dir) or "Local" in str(cache_dir)
        elif platform.system() == "Darwin":
            assert "Library" in str(cache_dir) or "Caches" in str(cache_dir)
        # Linux uses XDG or .cache

    def test_log_dir_platform_specific(self):
        """Log dir should be platform-specific"""
        log_dir = get_log_dir()

        assert isinstance(log_dir, Path)

    def test_agent_config_default_device_id(self):
        """Config should generate unique device ID"""
        config = AgentConfig()

        assert config.device_id is not None
        assert len(config.device_id) == 16  # SHA-256 hex truncated

    def test_agent_config_default_device_name(self):
        """Config should have default device name"""
        config = AgentConfig()

        assert config.device_name is not None
        assert len(config.device_name) > 0

    def test_agent_config_directories_set(self):
        """Config should set default directories"""
        config = AgentConfig()

        assert config.config_dir != ""
        assert config.data_dir != ""
        assert config.cache_dir != ""
        assert config.log_dir != ""

    def test_ensure_directories_creates(self):
        """ensure_directories should create dirs"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = AgentConfig(
                config_dir=str(Path(tmpdir) / "config"),
                data_dir=str(Path(tmpdir) / "data"),
                cache_dir=str(Path(tmpdir) / "cache"),
                log_dir=str(Path(tmpdir) / "logs"),
            )

            ensure_directories(config)

            assert Path(config.config_dir).exists()
            assert Path(config.data_dir).exists()
            assert Path(config.cache_dir).exists()
            assert Path(config.log_dir).exists()

    def test_config_save_load_roundtrip(self):
        """Config should save and load correctly"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_config.json"

            original = AgentConfig(
                device_name="test-device",
                max_cpu_percent=50.0,
                task_types=["compute", "inference"],
            )

            original.save(config_path)
            loaded = AgentConfig.load(config_path)

            assert loaded.device_name == original.device_name
            assert loaded.max_cpu_percent == original.max_cpu_percent
            assert loaded.task_types == original.task_types


class TestResourceMonitor:
    """
    Tests for PHASE3-AGENT-004: Resource Limits Enforcement
    """

    @pytest.fixture
    def monitor(self):
        """Create resource monitor for tests"""
        thresholds = ResourceThresholds(
            cpu_available=50.0,
            cpu_limited=70.0,
            cpu_overloaded=90.0,
            memory_available=50.0,
            memory_limited=70.0,
            memory_overloaded=85.0,
        )
        return ResourceMonitor(thresholds=thresholds)

    def test_initial_status_unknown(self, monitor):
        """Initial status should be unknown"""
        assert monitor.get_status() == ResourceStatus.UNKNOWN

    def test_can_accept_task_default(self, monitor):
        """Should accept tasks by default"""
        # Default unknown state allows acceptance
        # (until first sample determines actual state)
        assert monitor.can_accept_task() is True

    def test_paused_rejects_tasks(self, monitor):
        """Paused monitor should reject all tasks"""
        monitor.pause()

        assert monitor.can_accept_task() is False

    def test_pause_resume(self, monitor):
        """Should pause and resume"""
        monitor.pause()
        assert monitor.can_accept_task() is False

        monitor.resume()
        # After resume, depends on resource state (unknown allows)

    def test_active_task_tracking(self, monitor):
        """Should track active tasks"""
        assert monitor._active_tasks == 0

        monitor.increment_active_tasks()
        assert monitor._active_tasks == 1

        monitor.increment_active_tasks()
        assert monitor._active_tasks == 2

        monitor.decrement_active_tasks()
        assert monitor._active_tasks == 1

        monitor.set_active_tasks(5)
        assert monitor._active_tasks == 5

    def test_decrement_below_zero(self, monitor):
        """Decrement should not go below zero"""
        monitor.set_active_tasks(0)
        monitor.decrement_active_tasks()

        assert monitor._active_tasks == 0

    def test_get_current_metrics(self, monitor):
        """Should get current metrics"""
        metrics = monitor.get_current_metrics()

        assert isinstance(metrics, ResourceMetrics)
        assert metrics.cpu_count >= 1
        assert metrics.memory_total_mb > 0

    def test_metrics_to_dict(self, monitor):
        """Metrics should convert to dict"""
        metrics = monitor.get_current_metrics()
        data = metrics.to_dict()

        assert "cpu_percent" in data
        assert "memory_percent" in data
        assert "status" in data
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_start_stop(self, monitor):
        """Should start and stop monitoring"""
        await monitor.start()
        assert monitor._is_running is True

        await monitor.stop()
        assert monitor._is_running is False

    def test_get_stats(self, monitor):
        """Should get monitor stats"""
        stats = monitor.get_stats()

        assert "status" in stats
        assert "paused" in stats
        assert "thresholds" in stats
        assert "platform" in stats


class TestCoordinatorDiscovery:
    """
    Tests for PHASE3-AGENT-003: Auto-Discovery + Manual Fallback
    """

    @pytest.fixture
    def discovery(self):
        """Create coordinator discovery for tests"""
        return CoordinatorDiscovery(
            service_name="_fogburst._tcp.local.",
            default_port=8000,
            tls_enabled=True,
            discovery_timeout_sec=5,
            max_retries=2,
            base_delay_sec=0.1,
            max_delay_sec=1.0,
        )

    def test_manual_url_creates_coordinator(self, discovery):
        """Manual URL should create coordinator info"""
        discovery.set_manual_url("https://coordinator.local:8000")

        coordinator = discovery._create_manual_coordinator()

        assert coordinator is not None
        assert coordinator.host == "coordinator.local"
        assert coordinator.port == 8000
        assert coordinator.method == DiscoveryMethod.MANUAL
        assert coordinator.tls_enabled is True

    def test_manual_url_without_protocol(self, discovery):
        """Should handle URL without protocol"""
        discovery.set_manual_url("coordinator.local:8000")

        coordinator = discovery._create_manual_coordinator()

        assert coordinator.host == "coordinator.local"
        assert coordinator.port == 8000
        assert coordinator.url.startswith("https://")

    def test_manual_url_without_port(self, discovery):
        """Should use default port"""
        discovery.set_manual_url("coordinator.local")

        coordinator = discovery._create_manual_coordinator()

        assert coordinator.host == "coordinator.local"
        assert coordinator.port == 8000

    def test_coordinator_info_to_dict(self, discovery):
        """Coordinator info should convert to dict"""
        discovery.set_manual_url("https://test.local:8000")
        coordinator = discovery._create_manual_coordinator()

        data = coordinator.to_dict()

        assert "url" in data
        assert "host" in data
        assert "port" in data
        assert "method" in data
        assert "discovered_at" in data

    @pytest.mark.asyncio
    async def test_discover_uses_manual_url_if_set(self, discovery):
        """Should use manual URL if set"""
        discovery.set_manual_url("https://coordinator.local:8000")

        coordinator = await discovery.discover()

        assert coordinator is not None
        assert coordinator.method == DiscoveryMethod.MANUAL

    def test_clear_cache(self, discovery):
        """Should clear cached coordinator"""
        discovery.set_manual_url("https://test.local:8000")
        discovery._create_manual_coordinator()

        assert discovery.get_current_coordinator() is not None

        discovery.clear_cache()

        assert discovery.get_current_coordinator() is None


class TestRetryWithBackoff:
    """Tests for retry with exponential backoff"""

    def test_initial_state(self):
        """Should start with zero attempts"""
        retry = RetryWithBackoff(max_retries=3)

        assert retry.attempt == 1
        assert retry.can_retry() is True

    def test_exponential_delay(self):
        """Delays should increase exponentially"""
        retry = RetryWithBackoff(
            max_retries=5,
            base_delay_sec=1.0,
            max_delay_sec=60.0,
            jitter=False,
        )

        delays = []
        while retry.can_retry():
            delays.append(retry.get_delay())

        assert len(delays) == 5
        assert delays[0] == 1.0
        assert delays[1] == 2.0
        assert delays[2] == 4.0
        assert delays[3] == 8.0
        assert delays[4] == 16.0

    def test_max_delay_capped(self):
        """Delay should not exceed max"""
        retry = RetryWithBackoff(
            max_retries=10,
            base_delay_sec=1.0,
            max_delay_sec=5.0,
            jitter=False,
        )

        for _ in range(10):
            delay = retry.get_delay()
            assert delay <= 5.0

    def test_reset(self):
        """Reset should clear attempt count"""
        retry = RetryWithBackoff(max_retries=3)

        retry.get_delay()
        retry.get_delay()
        assert retry.attempt == 3

        retry.reset()
        assert retry.attempt == 1

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Should return result on success"""
        retry = RetryWithBackoff(max_retries=3)

        async def success_func():
            return "success"

        result = await retry.execute(success_func)

        assert result == "success"

    @pytest.mark.asyncio
    async def test_execute_retries_on_failure(self):
        """Should retry on failure"""
        retry = RetryWithBackoff(
            max_retries=3,
            base_delay_sec=0.01,
            jitter=False,
        )

        call_count = 0

        async def fail_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("fail")
            return "success"

        result = await retry.execute(fail_twice)

        assert result == "success"
        assert call_count == 3


class TestTaskExecutor:
    """
    Tests for PHASE3-AGENT-002: Sandboxed Task Execution
    """

    @pytest.fixture
    def executor(self):
        """Create task executor for tests"""
        return TaskExecutor(
            allowed_task_types=["compute", "inference"],
            max_concurrent_tasks=2,
        )

    def test_allowed_task_types(self, executor):
        """Should have allowed task types"""
        assert "compute" in executor.allowed_task_types
        assert "inference" in executor.allowed_task_types

    def test_can_accept_allowed_type(self, executor):
        """Should accept allowed task types"""
        task = TaskAssignment(
            command_id="cmd-test-1",
            task_type="compute",
            command=["echo", "test"],
        )

        can_accept, reason = executor.can_accept_task(task)

        assert can_accept is True

    def test_rejects_unknown_type(self, executor):
        """Should reject unknown task types"""
        task = TaskAssignment(
            command_id="cmd-test-2",
            task_type="unknown_type",
            command=["echo", "test"],
        )

        can_accept, reason = executor.can_accept_task(task)

        assert can_accept is False
        assert "not in allowed types" in reason

    def test_rejects_at_max_concurrent(self, executor):
        """Should reject when at max concurrent tasks"""
        # Simulate max concurrent
        executor._active_executions = {"exec-1": Mock(), "exec-2": Mock()}

        task = TaskAssignment(
            command_id="cmd-test-3",
            task_type="compute",
            command=["echo", "test"],
        )

        can_accept, reason = executor.can_accept_task(task)

        assert can_accept is False
        assert "max concurrent" in reason

    def test_get_stats(self, executor):
        """Should get executor stats"""
        stats = executor.get_stats()

        assert "total_executions" in stats
        assert "successful" in stats
        assert "failed" in stats
        assert "allowed_task_types" in stats

    def test_execution_result_to_dict(self):
        """Execution result should convert to dict"""
        result = ExecutionResult(
            execution_id="exec-123",
            command_id="cmd-456",
            status=ExecutionStatus.COMPLETED,
            exit_code=0,
            stdout="output",
            duration_ms=100,
        )

        data = result.to_dict()

        assert data["execution_id"] == "exec-123"
        assert data["command_id"] == "cmd-456"
        assert data["status"] == "completed"
        assert data["exit_code"] == 0


class TestTaskQueue:
    """Tests for task queue"""

    @pytest.fixture
    def queue(self):
        """Create task queue for tests"""
        return TaskQueue(max_size=5)

    @pytest.mark.asyncio
    async def test_enqueue_dequeue(self, queue):
        """Should enqueue and dequeue tasks"""
        task = TaskAssignment(
            command_id="cmd-1",
            task_type="compute",
            command=["echo", "test"],
        )

        result = await queue.enqueue(task)
        assert result is True
        assert queue.pending_count() == 1

        dequeued = await queue.dequeue()
        assert dequeued.command_id == "cmd-1"
        assert queue.pending_count() == 0

    @pytest.mark.asyncio
    async def test_queue_full(self, queue):
        """Should reject when queue full"""
        # Fill queue
        for i in range(5):
            await queue.enqueue(TaskAssignment(
                command_id=f"cmd-{i}",
                task_type="compute",
                command=["echo", str(i)],
            ))

        assert queue.is_full() is True

        # Try to add one more
        result = await queue.enqueue(TaskAssignment(
            command_id="cmd-extra",
            task_type="compute",
            command=["echo", "extra"],
        ))

        assert result is False

    @pytest.mark.asyncio
    async def test_is_empty(self, queue):
        """Should detect empty queue"""
        assert queue.is_empty() is True

        await queue.enqueue(TaskAssignment(
            command_id="cmd-1",
            task_type="compute",
            command=["echo", "test"],
        ))

        assert queue.is_empty() is False


class TestDesktopAgent:
    """
    Tests for Desktop Agent integration
    """

    @pytest.fixture
    def agent_config(self):
        """Create test config"""
        return AgentConfig(
            device_name="test-agent",
            coordinator_url="https://localhost:8000",
            task_types=["compute"],
            max_concurrent_tasks=2,
        )

    def test_agent_initialization(self, agent_config):
        """Should initialize agent"""
        agent = DesktopAgent(agent_config)

        assert agent.config.device_name == "test-agent"
        assert agent.status == AgentStatus.INITIALIZING

    def test_agent_device_id(self, agent_config):
        """Should have device ID"""
        agent = DesktopAgent(agent_config)

        assert agent.device_id is not None
        assert len(agent.device_id) > 0

    def test_agent_is_active_default(self, agent_config):
        """Should not be active initially"""
        agent = DesktopAgent(agent_config)

        assert agent.is_active is False

    def test_agent_get_info(self, agent_config):
        """Should get agent info"""
        agent = DesktopAgent(agent_config)

        info = agent.get_info()

        assert "device_id" in info
        assert "device_name" in info
        assert "status" in info
        assert "platform" in info
        assert "task_types" in info
        assert "resource_metrics" in info


class TestAgentStatus:
    """Tests for agent status enum"""

    def test_all_statuses_defined(self):
        """All statuses should be defined"""
        statuses = [
            AgentStatus.INITIALIZING,
            AgentStatus.DISCOVERING,
            AgentStatus.CONNECTING,
            AgentStatus.REGISTERING,
            AgentStatus.ACTIVE,
            AgentStatus.PAUSED,
            AgentStatus.DISCONNECTED,
            AgentStatus.SHUTTING_DOWN,
            AgentStatus.STOPPED,
            AgentStatus.ERROR,
        ]

        assert len(statuses) == 10

    def test_status_values(self):
        """Status values should be lowercase strings"""
        for status in AgentStatus:
            assert status.value.islower()


class TestExecutionStatus:
    """Tests for execution status enum"""

    def test_all_execution_statuses(self):
        """All execution statuses should be defined"""
        statuses = [
            ExecutionStatus.PENDING,
            ExecutionStatus.RUNNING,
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
            ExecutionStatus.TIMEOUT,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.REJECTED,
        ]

        assert len(statuses) == 7


class TestResourceStatus:
    """Tests for resource status enum"""

    def test_all_resource_statuses(self):
        """All resource statuses should be defined"""
        statuses = [
            ResourceStatus.AVAILABLE,
            ResourceStatus.LIMITED,
            ResourceStatus.OVERLOADED,
            ResourceStatus.PAUSED,
            ResourceStatus.UNKNOWN,
        ]

        assert len(statuses) == 5


class TestDiscoveryMethod:
    """Tests for discovery method enum"""

    def test_all_discovery_methods(self):
        """All discovery methods should be defined"""
        methods = [
            DiscoveryMethod.MDNS,
            DiscoveryMethod.MANUAL,
            DiscoveryMethod.CACHED,
            DiscoveryMethod.FALLBACK,
        ]

        assert len(methods) == 4
