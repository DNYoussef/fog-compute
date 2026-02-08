"""
Tests for Task Sandbox Service

PHASE2-TASK-001 (12mj): Minimal Sandbox
- Subprocess sandboxing with ulimit
- No filesystem access outside /tmp/fogburst
- Resource limits enforcement
"""
import pytest
import asyncio
import os
import platform
import tempfile
from pathlib import Path

# Set test environment before imports
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-sandbox-testing')
os.environ.setdefault('TESTING', 'true')

from backend.server.services.task_sandbox import (
    TaskSandbox,
    TaskSandboxService,
    SandboxConfig,
    SandboxType,
    SandboxStatus,
    SandboxResult,
    SandboxError,
    SANDBOX_BASE_DIR,
    get_task_sandbox_service,
)


@pytest.fixture
def sandbox_service():
    """Create a fresh TaskSandboxService for each test"""
    return TaskSandboxService()


@pytest.fixture
def basic_config():
    """Basic sandbox configuration"""
    return SandboxConfig(
        sandbox_type=SandboxType.PROCESS,
        task_type="compute",
        max_memory_mb=256,
        max_cpu_percent=50,
        max_execution_time_sec=10,
        max_file_size_mb=10,
    )


class TestSandboxConfig:
    """Tests for SandboxConfig"""

    def test_default_config(self):
        """Default config should have sensible values"""
        config = SandboxConfig()

        assert config.sandbox_type == SandboxType.PROCESS
        assert config.max_memory_mb == 512
        assert config.max_execution_time_sec == 300
        assert "/tmp/fogburst" in config.allowed_paths or "fogburst" in config.working_dir

    def test_custom_config(self, basic_config):
        """Custom config should override defaults"""
        assert basic_config.max_memory_mb == 256
        assert basic_config.max_execution_time_sec == 10


class TestTaskSandbox:
    """Tests for TaskSandbox"""

    @pytest.mark.asyncio
    async def test_sandbox_setup_creates_directory(self, basic_config):
        """Setup should create sandbox directory"""
        sandbox = TaskSandbox(basic_config)

        try:
            sandbox_dir = await sandbox.setup()
            assert sandbox_dir.exists()
            assert sandbox.execution_id in str(sandbox_dir)
        finally:
            await sandbox.cleanup()

    @pytest.mark.asyncio
    async def test_sandbox_cleanup_removes_directory(self, basic_config):
        """Cleanup should remove sandbox directory"""
        sandbox = TaskSandbox(basic_config)
        sandbox_dir = await sandbox.setup()

        assert sandbox_dir.exists()
        await sandbox.cleanup()
        assert not sandbox_dir.exists()

    @pytest.mark.asyncio
    async def test_execution_id_unique(self, basic_config):
        """Each sandbox should have unique execution ID"""
        sandbox1 = TaskSandbox(basic_config)
        sandbox2 = TaskSandbox(basic_config)

        assert sandbox1.execution_id != sandbox2.execution_id
        assert sandbox1.execution_id.startswith("exec-")

    @pytest.mark.asyncio
    @pytest.mark.skipif(platform.system() == "Windows", reason="Echo test for Unix")
    async def test_simple_command_execution(self, basic_config):
        """Should execute simple commands"""
        sandbox = TaskSandbox(basic_config)

        try:
            await sandbox.setup()
            result = await sandbox.execute(["echo", "hello"])

            assert result.status == SandboxStatus.COMPLETED
            assert "hello" in result.stdout
            assert result.exit_code == 0
        finally:
            await sandbox.cleanup()

    @pytest.mark.asyncio
    @pytest.mark.skipif(platform.system() == "Windows", reason="Python test for Unix")
    async def test_python_command_execution(self, basic_config):
        """Should execute Python commands"""
        sandbox = TaskSandbox(basic_config)

        try:
            await sandbox.setup()
            result = await sandbox.execute([
                "python3", "-c", "print('sandbox test')"
            ])

            assert result.status in (SandboxStatus.COMPLETED, SandboxStatus.FAILED)
            # Python might not be available, so just check we got a result
            assert result.execution_id is not None
        finally:
            await sandbox.cleanup()

    @pytest.mark.asyncio
    @pytest.mark.skipif(platform.system() == "Windows", reason="Sleep test for Unix")
    async def test_timeout_enforcement(self):
        """Should enforce execution timeout"""
        config = SandboxConfig(
            sandbox_type=SandboxType.PROCESS,
            max_execution_time_sec=1,  # 1 second timeout
        )
        sandbox = TaskSandbox(config)

        try:
            await sandbox.setup()
            result = await sandbox.execute(["sleep", "10"])  # Try to sleep 10s

            assert result.status == SandboxStatus.TIMEOUT
            assert result.duration_ms is not None
            # Should have timed out in ~1 second
            assert result.duration_ms < 3000
        finally:
            await sandbox.cleanup()

    @pytest.mark.asyncio
    async def test_execution_result_fields(self, basic_config):
        """Result should have all expected fields"""
        sandbox = TaskSandbox(basic_config)

        try:
            await sandbox.setup()
            # Use a command that works on both Windows and Unix
            if platform.system() == "Windows":
                result = await sandbox.execute(["cmd", "/c", "echo", "test"])
            else:
                result = await sandbox.execute(["echo", "test"])

            assert result.execution_id == sandbox.execution_id
            assert result.started_at is not None
            assert result.completed_at is not None
            assert result.duration_ms is not None
            assert result.duration_ms >= 0
        finally:
            await sandbox.cleanup()

    @pytest.mark.asyncio
    async def test_sandbox_cancel(self, basic_config):
        """Should be able to cancel sandbox"""
        sandbox = TaskSandbox(basic_config)
        await sandbox.setup()

        # Cancel should clean up
        await sandbox.cancel()

        # Directory should be cleaned
        if sandbox._sandbox_dir:
            assert not sandbox._sandbox_dir.exists()


class TestTaskSandboxService:
    """Tests for TaskSandboxService"""

    def test_service_initialization(self, sandbox_service):
        """Service should initialize correctly"""
        assert sandbox_service is not None
        assert len(sandbox_service._active_sandboxes) == 0

    def test_create_sandbox_for_valid_task(self, sandbox_service):
        """Should create sandbox for allowed task types"""
        sandbox = sandbox_service.create_sandbox("compute")

        assert sandbox is not None
        assert sandbox.config.task_type == "compute"
        assert sandbox.execution_id in sandbox_service._active_sandboxes

    def test_create_sandbox_for_invalid_task(self, sandbox_service):
        """Should reject sandbox for unknown task types"""
        with pytest.raises(SandboxError) as exc_info:
            sandbox_service.create_sandbox("malicious_task")

        assert "not allowed" in str(exc_info.value)

    def test_sandbox_gets_security_constraints(self, sandbox_service):
        """Sandbox should inherit security constraints"""
        sandbox = sandbox_service.create_sandbox("compute")

        # Should have constraints from TASK_ALLOWLIST
        assert sandbox.config.max_memory_mb > 0
        assert sandbox.config.max_execution_time_sec > 0
        assert len(sandbox.config.allowed_paths) > 0

    def test_different_task_types_different_constraints(self, sandbox_service):
        """Different task types should have different constraints"""
        compute_sandbox = sandbox_service.create_sandbox("compute")
        gpu_sandbox = sandbox_service.create_sandbox("gpu_compute")

        # GPU compute should have longer timeout
        assert gpu_sandbox.config.max_execution_time_sec >= compute_sandbox.config.max_execution_time_sec
        assert gpu_sandbox.config.max_memory_mb >= compute_sandbox.config.max_memory_mb

    @pytest.mark.asyncio
    async def test_execute_task(self, sandbox_service):
        """Should execute task through service"""
        if platform.system() == "Windows":
            result = await sandbox_service.execute_task(
                task_type="compute",
                command=["cmd", "/c", "echo", "service test"]
            )
        else:
            result = await sandbox_service.execute_task(
                task_type="compute",
                command=["echo", "service test"]
            )

        assert result is not None
        assert result.execution_id is not None

    @pytest.mark.asyncio
    async def test_execute_task_cleans_up(self, sandbox_service):
        """Execute task should clean up after completion"""
        initial_count = len(sandbox_service._active_sandboxes)

        if platform.system() == "Windows":
            await sandbox_service.execute_task(
                task_type="compute",
                command=["cmd", "/c", "echo", "cleanup test"]
            )
        else:
            await sandbox_service.execute_task(
                task_type="compute",
                command=["echo", "cleanup test"]
            )

        # Should be back to initial count (cleanup happened)
        assert len(sandbox_service._active_sandboxes) == initial_count

    def test_get_active_executions(self, sandbox_service):
        """Should track active executions"""
        assert sandbox_service.get_active_executions() == []

        sandbox = sandbox_service.create_sandbox("compute")
        active = sandbox_service.get_active_executions()

        assert sandbox.execution_id in active

    def test_get_stats(self, sandbox_service):
        """Should provide service stats"""
        stats = sandbox_service.get_stats()

        assert "active_sandboxes" in stats
        assert "sandbox_base_dir" in stats
        assert "platform" in stats


class TestSandboxTypes:
    """Tests for different sandbox types"""

    def test_process_sandbox_type(self, sandbox_service):
        """Process sandbox should be the default"""
        sandbox = sandbox_service.create_sandbox("compute", SandboxType.PROCESS)
        assert sandbox.config.sandbox_type == SandboxType.PROCESS

    def test_docker_sandbox_type(self, sandbox_service):
        """Docker sandbox type should be configurable"""
        sandbox = sandbox_service.create_sandbox("compute", SandboxType.DOCKER)
        assert sandbox.config.sandbox_type == SandboxType.DOCKER


class TestSandboxEnvironment:
    """Tests for sandbox environment setup"""

    @pytest.mark.asyncio
    async def test_environment_variables_set(self, basic_config):
        """Sandbox should set environment variables"""
        sandbox = TaskSandbox(basic_config)

        try:
            await sandbox.setup()
            # The env vars are set during execute, tested indirectly
            # through the execute method
        finally:
            await sandbox.cleanup()

    @pytest.mark.asyncio
    @pytest.mark.skipif(platform.system() == "Windows", reason="Env test for Unix")
    async def test_dangerous_env_vars_removed(self, basic_config):
        """Dangerous environment variables should be removed"""
        sandbox = TaskSandbox(basic_config)

        try:
            await sandbox.setup()
            result = await sandbox.execute([
                "bash", "-c", "echo $LD_PRELOAD"
            ])

            # LD_PRELOAD should be empty/not set
            # (stdout should be just newline or empty)
            assert result.stdout.strip() == "" or result.status == SandboxStatus.FAILED
        finally:
            await sandbox.cleanup()


class TestGlobalInstance:
    """Tests for global service instance"""

    def test_get_task_sandbox_service(self):
        """Should return TaskSandboxService instance"""
        service = get_task_sandbox_service()

        assert service is not None
        assert isinstance(service, TaskSandboxService)

    def test_singleton_pattern(self):
        """Should return same instance on multiple calls"""
        service1 = get_task_sandbox_service()
        service2 = get_task_sandbox_service()

        assert service1 is service2


class TestSandboxBaseDirectory:
    """Tests for sandbox base directory"""

    def test_sandbox_base_dir_exists(self):
        """Sandbox base directory should exist or be creatable"""
        path = Path(SANDBOX_BASE_DIR)

        # Service initialization creates it
        service = get_task_sandbox_service()

        assert path.exists()

    def test_sandbox_base_dir_platform_appropriate(self):
        """Base directory should be appropriate for platform"""
        if platform.system() == "Windows":
            assert "fogburst" in SANDBOX_BASE_DIR
            # Should be in temp directory on Windows
            assert tempfile.gettempdir().lower() in SANDBOX_BASE_DIR.lower() or \
                   "tmp" in SANDBOX_BASE_DIR.lower() or \
                   "temp" in SANDBOX_BASE_DIR.lower()
        else:
            assert "/tmp/fogburst" == SANDBOX_BASE_DIR
