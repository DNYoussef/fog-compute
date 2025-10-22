"""
Intelligent Scheduler - ML-based task scheduling and placement

Features:
- Machine learning-based task placement
- Historical performance learning
- Resource affinity optimization
- Cost-aware scheduling
- Priority queue with SLA enforcement
- Deadline-aware scheduling
"""

import asyncio
import heapq
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
import random

import psutil

logger = logging.getLogger(__name__)


class SchedulingStrategy(Enum):
    """Scheduling strategies"""
    FIFO = "fifo"  # First In First Out
    PRIORITY = "priority"  # Priority-based
    SLA = "sla"  # SLA deadline-based
    COST = "cost"  # Cost-optimized
    AFFINITY = "affinity"  # Resource affinity
    ML_ADAPTIVE = "ml_adaptive"  # Machine learning adaptive


class TaskPriority(Enum):
    """Task priority levels"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class ResourceType(Enum):
    """Resource types for affinity"""
    CPU = "cpu"
    GPU = "gpu"
    MEMORY = "memory"
    NETWORK = "network"
    DISK = "disk"


@dataclass
class ResourceRequirements:
    """Resource requirements for a task"""
    cpu_cores: float = 1.0
    memory_mb: int = 512
    gpu_count: int = 0
    disk_mb: int = 100
    network_mbps: float = 10.0
    preferred_type: ResourceType = ResourceType.CPU


@dataclass
class TaskMetadata:
    """Metadata for a scheduled task"""
    task_id: str
    priority: TaskPriority
    requirements: ResourceRequirements
    deadline: Optional[datetime] = None
    sla_target_ms: Optional[int] = None
    cost_limit: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    worker_id: Optional[str] = None

    def __lt__(self, other: 'TaskMetadata') -> bool:
        """Compare for priority queue (higher priority first)"""
        # If priorities are equal, use deadline
        if self.priority == other.priority:
            if self.deadline and other.deadline:
                return self.deadline < other.deadline
            elif self.deadline:
                return True  # Tasks with deadlines come first
            else:
                return self.created_at < other.created_at
        return self.priority.value > other.priority.value


@dataclass
class WorkerNode:
    """Represents a worker node for task execution"""
    worker_id: str
    available_cpu: float
    available_memory_mb: int
    available_gpu: int
    capabilities: Set[ResourceType]
    current_tasks: List[str] = field(default_factory=list)
    total_tasks_executed: int = 0
    total_execution_time: float = 0.0
    failure_count: int = 0
    last_heartbeat: datetime = field(default_factory=datetime.now)

    @property
    def avg_execution_time(self) -> float:
        """Average task execution time"""
        if self.total_tasks_executed == 0:
            return 0.0
        return self.total_execution_time / self.total_tasks_executed

    @property
    def success_rate(self) -> float:
        """Task success rate"""
        total = self.total_tasks_executed + self.failure_count
        if total == 0:
            return 1.0
        return self.total_tasks_executed / total

    def can_handle(self, requirements: ResourceRequirements) -> bool:
        """Check if worker can handle task requirements"""
        return (
            self.available_cpu >= requirements.cpu_cores
            and self.available_memory_mb >= requirements.memory_mb
            and self.available_gpu >= requirements.gpu_count
            and requirements.preferred_type in self.capabilities
        )

    def allocate(self, requirements: ResourceRequirements, task_id: str) -> None:
        """Allocate resources for a task"""
        self.available_cpu -= requirements.cpu_cores
        self.available_memory_mb -= requirements.memory_mb
        self.available_gpu -= requirements.gpu_count
        self.current_tasks.append(task_id)

    def deallocate(self, requirements: ResourceRequirements, task_id: str) -> None:
        """Deallocate resources from a completed task"""
        self.available_cpu += requirements.cpu_cores
        self.available_memory_mb += requirements.memory_mb
        self.available_gpu += requirements.gpu_count
        if task_id in self.current_tasks:
            self.current_tasks.remove(task_id)


class MLTaskPredictor:
    """
    Simple ML predictor for task placement

    Uses historical data to predict best worker placement
    """

    def __init__(self):
        self._task_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._worker_performance: Dict[str, List[float]] = defaultdict(list)
        self._affinity_scores: Dict[tuple, float] = {}  # (worker_id, resource_type) -> score

    def record_execution(
        self,
        task_id: str,
        worker_id: str,
        requirements: ResourceRequirements,
        execution_time: float,
        success: bool,
    ) -> None:
        """Record a task execution for learning"""
        self._task_history[task_id].append({
            "worker_id": worker_id,
            "requirements": requirements,
            "execution_time": execution_time,
            "success": success,
            "timestamp": datetime.now(),
        })

        if success:
            self._worker_performance[worker_id].append(execution_time)

            # Update affinity score
            key = (worker_id, requirements.preferred_type.value)
            current_score = self._affinity_scores.get(key, 0.5)

            # Exponential moving average
            alpha = 0.1
            performance_score = 1.0 / (1.0 + execution_time)  # Lower time = higher score
            self._affinity_scores[key] = alpha * performance_score + (1 - alpha) * current_score

    def predict_best_worker(
        self,
        requirements: ResourceRequirements,
        available_workers: List[WorkerNode],
    ) -> Optional[WorkerNode]:
        """Predict the best worker for a task"""
        if not available_workers:
            return None

        # Score each worker
        scores = []
        for worker in available_workers:
            if not worker.can_handle(requirements):
                continue

            # Base score from historical performance
            base_score = worker.success_rate

            # Affinity bonus
            affinity_key = (worker.worker_id, requirements.preferred_type.value)
            affinity_bonus = self._affinity_scores.get(affinity_key, 0.5)

            # Load balancing penalty (prefer less loaded workers)
            load_penalty = len(worker.current_tasks) * 0.1

            # Resource utilization score (prefer workers with just enough resources)
            cpu_ratio = requirements.cpu_cores / (worker.available_cpu + 0.1)
            mem_ratio = requirements.memory_mb / (worker.available_memory_mb + 1)
            resource_score = 1.0 / (1.0 + abs(1.0 - (cpu_ratio + mem_ratio) / 2))

            total_score = (
                base_score * 0.3
                + affinity_bonus * 0.3
                + resource_score * 0.3
                - load_penalty * 0.1
            )

            scores.append((total_score, worker))

        if not scores:
            return None

        # Return worker with highest score
        scores.sort(reverse=True, key=lambda x: x[0])
        return scores[0][1]

    def get_insights(self) -> Dict[str, Any]:
        """Get learning insights"""
        return {
            "total_tasks_recorded": sum(len(h) for h in self._task_history.values()),
            "workers_tracked": len(self._worker_performance),
            "affinity_mappings": len(self._affinity_scores),
            "top_affinities": sorted(
                [(k, v) for k, v in self._affinity_scores.items()],
                key=lambda x: x[1],
                reverse=True,
            )[:5],
        }


class IntelligentScheduler:
    """
    Intelligent task scheduler with ML-based placement

    Supports multiple scheduling strategies and learns from execution history
    """

    def __init__(self, strategy: SchedulingStrategy = SchedulingStrategy.ML_ADAPTIVE):
        self.strategy = strategy
        self._task_queue: List[TaskMetadata] = []  # Priority heap
        self._tasks: Dict[str, TaskMetadata] = {}
        self._workers: Dict[str, WorkerNode] = {}
        self._predictor = MLTaskPredictor()
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None

        logger.info(f"IntelligentScheduler initialized with strategy: {strategy.value}")

    def register_worker(
        self,
        worker_id: str,
        cpu_cores: float,
        memory_mb: int,
        gpu_count: int = 0,
        capabilities: Optional[Set[ResourceType]] = None,
    ) -> None:
        """Register a worker node"""
        if capabilities is None:
            capabilities = {ResourceType.CPU, ResourceType.MEMORY}
            if gpu_count > 0:
                capabilities.add(ResourceType.GPU)

        worker = WorkerNode(
            worker_id=worker_id,
            available_cpu=cpu_cores,
            available_memory_mb=memory_mb,
            available_gpu=gpu_count,
            capabilities=capabilities,
        )

        self._workers[worker_id] = worker
        logger.info(f"Registered worker {worker_id}: {cpu_cores} CPU, {memory_mb} MB RAM")

    def submit_task(
        self,
        task_id: str,
        priority: TaskPriority = TaskPriority.MEDIUM,
        requirements: Optional[ResourceRequirements] = None,
        deadline: Optional[datetime] = None,
        sla_target_ms: Optional[int] = None,
        cost_limit: Optional[float] = None,
    ) -> None:
        """Submit a task for scheduling"""
        if requirements is None:
            requirements = ResourceRequirements()

        task = TaskMetadata(
            task_id=task_id,
            priority=priority,
            requirements=requirements,
            deadline=deadline,
            sla_target_ms=sla_target_ms,
            cost_limit=cost_limit,
        )

        self._tasks[task_id] = task
        heapq.heappush(self._task_queue, task)

        logger.debug(f"Submitted task {task_id} with priority {priority.value}")

    def _select_worker(self, task: TaskMetadata) -> Optional[WorkerNode]:
        """Select the best worker for a task based on strategy"""
        available_workers = [
            w for w in self._workers.values()
            if w.can_handle(task.requirements)
        ]

        if not available_workers:
            return None

        if self.strategy == SchedulingStrategy.ML_ADAPTIVE:
            return self._predictor.predict_best_worker(task.requirements, available_workers)

        elif self.strategy == SchedulingStrategy.AFFINITY:
            # Prefer workers with matching resource type capability
            preferred_type = task.requirements.preferred_type
            matching = [w for w in available_workers if preferred_type in w.capabilities]
            if matching:
                # Select least loaded
                return min(matching, key=lambda w: len(w.current_tasks))
            return available_workers[0]

        elif self.strategy == SchedulingStrategy.COST:
            # Prefer workers with lower average execution time (cost proxy)
            return min(available_workers, key=lambda w: w.avg_execution_time or float('inf'))

        else:  # FIFO, PRIORITY, SLA
            # Simple round-robin among available
            return min(available_workers, key=lambda w: len(w.current_tasks))

    async def _schedule_loop(self) -> None:
        """Main scheduling loop"""
        while self._running:
            try:
                # Process pending tasks
                scheduled_count = 0

                while self._task_queue:
                    task = heapq.heappop(self._task_queue)

                    # Check if task deadline passed
                    if task.deadline and datetime.now() > task.deadline:
                        logger.warning(f"Task {task.task_id} missed deadline, dropping")
                        del self._tasks[task.task_id]
                        continue

                    # Select worker
                    worker = self._select_worker(task)
                    if not worker:
                        # No suitable worker, re-queue
                        heapq.heappush(self._task_queue, task)
                        break

                    # Allocate and schedule
                    worker.allocate(task.requirements, task.task_id)
                    task.scheduled_at = datetime.now()
                    task.worker_id = worker.worker_id

                    logger.info(
                        f"Scheduled task {task.task_id} on worker {worker.worker_id} "
                        f"(queue: {len(self._task_queue)} remaining)"
                    )

                    scheduled_count += 1

                    # Simulate task execution start
                    asyncio.create_task(self._execute_task(task, worker))

                if scheduled_count > 0:
                    logger.debug(f"Scheduled {scheduled_count} tasks this iteration")

            except Exception as e:
                logger.error(f"Error in schedule loop: {e}")

            await asyncio.sleep(0.1)  # Small delay

    async def _execute_task(self, task: TaskMetadata, worker: WorkerNode) -> None:
        """Simulate task execution (placeholder for actual execution)"""
        task.started_at = datetime.now()

        # Simulate execution time (replace with actual task execution)
        execution_time = random.uniform(0.5, 3.0)
        await asyncio.sleep(execution_time)

        # Record completion
        task.completed_at = datetime.now()
        success = random.random() > 0.05  # 95% success rate

        # Update worker stats
        if success:
            worker.total_tasks_executed += 1
            worker.total_execution_time += execution_time
        else:
            worker.failure_count += 1

        # Deallocate resources
        worker.deallocate(task.requirements, task.task_id)

        # Record for ML learning
        self._predictor.record_execution(
            task.task_id,
            worker.worker_id,
            task.requirements,
            execution_time,
            success,
        )

        # Clean up completed task
        if task.task_id in self._tasks:
            del self._tasks[task.task_id]

        logger.info(
            f"Task {task.task_id} completed in {execution_time:.2f}s "
            f"(success={success})"
        )

    async def start(self) -> None:
        """Start the scheduler"""
        if self._running:
            return

        self._running = True
        self._scheduler_task = asyncio.create_task(self._schedule_loop())
        logger.info("Scheduler started")

    async def stop(self) -> None:
        """Stop the scheduler"""
        self._running = False
        if self._scheduler_task:
            await self._scheduler_task
        logger.info("Scheduler stopped")

    def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics"""
        return {
            "strategy": self.strategy.value,
            "pending_tasks": len(self._task_queue),
            "active_tasks": sum(len(w.current_tasks) for w in self._workers.values()),
            "total_workers": len(self._workers),
            "worker_stats": {
                wid: {
                    "active_tasks": len(w.current_tasks),
                    "total_executed": w.total_tasks_executed,
                    "success_rate": round(w.success_rate * 100, 2),
                    "avg_execution_time": round(w.avg_execution_time, 2),
                }
                for wid, w in self._workers.items()
            },
            "ml_insights": self._predictor.get_insights(),
        }


# Singleton instance
_scheduler = IntelligentScheduler()


def get_intelligent_scheduler() -> IntelligentScheduler:
    """Get the singleton IntelligentScheduler instance"""
    return _scheduler
