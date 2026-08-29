import pytest
from datetime import UTC, datetime, timedelta
from sqlalchemy import text

from backend.pipeline.models import PipelineStage, PipelineStatus, StageStatus, TaskExecutionStatus
from backend.pipeline.scheduler import PipelineScheduler, SchedulerConfig
from backend.server.database import engine, get_alembic_head_revisions
from backend.server.models.database import Base
from backend.server.models.control_plane import ControlPlaneTaskState
from backend.server.models.control_plane import (
    ControlPlaneTask,
    ControlPlaneTaskAttempt,
    ControlPlaneTaskLease,
    ControlPlaneWorker,
    PipelineRecord,
)
from backend.server.services.fog_task_control_plane import FogTaskControlPlaneService


CONTROL_PLANE_TABLES = [
    ControlPlaneWorker.__table__,
    ControlPlaneTask.__table__,
    ControlPlaneTaskAttempt.__table__,
    ControlPlaneTaskLease.__table__,
    PipelineRecord.__table__,
]


@pytest.fixture
async def durable_control_plane():
    service = FogTaskControlPlaneService(lease_ttl_seconds=5)
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.drop_all(sync_conn, tables=CONTROL_PLANE_TABLES))
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=CONTROL_PLANE_TABLES))
        await conn.execute(
            text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)")
        )
        await conn.execute(text("DELETE FROM alembic_version"))
        for revision in get_alembic_head_revisions():
            await conn.execute(
                text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
                {"revision": revision},
            )
    await service.reset_state_for_tests()
    yield service
    await service.reset_state_for_tests()


def _make_scheduler(control_plane: FogTaskControlPlaneService) -> PipelineScheduler:
    return PipelineScheduler(
        config=SchedulerConfig(poll_interval_sec=0.01),
        fog_task_control_plane_service=control_plane,
    )


@pytest.mark.asyncio
async def test_pipeline_restart_mid_stage_recovers_running_task(durable_control_plane: FogTaskControlPlaneService):
    scheduler = _make_scheduler(durable_control_plane)
    pipeline = scheduler.create_pipeline(name="restart-mid-stage", created_by="worker-a")
    stage = PipelineStage(name="stage-1")
    task = stage.add_task("compute", {"value": 1}, max_retries=1)
    pipeline.add_stage(stage)
    await scheduler.submit_pipeline(pipeline)
    await scheduler._process_pipeline(pipeline)

    await durable_control_plane.register_worker("worker-a", "Worker A", "desktop", {"cpu_cores": 4, "memory_mb": 4096})
    grant = await durable_control_plane.lease_task("worker-a", preferred_task_id=task.task_id)
    assert grant is not None
    await durable_control_plane.start_task(
        task.task_id,
        worker_id="worker-a",
        attempt_id=grant.attempt.attempt_id,
        lease_id=grant.lease.lease_id,
    )

    restarted = _make_scheduler(durable_control_plane)
    await restarted.fog_task_control_plane.reconcile_startup()
    await restarted._load_persisted_pipelines()
    recovered = restarted.get_pipeline(pipeline.pipeline_id)
    assert recovered is not None
    recovered_task = recovered.stages[stage.stage_id].tasks[0]
    await restarted._process_pipeline(recovered)
    assert recovered_task.status == TaskExecutionStatus.RUNNING


@pytest.mark.asyncio
async def test_pipeline_retry_after_failure_requeues_through_control_plane(durable_control_plane: FogTaskControlPlaneService):
    scheduler = _make_scheduler(durable_control_plane)
    pipeline = scheduler.create_pipeline(name="retry-after-failure", created_by="worker-a")
    stage = PipelineStage(name="stage-1")
    task = stage.add_task("compute", {"value": 2}, max_retries=1)
    pipeline.add_stage(stage)
    await scheduler.submit_pipeline(pipeline)
    await scheduler._process_pipeline(pipeline)

    await durable_control_plane.register_worker("worker-a", "Worker A", "desktop", {"cpu_cores": 4, "memory_mb": 4096})
    grant = await durable_control_plane.lease_task("worker-a", preferred_task_id=task.task_id)
    assert grant is not None
    await durable_control_plane.start_task(
        task.task_id,
        worker_id="worker-a",
        attempt_id=grant.attempt.attempt_id,
        lease_id=grant.lease.lease_id,
    )
    await durable_control_plane.complete_task(
        task.task_id,
        worker_id="worker-a",
        attempt_id=grant.attempt.attempt_id,
        lease_id=grant.lease.lease_id,
        success=False,
        result=None,
        error="boom",
        execution_time_ms=10,
    )

    await scheduler._process_pipeline(pipeline)

    row = await durable_control_plane.get_task(task.task_id)
    assert row is not None
    assert row.status == ControlPlaneTaskState.PENDING.value
    assert row.retry_count == 1
    assert task.status == TaskExecutionStatus.PENDING


@pytest.mark.asyncio
async def test_pipeline_partial_stage_completion_reconciles_after_expiry(durable_control_plane: FogTaskControlPlaneService):
    now = datetime.now(UTC)
    scheduler = _make_scheduler(durable_control_plane)
    pipeline = scheduler.create_pipeline(name="partial-stage", created_by="worker-a")
    stage = PipelineStage(name="stage-1")
    task_a = stage.add_task("compute", {"value": "a"}, max_retries=1)
    task_b = stage.add_task("compute", {"value": "b"}, max_retries=1)
    pipeline.add_stage(stage)
    await scheduler.submit_pipeline(pipeline)
    await scheduler._process_pipeline(pipeline)

    await durable_control_plane.register_worker("worker-a", "Worker A", "desktop", {"cpu_cores": 4, "memory_mb": 4096})
    await durable_control_plane.register_worker("worker-b", "Worker B", "desktop", {"cpu_cores": 4, "memory_mb": 4096})

    grant_a = await durable_control_plane.lease_task("worker-a", preferred_task_id=task_a.task_id, now=now)
    grant_b = await durable_control_plane.lease_task("worker-b", preferred_task_id=task_b.task_id, now=now)
    assert grant_a is not None and grant_b is not None

    await durable_control_plane.start_task(task_a.task_id, worker_id="worker-a", attempt_id=grant_a.attempt.attempt_id, lease_id=grant_a.lease.lease_id)
    await durable_control_plane.start_task(task_b.task_id, worker_id="worker-b", attempt_id=grant_b.attempt.attempt_id, lease_id=grant_b.lease.lease_id)

    await durable_control_plane.complete_task(
        task_a.task_id,
        worker_id="worker-a",
        attempt_id=grant_a.attempt.attempt_id,
        lease_id=grant_a.lease.lease_id,
        success=True,
        result={"value": "done"},
        error=None,
        execution_time_ms=5,
    )
    await durable_control_plane.expire_stale_leases(now=now + timedelta(seconds=10))

    restarted = _make_scheduler(durable_control_plane)
    await restarted.fog_task_control_plane.reconcile_startup()
    await restarted._load_persisted_pipelines()
    recovered = restarted.get_pipeline(pipeline.pipeline_id)
    assert recovered is not None
    await restarted._process_pipeline(recovered)

    recovered_stage = recovered.stages[stage.stage_id]
    task_map = {task.task_id: task for task in recovered_stage.tasks}
    assert task_map[task_a.task_id].status == TaskExecutionStatus.SUCCEEDED
    assert task_map[task_b.task_id].status == TaskExecutionStatus.PENDING

    grant_b_retry = await durable_control_plane.lease_task("worker-b", preferred_task_id=task_b.task_id)
    assert grant_b_retry is not None
    await durable_control_plane.start_task(task_b.task_id, worker_id="worker-b", attempt_id=grant_b_retry.attempt.attempt_id, lease_id=grant_b_retry.lease.lease_id)
    await durable_control_plane.complete_task(
        task_b.task_id,
        worker_id="worker-b",
        attempt_id=grant_b_retry.attempt.attempt_id,
        lease_id=grant_b_retry.lease.lease_id,
        success=True,
        result={"value": "done-too"},
        error=None,
        execution_time_ms=5,
    )

    await restarted._process_pipeline(recovered)
    assert recovered_stage.status == StageStatus.COMPLETED
    assert recovered.status == PipelineStatus.COMPLETED


@pytest.mark.asyncio
async def test_duplicate_resume_attempt_returns_false(durable_control_plane: FogTaskControlPlaneService):
    scheduler = _make_scheduler(durable_control_plane)
    pipeline = scheduler.create_pipeline(name="resume-dup")
    stage = PipelineStage(name="stage-1")
    stage.add_task("compute", {"value": 1})
    pipeline.add_stage(stage)
    await scheduler.submit_pipeline(pipeline)

    paused = await scheduler.pause_pipeline(pipeline.pipeline_id)
    resumed = await scheduler.resume_pipeline(pipeline.pipeline_id)
    duplicate_resume = await scheduler.resume_pipeline(pipeline.pipeline_id)

    assert paused is True
    assert resumed is True
    assert duplicate_resume is False
