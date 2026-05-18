"""
Pipeline models with restart-safe task execution state.

Stages keep their local orchestration lifecycle. Tasks use the canonical
control-plane vocabulary so the scheduler can persist and reconcile them
without inventing a second ownership model.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class PipelineStatus(str, Enum):
    """Pipeline execution status."""

    DRAFT = "draft"
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StageStatus(str, Enum):
    """Individual stage status."""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskExecutionStatus(str, Enum):
    """Canonical control-plane task states."""

    PENDING = "PENDING"
    LEASED = "LEASED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class DependencyType(str, Enum):
    """Type of dependency between stages."""

    SEQUENTIAL = "sequential"
    DATA = "data"
    RESOURCE = "resource"
    CONDITIONAL = "conditional"


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value)


@dataclass
class PipelineDependency:
    """Dependency relationship between pipeline stages."""

    source_stage_id: str
    target_stage_id: str
    dependency_type: DependencyType = DependencyType.SEQUENTIAL
    condition: Optional[str] = None
    data_key: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_stage_id": self.source_stage_id,
            "target_stage_id": self.target_stage_id,
            "dependency_type": self.dependency_type.value,
            "condition": self.condition,
            "data_key": self.data_key,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PipelineDependency":
        return cls(
            source_stage_id=data["source_stage_id"],
            target_stage_id=data["target_stage_id"],
            dependency_type=DependencyType(data.get("dependency_type", DependencyType.SEQUENTIAL.value)),
            condition=data.get("condition"),
            data_key=data.get("data_key"),
        )


@dataclass
class PipelineTask:
    """A distributed task owned by the authoritative control plane."""

    task_id: str = field(default_factory=lambda: f"ptask-{uuid4().hex[:12]}")
    stage_id: str = ""
    task_type: str = "compute"
    payload: dict[str, Any] = field(default_factory=dict)
    worker_id: Optional[str] = None
    assigned_device_id: Optional[str] = None  # Deprecated alias for worker_id
    attempt_id: Optional[str] = None
    lease_id: Optional[str] = None
    assigned_at: Optional[datetime] = None
    lease_expires_at: Optional[datetime] = None
    idempotency_key: Optional[str] = None
    status: TaskExecutionStatus = TaskExecutionStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time_ms: int = 0
    result_data: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

    def bind_worker(self, worker_id: Optional[str]) -> None:
        self.worker_id = worker_id
        self.assigned_device_id = worker_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "stage_id": self.stage_id,
            "task_type": self.task_type,
            "payload": self.payload,
            "worker_id": self.worker_id,
            "assigned_device_id": self.assigned_device_id,
            "attempt_id": self.attempt_id,
            "lease_id": self.lease_id,
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
            "lease_expires_at": self.lease_expires_at.isoformat() if self.lease_expires_at else None,
            "idempotency_key": self.idempotency_key,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_time_ms": self.execution_time_ms,
            "result_data": self.result_data,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PipelineTask":
        task = cls(
            task_id=data.get("task_id", f"ptask-{uuid4().hex[:12]}"),
            stage_id=data.get("stage_id", ""),
            task_type=data.get("task_type", "compute"),
            payload=dict(data.get("payload") or {}),
            worker_id=data.get("worker_id") or data.get("assigned_device_id"),
            assigned_device_id=data.get("assigned_device_id") or data.get("worker_id"),
            attempt_id=data.get("attempt_id"),
            lease_id=data.get("lease_id"),
            assigned_at=_parse_datetime(data.get("assigned_at")),
            lease_expires_at=_parse_datetime(data.get("lease_expires_at")),
            idempotency_key=data.get("idempotency_key"),
            status=TaskExecutionStatus(data.get("status", TaskExecutionStatus.PENDING.value)),
            started_at=_parse_datetime(data.get("started_at")),
            completed_at=_parse_datetime(data.get("completed_at")),
            execution_time_ms=int(data.get("execution_time_ms", 0) or 0),
            result_data=data.get("result_data"),
            error_message=data.get("error_message"),
            retry_count=int(data.get("retry_count", 0) or 0),
            max_retries=int(data.get("max_retries", 3) or 0),
        )
        task.bind_worker(task.worker_id)
        return task


@dataclass
class PipelineStage:
    """A stage in a pipeline containing one or more tasks."""

    stage_id: str = field(default_factory=lambda: f"stage-{uuid4().hex[:8]}")
    name: str = "unnamed_stage"
    description: str = ""
    parallel_tasks: int = 1
    timeout_seconds: int = 3600
    fail_fast: bool = True
    required_cpu_cores: int = 1
    required_memory_mb: int = 512
    required_gpu: bool = False
    required_capabilities: list[str] = field(default_factory=list)
    tasks: list[PipelineTask] = field(default_factory=list)
    status: StageStatus = StageStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    aggregate_results: bool = False
    results: Optional[dict[str, Any]] = None
    error: Optional[str] = None

    def add_task(self, task_type: str, payload: dict[str, Any], max_retries: int = 3) -> PipelineTask:
        task = PipelineTask(
            stage_id=self.stage_id,
            task_type=task_type,
            payload=payload,
            max_retries=max_retries,
        )
        self.tasks.append(task)
        return task

    def get_pending_tasks(self) -> list[PipelineTask]:
        return [task for task in self.tasks if task.status == TaskExecutionStatus.PENDING]

    def get_running_tasks(self) -> list[PipelineTask]:
        return [
            task
            for task in self.tasks
            if task.status in {TaskExecutionStatus.LEASED, TaskExecutionStatus.RUNNING}
        ]

    def is_complete(self) -> bool:
        return all(
            task.status in {
                TaskExecutionStatus.SUCCEEDED,
                TaskExecutionStatus.FAILED,
                TaskExecutionStatus.CANCELLED,
            }
            for task in self.tasks
        )

    def has_failures(self) -> bool:
        return any(
            task.status in {TaskExecutionStatus.FAILED, TaskExecutionStatus.CANCELLED}
            for task in self.tasks
        )

    def get_progress(self) -> float:
        if not self.tasks:
            return 100.0
        terminal = sum(
            1
            for task in self.tasks
            if task.status in {
                TaskExecutionStatus.SUCCEEDED,
                TaskExecutionStatus.FAILED,
                TaskExecutionStatus.CANCELLED,
            }
        )
        return (terminal / len(self.tasks)) * 100

    def to_dict(self) -> dict[str, Any]:
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
            "tasks": [task.to_dict() for task in self.tasks],
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "aggregate_results": self.aggregate_results,
            "results": self.results,
            "error": self.error,
            "progress": self.get_progress(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PipelineStage":
        return cls(
            stage_id=data.get("stage_id", f"stage-{uuid4().hex[:8]}"),
            name=data.get("name", "unnamed_stage"),
            description=data.get("description", ""),
            parallel_tasks=int(data.get("parallel_tasks", 1) or 1),
            timeout_seconds=int(data.get("timeout_seconds", 3600) or 3600),
            fail_fast=bool(data.get("fail_fast", True)),
            required_cpu_cores=int(data.get("required_cpu_cores", 1) or 1),
            required_memory_mb=int(data.get("required_memory_mb", 512) or 512),
            required_gpu=bool(data.get("required_gpu", False)),
            required_capabilities=list(data.get("required_capabilities") or []),
            tasks=[PipelineTask.from_dict(task) for task in data.get("tasks", [])],
            status=StageStatus(data.get("status", StageStatus.PENDING.value)),
            started_at=_parse_datetime(data.get("started_at")),
            completed_at=_parse_datetime(data.get("completed_at")),
            aggregate_results=bool(data.get("aggregate_results", False)),
            results=data.get("results"),
            error=data.get("error"),
        )


@dataclass
class Pipeline:
    """A complete multi-stage execution pipeline."""

    pipeline_id: str = field(default_factory=lambda: f"pipe-{uuid4().hex[:12]}")
    name: str = "unnamed_pipeline"
    description: str = ""
    priority: int = 5
    timeout_seconds: int = 86400
    max_concurrent_stages: int = 1
    created_by: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    stages: dict[str, PipelineStage] = field(default_factory=dict)
    dependencies: list[PipelineDependency] = field(default_factory=list)
    status: PipelineStatus = PipelineStatus.DRAFT
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    final_results: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    callback_url: Optional[str] = None

    def add_stage(self, stage: PipelineStage) -> None:
        self.stages[stage.stage_id] = stage

    def add_dependency(
        self,
        source_stage_id: str,
        target_stage_id: str,
        dependency_type: DependencyType = DependencyType.SEQUENTIAL,
        condition: Optional[str] = None,
        data_key: Optional[str] = None,
    ) -> None:
        if source_stage_id not in self.stages:
            raise ValueError(f"Source stage {source_stage_id} not found")
        if target_stage_id not in self.stages:
            raise ValueError(f"Target stage {target_stage_id} not found")
        self.dependencies.append(
            PipelineDependency(
                source_stage_id=source_stage_id,
                target_stage_id=target_stage_id,
                dependency_type=dependency_type,
                condition=condition,
                data_key=data_key,
            )
        )

    def get_ready_stages(self) -> list[PipelineStage]:
        ready: list[PipelineStage] = []
        for stage_id, stage in self.stages.items():
            if stage.status != StageStatus.PENDING:
                continue
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
        target_ids = {dep.target_stage_id for dep in self.dependencies}
        return [stage for stage_id, stage in self.stages.items() if stage_id not in target_ids]

    def get_stage_dependencies(self, stage_id: str) -> list[str]:
        return [dep.source_stage_id for dep in self.dependencies if dep.target_stage_id == stage_id]

    def get_stage_dependents(self, stage_id: str) -> list[str]:
        return [dep.target_stage_id for dep in self.dependencies if dep.source_stage_id == stage_id]

    def is_complete(self) -> bool:
        return all(
            stage.status in {StageStatus.COMPLETED, StageStatus.SKIPPED, StageStatus.FAILED}
            for stage in self.stages.values()
        )

    def has_failures(self) -> bool:
        return any(stage.status == StageStatus.FAILED for stage in self.stages.values())

    def get_progress(self) -> float:
        if not self.stages:
            return 100.0
        total_progress = sum(stage.get_progress() for stage in self.stages.values())
        return total_progress / len(self.stages)

    def get_stats(self) -> dict[str, Any]:
        stages_by_status: dict[str, int] = {}
        tasks_by_status: dict[str, int] = {}
        total_tasks = 0
        total_execution_time = 0

        for stage in self.stages.values():
            stages_by_status[stage.status.value] = stages_by_status.get(stage.status.value, 0) + 1
            for task in stage.tasks:
                total_tasks += 1
                tasks_by_status[task.status.value] = tasks_by_status.get(task.status.value, 0) + 1
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
        return {
            "pipeline_id": self.pipeline_id,
            "name": self.name,
            "description": self.description,
            "priority": self.priority,
            "timeout_seconds": self.timeout_seconds,
            "max_concurrent_stages": self.max_concurrent_stages,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "stages": {stage_id: stage.to_dict() for stage_id, stage in self.stages.items()},
            "dependencies": [dep.to_dict() for dep in self.dependencies],
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "final_results": self.final_results,
            "error": self.error,
            "callback_url": self.callback_url,
            "stats": self.get_stats(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Pipeline":
        pipeline = cls(
            pipeline_id=data.get("pipeline_id", f"pipe-{uuid4().hex[:12]}"),
            name=data.get("name", "unnamed_pipeline"),
            description=data.get("description", ""),
            priority=int(data.get("priority", 5) or 5),
            timeout_seconds=int(data.get("timeout_seconds", 86400) or 86400),
            max_concurrent_stages=int(data.get("max_concurrent_stages", 1) or 1),
            created_by=data.get("created_by"),
            created_at=_parse_datetime(data.get("created_at")) or datetime.now(UTC),
            dependencies=[PipelineDependency.from_dict(dep) for dep in data.get("dependencies", [])],
            status=PipelineStatus(data.get("status", PipelineStatus.DRAFT.value)),
            started_at=_parse_datetime(data.get("started_at")),
            completed_at=_parse_datetime(data.get("completed_at")),
            final_results=data.get("final_results"),
            error=data.get("error"),
            callback_url=data.get("callback_url"),
        )
        pipeline.stages = {
            stage_id: PipelineStage.from_dict(stage_data)
            for stage_id, stage_data in (data.get("stages") or {}).items()
        }
        return pipeline
