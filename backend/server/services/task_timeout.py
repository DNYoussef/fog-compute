"""
Task Timeout Service
Coordinator-side timeout enforcement for fog compute tasks

PHASE2-TASK-004 (s74b): Timeout Enforcement
- Coordinator-side timeout for task execution
- Kill runaway tasks
- Return FAILED status with timeout reason
"""
import asyncio
import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC
from enum import Enum
from typing import Optional, Any, Callable, Awaitable
from uuid import uuid4

from .task_sandbox import TaskSandbox, SandboxStatus, get_task_sandbox_service
from .command_idempotency import (
    CommandIdempotencyService,
    CommandStatus,
    get_command_idempotency_service,
)
from .task_security import TaskSecurityService, get_task_security_service

logger = logging.getLogger(__name__)


class TaskExecutionStatus(str, Enum):
    """Status of task execution with timeout tracking"""
    QUEUED = "queued"           # Waiting to be executed
    RUNNING = "running"         # Currently executing
    COMPLETED = "completed"     # Successfully completed
    FAILED = "failed"           # Execution failed
    TIMEOUT = "timeout"         # Killed due to timeout
    CANCELLED = "cancelled"     # Manually cancelled


@dataclass
class TaskExecution:
    """Tracked task execution with timeout support"""
    execution_id: str
    command_id: str
    device_id: str
    task_type: str
    status: TaskExecutionStatus
    timeout_sec: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    deadline: Optional[datetime] = None
    result: Optional[Any] = None
    error_message: Optional[str] = None

    # Timeout tracking
    timeout_warned: bool = False
    extension_count: int = 0
    max_extensions: int = 2

    # Sandbox reference
    sandbox: Optional[TaskSandbox] = None


@dataclass
class TimeoutResult:
    """Result of timeout check or enforcement"""
    execution_id: str
    timed_out: bool
    status: TaskExecutionStatus
    message: str
    remaining_sec: Optional[int] = None


class TaskTimeoutService:
    """
    Service for enforcing task execution timeouts.

    PHASE2-TASK-004: Coordinator-side timeout enforcement.
    Integrates with TaskSandbox and CommandIdempotency services.
    """

    def __init__(
        self,
        default_timeout_sec: int = 300,
        check_interval_sec: int = 5,
        warning_threshold_percent: int = 80,
    ):
        """
        Initialize timeout service.

        Args:
            default_timeout_sec: Default timeout for tasks
            check_interval_sec: Interval for timeout checks
            warning_threshold_percent: Percentage of timeout to warn at
        """
        self.default_timeout_sec = default_timeout_sec
        self.check_interval_sec = check_interval_sec
        self.warning_threshold_percent = warning_threshold_percent

        self._executions: OrderedDict[str, TaskExecution] = OrderedDict()
        self._monitor_task: Optional[asyncio.Task] = None
        self._is_running = False

        # Callback for timeout notifications
        self._timeout_callback: Optional[Callable[[TaskExecution], Awaitable[None]]] = None

        # Service integrations
        self._sandbox_service = get_task_sandbox_service()
        self._idempotency_service = get_command_idempotency_service()
        self._security_service = get_task_security_service()

        # Statistics
        self._stats = {
            "total_executions": 0,
            "timeouts": 0,
            "completions": 0,
            "failures": 0,
            "extensions_granted": 0,
        }

        logger.info(
            f"TaskTimeoutService initialized: "
            f"default_timeout={default_timeout_sec}s, "
            f"check_interval={check_interval_sec}s"
        )

    def set_timeout_callback(
        self,
        callback: Callable[[TaskExecution], Awaitable[None]]
    ) -> None:
        """Set callback for timeout events."""
        self._timeout_callback = callback

    async def start(self) -> None:
        """Start background timeout monitoring."""
        if self._is_running:
            return

        self._is_running = True

        async def monitor_loop():
            while self._is_running:
                await asyncio.sleep(self.check_interval_sec)
                await self._check_timeouts()

        self._monitor_task = asyncio.create_task(monitor_loop())
        logger.info("Task timeout monitoring started")

    async def stop(self) -> None:
        """Stop background timeout monitoring."""
        self._is_running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Task timeout monitoring stopped")

    def register_execution(
        self,
        command_id: str,
        device_id: str,
        task_type: str,
        timeout_sec: Optional[int] = None,
    ) -> TaskExecution:
        """
        Register a new task execution for timeout tracking.

        PHASE2-TASK-004: Entry point for timeout tracking.

        Args:
            command_id: Command ID from idempotency service
            device_id: Device executing the task
            task_type: Type of task
            timeout_sec: Custom timeout (uses security constraints if None)

        Returns:
            TaskExecution record
        """
        # Get timeout from security constraints if not specified
        if timeout_sec is None:
            constraints = self._security_service.get_security_constraints(task_type)
            if constraints:
                timeout_sec = constraints.max_execution_time_sec
            else:
                timeout_sec = self.default_timeout_sec

        execution_id = f"texec-{uuid4().hex[:8]}"
        now = datetime.now(UTC)

        execution = TaskExecution(
            execution_id=execution_id,
            command_id=command_id,
            device_id=device_id,
            task_type=task_type,
            status=TaskExecutionStatus.QUEUED,
            timeout_sec=timeout_sec,
            created_at=now,
        )

        self._executions[execution_id] = execution
        self._stats["total_executions"] += 1

        logger.info(
            f"Registered execution {execution_id} for command {command_id}, "
            f"timeout={timeout_sec}s"
        )

        return execution

    def start_execution(self, execution_id: str) -> bool:
        """
        Mark execution as started and set deadline.

        PHASE2-TASK-004: Begins timeout countdown.

        Args:
            execution_id: Execution to start

        Returns:
            True if started successfully
        """
        execution = self._executions.get(execution_id)
        if not execution:
            return False

        if execution.status != TaskExecutionStatus.QUEUED:
            logger.warning(f"Cannot start execution {execution_id}: status is {execution.status}")
            return False

        now = datetime.now(UTC)
        execution.status = TaskExecutionStatus.RUNNING
        execution.started_at = now
        execution.deadline = now + timedelta(seconds=execution.timeout_sec)

        # Update idempotency service
        self._idempotency_service.mark_executing(execution.command_id)

        logger.debug(f"Execution {execution_id} started, deadline: {execution.deadline}")
        return True

    def complete_execution(
        self,
        execution_id: str,
        result: Any = None
    ) -> bool:
        """
        Mark execution as completed.

        Args:
            execution_id: Execution to complete
            result: Optional result data

        Returns:
            True if completed
        """
        execution = self._executions.get(execution_id)
        if not execution:
            return False

        execution.status = TaskExecutionStatus.COMPLETED
        execution.completed_at = datetime.now(UTC)
        execution.result = result

        # Update idempotency service
        self._idempotency_service.mark_completed(execution.command_id, result=result)

        self._stats["completions"] += 1
        logger.info(f"Execution {execution_id} completed successfully")

        return True

    def fail_execution(
        self,
        execution_id: str,
        error_message: str
    ) -> bool:
        """
        Mark execution as failed.

        Args:
            execution_id: Execution to fail
            error_message: Error description

        Returns:
            True if marked failed
        """
        execution = self._executions.get(execution_id)
        if not execution:
            return False

        execution.status = TaskExecutionStatus.FAILED
        execution.completed_at = datetime.now(UTC)
        execution.error_message = error_message

        # Update idempotency service
        self._idempotency_service.mark_failed(execution.command_id, error_message)

        self._stats["failures"] += 1
        logger.warning(f"Execution {execution_id} failed: {error_message}")

        return True

    async def timeout_execution(self, execution_id: str) -> bool:
        """
        Mark execution as timed out and kill it.

        PHASE2-TASK-004: Timeout enforcement action.

        Args:
            execution_id: Execution to timeout

        Returns:
            True if timed out
        """
        execution = self._executions.get(execution_id)
        if not execution:
            return False

        if execution.status != TaskExecutionStatus.RUNNING:
            return False

        # Kill sandbox if active
        if execution.sandbox:
            await execution.sandbox.cancel()

        execution.status = TaskExecutionStatus.TIMEOUT
        execution.completed_at = datetime.now(UTC)
        execution.error_message = f"Task timed out after {execution.timeout_sec} seconds"

        # Update idempotency service
        self._idempotency_service.mark_failed(
            execution.command_id,
            execution.error_message
        )

        self._stats["timeouts"] += 1
        logger.warning(f"Execution {execution_id} timed out")

        # Trigger callback
        if self._timeout_callback:
            try:
                await self._timeout_callback(execution)
            except Exception as e:
                logger.error(f"Timeout callback error: {e}")

        return True

    def cancel_execution(self, execution_id: str) -> bool:
        """
        Cancel execution.

        Args:
            execution_id: Execution to cancel

        Returns:
            True if cancelled
        """
        execution = self._executions.get(execution_id)
        if not execution:
            return False

        if execution.status not in (TaskExecutionStatus.QUEUED, TaskExecutionStatus.RUNNING):
            return False

        execution.status = TaskExecutionStatus.CANCELLED
        execution.completed_at = datetime.now(UTC)
        execution.error_message = "Execution cancelled"

        logger.info(f"Execution {execution_id} cancelled")
        return True

    def extend_timeout(
        self,
        execution_id: str,
        additional_sec: int
    ) -> bool:
        """
        Extend timeout for an execution.

        Allows limited extensions for long-running tasks.

        Args:
            execution_id: Execution to extend
            additional_sec: Seconds to add

        Returns:
            True if extended
        """
        execution = self._executions.get(execution_id)
        if not execution:
            return False

        if execution.status != TaskExecutionStatus.RUNNING:
            return False

        if execution.extension_count >= execution.max_extensions:
            logger.warning(
                f"Cannot extend {execution_id}: max extensions reached "
                f"({execution.max_extensions})"
            )
            return False

        execution.deadline += timedelta(seconds=additional_sec)
        execution.timeout_sec += additional_sec
        execution.extension_count += 1

        # Also extend idempotency window
        self._idempotency_service.extend_dedupe_window(
            execution.command_id,
            additional_sec
        )

        self._stats["extensions_granted"] += 1
        logger.info(
            f"Extended {execution_id} by {additional_sec}s "
            f"(extension {execution.extension_count}/{execution.max_extensions})"
        )

        return True

    def check_timeout(self, execution_id: str) -> TimeoutResult:
        """
        Check if an execution has timed out.

        PHASE2-TASK-004: Point-in-time timeout check.

        Args:
            execution_id: Execution to check

        Returns:
            Timeout check result
        """
        execution = self._executions.get(execution_id)
        if not execution:
            return TimeoutResult(
                execution_id=execution_id,
                timed_out=False,
                status=TaskExecutionStatus.FAILED,
                message="Execution not found"
            )

        if execution.status != TaskExecutionStatus.RUNNING:
            return TimeoutResult(
                execution_id=execution_id,
                timed_out=False,
                status=execution.status,
                message=f"Execution not running: {execution.status.value}"
            )

        now = datetime.now(UTC)

        if execution.deadline and now >= execution.deadline:
            return TimeoutResult(
                execution_id=execution_id,
                timed_out=True,
                status=TaskExecutionStatus.TIMEOUT,
                message=f"Execution timed out (deadline: {execution.deadline})",
                remaining_sec=0
            )

        remaining = (execution.deadline - now).total_seconds() if execution.deadline else 0

        # Check warning threshold
        if execution.deadline and not execution.timeout_warned:
            warning_threshold = execution.timeout_sec * (self.warning_threshold_percent / 100)
            if remaining <= (execution.timeout_sec - warning_threshold):
                execution.timeout_warned = True
                logger.warning(
                    f"Execution {execution_id} approaching timeout: "
                    f"{int(remaining)}s remaining"
                )

        return TimeoutResult(
            execution_id=execution_id,
            timed_out=False,
            status=execution.status,
            message=f"Execution running, {int(remaining)}s remaining",
            remaining_sec=int(remaining)
        )

    async def _check_timeouts(self) -> None:
        """Background task to check and enforce timeouts."""
        now = datetime.now(UTC)
        timed_out = []

        for execution_id, execution in self._executions.items():
            if execution.status != TaskExecutionStatus.RUNNING:
                continue

            if execution.deadline and now >= execution.deadline:
                timed_out.append(execution_id)

        for execution_id in timed_out:
            await self.timeout_execution(execution_id)

    def get_execution(self, execution_id: str) -> Optional[TaskExecution]:
        """Get execution by ID."""
        return self._executions.get(execution_id)

    def get_execution_by_command(self, command_id: str) -> Optional[TaskExecution]:
        """Get execution by command ID."""
        for execution in self._executions.values():
            if execution.command_id == command_id:
                return execution
        return None

    def get_running_executions(self, device_id: Optional[str] = None) -> list[TaskExecution]:
        """Get all running executions, optionally filtered by device."""
        running = [
            e for e in self._executions.values()
            if e.status == TaskExecutionStatus.RUNNING
        ]

        if device_id:
            running = [e for e in running if e.device_id == device_id]

        return running

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        running_count = len([
            e for e in self._executions.values()
            if e.status == TaskExecutionStatus.RUNNING
        ])

        return {
            "total_executions": self._stats["total_executions"],
            "timeouts": self._stats["timeouts"],
            "completions": self._stats["completions"],
            "failures": self._stats["failures"],
            "extensions_granted": self._stats["extensions_granted"],
            "currently_running": running_count,
            "tracked_executions": len(self._executions),
            "default_timeout_sec": self.default_timeout_sec,
            "check_interval_sec": self.check_interval_sec,
        }

    def cleanup_completed(self, max_age_sec: int = 3600) -> int:
        """
        Remove completed executions older than max_age.

        Args:
            max_age_sec: Max age for completed executions

        Returns:
            Number of removed executions
        """
        now = datetime.now(UTC)
        cutoff = now - timedelta(seconds=max_age_sec)
        to_remove = []

        for execution_id, execution in self._executions.items():
            if execution.status in (
                TaskExecutionStatus.COMPLETED,
                TaskExecutionStatus.FAILED,
                TaskExecutionStatus.TIMEOUT,
                TaskExecutionStatus.CANCELLED,
            ):
                if execution.completed_at and execution.completed_at < cutoff:
                    to_remove.append(execution_id)

        for execution_id in to_remove:
            del self._executions[execution_id]

        if to_remove:
            logger.debug(f"Cleaned up {len(to_remove)} old executions")

        return len(to_remove)


# Global instance
_timeout_service: Optional[TaskTimeoutService] = None


def get_task_timeout_service() -> TaskTimeoutService:
    """Get or create the task timeout service instance."""
    global _timeout_service

    if _timeout_service is None:
        _timeout_service = TaskTimeoutService()

    return _timeout_service
