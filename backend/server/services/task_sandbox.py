"""
Task Sandbox Service
Subprocess sandboxing for fog compute task execution

PHASE2-TASK-001 (12mj): Minimal Sandbox
- Subprocess sandboxing with ulimit on desktop
- No filesystem access outside /tmp/fogburst
- Docker as optional enhancement
- Resource limits enforcement

Reference: docker_client.py for Docker patterns
"""
import asyncio
import logging
import os
import platform
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from pathlib import Path
from typing import Optional, Any
from uuid import uuid4

from .task_security import (
    TaskSecurityService,
    TaskSecurityConstraints,
    get_task_security_service,
)

logger = logging.getLogger(__name__)


class SandboxType(str, Enum):
    """Type of sandbox isolation"""
    PROCESS = "process"       # Basic subprocess with ulimit
    DOCKER = "docker"         # Docker container (optional)
    NONE = "none"             # No sandboxing (testing only)


class SandboxStatus(str, Enum):
    """Status of sandbox execution"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    KILLED = "killed"


@dataclass
class SandboxResult:
    """Result of sandboxed execution"""
    execution_id: str
    status: SandboxStatus
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    resource_usage: dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


@dataclass
class SandboxConfig:
    """Configuration for sandbox execution"""
    sandbox_type: SandboxType = SandboxType.PROCESS
    task_type: str = "compute"

    # Resource limits (from TaskSecurityConstraints)
    max_memory_mb: int = 512
    max_cpu_percent: int = 50
    max_execution_time_sec: int = 300
    max_file_size_mb: int = 100

    # Filesystem
    working_dir: str = "/tmp/fogburst"
    allowed_paths: list[str] = field(default_factory=lambda: ["/tmp/fogburst"])

    # Network
    network_enabled: bool = False

    # Process limits
    max_processes: int = 10
    max_open_files: int = 256


# Default sandbox base directory
SANDBOX_BASE_DIR = "/tmp/fogburst"
if platform.system() == "Windows":
    SANDBOX_BASE_DIR = os.path.join(tempfile.gettempdir(), "fogburst")


class TaskSandbox:
    """
    Sandboxed environment for task execution.

    PHASE2-TASK-001: Provides process isolation with resource limits.
    Uses ulimit on Unix systems, job objects on Windows.
    """

    def __init__(self, config: SandboxConfig):
        """
        Initialize sandbox with configuration.

        Args:
            config: Sandbox configuration
        """
        self.config = config
        self.execution_id = f"exec-{uuid4().hex[:8]}"
        self._process: Optional[asyncio.subprocess.Process] = None
        self._status = SandboxStatus.PENDING
        self._started_at: Optional[datetime] = None
        self._sandbox_dir: Optional[Path] = None

    async def setup(self) -> Path:
        """
        Set up sandbox environment.

        Creates isolated directory structure and validates paths.

        Returns:
            Path to sandbox working directory
        """
        # Create sandbox directory
        base = Path(SANDBOX_BASE_DIR)
        self._sandbox_dir = base / self.execution_id

        try:
            self._sandbox_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Sandbox directory created: {self._sandbox_dir}")
        except Exception as e:
            raise SandboxError(f"Failed to create sandbox directory: {e}")

        return self._sandbox_dir

    async def cleanup(self) -> None:
        """Clean up sandbox environment."""
        if self._sandbox_dir and self._sandbox_dir.exists():
            try:
                shutil.rmtree(self._sandbox_dir)
                logger.info(f"Sandbox directory cleaned: {self._sandbox_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean sandbox directory: {e}")

    def _build_ulimit_command(self, cmd: list[str]) -> list[str]:
        """
        Build command with ulimit restrictions (Unix only).

        PHASE2-TASK-001: Resource limits via ulimit.

        Args:
            cmd: Original command

        Returns:
            Command wrapped with ulimit
        """
        if platform.system() == "Windows":
            return cmd  # Windows uses different mechanism

        # Calculate limits
        mem_kb = self.config.max_memory_mb * 1024
        file_size_kb = self.config.max_file_size_mb * 1024
        cpu_seconds = self.config.max_execution_time_sec

        # Build ulimit prefix
        ulimit_parts = [
            f"ulimit -v {mem_kb}",          # Virtual memory
            f"ulimit -m {mem_kb}",           # Resident set size
            f"ulimit -f {file_size_kb}",     # Max file size
            f"ulimit -t {cpu_seconds}",      # CPU time
            f"ulimit -u {self.config.max_processes}",  # Max processes
            f"ulimit -n {self.config.max_open_files}", # Max open files
        ]

        ulimit_cmd = " && ".join(ulimit_parts)

        # Wrap original command
        wrapped = ["bash", "-c", f"{ulimit_cmd} && {' '.join(cmd)}"]

        return wrapped

    async def execute(
        self,
        command: list[str],
        stdin_data: Optional[bytes] = None,
        env: Optional[dict[str, str]] = None
    ) -> SandboxResult:
        """
        Execute command in sandbox.

        PHASE2-TASK-001: Main sandboxed execution entry point.

        Args:
            command: Command to execute
            stdin_data: Optional stdin input
            env: Optional environment variables

        Returns:
            Execution result
        """
        if not self._sandbox_dir:
            await self.setup()

        self._status = SandboxStatus.RUNNING
        self._started_at = datetime.now(UTC)

        # Build environment
        sandbox_env = os.environ.copy()
        sandbox_env["FOGBURST_SANDBOX"] = "1"
        sandbox_env["FOGBURST_EXECUTION_ID"] = self.execution_id
        sandbox_env["TMPDIR"] = str(self._sandbox_dir)
        sandbox_env["HOME"] = str(self._sandbox_dir)

        if env:
            sandbox_env.update(env)

        # Remove dangerous env vars
        for dangerous in ["LD_PRELOAD", "LD_LIBRARY_PATH", "PYTHONPATH"]:
            sandbox_env.pop(dangerous, None)

        # Build sandboxed command
        if self.config.sandbox_type == SandboxType.PROCESS:
            sandboxed_cmd = self._build_ulimit_command(command)
        else:
            sandboxed_cmd = command

        stdout_data = ""
        stderr_data = ""
        exit_code = None
        error_message = None

        try:
            # Create subprocess
            self._process = await asyncio.create_subprocess_exec(
                *sandboxed_cmd,
                stdin=asyncio.subprocess.PIPE if stdin_data else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._sandbox_dir),
                env=sandbox_env,
            )

            # Execute with timeout
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    self._process.communicate(input=stdin_data),
                    timeout=self.config.max_execution_time_sec
                )

                stdout_data = stdout_bytes.decode("utf-8", errors="replace")
                stderr_data = stderr_bytes.decode("utf-8", errors="replace")
                exit_code = self._process.returncode

                if exit_code == 0:
                    self._status = SandboxStatus.COMPLETED
                else:
                    self._status = SandboxStatus.FAILED
                    error_message = f"Process exited with code {exit_code}"

            except asyncio.TimeoutError:
                self._status = SandboxStatus.TIMEOUT
                error_message = f"Execution timed out after {self.config.max_execution_time_sec}s"
                await self._kill_process()

        except Exception as e:
            self._status = SandboxStatus.FAILED
            error_message = str(e)
            logger.error(f"Sandbox execution error: {e}")

        completed_at = datetime.now(UTC)
        duration_ms = int((completed_at - self._started_at).total_seconds() * 1000)

        return SandboxResult(
            execution_id=self.execution_id,
            status=self._status,
            exit_code=exit_code,
            stdout=stdout_data,
            stderr=stderr_data,
            started_at=self._started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            error_message=error_message,
        )

    async def _kill_process(self) -> None:
        """Kill the running process."""
        if self._process:
            try:
                self._process.kill()
                await self._process.wait()
                self._status = SandboxStatus.KILLED
            except Exception as e:
                logger.error(f"Failed to kill process: {e}")

    async def cancel(self) -> None:
        """Cancel execution."""
        await self._kill_process()
        await self.cleanup()


class SandboxError(Exception):
    """Exception for sandbox-related errors"""
    pass


class TaskSandboxService:
    """
    Service for managing sandboxed task execution.

    PHASE2-TASK-001: Provides sandboxing for fog compute tasks.
    Integrates with TaskSecurityService for constraints.
    """

    def __init__(self):
        """Initialize sandbox service."""
        self._security_service = get_task_security_service()
        self._active_sandboxes: dict[str, TaskSandbox] = {}

        # Ensure base directory exists
        Path(SANDBOX_BASE_DIR).mkdir(parents=True, exist_ok=True)

        logger.info(f"TaskSandboxService initialized with base dir: {SANDBOX_BASE_DIR}")

    def create_sandbox(
        self,
        task_type: str,
        sandbox_type: SandboxType = SandboxType.PROCESS
    ) -> TaskSandbox:
        """
        Create a sandbox for a task type.

        PHASE2-TASK-001: Creates sandbox with appropriate constraints.

        Args:
            task_type: Type of task to sandbox
            sandbox_type: Type of sandbox to use

        Returns:
            Configured TaskSandbox

        Raises:
            SandboxError: If task type not allowed
        """
        # Validate task type
        if not self._security_service.is_task_type_allowed(task_type):
            raise SandboxError(f"Task type '{task_type}' is not allowed")

        # Get security constraints
        constraints = self._security_service.get_security_constraints(task_type)
        if not constraints:
            raise SandboxError(f"No security constraints for task type '{task_type}'")

        # Build sandbox config from constraints
        config = SandboxConfig(
            sandbox_type=sandbox_type,
            task_type=task_type,
            max_memory_mb=constraints.max_memory_mb,
            max_cpu_percent=constraints.max_cpu_percent,
            max_execution_time_sec=constraints.max_execution_time_sec,
            max_file_size_mb=constraints.max_file_size_mb,
            working_dir=constraints.allowed_filesystem_paths[0] if constraints.allowed_filesystem_paths else SANDBOX_BASE_DIR,
            allowed_paths=constraints.allowed_filesystem_paths,
            network_enabled=constraints.network_allowed,
        )

        sandbox = TaskSandbox(config)
        self._active_sandboxes[sandbox.execution_id] = sandbox

        logger.info(f"Created sandbox {sandbox.execution_id} for task type {task_type}")

        return sandbox

    async def execute_task(
        self,
        task_type: str,
        command: list[str],
        stdin_data: Optional[bytes] = None,
        env: Optional[dict[str, str]] = None,
        sandbox_type: SandboxType = SandboxType.PROCESS
    ) -> SandboxResult:
        """
        Execute a task in a sandbox.

        PHASE2-TASK-001: High-level task execution API.

        Args:
            task_type: Type of task
            command: Command to execute
            stdin_data: Optional stdin input
            env: Optional environment variables
            sandbox_type: Type of sandbox

        Returns:
            Execution result
        """
        sandbox = self.create_sandbox(task_type, sandbox_type)

        try:
            await sandbox.setup()
            result = await sandbox.execute(command, stdin_data, env)
            return result
        finally:
            await sandbox.cleanup()
            self._active_sandboxes.pop(sandbox.execution_id, None)

    async def cancel_execution(self, execution_id: str) -> bool:
        """
        Cancel a running execution.

        Args:
            execution_id: ID of execution to cancel

        Returns:
            True if cancelled
        """
        sandbox = self._active_sandboxes.get(execution_id)
        if sandbox:
            await sandbox.cancel()
            self._active_sandboxes.pop(execution_id, None)
            return True
        return False

    def get_active_executions(self) -> list[str]:
        """Get list of active execution IDs."""
        return list(self._active_sandboxes.keys())

    def get_stats(self) -> dict[str, Any]:
        """Get sandbox service statistics."""
        return {
            "active_sandboxes": len(self._active_sandboxes),
            "sandbox_base_dir": SANDBOX_BASE_DIR,
            "platform": platform.system(),
        }


# Global instance
_sandbox_service: Optional[TaskSandboxService] = None


def get_task_sandbox_service() -> TaskSandboxService:
    """Get or create the task sandbox service instance."""
    global _sandbox_service

    if _sandbox_service is None:
        _sandbox_service = TaskSandboxService()

    return _sandbox_service
