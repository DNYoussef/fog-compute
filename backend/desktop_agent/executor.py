"""
Task Executor for Desktop Agent
Sandboxed task execution integration

PHASE3-AGENT-002: Sandboxed Task Execution
- Agent runs tasks in subprocess with ulimit constraints
- Isolated /tmp/fogburst working directory
- No network except coordinator callback
- Integrates with PHASE2-TASK-001 TaskSandbox
"""
import asyncio
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from pathlib import Path
from typing import Optional, Any, Callable, Awaitable

# Add parent path to allow imports from server.services
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.services.task_sandbox import (
    TaskSandbox,
    TaskSandboxService,
    SandboxConfig,
    SandboxType,
    SandboxStatus,
    SandboxResult,
    SandboxError,
    SANDBOX_BASE_DIR,
)
from server.services.task_security import (
    TaskSecurityService,
    TaskSecurityConstraints,
    get_task_security_service,
)

logger = logging.getLogger(__name__)


class ExecutionStatus(str, Enum):
    """Status of task execution"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    REJECTED = "rejected"  # Task rejected due to resource limits


@dataclass
class ExecutionResult:
    """
    Result of task execution.

    PHASE3-AGENT-002: Execution result with sandbox details.
    """
    execution_id: str
    command_id: str
    status: ExecutionStatus
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    result_data: Optional[Any] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    resource_usage: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "execution_id": self.execution_id,
            "command_id": self.command_id,
            "status": self.status.value,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "result_data": self.result_data,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "resource_usage": self.resource_usage,
        }


@dataclass
class TaskAssignment:
    """Task assigned to this agent"""
    command_id: str
    task_type: str
    command: list[str]
    input_data: Optional[bytes] = None
    env: Optional[dict[str, str]] = None
    timeout_sec: Optional[int] = None
    required_memory_mb: float = 0
    required_cpu_percent: float = 0


class TaskExecutor:
    """
    Executes tasks in sandboxed environment.

    PHASE3-AGENT-002: Sandboxed Task Execution.
    Integrates with TaskSandboxService from PHASE2-TASK-001.
    """

    def __init__(
        self,
        allowed_task_types: Optional[list[str]] = None,
        max_concurrent_tasks: int = 2,
        callback_url: Optional[str] = None,
        on_task_complete: Optional[Callable[[ExecutionResult], Awaitable[None]]] = None,
    ):
        """
        Initialize task executor.

        Args:
            allowed_task_types: Task types this agent can execute
            max_concurrent_tasks: Maximum concurrent tasks
            callback_url: Coordinator URL for result callbacks
            on_task_complete: Callback when task completes
        """
        self.allowed_task_types = allowed_task_types or ["compute"]
        self.max_concurrent_tasks = max_concurrent_tasks
        self.callback_url = callback_url
        self._on_task_complete = on_task_complete

        # Initialize sandbox service
        self._sandbox_service = TaskSandboxService()
        self._security_service = get_task_security_service()

        # Track active executions
        self._active_executions: dict[str, asyncio.Task] = {}
        self._execution_results: dict[str, ExecutionResult] = {}
        self._execution_lock = asyncio.Lock()

        # Statistics
        self._stats = {
            "total_executions": 0,
            "successful": 0,
            "failed": 0,
            "timeouts": 0,
            "rejected": 0,
        }

        logger.info(
            f"TaskExecutor initialized: "
            f"task_types={allowed_task_types}, "
            f"max_concurrent={max_concurrent_tasks}"
        )

    def can_accept_task(self, task: TaskAssignment) -> tuple[bool, str]:
        """
        Check if executor can accept a task.

        PHASE3-AGENT-002: Pre-execution validation.

        Args:
            task: Task assignment to check

        Returns:
            Tuple of (can_accept, reason)
        """
        # Check task type
        if task.task_type not in self.allowed_task_types:
            return False, f"Task type '{task.task_type}' not in allowed types: {self.allowed_task_types}"

        # Check security allowlist
        if not self._security_service.is_task_type_allowed(task.task_type):
            return False, f"Task type '{task.task_type}' not in security allowlist"

        # Check concurrent task limit
        if len(self._active_executions) >= self.max_concurrent_tasks:
            return False, f"At max concurrent tasks: {self.max_concurrent_tasks}"

        return True, "Task accepted"

    async def execute_task(self, task: TaskAssignment) -> ExecutionResult:
        """
        Execute a task in sandbox.

        PHASE3-AGENT-002: Main execution entry point.

        Args:
            task: Task assignment

        Returns:
            Execution result
        """
        # Validate task
        can_accept, reason = self.can_accept_task(task)
        if not can_accept:
            result = ExecutionResult(
                execution_id=f"rejected-{task.command_id}",
                command_id=task.command_id,
                status=ExecutionStatus.REJECTED,
                error_message=reason,
            )
            self._stats["rejected"] += 1
            return result

        # Create sandbox
        try:
            sandbox = self._sandbox_service.create_sandbox(
                task.task_type,
                SandboxType.PROCESS
            )
        except SandboxError as e:
            result = ExecutionResult(
                execution_id=f"error-{task.command_id}",
                command_id=task.command_id,
                status=ExecutionStatus.FAILED,
                error_message=f"Sandbox creation failed: {e}",
            )
            self._stats["failed"] += 1
            return result

        execution_id = sandbox.execution_id
        self._stats["total_executions"] += 1

        # Start execution
        result = ExecutionResult(
            execution_id=execution_id,
            command_id=task.command_id,
            status=ExecutionStatus.PENDING,
        )
        self._execution_results[execution_id] = result

        # Run in sandbox
        try:
            async with self._execution_lock:
                self._active_executions[execution_id] = asyncio.current_task()

            result.status = ExecutionStatus.RUNNING
            result.started_at = datetime.now(UTC)

            # Set up sandbox
            await sandbox.setup()

            # Build environment with coordinator callback
            env = task.env.copy() if task.env else {}
            if self.callback_url:
                env["FOGBURST_CALLBACK_URL"] = self.callback_url
            env["FOGBURST_COMMAND_ID"] = task.command_id

            # Execute in sandbox
            sandbox_result = await sandbox.execute(
                command=task.command,
                stdin_data=task.input_data,
                env=env,
            )

            # Map sandbox result to execution result
            result.exit_code = sandbox_result.exit_code
            result.stdout = sandbox_result.stdout
            result.stderr = sandbox_result.stderr
            result.completed_at = sandbox_result.completed_at
            result.duration_ms = sandbox_result.duration_ms
            result.resource_usage = sandbox_result.resource_usage

            if sandbox_result.status == SandboxStatus.COMPLETED:
                result.status = ExecutionStatus.COMPLETED
                self._stats["successful"] += 1
            elif sandbox_result.status == SandboxStatus.TIMEOUT:
                result.status = ExecutionStatus.TIMEOUT
                result.error_message = sandbox_result.error_message
                self._stats["timeouts"] += 1
            else:
                result.status = ExecutionStatus.FAILED
                result.error_message = sandbox_result.error_message
                self._stats["failed"] += 1

        except asyncio.CancelledError:
            result.status = ExecutionStatus.CANCELLED
            result.error_message = "Execution cancelled"
            result.completed_at = datetime.now(UTC)
            logger.info(f"Execution {execution_id} cancelled")

        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error_message = str(e)
            result.completed_at = datetime.now(UTC)
            self._stats["failed"] += 1
            logger.error(f"Execution {execution_id} error: {e}")

        finally:
            # Clean up
            try:
                await sandbox.cleanup()
            except Exception as e:
                logger.warning(f"Sandbox cleanup error: {e}")

            async with self._execution_lock:
                self._active_executions.pop(execution_id, None)

        # Trigger callback
        if self._on_task_complete:
            try:
                await self._on_task_complete(result)
            except Exception as e:
                logger.error(f"Task complete callback error: {e}")

        return result

    async def cancel_execution(self, execution_id: str) -> bool:
        """
        Cancel a running execution.

        Args:
            execution_id: Execution to cancel

        Returns:
            True if cancelled
        """
        async with self._execution_lock:
            task = self._active_executions.get(execution_id)
            if task:
                task.cancel()
                logger.info(f"Cancelled execution {execution_id}")
                return True
        return False

    async def cancel_all(self) -> int:
        """
        Cancel all running executions.

        Returns:
            Number of executions cancelled
        """
        async with self._execution_lock:
            count = len(self._active_executions)
            for task in self._active_executions.values():
                task.cancel()

        logger.info(f"Cancelled {count} executions")
        return count

    def get_active_executions(self) -> list[str]:
        """Get list of active execution IDs."""
        return list(self._active_executions.keys())

    def get_execution_result(self, execution_id: str) -> Optional[ExecutionResult]:
        """Get result for an execution."""
        return self._execution_results.get(execution_id)

    def get_stats(self) -> dict[str, Any]:
        """Get executor statistics."""
        return {
            "total_executions": self._stats["total_executions"],
            "successful": self._stats["successful"],
            "failed": self._stats["failed"],
            "timeouts": self._stats["timeouts"],
            "rejected": self._stats["rejected"],
            "active_executions": len(self._active_executions),
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "allowed_task_types": self.allowed_task_types,
        }

    def cleanup_old_results(self, max_results: int = 1000) -> int:
        """
        Clean up old execution results to prevent memory growth.

        Args:
            max_results: Maximum results to keep

        Returns:
            Number of results removed
        """
        if len(self._execution_results) <= max_results:
            return 0

        # Sort by completion time and remove oldest
        sorted_results = sorted(
            self._execution_results.items(),
            key=lambda x: x[1].completed_at or datetime.min.replace(tzinfo=UTC),
            reverse=True
        )

        to_keep = dict(sorted_results[:max_results])
        removed = len(self._execution_results) - len(to_keep)

        self._execution_results = to_keep
        logger.debug(f"Cleaned up {removed} old execution results")

        return removed


class TaskQueue:
    """
    Simple task queue for managing pending tasks.

    PHASE3-AGENT-002: Task queue for handling multiple assignments.
    """

    def __init__(self, max_size: int = 100):
        """Initialize task queue."""
        self.max_size = max_size
        self._queue: asyncio.Queue[TaskAssignment] = asyncio.Queue(maxsize=max_size)
        self._pending_count = 0

    async def enqueue(self, task: TaskAssignment) -> bool:
        """
        Add task to queue.

        Returns:
            True if added, False if queue full
        """
        try:
            self._queue.put_nowait(task)
            self._pending_count += 1
            return True
        except asyncio.QueueFull:
            return False

    async def dequeue(self) -> TaskAssignment:
        """Get next task from queue (blocks if empty)."""
        task = await self._queue.get()
        self._pending_count -= 1
        return task

    def pending_count(self) -> int:
        """Get number of pending tasks."""
        return self._pending_count

    def is_full(self) -> bool:
        """Check if queue is full."""
        return self._pending_count >= self.max_size

    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return self._pending_count == 0
