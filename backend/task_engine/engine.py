"""
Task Engine
FOGBURST-004: Main task execution engine

Orchestrates task handlers, manages queue, and reports to coordinator.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Optional, Any, Callable, Awaitable
from collections import deque

from .runner import TaskRunner, TaskSpec, TaskResult, TaskStatus
from .handlers import get_handler, TaskHandler, HANDLERS

logger = logging.getLogger(__name__)


@dataclass
class EngineConfig:
    """
    Task engine configuration.

    FOGBURST-004: Configurable engine settings.
    """
    # Concurrency
    max_concurrent_tasks: int = 4
    default_timeout_sec: int = 300

    # Queue settings
    max_queue_size: int = 100
    enable_priority_queue: bool = True

    # Coordinator connection
    coordinator_url: Optional[str] = None
    report_results: bool = True
    report_interval_sec: float = 5.0

    # Resource limits
    max_memory_percent: float = 80.0
    max_cpu_percent: float = 90.0
    pause_on_overload: bool = True


class TaskEngine:
    """
    Main task execution engine.

    FOGBURST-004: Orchestrates task execution for the agent.

    Features:
    - Priority queue for tasks
    - Concurrent execution with limits
    - Handler-based task routing
    - Result reporting to coordinator
    """

    def __init__(
        self,
        config: Optional[EngineConfig] = None,
        on_result: Optional[Callable[[TaskResult], Awaitable[None]]] = None,
    ):
        """
        Initialize task engine.

        Args:
            config: Engine configuration
            on_result: Callback for task results
        """
        self.config = config or EngineConfig()
        self._on_result = on_result

        # Task runner
        self._runner = TaskRunner(
            default_timeout_sec=self.config.default_timeout_sec,
            max_concurrent=self.config.max_concurrent_tasks,
            on_task_complete=self._handle_task_complete,
        )

        # Task queue (priority queue as list of tuples: (priority, timestamp, spec))
        self._task_queue: deque[TaskSpec] = deque(maxlen=self.config.max_queue_size)
        self._pending_results: list[TaskResult] = []

        # State
        self._is_running = False
        self._is_paused = False
        self._process_task: Optional[asyncio.Task] = None

        # Statistics
        self._stats = {
            "tasks_queued": 0,
            "tasks_processed": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "queue_rejections": 0,
        }

        logger.info(
            f"TaskEngine initialized: "
            f"max_concurrent={self.config.max_concurrent_tasks}, "
            f"max_queue={self.config.max_queue_size}"
        )

    async def start(self) -> None:
        """Start the task engine."""
        if self._is_running:
            return

        self._is_running = True
        self._process_task = asyncio.create_task(self._process_loop())
        logger.info("TaskEngine started")

    async def stop(self) -> None:
        """Stop the task engine."""
        self._is_running = False

        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass

        logger.info("TaskEngine stopped")

    def pause(self) -> None:
        """Pause task processing."""
        self._is_paused = True
        logger.info("TaskEngine paused")

    def resume(self) -> None:
        """Resume task processing."""
        self._is_paused = False
        logger.info("TaskEngine resumed")

    def submit(self, spec: TaskSpec) -> bool:
        """
        Submit a task for execution.

        Args:
            spec: Task specification

        Returns:
            True if queued successfully
        """
        if len(self._task_queue) >= self.config.max_queue_size:
            logger.warning(f"Queue full, rejecting task {spec.task_id}")
            self._stats["queue_rejections"] += 1
            return False

        self._task_queue.append(spec)
        self._stats["tasks_queued"] += 1

        logger.debug(f"Task queued: {spec.task_id} ({spec.task_type})")
        return True

    async def execute_immediate(self, spec: TaskSpec) -> TaskResult:
        """
        Execute a task immediately, bypassing queue.

        Args:
            spec: Task specification

        Returns:
            Task result
        """
        return await self._execute_task(spec)

    async def _process_loop(self) -> None:
        """Main processing loop."""
        while self._is_running:
            try:
                if self._is_paused or not self._task_queue:
                    await asyncio.sleep(0.1)
                    continue

                # Get next task
                spec = self._task_queue.popleft()
                self._stats["tasks_processed"] += 1

                # Execute task
                asyncio.create_task(self._execute_task(spec))

                # Small delay to prevent tight loop
                await asyncio.sleep(0.01)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Process loop error: {e}")
                await asyncio.sleep(1)

    async def _execute_task(self, spec: TaskSpec) -> TaskResult:
        """Execute a task using appropriate handler."""
        # Try to get specialized handler
        handler = get_handler(spec.task_type)

        if handler:
            result = await handler.execute(spec)
        else:
            # Fall back to runner
            result = await self._runner.execute(spec)

        # Update stats
        if result.status == TaskStatus.COMPLETED:
            self._stats["tasks_completed"] += 1
        else:
            self._stats["tasks_failed"] += 1

        # Call result callback
        await self._handle_task_complete(result)

        return result

    async def _handle_task_complete(self, result: TaskResult) -> None:
        """Handle task completion."""
        self._pending_results.append(result)

        if self._on_result:
            try:
                await self._on_result(result)
            except Exception as e:
                logger.error(f"Result callback failed: {e}")

    def get_queue_size(self) -> int:
        """Get current queue size."""
        return len(self._task_queue)

    def get_pending_results(self) -> list[TaskResult]:
        """Get and clear pending results."""
        results = self._pending_results.copy()
        self._pending_results.clear()
        return results

    def get_stats(self) -> dict[str, Any]:
        """Get engine statistics."""
        runner_stats = self._runner.get_stats()

        return {
            "is_running": self._is_running,
            "is_paused": self._is_paused,
            "queue_size": len(self._task_queue),
            "max_queue_size": self.config.max_queue_size,
            "pending_results": len(self._pending_results),
            "tasks_queued": self._stats["tasks_queued"],
            "tasks_processed": self._stats["tasks_processed"],
            "tasks_completed": self._stats["tasks_completed"],
            "tasks_failed": self._stats["tasks_failed"],
            "queue_rejections": self._stats["queue_rejections"],
            "runner": runner_stats,
            "available_handlers": list(HANDLERS.keys()),
        }

    def get_available_task_types(self) -> list[str]:
        """Get list of supported task types."""
        return list(HANDLERS.keys())

    @property
    def is_running(self) -> bool:
        """Check if engine is running."""
        return self._is_running

    @property
    def is_paused(self) -> bool:
        """Check if engine is paused."""
        return self._is_paused
