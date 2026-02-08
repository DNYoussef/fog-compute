"""
Tests for Pipeline Task Distribution
FOG-006: Distributed AI Execution Pipeline

Tests cover:
- Pipeline models (Pipeline, Stage, Task)
- Task distributor and load balancing
- Pipeline scheduler
- AI task handlers
"""
import asyncio
import pytest
from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, MagicMock, patch

from pipeline.models import (
    Pipeline,
    PipelineStage,
    PipelineTask,
    PipelineStatus,
    StageStatus,
    PipelineDependency,
    DependencyType,
)
from pipeline.distributor import (
    TaskDistributor,
    LoadBalancer,
    DeviceMetrics,
    DistributionStrategy,
)
from pipeline.scheduler import PipelineScheduler, SchedulerConfig
from pipeline.ai_handlers import (
    AIInferenceHandler,
    DataPreprocessHandler,
    ModelDownloadHandler,
    get_ai_handler,
    register_ai_handler,
)
from task_engine.runner import TaskSpec, TaskResult, TaskStatus


# =============================================================================
# Pipeline Model Tests
# =============================================================================

class TestPipelineTask:
    """Tests for PipelineTask dataclass."""

    def test_create_task(self):
        """Test task creation with defaults."""
        task = PipelineTask()
        assert task.task_id.startswith("ptask-")
        assert task.status == StageStatus.PENDING
        assert task.retry_count == 0
        assert task.max_retries == 3

    def test_create_task_with_payload(self):
        """Test task creation with custom payload."""
        task = PipelineTask(
            task_type="compute",
            payload={"operation": "add", "a": 1, "b": 2},
        )
        assert task.task_type == "compute"
        assert task.payload["operation"] == "add"

    def test_task_to_dict(self):
        """Test task serialization."""
        task = PipelineTask(
            task_type="ai_inference",
            payload={"prompt": "test"},
        )
        d = task.to_dict()
        assert d["task_type"] == "ai_inference"
        assert d["payload"]["prompt"] == "test"
        assert d["status"] == "pending"


class TestPipelineStage:
    """Tests for PipelineStage dataclass."""

    def test_create_stage(self):
        """Test stage creation with defaults."""
        stage = PipelineStage(name="test_stage")
        assert stage.stage_id.startswith("stage-")
        assert stage.name == "test_stage"
        assert stage.status == StageStatus.PENDING
        assert stage.parallel_tasks == 1

    def test_add_task(self):
        """Test adding tasks to stage."""
        stage = PipelineStage(name="compute_stage")
        task = stage.add_task("compute", {"operation": "multiply"})

        assert len(stage.tasks) == 1
        assert task.stage_id == stage.stage_id
        assert task.task_type == "compute"

    def test_get_pending_tasks(self):
        """Test getting pending tasks."""
        stage = PipelineStage()
        stage.add_task("compute", {})
        stage.add_task("compute", {})
        stage.tasks[0].status = StageStatus.RUNNING

        pending = stage.get_pending_tasks()
        assert len(pending) == 1

    def test_get_running_tasks(self):
        """Test getting running tasks."""
        stage = PipelineStage()
        stage.add_task("compute", {})
        stage.add_task("compute", {})
        stage.tasks[0].status = StageStatus.RUNNING

        running = stage.get_running_tasks()
        assert len(running) == 1

    def test_is_complete(self):
        """Test stage completion check."""
        stage = PipelineStage()
        stage.add_task("compute", {})
        stage.add_task("compute", {})

        assert not stage.is_complete()

        stage.tasks[0].status = StageStatus.COMPLETED
        assert not stage.is_complete()

        stage.tasks[1].status = StageStatus.COMPLETED
        assert stage.is_complete()

    def test_is_complete_with_failures(self):
        """Test stage completion includes failures."""
        stage = PipelineStage()
        stage.add_task("compute", {})
        stage.tasks[0].status = StageStatus.FAILED

        assert stage.is_complete()
        assert stage.has_failures()

    def test_get_progress(self):
        """Test progress calculation."""
        stage = PipelineStage()
        stage.add_task("compute", {})
        stage.add_task("compute", {})
        stage.add_task("compute", {})
        stage.add_task("compute", {})

        assert stage.get_progress() == 0.0

        stage.tasks[0].status = StageStatus.COMPLETED
        assert stage.get_progress() == 25.0

        stage.tasks[1].status = StageStatus.COMPLETED
        assert stage.get_progress() == 50.0

    def test_stage_to_dict(self):
        """Test stage serialization."""
        stage = PipelineStage(
            name="test_stage",
            required_cpu_cores=4,
            required_gpu=True,
        )
        stage.add_task("compute", {})

        d = stage.to_dict()
        assert d["name"] == "test_stage"
        assert d["required_cpu_cores"] == 4
        assert d["required_gpu"] is True
        assert len(d["tasks"]) == 1


class TestPipeline:
    """Tests for Pipeline dataclass."""

    def test_create_pipeline(self):
        """Test pipeline creation."""
        pipeline = Pipeline(name="test_pipeline")
        assert pipeline.pipeline_id.startswith("pipe-")
        assert pipeline.name == "test_pipeline"
        assert pipeline.status == PipelineStatus.DRAFT

    def test_add_stage(self):
        """Test adding stages to pipeline."""
        pipeline = Pipeline(name="test")
        stage = PipelineStage(name="stage1")
        pipeline.add_stage(stage)

        assert stage.stage_id in pipeline.stages

    def test_add_dependency(self):
        """Test adding dependencies."""
        pipeline = Pipeline(name="test")
        stage1 = PipelineStage(name="stage1")
        stage2 = PipelineStage(name="stage2")
        pipeline.add_stage(stage1)
        pipeline.add_stage(stage2)

        pipeline.add_dependency(stage1.stage_id, stage2.stage_id)

        assert len(pipeline.dependencies) == 1
        assert pipeline.dependencies[0].source_stage_id == stage1.stage_id
        assert pipeline.dependencies[0].target_stage_id == stage2.stage_id

    def test_add_dependency_invalid_stage(self):
        """Test adding dependency with invalid stage."""
        pipeline = Pipeline(name="test")
        stage1 = PipelineStage(name="stage1")
        pipeline.add_stage(stage1)

        with pytest.raises(ValueError):
            pipeline.add_dependency(stage1.stage_id, "nonexistent")

    def test_get_ready_stages_no_deps(self):
        """Test getting ready stages without dependencies."""
        pipeline = Pipeline(name="test")
        stage1 = PipelineStage(name="stage1")
        stage2 = PipelineStage(name="stage2")
        pipeline.add_stage(stage1)
        pipeline.add_stage(stage2)

        ready = pipeline.get_ready_stages()
        assert len(ready) == 2

    def test_get_ready_stages_with_deps(self):
        """Test getting ready stages with dependencies."""
        pipeline = Pipeline(name="test")
        stage1 = PipelineStage(name="stage1")
        stage2 = PipelineStage(name="stage2")
        pipeline.add_stage(stage1)
        pipeline.add_stage(stage2)
        pipeline.add_dependency(stage1.stage_id, stage2.stage_id)

        ready = pipeline.get_ready_stages()
        assert len(ready) == 1
        assert ready[0].stage_id == stage1.stage_id

    def test_get_ready_stages_after_completion(self):
        """Test ready stages after dependency completion."""
        pipeline = Pipeline(name="test")
        stage1 = PipelineStage(name="stage1")
        stage2 = PipelineStage(name="stage2")
        pipeline.add_stage(stage1)
        pipeline.add_stage(stage2)
        pipeline.add_dependency(stage1.stage_id, stage2.stage_id)

        stage1.status = StageStatus.COMPLETED

        ready = pipeline.get_ready_stages()
        assert len(ready) == 1
        assert ready[0].stage_id == stage2.stage_id

    def test_get_entry_stages(self):
        """Test getting entry stages."""
        pipeline = Pipeline(name="test")
        stage1 = PipelineStage(name="stage1")
        stage2 = PipelineStage(name="stage2")
        stage3 = PipelineStage(name="stage3")
        pipeline.add_stage(stage1)
        pipeline.add_stage(stage2)
        pipeline.add_stage(stage3)
        pipeline.add_dependency(stage1.stage_id, stage2.stage_id)
        pipeline.add_dependency(stage2.stage_id, stage3.stage_id)

        entry = pipeline.get_entry_stages()
        assert len(entry) == 1
        assert entry[0].stage_id == stage1.stage_id

    def test_get_stage_dependencies(self):
        """Test getting stage dependencies."""
        pipeline = Pipeline(name="test")
        stage1 = PipelineStage(name="stage1")
        stage2 = PipelineStage(name="stage2")
        pipeline.add_stage(stage1)
        pipeline.add_stage(stage2)
        pipeline.add_dependency(stage1.stage_id, stage2.stage_id)

        deps = pipeline.get_stage_dependencies(stage2.stage_id)
        assert stage1.stage_id in deps

    def test_get_stage_dependents(self):
        """Test getting stage dependents."""
        pipeline = Pipeline(name="test")
        stage1 = PipelineStage(name="stage1")
        stage2 = PipelineStage(name="stage2")
        pipeline.add_stage(stage1)
        pipeline.add_stage(stage2)
        pipeline.add_dependency(stage1.stage_id, stage2.stage_id)

        dependents = pipeline.get_stage_dependents(stage1.stage_id)
        assert stage2.stage_id in dependents

    def test_is_complete(self):
        """Test pipeline completion check."""
        pipeline = Pipeline(name="test")
        stage = PipelineStage(name="stage1")
        pipeline.add_stage(stage)

        assert not pipeline.is_complete()

        stage.status = StageStatus.COMPLETED
        assert pipeline.is_complete()

    def test_get_progress(self):
        """Test pipeline progress."""
        pipeline = Pipeline(name="test")
        stage1 = PipelineStage(name="stage1")
        stage2 = PipelineStage(name="stage2")
        pipeline.add_stage(stage1)
        pipeline.add_stage(stage2)

        assert pipeline.get_progress() == 100.0  # No tasks

        stage1.add_task("compute", {})
        stage2.add_task("compute", {})

        assert pipeline.get_progress() == 0.0

        stage1.tasks[0].status = StageStatus.COMPLETED
        assert pipeline.get_progress() == 50.0

    def test_get_stats(self):
        """Test pipeline statistics."""
        pipeline = Pipeline(name="test")
        stage = PipelineStage(name="stage1")
        stage.add_task("compute", {})
        stage.add_task("compute", {})
        pipeline.add_stage(stage)

        stats = pipeline.get_stats()
        assert stats["total_stages"] == 1
        assert stats["total_tasks"] == 2


class TestPipelineDependency:
    """Tests for PipelineDependency."""

    def test_create_dependency(self):
        """Test dependency creation."""
        dep = PipelineDependency(
            source_stage_id="stage1",
            target_stage_id="stage2",
            dependency_type=DependencyType.DATA,
            data_key="output",
        )
        assert dep.source_stage_id == "stage1"
        assert dep.dependency_type == DependencyType.DATA
        assert dep.data_key == "output"

    def test_dependency_to_dict(self):
        """Test dependency serialization."""
        dep = PipelineDependency(
            source_stage_id="stage1",
            target_stage_id="stage2",
        )
        d = dep.to_dict()
        assert d["source_stage_id"] == "stage1"
        assert d["dependency_type"] == "sequential"


# =============================================================================
# Load Balancer Tests
# =============================================================================

class TestDeviceMetrics:
    """Tests for DeviceMetrics."""

    def test_create_metrics(self):
        """Test metrics creation."""
        metrics = DeviceMetrics(
            device_id="device-1",
            cpu_cores=8,
            memory_mb=16384,
            gpu_available=True,
        )
        assert metrics.device_id == "device-1"
        assert metrics.cpu_cores == 8
        assert metrics.reputation_score == 1.0

    def test_get_load_score(self):
        """Test load score calculation."""
        metrics = DeviceMetrics(
            device_id="device-1",
            cpu_usage_percent=50,
            memory_usage_percent=30,
            active_tasks=2,
            max_concurrent_tasks=5,
        )
        score = metrics.get_load_score()
        # (0.5 * 0.4) + (0.3 * 0.3) + (0.4 * 0.3) = 0.2 + 0.09 + 0.12 = 0.41
        assert 0.4 < score < 0.45

    def test_get_fitness_score_basic(self):
        """Test basic fitness score."""
        metrics = DeviceMetrics(
            device_id="device-1",
            cpu_cores=8,
            memory_mb=16384,
            cpu_usage_percent=0,
            memory_usage_percent=0,
        )
        score = metrics.get_fitness_score(required_cpu=4, required_memory=8192)
        assert score > 0

    def test_get_fitness_score_gpu_required(self):
        """Test fitness with GPU requirement."""
        metrics = DeviceMetrics(
            device_id="device-1",
            gpu_available=False,
        )
        score = metrics.get_fitness_score(required_gpu=True)
        assert score == 0.0

    def test_get_fitness_score_insufficient_resources(self):
        """Test fitness with insufficient resources."""
        metrics = DeviceMetrics(
            device_id="device-1",
            cpu_cores=2,
            memory_mb=1024,
            cpu_usage_percent=90,  # Only 0.2 cores available
        )
        score = metrics.get_fitness_score(required_cpu=4, required_memory=512)
        assert score == 0.0


class TestLoadBalancer:
    """Tests for LoadBalancer."""

    def test_create_balancer(self):
        """Test balancer creation."""
        balancer = LoadBalancer(strategy=DistributionStrategy.LEAST_LOADED)
        assert balancer.strategy == DistributionStrategy.LEAST_LOADED

    def test_register_device(self):
        """Test device registration."""
        balancer = LoadBalancer()
        metrics = DeviceMetrics(device_id="device-1")
        balancer.register_device(metrics)

        assert "device-1" in balancer._devices

    def test_unregister_device(self):
        """Test device unregistration."""
        balancer = LoadBalancer()
        metrics = DeviceMetrics(device_id="device-1")
        balancer.register_device(metrics)
        balancer.unregister_device("device-1")

        assert "device-1" not in balancer._devices

    def test_update_metrics(self):
        """Test metrics update."""
        balancer = LoadBalancer()
        metrics = DeviceMetrics(device_id="device-1", cpu_usage_percent=0)
        balancer.register_device(metrics)
        balancer.update_metrics("device-1", cpu_usage_percent=50)

        assert balancer._devices["device-1"].cpu_usage_percent == 50
        assert balancer._devices["device-1"].last_heartbeat is not None

    def test_get_available_devices(self):
        """Test getting available devices."""
        balancer = LoadBalancer()
        metrics1 = DeviceMetrics(
            device_id="device-1",
            cpu_cores=4,
            memory_mb=8192,
            is_available=True,
            last_heartbeat=datetime.now(UTC),
        )
        metrics2 = DeviceMetrics(
            device_id="device-2",
            is_available=False,  # Unavailable
            last_heartbeat=datetime.now(UTC),
        )
        balancer.register_device(metrics1)
        balancer.register_device(metrics2)

        available = balancer.get_available_devices()
        assert len(available) == 1
        assert available[0].device_id == "device-1"

    def test_get_available_devices_filters_stale(self):
        """Test that stale devices are filtered."""
        balancer = LoadBalancer()
        metrics = DeviceMetrics(
            device_id="device-1",
            cpu_cores=4,
            memory_mb=8192,
            is_available=True,
            last_heartbeat=datetime.now(UTC) - timedelta(minutes=5),  # Stale
        )
        balancer.register_device(metrics)

        available = balancer.get_available_devices()
        assert len(available) == 0

    @pytest.mark.asyncio
    async def test_select_device_round_robin(self):
        """Test round robin selection."""
        balancer = LoadBalancer(strategy=DistributionStrategy.ROUND_ROBIN)

        for i in range(3):
            metrics = DeviceMetrics(
                device_id=f"device-{i}",
                cpu_cores=4,
                memory_mb=8192,
                is_available=True,
                last_heartbeat=datetime.now(UTC),
            )
            balancer.register_device(metrics)

        selections = []
        for _ in range(6):
            device_id = await balancer.select_device()
            selections.append(device_id)
            balancer.release_device(device_id)

        # Should cycle through devices
        assert len(set(selections)) == 3

    @pytest.mark.asyncio
    async def test_select_device_least_loaded(self):
        """Test least loaded selection."""
        balancer = LoadBalancer(strategy=DistributionStrategy.LEAST_LOADED)

        metrics1 = DeviceMetrics(
            device_id="device-1",
            cpu_cores=4,
            memory_mb=8192,
            cpu_usage_percent=80,
            is_available=True,
            last_heartbeat=datetime.now(UTC),
        )
        metrics2 = DeviceMetrics(
            device_id="device-2",
            cpu_cores=4,
            memory_mb=8192,
            cpu_usage_percent=20,  # Lower load
            is_available=True,
            last_heartbeat=datetime.now(UTC),
        )
        balancer.register_device(metrics1)
        balancer.register_device(metrics2)

        device_id = await balancer.select_device()
        assert device_id == "device-2"

    @pytest.mark.asyncio
    async def test_select_device_reputation(self):
        """Test reputation-based selection."""
        balancer = LoadBalancer(strategy=DistributionStrategy.REPUTATION)

        metrics1 = DeviceMetrics(
            device_id="device-1",
            cpu_cores=4,
            memory_mb=8192,
            reputation_score=0.5,
            is_available=True,
            last_heartbeat=datetime.now(UTC),
        )
        metrics2 = DeviceMetrics(
            device_id="device-2",
            cpu_cores=4,
            memory_mb=8192,
            reputation_score=0.9,  # Higher reputation
            is_available=True,
            last_heartbeat=datetime.now(UTC),
        )
        balancer.register_device(metrics1)
        balancer.register_device(metrics2)

        device_id = await balancer.select_device()
        assert device_id == "device-2"

    @pytest.mark.asyncio
    async def test_select_device_no_available(self):
        """Test selection with no available devices."""
        balancer = LoadBalancer()
        device_id = await balancer.select_device()
        assert device_id is None

    def test_release_device(self):
        """Test releasing a device."""
        balancer = LoadBalancer()
        metrics = DeviceMetrics(device_id="device-1", active_tasks=2)
        balancer.register_device(metrics)

        balancer.release_device("device-1")
        assert balancer._devices["device-1"].active_tasks == 1

    def test_get_stats(self):
        """Test balancer statistics."""
        balancer = LoadBalancer(strategy=DistributionStrategy.LEAST_LOADED)
        metrics = DeviceMetrics(
            device_id="device-1",
            active_tasks=2,
            max_concurrent_tasks=5,
            is_available=True,
        )
        balancer.register_device(metrics)

        stats = balancer.get_stats()
        assert stats["total_devices"] == 1
        assert stats["total_active_tasks"] == 2
        assert stats["strategy"] == "least_loaded"


# =============================================================================
# Task Distributor Tests
# =============================================================================

class TestTaskDistributor:
    """Tests for TaskDistributor."""

    @pytest.fixture
    def distributor(self):
        """Create distributor with mock devices."""
        lb = LoadBalancer(strategy=DistributionStrategy.LEAST_LOADED)
        metrics = DeviceMetrics(
            device_id="device-1",
            cpu_cores=4,
            memory_mb=8192,
            is_available=True,
            last_heartbeat=datetime.now(UTC),
        )
        lb.register_device(metrics)
        return TaskDistributor(load_balancer=lb)

    @pytest.mark.asyncio
    async def test_distribute_task(self, distributor):
        """Test task distribution."""
        stage = PipelineStage(name="test")
        task = PipelineTask(task_type="compute")

        device_id = await distributor.distribute_task(task, stage)

        assert device_id == "device-1"
        assert task.status == StageStatus.RUNNING
        assert task.assigned_device_id == "device-1"

    @pytest.mark.asyncio
    async def test_distribute_task_no_devices(self):
        """Test distribution with no devices."""
        distributor = TaskDistributor()
        stage = PipelineStage(name="test")
        task = PipelineTask(task_type="compute")

        device_id = await distributor.distribute_task(task, stage)

        assert device_id is None
        assert task.task_id in distributor._pending_tasks

    @pytest.mark.asyncio
    async def test_distribute_task_callback(self):
        """Test distribution callback."""
        callback = AsyncMock()
        lb = LoadBalancer()
        lb.register_device(DeviceMetrics(
            device_id="device-1",
            is_available=True,
            last_heartbeat=datetime.now(UTC),
        ))
        distributor = TaskDistributor(load_balancer=lb, on_task_assigned=callback)

        stage = PipelineStage(name="test")
        task = PipelineTask(task_type="compute")

        await distributor.distribute_task(task, stage)

        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_task_complete_success(self, distributor):
        """Test handling successful task completion."""
        stage = PipelineStage(name="test")
        task = PipelineTask(task_type="compute")

        await distributor.distribute_task(task, stage)
        await distributor.handle_task_complete(
            task.task_id,
            success=True,
            result_data={"value": 42},
            execution_time_ms=100,
        )

        assert task.status == StageStatus.COMPLETED
        assert task.result_data == {"value": 42}

    @pytest.mark.asyncio
    async def test_handle_task_complete_failure(self, distributor):
        """Test handling task failure."""
        stage = PipelineStage(name="test")
        task = PipelineTask(task_type="compute")

        await distributor.distribute_task(task, stage)
        await distributor.handle_task_complete(
            task.task_id,
            success=False,
            error_message="Test error",
        )

        assert task.status == StageStatus.FAILED
        assert task.error_message == "Test error"

    @pytest.mark.asyncio
    async def test_handle_task_failure_with_retry(self, distributor):
        """Test task failure triggers retry."""
        stage = PipelineStage(name="test")
        task = PipelineTask(task_type="compute", max_retries=3)

        await distributor.distribute_task(task, stage)

        await distributor.handle_task_failure(
            task.task_id,
            error_message="Test error",
            should_retry=True,
        )

        assert task.retry_count == 1
        assert task.status == StageStatus.PENDING
        assert task.task_id in distributor._pending_tasks

    @pytest.mark.asyncio
    async def test_handle_task_failure_max_retries(self, distributor):
        """Test task failure after max retries."""
        stage = PipelineStage(name="test")
        task = PipelineTask(task_type="compute", max_retries=0)

        await distributor.distribute_task(task, stage)

        await distributor.handle_task_failure(
            task.task_id,
            error_message="Test error",
            should_retry=True,
        )

        assert task.status == StageStatus.FAILED

    def test_get_stats(self, distributor):
        """Test distributor statistics."""
        stats = distributor.get_stats()
        assert "total_distributed" in stats
        assert "load_balancer" in stats


# =============================================================================
# Pipeline Scheduler Tests
# =============================================================================

class TestSchedulerConfig:
    """Tests for SchedulerConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = SchedulerConfig()
        assert config.poll_interval_sec == 1.0
        assert config.max_concurrent_pipelines == 10
        assert config.distribution_strategy == DistributionStrategy.LEAST_LOADED


class TestPipelineScheduler:
    """Tests for PipelineScheduler."""

    @pytest.fixture
    def scheduler(self):
        """Create scheduler with mock devices."""
        config = SchedulerConfig(poll_interval_sec=0.1)
        lb = LoadBalancer()
        lb.register_device(DeviceMetrics(
            device_id="device-1",
            cpu_cores=4,
            memory_mb=8192,
            is_available=True,
            last_heartbeat=datetime.now(UTC),
        ))
        distributor = TaskDistributor(load_balancer=lb)
        return PipelineScheduler(config=config, distributor=distributor)

    def test_create_pipeline(self, scheduler):
        """Test pipeline creation."""
        pipeline = scheduler.create_pipeline(
            name="test_pipeline",
            description="Test description",
            priority=8,
        )

        assert pipeline.name == "test_pipeline"
        assert pipeline.priority == 8
        assert pipeline.pipeline_id in scheduler._pipelines

    def test_get_pipeline(self, scheduler):
        """Test getting pipeline by ID."""
        pipeline = scheduler.create_pipeline(name="test")
        retrieved = scheduler.get_pipeline(pipeline.pipeline_id)

        assert retrieved == pipeline

    def test_list_pipelines(self, scheduler):
        """Test listing pipelines."""
        scheduler.create_pipeline(name="test1", priority=5)
        scheduler.create_pipeline(name="test2", priority=8)

        pipelines = scheduler.list_pipelines()
        assert len(pipelines) == 2
        assert pipelines[0].priority == 8  # Higher priority first

    def test_list_pipelines_by_status(self, scheduler):
        """Test listing pipelines by status."""
        p1 = scheduler.create_pipeline(name="test1")
        p2 = scheduler.create_pipeline(name="test2")
        p1.status = PipelineStatus.RUNNING

        running = scheduler.list_pipelines(status=PipelineStatus.RUNNING)
        assert len(running) == 1
        assert running[0].pipeline_id == p1.pipeline_id

    @pytest.mark.asyncio
    async def test_submit_pipeline(self, scheduler):
        """Test pipeline submission."""
        pipeline = scheduler.create_pipeline(name="test")
        stage = PipelineStage(name="stage1")
        stage.add_task("compute", {})
        pipeline.add_stage(stage)

        success = await scheduler.submit_pipeline(pipeline)

        assert success
        assert pipeline.status == PipelineStatus.RUNNING
        assert pipeline.started_at is not None

    @pytest.mark.asyncio
    async def test_submit_pipeline_no_stages(self, scheduler):
        """Test submitting pipeline without stages."""
        pipeline = scheduler.create_pipeline(name="test")

        success = await scheduler.submit_pipeline(pipeline)

        assert not success

    @pytest.mark.asyncio
    async def test_submit_pipeline_with_cycle(self, scheduler):
        """Test submitting pipeline with dependency cycle."""
        pipeline = scheduler.create_pipeline(name="test")
        stage1 = PipelineStage(name="stage1")
        stage2 = PipelineStage(name="stage2")
        pipeline.add_stage(stage1)
        pipeline.add_stage(stage2)
        pipeline.add_dependency(stage1.stage_id, stage2.stage_id)
        pipeline.add_dependency(stage2.stage_id, stage1.stage_id)  # Cycle!

        success = await scheduler.submit_pipeline(pipeline)

        assert not success

    @pytest.mark.asyncio
    async def test_cancel_pipeline(self, scheduler):
        """Test pipeline cancellation."""
        pipeline = scheduler.create_pipeline(name="test")
        stage = PipelineStage(name="stage1")
        stage.add_task("compute", {})
        pipeline.add_stage(stage)
        await scheduler.submit_pipeline(pipeline)

        success = await scheduler.cancel_pipeline(pipeline.pipeline_id)

        assert success
        assert pipeline.status == PipelineStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_pause_resume_pipeline(self, scheduler):
        """Test pipeline pause and resume."""
        pipeline = scheduler.create_pipeline(name="test")
        stage = PipelineStage(name="stage1")
        stage.add_task("compute", {})
        pipeline.add_stage(stage)
        await scheduler.submit_pipeline(pipeline)

        await scheduler.pause_pipeline(pipeline.pipeline_id)
        assert pipeline.status == PipelineStatus.PAUSED

        await scheduler.resume_pipeline(pipeline.pipeline_id)
        assert pipeline.status == PipelineStatus.RUNNING

    @pytest.mark.asyncio
    async def test_handle_task_result(self, scheduler):
        """Test handling task result."""
        pipeline = scheduler.create_pipeline(name="test")
        stage = PipelineStage(name="stage1")
        task = stage.add_task("compute", {})
        pipeline.add_stage(stage)
        await scheduler.submit_pipeline(pipeline)

        # Simulate task assignment
        task.status = StageStatus.RUNNING
        task.assigned_device_id = "device-1"
        scheduler.distributor._assigned_tasks[task.task_id] = (task, "device-1")

        await scheduler.handle_task_result(
            pipeline.pipeline_id,
            task.task_id,
            success=True,
            result_data={"value": 42},
            execution_time_ms=100,
        )

        assert task.status == StageStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_scheduler_lifecycle(self, scheduler):
        """Test scheduler start and stop."""
        await scheduler.start()
        assert scheduler._is_running

        await asyncio.sleep(0.15)  # Let it poll once

        await scheduler.stop()
        assert not scheduler._is_running

    def test_get_stats(self, scheduler):
        """Test scheduler statistics."""
        scheduler.create_pipeline(name="test")

        stats = scheduler.get_stats()
        assert stats["pipelines_created"] == 1
        assert "distributor" in stats


# =============================================================================
# AI Handler Tests
# =============================================================================

class TestAIInferenceHandler:
    """Tests for AIInferenceHandler."""

    @pytest.fixture
    def handler(self):
        return AIInferenceHandler()

    def test_task_type(self, handler):
        """Test handler task type."""
        assert handler.task_type == "ai_inference"

    def test_can_handle(self, handler):
        """Test can_handle method."""
        spec = TaskSpec(task_id="test", task_type="ai_inference")
        assert handler.can_handle(spec)

        spec2 = TaskSpec(task_id="test", task_type="other")
        assert not handler.can_handle(spec2)

    @pytest.mark.asyncio
    async def test_text_generation(self, handler):
        """Test text generation inference."""
        spec = TaskSpec(
            task_id="test",
            task_type="ai_inference",
            payload={
                "type": "text_generation",
                "prompt": "Hello world",
                "max_tokens": 50,
            },
        )

        result = await handler.execute(spec)

        assert result.status == TaskStatus.COMPLETED
        assert result.result_data["type"] == "text_generation"
        assert "generated_text" in result.result_data

    @pytest.mark.asyncio
    async def test_classification(self, handler):
        """Test classification inference."""
        spec = TaskSpec(
            task_id="test",
            task_type="ai_inference",
            payload={
                "type": "classification",
                "text": "This is great!",
                "labels": ["positive", "negative"],
            },
        )

        result = await handler.execute(spec)

        assert result.status == TaskStatus.COMPLETED
        assert result.result_data["type"] == "classification"
        assert "predictions" in result.result_data

    @pytest.mark.asyncio
    async def test_embedding(self, handler):
        """Test embedding generation."""
        spec = TaskSpec(
            task_id="test",
            task_type="ai_inference",
            payload={
                "type": "embedding",
                "texts": ["Hello", "World"],
                "dimensions": 128,
            },
        )

        result = await handler.execute(spec)

        assert result.status == TaskStatus.COMPLETED
        assert result.result_data["type"] == "embedding"
        assert len(result.result_data["embeddings"]) == 2
        assert len(result.result_data["embeddings"][0]) == 128

    @pytest.mark.asyncio
    async def test_unknown_inference_type(self, handler):
        """Test unknown inference type."""
        spec = TaskSpec(
            task_id="test",
            task_type="ai_inference",
            payload={"type": "unknown"},
        )

        result = await handler.execute(spec)

        assert result.status == TaskStatus.FAILED
        assert "Unknown inference type" in result.error_message


class TestDataPreprocessHandler:
    """Tests for DataPreprocessHandler."""

    @pytest.fixture
    def handler(self):
        return DataPreprocessHandler()

    def test_task_type(self, handler):
        """Test handler task type."""
        assert handler.task_type == "data_preprocess"

    @pytest.mark.asyncio
    async def test_clean_text(self, handler):
        """Test text cleaning."""
        spec = TaskSpec(
            task_id="test",
            task_type="data_preprocess",
            payload={
                "operation": "clean",
                "text": "<p>Hello WORLD</p> https://example.com",
                "lowercase": True,
                "remove_html": True,
                "remove_urls": True,
            },
        )

        result = await handler.execute(spec)

        assert result.status == TaskStatus.COMPLETED
        assert result.result_data["cleaned_text"] == "hello world"

    @pytest.mark.asyncio
    async def test_tokenize(self, handler):
        """Test tokenization."""
        spec = TaskSpec(
            task_id="test",
            task_type="data_preprocess",
            payload={
                "operation": "tokenize",
                "text": "Hello, world! How are you?",
                "method": "word",
            },
        )

        result = await handler.execute(spec)

        assert result.status == TaskStatus.COMPLETED
        assert result.result_data["token_count"] == 5

    @pytest.mark.asyncio
    async def test_chunk_text(self, handler):
        """Test text chunking."""
        spec = TaskSpec(
            task_id="test",
            task_type="data_preprocess",
            payload={
                "operation": "chunk",
                "text": "A" * 100,
                "chunk_size": 30,
                "overlap": 10,
                "method": "char",
            },
        )

        result = await handler.execute(spec)

        assert result.status == TaskStatus.COMPLETED
        assert result.result_data["chunk_count"] >= 3

    @pytest.mark.asyncio
    async def test_extract_features(self, handler):
        """Test feature extraction."""
        spec = TaskSpec(
            task_id="test",
            task_type="data_preprocess",
            payload={
                "operation": "extract_features",
                "text": "Hello world. This is a test. Testing features",
            },
        )

        result = await handler.execute(spec)

        assert result.status == TaskStatus.COMPLETED
        features = result.result_data["features"]
        assert "word_count" in features
        assert "sentence_count" in features
        assert features["sentence_count"] == 3

    @pytest.mark.asyncio
    async def test_transform_flatten(self, handler):
        """Test data transformation."""
        spec = TaskSpec(
            task_id="test",
            task_type="data_preprocess",
            payload={
                "operation": "transform",
                "transform_type": "flatten",
                "data": {"a": {"b": 1, "c": 2}},
            },
        )

        result = await handler.execute(spec)

        assert result.status == TaskStatus.COMPLETED
        assert result.result_data["transformed_data"] == {"a.b": 1, "a.c": 2}


class TestModelDownloadHandler:
    """Tests for ModelDownloadHandler."""

    @pytest.fixture
    def handler(self):
        return ModelDownloadHandler()

    def test_task_type(self, handler):
        """Test handler task type."""
        assert handler.task_type == "model_download"

    @pytest.mark.asyncio
    async def test_download_model(self, handler):
        """Test model download."""
        spec = TaskSpec(
            task_id="test",
            task_type="model_download",
            payload={
                "operation": "download",
                "model_id": "bert-base",
                "source": "huggingface",
            },
        )

        result = await handler.execute(spec)

        assert result.status == TaskStatus.COMPLETED
        assert result.result_data["status"] == "downloaded"
        assert result.result_data["model_id"] == "bert-base"

    @pytest.mark.asyncio
    async def test_verify_model(self, handler):
        """Test model verification."""
        spec = TaskSpec(
            task_id="test",
            task_type="model_download",
            payload={
                "operation": "verify",
                "model_id": "bert-base",
            },
        )

        result = await handler.execute(spec)

        assert result.status == TaskStatus.COMPLETED
        assert result.result_data["verified"] is True

    @pytest.mark.asyncio
    async def test_cache_status(self, handler):
        """Test cache status check."""
        spec = TaskSpec(
            task_id="test",
            task_type="model_download",
            payload={
                "operation": "cache_status",
                "model_id": "bert-base",
            },
        )

        result = await handler.execute(spec)

        assert result.status == TaskStatus.COMPLETED
        assert "is_cached" in result.result_data

    @pytest.mark.asyncio
    async def test_clear_cache(self, handler):
        """Test cache clearing."""
        spec = TaskSpec(
            task_id="test",
            task_type="model_download",
            payload={
                "operation": "clear_cache",
                "model_id": "bert-base",
            },
        )

        result = await handler.execute(spec)

        assert result.status == TaskStatus.COMPLETED
        assert result.result_data["cleared"] is True


class TestHandlerRegistry:
    """Tests for AI handler registry."""

    def test_get_ai_handler(self):
        """Test getting handler by type."""
        handler = get_ai_handler("ai_inference")
        assert isinstance(handler, AIInferenceHandler)

        handler = get_ai_handler("data_preprocess")
        assert isinstance(handler, DataPreprocessHandler)

    def test_get_ai_handler_unknown(self):
        """Test getting unknown handler type."""
        handler = get_ai_handler("unknown_type")
        assert handler is None

    def test_register_ai_handler(self):
        """Test registering custom handler."""
        from pipeline.ai_handlers import AITaskHandler, AI_HANDLERS

        class CustomHandler(AITaskHandler):
            @property
            def task_type(self) -> str:
                return "custom_ai"

            async def execute(self, spec):
                return TaskResult(task_id=spec.task_id, status=TaskStatus.COMPLETED)

        register_ai_handler(CustomHandler)

        assert "custom_ai" in AI_HANDLERS
        handler = get_ai_handler("custom_ai")
        assert handler is not None


# =============================================================================
# Integration Tests
# =============================================================================

class TestPipelineIntegration:
    """Integration tests for pipeline system."""

    @pytest.mark.asyncio
    async def test_simple_pipeline_execution(self):
        """Test simple single-stage pipeline."""
        # Setup
        lb = LoadBalancer()
        lb.register_device(DeviceMetrics(
            device_id="device-1",
            cpu_cores=4,
            memory_mb=8192,
            is_available=True,
            last_heartbeat=datetime.now(UTC),
        ))
        distributor = TaskDistributor(load_balancer=lb)
        scheduler = PipelineScheduler(
            config=SchedulerConfig(poll_interval_sec=0.05),
            distributor=distributor,
        )

        # Create pipeline
        pipeline = scheduler.create_pipeline(name="simple_test")
        stage = PipelineStage(name="compute_stage")
        stage.add_task("compute", {"operation": "add", "a": 1, "b": 2})
        pipeline.add_stage(stage)

        # Submit
        await scheduler.submit_pipeline(pipeline)
        assert pipeline.status == PipelineStatus.RUNNING

        # The entry stage should be marked as READY
        assert stage.status == StageStatus.READY

        # Manually simulate what the scheduler loop would do
        task = stage.tasks[0]
        task.status = StageStatus.RUNNING
        task.assigned_device_id = "device-1"
        distributor._assigned_tasks[task.task_id] = (task, "device-1")

        # Now complete the task
        await scheduler.handle_task_result(
            pipeline.pipeline_id,
            task.task_id,
            success=True,
            result_data={"result": 3},
            execution_time_ms=50,
        )

        # Verify
        assert stage.status == StageStatus.COMPLETED
        assert pipeline.is_complete()

    @pytest.mark.asyncio
    async def test_multi_stage_pipeline(self):
        """Test multi-stage pipeline with dependencies."""
        # Setup
        lb = LoadBalancer()
        lb.register_device(DeviceMetrics(
            device_id="device-1",
            cpu_cores=4,
            memory_mb=8192,
            is_available=True,
            last_heartbeat=datetime.now(UTC),
        ))
        distributor = TaskDistributor(load_balancer=lb)
        scheduler = PipelineScheduler(
            config=SchedulerConfig(poll_interval_sec=0.05),
            distributor=distributor,
        )

        # Create pipeline
        pipeline = scheduler.create_pipeline(name="multi_stage_test")

        stage1 = PipelineStage(name="preprocess")
        stage1.add_task("data_preprocess", {"operation": "clean"})
        pipeline.add_stage(stage1)

        stage2 = PipelineStage(name="inference")
        stage2.add_task("ai_inference", {"type": "classification"})
        pipeline.add_stage(stage2)

        pipeline.add_dependency(
            stage1.stage_id,
            stage2.stage_id,
            dependency_type=DependencyType.DATA,
        )

        # Submit
        await scheduler.submit_pipeline(pipeline)

        # The entry stage (stage1) should be marked as READY
        assert stage1.status == StageStatus.READY
        # stage2 should still be PENDING (waiting on dependency)
        assert stage2.status == StageStatus.PENDING

        # Manually simulate stage1 task execution
        task1 = stage1.tasks[0]
        task1.status = StageStatus.RUNNING
        task1.assigned_device_id = "device-1"
        distributor._assigned_tasks[task1.task_id] = (task1, "device-1")

        # Complete stage1
        await scheduler.handle_task_result(
            pipeline.pipeline_id,
            task1.task_id,
            success=True,
            result_data={"cleaned": "text"},
            execution_time_ms=50,
        )

        # Now stage1 should be COMPLETED and stage2 should be READY
        assert stage1.status == StageStatus.COMPLETED
        assert stage2.status == StageStatus.READY
