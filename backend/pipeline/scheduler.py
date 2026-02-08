"""
Pipeline Scheduler
FOG-006: Orchestrates pipeline execution across fog network

Manages pipeline lifecycle, stage transitions, and result aggregation.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Optional, Any, Callable, Awaitable

from .models import (
    Pipeline,
    PipelineStage,
    PipelineTask,
    PipelineStatus,
    StageStatus,
    DependencyType,
)
from .distributor import TaskDistributor, LoadBalancer, DistributionStrategy

logger = logging.getLogger(__name__)


@dataclass
class SchedulerConfig:
    """
    Pipeline scheduler configuration.

    FOG-006: Configurable scheduling behavior.
    """
    # Polling intervals
    poll_interval_sec: float = 1.0        # Check for ready stages
    heartbeat_interval_sec: float = 30.0  # Device heartbeat timeout

    # Execution limits
    max_concurrent_pipelines: int = 10
    max_concurrent_stages: int = 5
    max_task_retries: int = 3

    # Timeouts
    default_stage_timeout_sec: int = 3600
    default_pipeline_timeout_sec: int = 86400

    # Distribution
    distribution_strategy: DistributionStrategy = DistributionStrategy.LEAST_LOADED
    prefer_locality: bool = True

    # Result handling
    aggregate_stage_results: bool = True
    store_intermediate_results: bool = True


class PipelineScheduler:
    """
    Pipeline execution scheduler.

    FOG-006: Core orchestration component.

    Features:
    - Multiple concurrent pipelines
    - Dependency-aware stage scheduling
    - Automatic failure recovery
    - Result aggregation and forwarding
    """

    def __init__(
        self,
        config: Optional[SchedulerConfig] = None,
        distributor: Optional[TaskDistributor] = None,
        on_pipeline_complete: Optional[Callable[[Pipeline], Awaitable[None]]] = None,
        on_stage_complete: Optional[Callable[[Pipeline, PipelineStage], Awaitable[None]]] = None,
    ):
        """
        Initialize scheduler.

        Args:
            config: Scheduler configuration
            distributor: Task distributor instance
            on_pipeline_complete: Callback when pipeline completes
            on_stage_complete: Callback when stage completes
        """
        self.config = config or SchedulerConfig()
        self.distributor = distributor or TaskDistributor(
            load_balancer=LoadBalancer(strategy=self.config.distribution_strategy)
        )

        self._on_pipeline_complete = on_pipeline_complete
        self._on_stage_complete = on_stage_complete

        # Pipeline storage
        self._pipelines: dict[str, Pipeline] = {}
        self._active_pipelines: set[str] = set()

        # Execution state
        self._is_running = False
        self._scheduler_task: Optional[asyncio.Task] = None

        # Statistics
        self._stats = {
            "pipelines_created": 0,
            "pipelines_completed": 0,
            "pipelines_failed": 0,
            "stages_executed": 0,
            "tasks_distributed": 0,
        }

        logger.info(f"PipelineScheduler initialized: {self.config.distribution_strategy.value}")

    async def start(self) -> None:
        """Start the scheduler."""
        if self._is_running:
            return

        self._is_running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("PipelineScheduler started")

    async def stop(self) -> None:
        """Stop the scheduler."""
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
        """
        Create a new pipeline.

        Returns:
            New Pipeline instance
        """
        pipeline = Pipeline(
            name=name,
            description=description,
            priority=priority,
            created_by=created_by,
            callback_url=callback_url,
        )

        self._pipelines[pipeline.pipeline_id] = pipeline
        self._stats["pipelines_created"] += 1

        logger.info(f"Created pipeline: {pipeline.pipeline_id} ({name})")
        return pipeline

    def get_pipeline(self, pipeline_id: str) -> Optional[Pipeline]:
        """Get a pipeline by ID."""
        return self._pipelines.get(pipeline_id)

    def list_pipelines(
        self,
        status: Optional[PipelineStatus] = None,
        limit: int = 100,
    ) -> list[Pipeline]:
        """List pipelines with optional filter."""
        pipelines = list(self._pipelines.values())

        if status:
            pipelines = [p for p in pipelines if p.status == status]

        # Sort by priority (higher first), then by creation time
        pipelines.sort(key=lambda p: (-p.priority, p.created_at))

        return pipelines[:limit]

    async def submit_pipeline(self, pipeline: Pipeline) -> bool:
        """
        Submit a pipeline for execution.

        Validates the pipeline and queues it for scheduling.

        Returns:
            True if submitted successfully
        """
        # Validate pipeline
        if not pipeline.stages:
            logger.error(f"Pipeline {pipeline.pipeline_id} has no stages")
            return False

        # Check for cycles (simple DFS)
        if self._has_cycle(pipeline):
            logger.error(f"Pipeline {pipeline.pipeline_id} has dependency cycles")
            return False

        # Check concurrent limit
        if len(self._active_pipelines) >= self.config.max_concurrent_pipelines:
            logger.warning(
                f"Max concurrent pipelines reached ({self.config.max_concurrent_pipelines})"
            )
            pipeline.status = PipelineStatus.PENDING
            return True

        # Start pipeline
        pipeline.status = PipelineStatus.RUNNING
        pipeline.started_at = datetime.now(UTC)
        self._active_pipelines.add(pipeline.pipeline_id)

        # Mark entry stages as ready
        for stage in pipeline.get_entry_stages():
            stage.status = StageStatus.READY

        logger.info(f"Pipeline {pipeline.pipeline_id} submitted")
        return True

    def _has_cycle(self, pipeline: Pipeline) -> bool:
        """Check for dependency cycles using DFS."""
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def dfs(stage_id: str) -> bool:
            visited.add(stage_id)
            rec_stack.add(stage_id)

            for dep in pipeline.dependencies:
                if dep.source_stage_id == stage_id:
                    target = dep.target_stage_id
                    if target not in visited:
                        if dfs(target):
                            return True
                    elif target in rec_stack:
                        return True

            rec_stack.remove(stage_id)
            return False

        for stage_id in pipeline.stages:
            if stage_id not in visited:
                if dfs(stage_id):
                    return True

        return False

    async def cancel_pipeline(self, pipeline_id: str) -> bool:
        """Cancel a running pipeline."""
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            return False

        if pipeline.status not in (PipelineStatus.RUNNING, PipelineStatus.PENDING):
            return False

        pipeline.status = PipelineStatus.CANCELLED
        pipeline.completed_at = datetime.now(UTC)
        self._active_pipelines.discard(pipeline_id)

        # Cancel running stages
        for stage in pipeline.stages.values():
            if stage.status == StageStatus.RUNNING:
                stage.status = StageStatus.SKIPPED

        logger.info(f"Pipeline {pipeline_id} cancelled")
        return True

    async def pause_pipeline(self, pipeline_id: str) -> bool:
        """Pause a running pipeline."""
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline or pipeline.status != PipelineStatus.RUNNING:
            return False

        pipeline.status = PipelineStatus.PAUSED
        logger.info(f"Pipeline {pipeline_id} paused")
        return True

    async def resume_pipeline(self, pipeline_id: str) -> bool:
        """Resume a paused pipeline."""
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline or pipeline.status != PipelineStatus.PAUSED:
            return False

        pipeline.status = PipelineStatus.RUNNING
        logger.info(f"Pipeline {pipeline_id} resumed")
        return True

    async def _scheduler_loop(self) -> None:
        """Main scheduling loop."""
        while self._is_running:
            try:
                await self._process_pipelines()
                await asyncio.sleep(self.config.poll_interval_sec)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(1)

    async def _process_pipelines(self) -> None:
        """Process all active pipelines."""
        # Check pending pipelines
        pending = [
            p for p in self._pipelines.values()
            if p.status == PipelineStatus.PENDING
        ]

        for pipeline in pending:
            if len(self._active_pipelines) < self.config.max_concurrent_pipelines:
                await self.submit_pipeline(pipeline)

        # Process active pipelines
        for pipeline_id in list(self._active_pipelines):
            pipeline = self._pipelines.get(pipeline_id)
            if not pipeline:
                self._active_pipelines.discard(pipeline_id)
                continue

            if pipeline.status != PipelineStatus.RUNNING:
                continue

            await self._process_pipeline(pipeline)

    async def _process_pipeline(self, pipeline: Pipeline) -> None:
        """Process a single pipeline."""
        # Check timeout
        if pipeline.started_at:
            elapsed = (datetime.now(UTC) - pipeline.started_at).total_seconds()
            if elapsed > pipeline.timeout_seconds:
                pipeline.status = PipelineStatus.FAILED
                pipeline.error = "Pipeline timeout"
                pipeline.completed_at = datetime.now(UTC)
                self._active_pipelines.discard(pipeline.pipeline_id)
                self._stats["pipelines_failed"] += 1
                await self._notify_pipeline_complete(pipeline)
                return

        # Process ready stages
        ready_stages = pipeline.get_ready_stages()

        for stage in ready_stages[:self.config.max_concurrent_stages]:
            await self._execute_stage(pipeline, stage)

        # Check for completion
        if pipeline.is_complete():
            await self._complete_pipeline(pipeline)

    async def _execute_stage(self, pipeline: Pipeline, stage: PipelineStage) -> None:
        """Execute a pipeline stage."""
        stage.status = StageStatus.RUNNING
        stage.started_at = datetime.now(UTC)
        self._stats["stages_executed"] += 1

        logger.info(f"Starting stage {stage.stage_id} ({stage.name})")

        # Get data from dependencies if needed
        stage_data = await self._gather_dependency_data(pipeline, stage)

        # Distribute tasks
        for task in stage.get_pending_tasks():
            # Inject dependency data into task payload
            if stage_data:
                task.payload["_dependency_data"] = stage_data

            device_id = await self.distributor.distribute_task(task, stage)
            self._stats["tasks_distributed"] += 1

            if device_id:
                logger.debug(f"Task {task.task_id} -> device {device_id}")

    async def _gather_dependency_data(
        self,
        pipeline: Pipeline,
        stage: PipelineStage
    ) -> dict[str, Any]:
        """Gather output data from completed dependencies."""
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

    async def handle_task_result(
        self,
        pipeline_id: str,
        task_id: str,
        success: bool,
        result_data: Optional[dict[str, Any]] = None,
        error_message: Optional[str] = None,
        execution_time_ms: int = 0,
    ) -> None:
        """Handle task completion from a device."""
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            logger.warning(f"Unknown pipeline: {pipeline_id}")
            return

        # Find the task
        task = None
        stage = None
        for s in pipeline.stages.values():
            for t in s.tasks:
                if t.task_id == task_id:
                    task = t
                    stage = s
                    break
            if task:
                break

        if not task or not stage:
            logger.warning(f"Unknown task: {task_id}")
            return

        # Update task
        await self.distributor.handle_task_complete(
            task_id, success, result_data, error_message, execution_time_ms
        )

        # Check stage completion
        if stage.is_complete():
            await self._complete_stage(pipeline, stage)

    async def _complete_stage(self, pipeline: Pipeline, stage: PipelineStage) -> None:
        """Handle stage completion."""
        stage.completed_at = datetime.now(UTC)

        if stage.has_failures():
            if stage.fail_fast:
                stage.status = StageStatus.FAILED
                stage.error = "Stage failed due to task failure(s)"
            else:
                # Partial completion
                stage.status = StageStatus.COMPLETED
        else:
            stage.status = StageStatus.COMPLETED

        # Aggregate results if configured
        if stage.aggregate_results:
            stage.results = self._aggregate_task_results(stage)

        logger.info(
            f"Stage {stage.stage_id} ({stage.name}) completed: {stage.status.value}"
        )

        # Notify
        if self._on_stage_complete:
            try:
                await self._on_stage_complete(pipeline, stage)
            except Exception as e:
                logger.error(f"Stage complete callback failed: {e}")

        # Mark dependent stages as ready
        for dependent_id in pipeline.get_stage_dependents(stage.stage_id):
            dependent = pipeline.stages.get(dependent_id)
            if dependent and dependent.status == StageStatus.PENDING:
                # Check all dependencies
                all_deps_complete = all(
                    pipeline.stages[d].status == StageStatus.COMPLETED
                    for d in pipeline.get_stage_dependencies(dependent_id)
                )
                if all_deps_complete:
                    dependent.status = StageStatus.READY

    def _aggregate_task_results(self, stage: PipelineStage) -> dict[str, Any]:
        """Aggregate results from all tasks in a stage."""
        results: dict[str, Any] = {
            "task_count": len(stage.tasks),
            "successful_count": sum(
                1 for t in stage.tasks if t.status == StageStatus.COMPLETED
            ),
            "failed_count": sum(
                1 for t in stage.tasks if t.status == StageStatus.FAILED
            ),
            "total_execution_time_ms": sum(t.execution_time_ms for t in stage.tasks),
            "task_results": [],
        }

        for task in stage.tasks:
            if task.result_data:
                results["task_results"].append({
                    "task_id": task.task_id,
                    "data": task.result_data,
                })

        return results

    async def _complete_pipeline(self, pipeline: Pipeline) -> None:
        """Handle pipeline completion."""
        pipeline.completed_at = datetime.now(UTC)
        self._active_pipelines.discard(pipeline.pipeline_id)

        if pipeline.has_failures():
            pipeline.status = PipelineStatus.FAILED
            pipeline.error = "Pipeline failed due to stage failure(s)"
            self._stats["pipelines_failed"] += 1
        else:
            pipeline.status = PipelineStatus.COMPLETED
            self._stats["pipelines_completed"] += 1

        # Aggregate final results
        pipeline.final_results = self._aggregate_pipeline_results(pipeline)

        logger.info(
            f"Pipeline {pipeline.pipeline_id} ({pipeline.name}) completed: "
            f"{pipeline.status.value}"
        )

        # Notify
        await self._notify_pipeline_complete(pipeline)

    def _aggregate_pipeline_results(self, pipeline: Pipeline) -> dict[str, Any]:
        """Aggregate results from all stages."""
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
        """Send completion notification."""
        if self._on_pipeline_complete:
            try:
                await self._on_pipeline_complete(pipeline)
            except Exception as e:
                logger.error(f"Pipeline complete callback failed: {e}")

        # Send to callback URL if specified
        if pipeline.callback_url:
            await self._send_callback(pipeline)

    async def _send_callback(self, pipeline: Pipeline) -> None:
        """Send HTTP callback with pipeline results."""
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    pipeline.callback_url,
                    json=pipeline.to_dict(),
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status >= 400:
                        logger.warning(
                            f"Callback failed for {pipeline.pipeline_id}: "
                            f"{response.status}"
                        )
        except ImportError:
            logger.warning("aiohttp not available for callbacks")
        except Exception as e:
            logger.error(f"Callback error for {pipeline.pipeline_id}: {e}")

    def get_stats(self) -> dict[str, Any]:
        """Get scheduler statistics."""
        return {
            **self._stats,
            "active_pipelines": len(self._active_pipelines),
            "total_pipelines": len(self._pipelines),
            "is_running": self._is_running,
            "distributor": self.distributor.get_stats(),
        }
