"""
Task Distributor
FOG-006: Intelligent task distribution across fog nodes

Implements load balancing strategies for distributing pipeline tasks.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Optional, Any, Protocol
from abc import ABC, abstractmethod

from .models import PipelineTask, PipelineStage, StageStatus

logger = logging.getLogger(__name__)


class DistributionStrategy(str, Enum):
    """Task distribution strategies."""
    ROUND_ROBIN = "round_robin"       # Simple rotation
    LEAST_LOADED = "least_loaded"     # Lowest current load
    BEST_FIT = "best_fit"             # Best matching capabilities
    RANDOM = "random"                  # Random selection
    LOCALITY = "locality"              # Prefer same region
    REPUTATION = "reputation"          # Highest reputation score


@dataclass
class DeviceMetrics:
    """
    Metrics for a fog node.

    FOG-006: Tracks load and availability for distribution decisions.
    """
    device_id: str
    device_type: str = "desktop"
    region: Optional[str] = None

    # Current load
    cpu_usage_percent: float = 0.0
    memory_usage_percent: float = 0.0
    active_tasks: int = 0
    max_concurrent_tasks: int = 5

    # Capabilities
    cpu_cores: int = 1
    memory_mb: int = 512
    gpu_available: bool = False
    capabilities: list[str] = field(default_factory=list)

    # Performance metrics
    reputation_score: float = 1.0
    avg_task_time_ms: float = 1000.0
    success_rate: float = 1.0
    tasks_completed: int = 0

    # Status
    last_heartbeat: Optional[datetime] = None
    is_available: bool = True

    def get_load_score(self) -> float:
        """
        Calculate normalized load score (0-1, lower is better).

        Considers CPU, memory, and task count.
        """
        cpu_load = self.cpu_usage_percent / 100
        mem_load = self.memory_usage_percent / 100
        task_load = self.active_tasks / max(self.max_concurrent_tasks, 1)

        # Weighted average
        return (cpu_load * 0.4 + mem_load * 0.3 + task_load * 0.3)

    def get_fitness_score(
        self,
        required_cpu: int = 1,
        required_memory: int = 512,
        required_gpu: bool = False,
        required_capabilities: Optional[list[str]] = None
    ) -> float:
        """
        Calculate fitness score for a task (0-1, higher is better).

        Considers capabilities match and available resources.
        """
        # Check hard requirements
        if required_gpu and not self.gpu_available:
            return 0.0

        available_cpu = self.cpu_cores * (1 - self.cpu_usage_percent / 100)
        available_memory = self.memory_mb * (1 - self.memory_usage_percent / 100)

        if available_cpu < required_cpu * 0.5:  # Need at least 50% of required
            return 0.0
        if available_memory < required_memory * 0.5:
            return 0.0

        # Check capabilities
        required_caps = required_capabilities or []
        if required_caps:
            matching = sum(1 for c in required_caps if c in self.capabilities)
            if matching < len(required_caps):
                return 0.0

        # Calculate fitness
        cpu_fit = min(available_cpu / required_cpu, 2.0) / 2.0  # Cap at 2x
        mem_fit = min(available_memory / required_memory, 2.0) / 2.0

        # Combine with reputation
        base_score = (cpu_fit * 0.4 + mem_fit * 0.4 + self.reputation_score * 0.2)

        return min(base_score, 1.0)


class LoadBalancer:
    """
    Load balancer for distributing tasks across fog nodes.

    FOG-006: Core distribution logic with multiple strategies.
    """

    def __init__(self, strategy: DistributionStrategy = DistributionStrategy.LEAST_LOADED):
        """
        Initialize load balancer.

        Args:
            strategy: Default distribution strategy
        """
        self.strategy = strategy
        self._devices: dict[str, DeviceMetrics] = {}
        self._round_robin_index = 0
        self._lock = asyncio.Lock()

    def register_device(self, metrics: DeviceMetrics) -> None:
        """Register a device for load balancing."""
        self._devices[metrics.device_id] = metrics
        logger.debug(f"Registered device: {metrics.device_id}")

    def unregister_device(self, device_id: str) -> None:
        """Remove a device from load balancing."""
        if device_id in self._devices:
            del self._devices[device_id]
            logger.debug(f"Unregistered device: {device_id}")

    def update_metrics(self, device_id: str, **kwargs) -> None:
        """Update metrics for a device."""
        if device_id in self._devices:
            device = self._devices[device_id]
            for key, value in kwargs.items():
                if hasattr(device, key):
                    setattr(device, key, value)
            device.last_heartbeat = datetime.now(UTC)

    def get_available_devices(
        self,
        required_cpu: int = 1,
        required_memory: int = 512,
        required_gpu: bool = False,
        required_capabilities: Optional[list[str]] = None,
        region: Optional[str] = None,
    ) -> list[DeviceMetrics]:
        """
        Get devices that can handle a task.

        Filters by availability and capability requirements.
        """
        available = []

        for device in self._devices.values():
            if not device.is_available:
                continue

            # Check staleness (no heartbeat in 2 minutes)
            if device.last_heartbeat:
                age = (datetime.now(UTC) - device.last_heartbeat).total_seconds()
                if age > 120:
                    continue

            # Check capacity
            if device.active_tasks >= device.max_concurrent_tasks:
                continue

            # Check fitness
            fitness = device.get_fitness_score(
                required_cpu=required_cpu,
                required_memory=required_memory,
                required_gpu=required_gpu,
                required_capabilities=required_capabilities,
            )

            if fitness > 0:
                available.append(device)

        # Filter by region if specified
        if region:
            region_devices = [d for d in available if d.region == region]
            if region_devices:
                available = region_devices

        return available

    async def select_device(
        self,
        required_cpu: int = 1,
        required_memory: int = 512,
        required_gpu: bool = False,
        required_capabilities: Optional[list[str]] = None,
        region: Optional[str] = None,
        strategy: Optional[DistributionStrategy] = None,
    ) -> Optional[str]:
        """
        Select the best device for a task.

        Args:
            required_cpu: Minimum CPU cores needed
            required_memory: Minimum memory in MB
            required_gpu: Whether GPU is required
            required_capabilities: Required capability tags
            region: Preferred region
            strategy: Override default strategy

        Returns:
            Device ID or None if no suitable device
        """
        async with self._lock:
            available = self.get_available_devices(
                required_cpu=required_cpu,
                required_memory=required_memory,
                required_gpu=required_gpu,
                required_capabilities=required_capabilities,
                region=region,
            )

            if not available:
                return None

            use_strategy = strategy or self.strategy
            selected = self._apply_strategy(available, use_strategy)

            if selected:
                # Update metrics
                selected.active_tasks += 1
                logger.debug(f"Selected device {selected.device_id} using {use_strategy.value}")

            return selected.device_id if selected else None

    def _apply_strategy(
        self,
        devices: list[DeviceMetrics],
        strategy: DistributionStrategy
    ) -> Optional[DeviceMetrics]:
        """Apply distribution strategy to select a device."""
        if not devices:
            return None

        if strategy == DistributionStrategy.ROUND_ROBIN:
            self._round_robin_index = (self._round_robin_index + 1) % len(devices)
            return devices[self._round_robin_index]

        elif strategy == DistributionStrategy.LEAST_LOADED:
            return min(devices, key=lambda d: d.get_load_score())

        elif strategy == DistributionStrategy.BEST_FIT:
            return max(devices, key=lambda d: d.get_fitness_score())

        elif strategy == DistributionStrategy.RANDOM:
            import random
            return random.choice(devices)

        elif strategy == DistributionStrategy.LOCALITY:
            # Group by region, prefer largest group
            by_region: dict[str, list[DeviceMetrics]] = {}
            for d in devices:
                region = d.region or "unknown"
                by_region.setdefault(region, []).append(d)

            largest_group = max(by_region.values(), key=len)
            return min(largest_group, key=lambda d: d.get_load_score())

        elif strategy == DistributionStrategy.REPUTATION:
            return max(devices, key=lambda d: d.reputation_score)

        return devices[0]

    def release_device(self, device_id: str) -> None:
        """Mark a task as completed on a device."""
        if device_id in self._devices:
            self._devices[device_id].active_tasks = max(
                0, self._devices[device_id].active_tasks - 1
            )

    def get_stats(self) -> dict[str, Any]:
        """Get load balancer statistics."""
        total_devices = len(self._devices)
        available_devices = len([d for d in self._devices.values() if d.is_available])
        total_active_tasks = sum(d.active_tasks for d in self._devices.values())
        total_capacity = sum(d.max_concurrent_tasks for d in self._devices.values())

        return {
            "total_devices": total_devices,
            "available_devices": available_devices,
            "total_active_tasks": total_active_tasks,
            "total_capacity": total_capacity,
            "utilization_percent": (total_active_tasks / total_capacity * 100) if total_capacity > 0 else 0,
            "strategy": self.strategy.value,
        }


class TaskDistributor:
    """
    High-level task distribution manager.

    FOG-006: Coordinates task assignment and tracking.
    """

    def __init__(
        self,
        load_balancer: Optional[LoadBalancer] = None,
        on_task_assigned: Optional[Any] = None,  # Callback
    ):
        """
        Initialize task distributor.

        Args:
            load_balancer: Load balancer instance
            on_task_assigned: Callback when task is assigned
        """
        self.load_balancer = load_balancer or LoadBalancer()
        self._on_task_assigned = on_task_assigned

        # Task tracking
        self._pending_tasks: dict[str, PipelineTask] = {}
        self._assigned_tasks: dict[str, tuple[PipelineTask, str]] = {}  # task_id -> (task, device_id)

        # Stats
        self._stats = {
            "total_distributed": 0,
            "successful_assignments": 0,
            "failed_assignments": 0,
            "total_completions": 0,
            "total_failures": 0,
        }

    async def distribute_task(
        self,
        task: PipelineTask,
        stage: PipelineStage,
        preferred_device_id: Optional[str] = None,
        strategy: Optional[DistributionStrategy] = None,
    ) -> Optional[str]:
        """
        Distribute a task to a suitable device.

        Args:
            task: Task to distribute
            stage: Parent stage (for requirements)
            preferred_device_id: Prefer this device if available
            strategy: Distribution strategy override

        Returns:
            Assigned device ID or None
        """
        self._stats["total_distributed"] += 1

        # Try preferred device first
        if preferred_device_id:
            device_id = await self._try_assign_to_device(
                task, stage, preferred_device_id
            )
            if device_id:
                return device_id

        # Use load balancer
        device_id = await self.load_balancer.select_device(
            required_cpu=stage.required_cpu_cores,
            required_memory=stage.required_memory_mb,
            required_gpu=stage.required_gpu,
            required_capabilities=stage.required_capabilities,
            strategy=strategy,
        )

        if not device_id:
            self._stats["failed_assignments"] += 1
            logger.warning(f"No device available for task {task.task_id}")
            self._pending_tasks[task.task_id] = task
            return None

        # Assign task
        await self._assign_task(task, device_id)
        return device_id

    async def _try_assign_to_device(
        self,
        task: PipelineTask,
        stage: PipelineStage,
        device_id: str,
    ) -> Optional[str]:
        """Try to assign task to a specific device."""
        available = self.load_balancer.get_available_devices(
            required_cpu=stage.required_cpu_cores,
            required_memory=stage.required_memory_mb,
            required_gpu=stage.required_gpu,
            required_capabilities=stage.required_capabilities,
        )

        if any(d.device_id == device_id for d in available):
            await self._assign_task(task, device_id)
            return device_id

        return None

    async def _assign_task(self, task: PipelineTask, device_id: str) -> None:
        """Assign a task to a device."""
        task.assigned_device_id = device_id
        task.assigned_at = datetime.now(UTC)
        task.status = StageStatus.RUNNING

        self._assigned_tasks[task.task_id] = (task, device_id)
        self._stats["successful_assignments"] += 1

        # Remove from pending if present
        self._pending_tasks.pop(task.task_id, None)

        logger.info(f"Task {task.task_id} assigned to device {device_id}")

        # Callback
        if self._on_task_assigned:
            try:
                await self._on_task_assigned(task, device_id)
            except Exception as e:
                logger.error(f"Task assigned callback failed: {e}")

    async def handle_task_complete(
        self,
        task_id: str,
        success: bool,
        result_data: Optional[dict[str, Any]] = None,
        error_message: Optional[str] = None,
        execution_time_ms: int = 0,
    ) -> None:
        """
        Handle task completion from a device.

        Args:
            task_id: Completed task ID
            success: Whether task succeeded
            result_data: Task result data
            error_message: Error if failed
            execution_time_ms: Execution time
        """
        if task_id not in self._assigned_tasks:
            logger.warning(f"Unknown task completed: {task_id}")
            return

        task, device_id = self._assigned_tasks.pop(task_id)

        # Update task
        task.completed_at = datetime.now(UTC)
        task.execution_time_ms = execution_time_ms

        if success:
            task.status = StageStatus.COMPLETED
            task.result_data = result_data
            self._stats["total_completions"] += 1
        else:
            task.status = StageStatus.FAILED
            task.error_message = error_message
            self._stats["total_failures"] += 1

        # Release device
        self.load_balancer.release_device(device_id)

        logger.info(
            f"Task {task_id} {'completed' if success else 'failed'} "
            f"on device {device_id}"
        )

    async def handle_task_failure(
        self,
        task_id: str,
        error_message: str,
        should_retry: bool = True,
    ) -> Optional[str]:
        """
        Handle task failure with optional retry.

        Returns:
            New device ID if retried, None otherwise
        """
        if task_id not in self._assigned_tasks:
            return None

        task, old_device_id = self._assigned_tasks[task_id]

        # Release old device
        self.load_balancer.release_device(old_device_id)

        # Check retry
        if should_retry and task.retry_count < task.max_retries:
            task.retry_count += 1
            task.status = StageStatus.PENDING
            task.assigned_device_id = None

            logger.info(
                f"Retrying task {task_id} (attempt {task.retry_count}/{task.max_retries})"
            )

            # Remove from assigned, add to pending
            del self._assigned_tasks[task_id]
            self._pending_tasks[task_id] = task

            return None  # Will be redistributed

        # Mark as failed
        task.status = StageStatus.FAILED
        task.error_message = error_message
        task.completed_at = datetime.now(UTC)

        del self._assigned_tasks[task_id]
        self._stats["total_failures"] += 1

        return None

    async def redistribute_pending(
        self,
        stage: PipelineStage,
    ) -> int:
        """
        Redistribute pending tasks.

        Returns:
            Number of tasks successfully distributed
        """
        distributed = 0

        for task_id in list(self._pending_tasks.keys()):
            task = self._pending_tasks[task_id]
            if task.stage_id != stage.stage_id:
                continue

            device_id = await self.distribute_task(task, stage)
            if device_id:
                distributed += 1

        return distributed

    def get_pending_count(self) -> int:
        """Get number of pending tasks."""
        return len(self._pending_tasks)

    def get_assigned_count(self) -> int:
        """Get number of assigned tasks."""
        return len(self._assigned_tasks)

    def get_stats(self) -> dict[str, Any]:
        """Get distributor statistics."""
        return {
            **self._stats,
            "pending_tasks": len(self._pending_tasks),
            "assigned_tasks": len(self._assigned_tasks),
            "load_balancer": self.load_balancer.get_stats(),
        }
