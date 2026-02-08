"""
Task Runner
FOGBURST-004: Core task execution logic

Executes tasks in isolated environment and reports results.
"""
import asyncio
import logging
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Optional, Any, Callable, Awaitable

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class TaskResult:
    """
    Result of task execution.

    FOGBURST-004: Standardized result format for all task types.
    """
    task_id: str
    status: TaskStatus
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    result_data: Optional[dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time_ms: int = 0
    error_message: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "result_data": self.result_data,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_time_ms": self.execution_time_ms,
            "error_message": self.error_message,
        }


@dataclass
class TaskSpec:
    """
    Task specification from coordinator.

    FOGBURST-004: What the coordinator sends to the agent.
    """
    task_id: str
    task_type: str
    command: Optional[str] = None
    script: Optional[str] = None
    payload: dict[str, Any] = field(default_factory=dict)
    timeout_sec: int = 300
    max_memory_mb: int = 512
    max_cpu_percent: int = 80
    priority: int = 5

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "command": self.command,
            "script": self.script,
            "payload": self.payload,
            "timeout_sec": self.timeout_sec,
            "max_memory_mb": self.max_memory_mb,
            "max_cpu_percent": self.max_cpu_percent,
            "priority": self.priority,
        }


class TaskRunner:
    """
    Executes tasks in isolated subprocess.

    FOGBURST-004: Main task execution component.

    Features:
    - Subprocess isolation
    - Timeout enforcement
    - Resource limits (when available)
    - Result capture
    """

    def __init__(
        self,
        default_timeout_sec: int = 300,
        max_concurrent: int = 4,
        on_task_complete: Optional[Callable[[TaskResult], Awaitable[None]]] = None,
    ):
        """
        Initialize task runner.

        Args:
            default_timeout_sec: Default timeout for tasks
            max_concurrent: Maximum concurrent tasks
            on_task_complete: Callback when task completes
        """
        self.default_timeout_sec = default_timeout_sec
        self.max_concurrent = max_concurrent
        self._on_task_complete = on_task_complete

        self._running_tasks: dict[str, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)

        # Statistics
        self._stats = {
            "total_executed": 0,
            "completed": 0,
            "failed": 0,
            "timeout": 0,
            "cancelled": 0,
        }

        logger.info(
            f"TaskRunner initialized: timeout={default_timeout_sec}s, "
            f"max_concurrent={max_concurrent}"
        )

    async def execute(self, spec: TaskSpec) -> TaskResult:
        """
        Execute a task.

        FOGBURST-004: Main entry point for task execution.

        Args:
            spec: Task specification

        Returns:
            Task result
        """
        async with self._semaphore:
            return await self._execute_task(spec)

    async def _execute_task(self, spec: TaskSpec) -> TaskResult:
        """Execute task with isolation and timeout."""
        self._stats["total_executed"] += 1
        start_time = datetime.now(UTC)

        result = TaskResult(
            task_id=spec.task_id,
            status=TaskStatus.RUNNING,
            started_at=start_time,
        )

        try:
            # Determine execution method
            if spec.command:
                result = await self._execute_command(spec, result)
            elif spec.script:
                result = await self._execute_script(spec, result)
            elif spec.task_type == "compute":
                result = await self._execute_compute(spec, result)
            elif spec.task_type == "benchmark":
                result = await self._execute_benchmark(spec, result)
            elif spec.task_type == "health_check":
                result = await self._execute_health_check(spec, result)
            else:
                result.status = TaskStatus.FAILED
                result.error_message = f"Unknown task type: {spec.task_type}"
                result.exit_code = 1

        except asyncio.TimeoutError:
            result.status = TaskStatus.TIMEOUT
            result.error_message = f"Task timed out after {spec.timeout_sec}s"
            result.exit_code = 124
            self._stats["timeout"] += 1

        except asyncio.CancelledError:
            result.status = TaskStatus.CANCELLED
            result.error_message = "Task was cancelled"
            result.exit_code = 125
            self._stats["cancelled"] += 1

        except Exception as e:
            result.status = TaskStatus.FAILED
            result.error_message = str(e)
            result.exit_code = 1
            self._stats["failed"] += 1
            logger.error(f"Task {spec.task_id} failed: {e}")

        # Finalize result
        result.completed_at = datetime.now(UTC)
        result.execution_time_ms = int(
            (result.completed_at - start_time).total_seconds() * 1000
        )

        if result.status == TaskStatus.RUNNING:
            result.status = TaskStatus.COMPLETED
            self._stats["completed"] += 1

        # Callback
        if self._on_task_complete:
            try:
                await self._on_task_complete(result)
            except Exception as e:
                logger.error(f"Task complete callback failed: {e}")

        return result

    async def _execute_command(
        self,
        spec: TaskSpec,
        result: TaskResult
    ) -> TaskResult:
        """Execute shell command."""
        timeout = spec.timeout_sec or self.default_timeout_sec

        try:
            proc = await asyncio.create_subprocess_shell(
                spec.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout
            )

            result.stdout = stdout.decode("utf-8", errors="replace")
            result.stderr = stderr.decode("utf-8", errors="replace")
            result.exit_code = proc.returncode or 0

            if proc.returncode != 0:
                result.status = TaskStatus.FAILED
                self._stats["failed"] += 1
            else:
                result.status = TaskStatus.COMPLETED
                self._stats["completed"] += 1

        except asyncio.TimeoutError:
            if proc:
                proc.kill()
            raise

        return result

    async def _execute_script(
        self,
        spec: TaskSpec,
        result: TaskResult
    ) -> TaskResult:
        """Execute Python script."""
        timeout = spec.timeout_sec or self.default_timeout_sec

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                spec.script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout
            )

            result.stdout = stdout.decode("utf-8", errors="replace")
            result.stderr = stderr.decode("utf-8", errors="replace")
            result.exit_code = proc.returncode or 0

            if proc.returncode != 0:
                result.status = TaskStatus.FAILED
                self._stats["failed"] += 1
            else:
                result.status = TaskStatus.COMPLETED
                self._stats["completed"] += 1

        except asyncio.TimeoutError:
            if proc:
                proc.kill()
            raise

        return result

    async def _execute_compute(
        self,
        spec: TaskSpec,
        result: TaskResult
    ) -> TaskResult:
        """
        Execute compute task.

        FOGBURST-004: Initial compute task support.
        """
        payload = spec.payload
        operation = payload.get("operation", "add")

        try:
            if operation == "add":
                a = payload.get("a", 0)
                b = payload.get("b", 0)
                computed = a + b
                result.result_data = {"result": computed, "operation": "add"}

            elif operation == "multiply":
                a = payload.get("a", 0)
                b = payload.get("b", 0)
                computed = a * b
                result.result_data = {"result": computed, "operation": "multiply"}

            elif operation == "factorial":
                n = payload.get("n", 1)
                computed = 1
                for i in range(2, n + 1):
                    computed *= i
                result.result_data = {"result": computed, "operation": "factorial"}

            elif operation == "fibonacci":
                n = payload.get("n", 10)
                a, b = 0, 1
                for _ in range(n):
                    a, b = b, a + b
                result.result_data = {"result": a, "operation": "fibonacci"}

            elif operation == "prime_check":
                n = payload.get("n", 2)
                is_prime = n > 1 and all(n % i != 0 for i in range(2, int(n**0.5) + 1))
                result.result_data = {"result": is_prime, "operation": "prime_check", "n": n}

            else:
                result.status = TaskStatus.FAILED
                result.error_message = f"Unknown compute operation: {operation}"
                return result

            result.status = TaskStatus.COMPLETED
            self._stats["completed"] += 1

        except Exception as e:
            result.status = TaskStatus.FAILED
            result.error_message = str(e)
            self._stats["failed"] += 1

        return result

    async def _execute_benchmark(
        self,
        spec: TaskSpec,
        result: TaskResult
    ) -> TaskResult:
        """Execute benchmark task for performance testing."""
        payload = spec.payload
        iterations = payload.get("iterations", 1000000)

        try:
            # Simple CPU benchmark
            start = time.perf_counter()
            total = 0
            for i in range(iterations):
                total += i * i
            elapsed = time.perf_counter() - start

            result.result_data = {
                "iterations": iterations,
                "elapsed_seconds": round(elapsed, 4),
                "operations_per_second": round(iterations / elapsed, 2),
                "checksum": total % (10**9 + 7),
            }
            result.status = TaskStatus.COMPLETED
            self._stats["completed"] += 1

        except Exception as e:
            result.status = TaskStatus.FAILED
            result.error_message = str(e)
            self._stats["failed"] += 1

        return result

    async def _execute_health_check(
        self,
        spec: TaskSpec,
        result: TaskResult
    ) -> TaskResult:
        """Execute health check task."""
        import platform

        try:
            result.result_data = {
                "status": "healthy",
                "platform": platform.system(),
                "python_version": platform.python_version(),
                "timestamp": datetime.now(UTC).isoformat(),
            }
            result.status = TaskStatus.COMPLETED
            self._stats["completed"] += 1

        except Exception as e:
            result.status = TaskStatus.FAILED
            result.error_message = str(e)
            self._stats["failed"] += 1

        return result

    async def cancel(self, task_id: str) -> bool:
        """Cancel a running task."""
        if task_id in self._running_tasks:
            self._running_tasks[task_id].cancel()
            return True
        return False

    def get_stats(self) -> dict[str, Any]:
        """Get runner statistics."""
        return {
            "total_executed": self._stats["total_executed"],
            "completed": self._stats["completed"],
            "failed": self._stats["failed"],
            "timeout": self._stats["timeout"],
            "cancelled": self._stats["cancelled"],
            "running": len(self._running_tasks),
            "max_concurrent": self.max_concurrent,
        }
