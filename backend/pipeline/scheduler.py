"""
Pipeline scheduler using the fog task control plane for task execution.

The scheduler owns pipeline/stage orchestration only. Task ownership,
attempts, leases, and restart reconciliation live in the backend control plane.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Awaitable, Callable, Optional

from backend.server.models.control_plane import ControlPlaneTaskState
from backend.server.services.fog_task_control_plane import fog_task_control_plane

from .distributor import DistributionStrategy, LoadBalancer, TaskDistributor
from .models import (
    DependencyType,
    Pipeline,
    PipelineStage,
    PipelineStatus,
    PipelineTask,
    StageStatus,
    TaskExecutionStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class SchedulerConfig:
    poll_interval_sec: float = 1.0
    heartbeat_interval_sec: float = 30.0
    max_concurrent_pipelines: int = 10
    max_concurrent_stages: int = 5
    max_task_retries: int = 3
    default_stage_timeout_sec: int = 3600
    default_pipeline_timeout_sec: int = 86400
    distribution_strategy: DistributionStrategy = DistributionStrategy.LEAST_LOADED
    prefer_locality: bool = True
    aggregate_stage_results: bool = True
    store_intermediate_results: bool = True


class PipelineScheduler:
    """Orchestrates durable pipeline execution over the control plane."""

    def __init__(
        self,
        config: Optional[SchedulerConfig] = None,
        distributor: Optional[TaskDistributor] = None,
        on_pipeline_complete: Optional[Callable[[Pipeline], Awaitable[None]]] = None,
        on_stage_complete: Optional[Callable[[Pipeline, PipelineStage], Awaitable[None]]] = None,
        fog_task_control_plane_service=None,
    ) -> None:
        self.config = config or SchedulerConfig()
        self.distributor = distributor or TaskDistributor(
            load_balancer=LoadBalancer(strategy=self.config.distribution_strategy)
        )
        self.fog_task_control_plane = fog_task_control_plane_service or fog_task_control_plane
        self._on_pipeline_complete = on_pipeline_complete
        self._on_stage_complete = on_stage_complete
        self._pipelines: dict[str, Pipeline] = {}
        self._active_pipelines: set[str] = set()
        self._is_running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._stats = {
            "pipelines_created": 0,
            "pipelines_completed": 0,
            "pipelines_failed": 0,
            "stages_executed": 0,
            "tasks_distributed": 0,
        }

    async def start(self) -> None:
        if self._is_running:
            return
        await self.fog_task_control_plane.reconcile_startup()
        await self._load_persisted_pipelines()
        self._is_running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("PipelineScheduler started")

    async def stop(self) -> None:
        self._is_running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        logger.info("PipelineScheduler stopped")

    def create_pipeline(
        self,
        name: str,
        description: str = "",
        priority: int = 5,
        created_by: Optional[str] = None,
        callback_url: Optional[str] = None,
    ) -> Pipeline:
        pipeline = Pipeline(
            name=name,
            description=description,
            priority=priority,
            created_by=created_by,
            callback_url=callback_url,
        )
        self._pipelines[pipeline.pipeline_id] = pipeline
        self._stats["pipelines_created"] += 1
        logger.info("Created pipeline %s (%s)", pipeline.pipeline_id, name)
        return pipeline

    def get_pipeline(self, pipeline_id: str) -> Optional[Pipeline]:
        return self._pipelines.get(pipeline_id)

    def list_pipelines(
        self,
        status: Optional[PipelineStatus] = None,
        limit: int = 100,
    ) -> list[Pipeline]:
        pipelines = list(self._pipelines.values())
        if status:
            pipelines = [pipeline for pipeline in pipelines if pipeline.status == status]
        pipelines.sort(key=lambda pipeline: (-pipeline.priority, pipeline.created_at))
        return pipelines[:limit]

    async def submit_pipeline(self, pipeline: Pipeline) -> bool:
        if not pipeline.stages:
            logger.error("Pipeline %s has no stages", pipeline.pipeline_id)
            return False
        if self._has_cycle(pipeline):
            logger.error("Pipeline %s has dependency cycles", pipeline.pipeline_id)
            return False

        self._prepare_pipeline_tasks(pipeline)
        self._pipelines[pipeline.pipeline_id] = pipeline

        if len(self._active_pipelines) >= self.config.max_concurrent_pipelines:
            pipeline.status = PipelineStatus.PENDING
            await self._persist_pipeline(pipeline)
            return True

        pipeline.status = PipelineStatus.RUNNING
        pipeline.started_at = pipeline.started_at or datetime.now(UTC)
        self._active_pipelines.add(pipeline.pipeline_id)
        for stage in pipeline.get_entry_stages():
            if stage.status == StageStatus.PENDING:
                stage.status = StageStatus.READY
        await self._persist_pipeline(pipeline)
        logger.info("Pipeline %s submitted", pipeline.pipeline_id)
        return True

    async def cancel_pipeline(self, pipeline_id: str) -> bool:
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline or pipeline.status not in {PipelineStatus.RUNNING, PipelineStatus.PENDING, PipelineStatus.PAUSED}:
            return False
        pipeline.status = PipelineStatus.CANCELLED
        pipeline.completed_at = datetime.now(UTC)
        self._active_pipelines.discard(pipeline_id)
        for stage in pipeline.stages.values():
            if stage.status == StageStatus.RUNNING:
                stage.status = StageStatus.SKIPPED
            for task in stage.tasks:
                if task.status not in {TaskExecutionStatus.SUCCEEDED, TaskExecutionStatus.FAILED, TaskExecutionStatus.CANCELLED}:
                    task.status = TaskExecutionStatus.CANCELLED
                    if await self.fog_task_control_plane.get_task(task.task_id):
                        await self.fog_task_control_plane.cancel_task(task.task_id)
        await self._persist_pipeline(pipeline)
        return True

    async def pause_pipeline(self, pipeline_id: str) -> bool:
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline or pipeline.status != PipelineStatus.RUNNING:
            return False
        pipeline.status = PipelineStatus.PAUSED
        await self._persist_pipeline(pipeline)
        return True

    async def resume_pipeline(self, pipeline_id: str) -> bool:
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline or pipeline.status != PipelineStatus.PAUSED:
            return False
        pipeline.status = PipelineStatus.RUNNING
        self._active_pipelines.add(pipeline.pipeline_id)
        await self._persist_pipeline(pipeline)
        return True

    async def handle_task_result(
        self,
        pipeline_id: str,
        task_id: str,
        success: bool,
        result_data: Optional[dict[str, Any]] = None,
        error_message: Optional[str] = None,
        execution_time_ms: int = 0,
    ) -> None:
        """Compatibility hook that now just reconciles persisted task state."""
        _ = (task_id, success, result_data, error_message, execution_time_ms)
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            logger.warning("Unknown pipeline %s", pipeline_id)
            return
        await self._reconcile_pipeline_tasks(pipeline)
        if pipeline.is_complete():
            await self._complete_pipeline(pipeline)

    async def _scheduler_loop(self) -> None:
        while self._is_running:
            try:
                await self._process_pipelines()
                await asyncio.sleep(self.config.poll_interval_sec)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Scheduler loop error: %s", exc)
                await asyncio.sleep(1)

    async def _process_pipelines(self) -> None:
        pending = [
            pipeline for pipeline in self._pipelines.values()
            if pipeline.status == PipelineStatus.PENDING
        ]
        for pipeline in pending:
            if len(self._active_pipelines) < self.config.max_concurrent_pipelines:
                await self.submit_pipeline(pipeline)

        for pipeline_id in list(self._active_pipelines):
            pipeline = self._pipelines.get(pipeline_id)
            if not pipeline:
                self._active_pipelines.discard(pipeline_id)
                continue
            if pipeline.status != PipelineStatus.RUNNING:
                continue
            await self._process_pipeline(pipeline)

    async def _process_pipeline(self, pipeline: Pipeline) -> None:
        await self._reconcile_pipeline_tasks(pipeline)

        if pipeline.started_at:
            elapsed = (datetime.now(UTC) - pipeline.started_at).total_seconds()
            if elapsed > pipeline.timeout_seconds:
                pipeline.status = PipelineStatus.FAILED
                pipeline.error = "Pipeline timeout"
                pipeline.completed_at = datetime.now(UTC)
                self._active_pipelines.discard(pipeline.pipeline_id)
                self._stats["pipelines_failed"] += 1
                await self._persist_pipeline(pipeline)
                await self._notify_pipeline_complete(pipeline)
                return

        ready_stages = [
            stage for stage in pipeline.stages.values()
            if stage.status == StageStatus.READY
        ]
        ready_stages.extend(
            stage
            for stage in pipeline.get_ready_stages()
            if stage.status == StageStatus.PENDING and stage not in ready_stages
        )
        running_with_pending = [
            stage
            for stage in pipeline.stages.values()
            if stage.status == StageStatus.RUNNING and stage.get_pending_tasks()
        ]
        candidate_stages = ready_stages + [
            stage for stage in running_with_pending if stage not in ready_stages
        ]
        for stage in candidate_stages[:self.config.max_concurrent_stages]:
            await self._execute_stage(pipeline, stage)

        for stage in pipeline.stages.values():
            if stage.status == StageStatus.RUNNING and stage.is_complete():
                await self._complete_stage(pipeline, stage)

        if pipeline.has_failures():
            for stage in pipeline.stages.values():
                if stage.status == StageStatus.PENDING:
                    stage.status = StageStatus.SKIPPED
            await self._complete_pipeline(pipeline)
            return

        if pipeline.is_complete():
            await self._complete_pipeline(pipeline)

    async def _execute_stage(self, pipeline: Pipeline, stage: PipelineStage) -> None:
        if stage.status == StageStatus.READY:
            stage.status = StageStatus.RUNNING
            stage.started_at = stage.started_at or datetime.now(UTC)
            self._stats["stages_executed"] += 1

        stage_data = await self._gather_dependency_data(pipeline, stage)
        for task in stage.get_pending_tasks():
            if stage_data:
                task.payload["_dependency_data"] = stage_data
            row = await self.fog_task_control_plane.create_task(
                task_type=task.task_type,
                priority=self._task_priority_for_pipeline(pipeline),
                payload=task.payload,
                resource_requirements={
                    "cpu_cores": stage.required_cpu_cores,
                    "memory_mb": stage.required_memory_mb,
                    "gpu_available": stage.required_gpu,
                },
                timeout_seconds=stage.timeout_seconds or self.config.default_stage_timeout_sec,
                max_retries=task.max_retries,
                callback_url=pipeline.callback_url,
                created_by_worker_id=pipeline.created_by,
                task_id=task.task_id,
                pipeline_id=pipeline.pipeline_id,
                stage_id=stage.stage_id,
                idempotency_key=task.idempotency_key,
            )
            self._apply_control_plane_task(task, row)
            self._stats["tasks_distributed"] += 1
        await self._persist_pipeline(pipeline)

    async def _gather_dependency_data(self, pipeline: Pipeline, stage: PipelineStage) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for dep in pipeline.dependencies:
            if dep.target_stage_id != stage.stage_id:
                continue
            if dep.dependency_type not in (DependencyType.DATA, DependencyType.SEQUENTIAL):
                continue
            source_stage = pipeline.stages.get(dep.source_stage_id)
            if source_stage and source_stage.results:
                key = dep.data_key or dep.source_stage_id
                data[key] = source_stage.results
        return data

    async def _reconcile_pipeline_tasks(self, pipeline: Pipeline) -> None:
        rows = await self.fog_task_control_plane.list_pipeline_tasks(pipeline.pipeline_id)
        by_task_id = {row.task_id: row for row in rows}
        pipeline_changed = False

        for stage in pipeline.stages.values():
            stage_changed = False
            for task in stage.tasks:
                row = by_task_id.get(task.task_id)
                if row is None:
                    continue
                self._apply_control_plane_task(task, row)
                if task.status in {TaskExecutionStatus.EXPIRED, TaskExecutionStatus.FAILED}:
                    if row.retry_count < row.max_retries and task.retry_count < task.max_retries:
                        requeued = await self.fog_task_control_plane.requeue_task(
                            task.task_id,
                            reason=row.error or "Retry requested after failure",
                        )
                        if requeued is not None:
                            self._apply_control_plane_task(task, requeued)
                            stage_changed = True
                    elif stage.fail_fast:
                        stage.status = StageStatus.FAILED
                        stage.error = row.error or task.error_message or "Task failure"
                        stage_changed = True

            if stage.status in {StageStatus.READY, StageStatus.RUNNING} and stage.is_complete():
                await self._complete_stage(pipeline, stage)
                stage_changed = True

            if stage_changed:
                pipeline_changed = True

        if pipeline_changed:
            await self._persist_pipeline(pipeline)

    async def _complete_stage(self, pipeline: Pipeline, stage: PipelineStage) -> None:
        stage.completed_at = datetime.now(UTC)
        if stage.has_failures():
            stage.status = StageStatus.FAILED if stage.fail_fast else StageStatus.COMPLETED
            stage.error = stage.error or "Stage failed due to task failure(s)"
        else:
            stage.status = StageStatus.COMPLETED

        if stage.aggregate_results:
            stage.results = self._aggregate_task_results(stage)

        if self._on_stage_complete:
            try:
                await self._on_stage_complete(pipeline, stage)
            except Exception as exc:
                logger.error("Stage complete callback failed: %s", exc)

        for dependent_id in pipeline.get_stage_dependents(stage.stage_id):
            dependent = pipeline.stages.get(dependent_id)
            if dependent and dependent.status == StageStatus.PENDING:
                if all(
                    pipeline.stages[dependency_id].status == StageStatus.COMPLETED
                    for dependency_id in pipeline.get_stage_dependencies(dependent_id)
                ):
                    dependent.status = StageStatus.READY
        await self._persist_pipeline(pipeline)

    def _aggregate_task_results(self, stage: PipelineStage) -> dict[str, Any]:
        return {
            "task_count": len(stage.tasks),
            "successful_count": sum(1 for task in stage.tasks if task.status == TaskExecutionStatus.SUCCEEDED),
            "failed_count": sum(1 for task in stage.tasks if task.status == TaskExecutionStatus.FAILED),
            "total_execution_time_ms": sum(task.execution_time_ms for task in stage.tasks),
            "task_results": [
                {"task_id": task.task_id, "data": task.result_data}
                for task in stage.tasks
                if task.result_data
            ],
        }

    async def _complete_pipeline(self, pipeline: Pipeline) -> None:
        pipeline.completed_at = datetime.now(UTC)
        self._active_pipelines.discard(pipeline.pipeline_id)
        if pipeline.has_failures():
            pipeline.status = PipelineStatus.FAILED
            pipeline.error = pipeline.error or "Pipeline failed due to stage failure(s)"
            self._stats["pipelines_failed"] += 1
        else:
            pipeline.status = PipelineStatus.COMPLETED
            self._stats["pipelines_completed"] += 1
        pipeline.final_results = self._aggregate_pipeline_results(pipeline)
        await self._persist_pipeline(pipeline)
        await self._notify_pipeline_complete(pipeline)

    def _aggregate_pipeline_results(self, pipeline: Pipeline) -> dict[str, Any]:
        return {
            "pipeline_id": pipeline.pipeline_id,
            "name": pipeline.name,
            "status": pipeline.status.value,
            "stats": pipeline.get_stats(),
            "stage_results": {
                stage_id: stage.results
                for stage_id, stage in pipeline.stages.items()
                if stage.results
            },
        }

    async def _notify_pipeline_complete(self, pipeline: Pipeline) -> None:
        if self._on_pipeline_complete:
            try:
                await self._on_pipeline_complete(pipeline)
            except Exception as exc:
                logger.error("Pipeline complete callback failed: %s", exc)
        if pipeline.callback_url:
            await self._send_callback(pipeline)

    async def _send_callback(self, pipeline: Pipeline) -> None:
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    pipeline.callback_url,
                    json=pipeline.to_dict(),
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status >= 400:
                        logger.warning("Callback failed for %s: %s", pipeline.pipeline_id, response.status)
        except ImportError:
            logger.warning("aiohttp not available for callbacks")
        except Exception as exc:
            logger.error("Callback error for %s: %s", pipeline.pipeline_id, exc)

    async def _load_persisted_pipelines(self) -> None:
        records = await self.fog_task_control_plane.list_pipeline_records(
            statuses={
                PipelineStatus.PENDING.value,
                PipelineStatus.RUNNING.value,
                PipelineStatus.PAUSED.value,
            }
        )
        for record in records:
            pipeline = Pipeline.from_dict(record.definition_json)
            self._pipelines[pipeline.pipeline_id] = pipeline
            if pipeline.status == PipelineStatus.RUNNING:
                self._active_pipelines.add(pipeline.pipeline_id)

    async def _persist_pipeline(self, pipeline: Pipeline) -> None:
        await self.fog_task_control_plane.save_pipeline_record(
            pipeline_id=pipeline.pipeline_id,
            name=pipeline.name,
            status=pipeline.status.value,
            definition_json=pipeline.to_dict(),
            created_by=pipeline.created_by,
            callback_url=pipeline.callback_url,
            error=pipeline.error,
            started_at=pipeline.started_at,
            completed_at=pipeline.completed_at,
        )

    def _prepare_pipeline_tasks(self, pipeline: Pipeline) -> None:
        for stage in pipeline.stages.values():
            for task in stage.tasks:
                if not task.idempotency_key:
                    task.idempotency_key = f"pipeline:{pipeline.pipeline_id}:{stage.stage_id}:{task.task_id}"

    def _apply_control_plane_task(self, task: PipelineTask, row) -> None:
        task.bind_worker(row.worker_id)
        task.attempt_id = row.current_attempt_id
        task.lease_id = row.current_lease_id
        task.assigned_at = row.assigned_at
        task.lease_expires_at = row.lease_expires_at
        task.status = TaskExecutionStatus(row.status)
        task.started_at = row.started_at
        task.completed_at = row.completed_at
        task.execution_time_ms = row.execution_time_ms
        task.result_data = row.result_json
        task.error_message = row.error
        task.retry_count = row.retry_count

    def _task_priority_for_pipeline(self, pipeline: Pipeline) -> str:
        if pipeline.priority >= 8:
            return "HIGH"
        if pipeline.priority <= 2:
            return "LOW"
        return "NORMAL"

    def _has_cycle(self, pipeline: Pipeline) -> bool:
        visited: set[str] = set()
        recursion: set[str] = set()

        def dfs(stage_id: str) -> bool:
            visited.add(stage_id)
            recursion.add(stage_id)
            for dep in pipeline.dependencies:
                if dep.source_stage_id != stage_id:
                    continue
                target = dep.target_stage_id
                if target not in visited:
                    if dfs(target):
                        return True
                elif target in recursion:
                    return True
            recursion.remove(stage_id)
            return False

        for stage_id in pipeline.stages:
            if stage_id not in visited and dfs(stage_id):
                return True
        return False

    def get_stats(self) -> dict[str, Any]:
        return {
            **self._stats,
            "active_pipelines": len(self._active_pipelines),
            "total_pipelines": len(self._pipelines),
            "is_running": self._is_running,
            "distributor": self.distributor.get_stats(),
        }
