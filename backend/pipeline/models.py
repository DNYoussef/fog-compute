"""
Pipeline Models
FOG-006: Data structures for pipeline orchestration

Defines pipelines, stages, tasks, and their relationships.
"""
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Optional, Any
from uuid import uuid4


class PipelineStatus(str, Enum):
    """Pipeline execution status."""
    DRAFT = "draft"           # Not yet started
    PENDING = "pending"       # Waiting to start
    RUNNING = "running"       # Currently executing
    PAUSED = "paused"         # Temporarily stopped
    COMPLETED = "completed"   # Successfully finished
    FAILED = "failed"         # Failed with error
    CANCELLED = "cancelled"   # User cancelled


class StageStatus(str, Enum):
    """Individual stage status."""
    PENDING = "pending"       # Waiting for dependencies
    READY = "ready"           # Dependencies met, can run
    RUNNING = "running"       # Currently executing
    COMPLETED = "completed"   # Successfully finished
    FAILED = "failed"         # Failed with error
    SKIPPED = "skipped"       # Skipped due to condition


class DependencyType(str, Enum):
    """Type of dependency between stages."""
    SEQUENTIAL = "sequential"     # Must complete before next starts
    DATA = "data"                  # Output data needed by next stage
    RESOURCE = "resource"          # Resource must be available
    CONDITIONAL = "conditional"    # Run based on condition


@dataclass
class PipelineDependency:
    """
    Dependency relationship between pipeline stages.

    FOG-006: Defines execution order and data flow.
    """
    source_stage_id: str
    target_stage_id: str
    dependency_type: DependencyType = DependencyType.SEQUENTIAL
    condition: Optional[str] = None  # Expression for conditional deps
    data_key: Optional[str] = None   # Key for data transfer

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source_stage_id": self.source_stage_id,
            "target_stage_id": self.target_stage_id,
            "dependency_type": self.dependency_type.value,
            "condition": self.condition,
            "data_key": self.data_key,
        }


@dataclass
class PipelineTask:
    """
    A task within a pipeline stage.

    FOG-006: Individual work unit that can be distributed.
    """
    task_id: str = field(default_factory=lambda: f"ptask-{uuid4().hex[:12]}")
    stage_id: str = ""
    task_type: str = "compute"
    payload: dict[str, Any] = field(default_factory=dict)

    # Assignment
    assigned_device_id: Optional[str] = None
    assigned_at: Optional[datetime] = None

    # Execution
    status: StageStatus = StageStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time_ms: int = 0

    # Results
    result_data: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "stage_id": self.stage_id,
            "task_type": self.task_type,
            "payload": self.payload,
            "assigned_device_id": self.assigned_device_id,
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_time_ms": self.execution_time_ms,
            "result_data": self.result_data,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }


@dataclass
class PipelineStage:
    """
    A stage in a pipeline containing one or more tasks.

    FOG-006: Groups related tasks that can run in parallel.
    """
    stage_id: str = field(default_factory=lambda: f"stage-{uuid4().hex[:8]}")
    name: str = "unnamed_stage"
    description: str = ""

    # Stage configuration
    parallel_tasks: int = 1           # Max tasks to run in parallel
    timeout_seconds: int = 3600       # Stage timeout
    fail_fast: bool = True            # Stop on first failure

    # Resource requirements
    required_cpu_cores: int = 1
    required_memory_mb: int = 512
    required_gpu: bool = False
    required_capabilities: list[str] = field(default_factory=list)

    # Tasks
    tasks: list[PipelineTask] = field(default_factory=list)

    # Execution state
    status: StageStatus = StageStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Results aggregation
    aggregate_results: bool = False   # Combine task results
    results: Optional[dict[str, Any]] = None
    error: Optional[str] = None

    def add_task(
        self,
        task_type: str,
        payload: dict[str, Any],
        max_retries: int = 3
    ) -> PipelineTask:
        """Add a task to this stage."""
        task = PipelineTask(
            stage_id=self.stage_id,
            task_type=task_type,
            payload=payload,
            max_retries=max_retries,
        )
        self.tasks.append(task)
        return task

    def get_pending_tasks(self) -> list[PipelineTask]:
        """Get tasks waiting to be executed."""
        return [t for t in self.tasks if t.status == StageStatus.PENDING]

    def get_running_tasks(self) -> list[PipelineTask]:
        """Get currently running tasks."""
        return [t for t in self.tasks if t.status == StageStatus.RUNNING]

    def is_complete(self) -> bool:
        """Check if all tasks are complete."""
        return all(
            t.status in (StageStatus.COMPLETED, StageStatus.SKIPPED, StageStatus.FAILED)
            for t in self.tasks
        )

    def has_failures(self) -> bool:
        """Check if any tasks failed."""
        return any(t.status == StageStatus.FAILED for t in self.tasks)

    def get_progress(self) -> float:
        """Get completion percentage."""
        if not self.tasks:
            return 100.0
        completed = sum(
            1 for t in self.tasks
            if t.status in (StageStatus.COMPLETED, StageStatus.SKIPPED)
        )
        return (completed / len(self.tasks)) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "stage_id": self.stage_id,
            "name": self.name,
            "description": self.description,
            "parallel_tasks": self.parallel_tasks,
            "timeout_seconds": self.timeout_seconds,
            "fail_fast": self.fail_fast,
            "required_cpu_cores": self.required_cpu_cores,
            "required_memory_mb": self.required_memory_mb,
            "required_gpu": self.required_gpu,
            "required_capabilities": self.required_capabilities,
            "tasks": [t.to_dict() for t in self.tasks],
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "aggregate_results": self.aggregate_results,
            "results": self.results,
            "error": self.error,
            "progress": self.get_progress(),
        }


@dataclass
class Pipeline:
    """
    A complete execution pipeline.

    FOG-006: Multi-stage workflow for distributed AI execution.

    Features:
    - Directed acyclic graph of stages
    - Parallel and sequential execution
    - Failure recovery with retries
    - Data passing between stages
    """
    pipeline_id: str = field(default_factory=lambda: f"pipe-{uuid4().hex[:12]}")
    name: str = "unnamed_pipeline"
    description: str = ""

    # Pipeline configuration
    priority: int = 5                  # 1-10, higher is more important
    timeout_seconds: int = 86400       # Total pipeline timeout (24h default)
    max_concurrent_stages: int = 1     # Stages to run in parallel

    # Metadata
    created_by: Optional[str] = None   # Device or user ID
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Stages and dependencies
    stages: dict[str, PipelineStage] = field(default_factory=dict)
    dependencies: list[PipelineDependency] = field(default_factory=list)

    # Execution state
    status: PipelineStatus = PipelineStatus.DRAFT
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Results
    final_results: Optional[dict[str, Any]] = None
    error: Optional[str] = None

    callback_url: Optional[str] = None

    def add_stage(self, stage: PipelineStage) -> None:
        """Add a stage to the pipeline."""
        self.stages[stage.stage_id] = stage

    def add_dependency(
        self,
        source_stage_id: str,
        target_stage_id: str,
        dependency_type: DependencyType = DependencyType.SEQUENTIAL,
        condition: Optional[str] = None,
        data_key: Optional[str] = None,
    ) -> None:
        """Add a dependency between stages."""
        if source_stage_id not in self.stages:
            raise ValueError(f"Source stage {source_stage_id} not found")
        if target_stage_id not in self.stages:
            raise ValueError(f"Target stage {target_stage_id} not found")

        dep = PipelineDependency(
            source_stage_id=source_stage_id,
            target_stage_id=target_stage_id,
            dependency_type=dependency_type,
            condition=condition,
            data_key=data_key,
        )
        self.dependencies.append(dep)

    def get_ready_stages(self) -> list[PipelineStage]:
        """Get stages ready to execute (dependencies met)."""
        ready = []

        for stage_id, stage in self.stages.items():
            if stage.status != StageStatus.PENDING:
                continue

            # Check all dependencies are met
            deps_met = True
            for dep in self.dependencies:
                if dep.target_stage_id != stage_id:
                    continue

                source = self.stages.get(dep.source_stage_id)
                if not source or source.status != StageStatus.COMPLETED:
                    deps_met = False
                    break

            if deps_met:
                ready.append(stage)

        return ready

    def get_entry_stages(self) -> list[PipelineStage]:
        """Get stages with no dependencies (entry points)."""
        target_ids = {d.target_stage_id for d in self.dependencies}
        return [
            stage for stage_id, stage in self.stages.items()
            if stage_id not in target_ids
        ]

    def get_stage_dependencies(self, stage_id: str) -> list[str]:
        """Get IDs of stages that must complete before this one."""
        return [
            d.source_stage_id for d in self.dependencies
            if d.target_stage_id == stage_id
        ]

    def get_stage_dependents(self, stage_id: str) -> list[str]:
        """Get IDs of stages that depend on this one."""
        return [
            d.target_stage_id for d in self.dependencies
            if d.source_stage_id == stage_id
        ]

    def is_complete(self) -> bool:
        """Check if all stages are complete."""
        return all(
            s.status in (StageStatus.COMPLETED, StageStatus.SKIPPED, StageStatus.FAILED)
            for s in self.stages.values()
        )

    def has_failures(self) -> bool:
        """Check if any stages failed."""
        return any(s.status == StageStatus.FAILED for s in self.stages.values())

    def get_progress(self) -> float:
        """Get overall completion percentage."""
        if not self.stages:
            return 100.0

        total_progress = sum(s.get_progress() for s in self.stages.values())
        return total_progress / len(self.stages)

    def get_stats(self) -> dict[str, Any]:
        """Get pipeline statistics."""
        stages_by_status = {}
        tasks_by_status = {}
        total_tasks = 0
        total_execution_time = 0

        for stage in self.stages.values():
            status = stage.status.value
            stages_by_status[status] = stages_by_status.get(status, 0) + 1

            for task in stage.tasks:
                total_tasks += 1
                task_status = task.status.value
                tasks_by_status[task_status] = tasks_by_status.get(task_status, 0) + 1
                total_execution_time += task.execution_time_ms

        return {
            "total_stages": len(self.stages),
            "total_tasks": total_tasks,
            "stages_by_status": stages_by_status,
            "tasks_by_status": tasks_by_status,
            "total_execution_time_ms": total_execution_time,
            "progress_percent": self.get_progress(),
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pipeline_id": self.pipeline_id,
            "name": self.name,
            "description": self.description,
            "priority": self.priority,
            "timeout_seconds": self.timeout_seconds,
            "max_concurrent_stages": self.max_concurrent_stages,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "stages": {sid: s.to_dict() for sid, s in self.stages.items()},
            "dependencies": [d.to_dict() for d in self.dependencies],
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "final_results": self.final_results,
            "error": self.error,
            "callback_url": self.callback_url,
            "stats": self.get_stats(),
        }
