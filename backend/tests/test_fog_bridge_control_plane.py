import pytest
from sqlalchemy import text

from backend.server.database import engine, get_alembic_head_revisions
from backend.server.models.database import Base
from backend.server.models.control_plane import (
    ControlPlaneTask,
    ControlPlaneTaskAttempt,
    ControlPlaneTaskLease,
    ControlPlaneWorker,
    PipelineRecord,
)
from backend.server.routes import fog_bridge
from backend.server.schemas.fog_bridge import (
    FogTaskCreate,
    TaskLeaseRequest,
    TaskLeaseRenewRequest,
    TaskPriority,
    TaskResultSubmit,
    TaskStartRequest,
    TaskType,
)
from backend.server.services.fog_task_control_plane import fog_task_control_plane


CONTROL_PLANE_TABLES = [
    ControlPlaneWorker.__table__,
    ControlPlaneTask.__table__,
    ControlPlaneTaskAttempt.__table__,
    ControlPlaneTaskLease.__table__,
    PipelineRecord.__table__,
]


@pytest.fixture(autouse=True)
async def reset_control_plane_state():
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
    await fog_task_control_plane.reset_state_for_tests()
    yield
    await fog_task_control_plane.reset_state_for_tests()


@pytest.mark.asyncio
async def test_route_level_lease_start_renew_and_result_flow():
    await fog_task_control_plane.register_worker(
        "worker-route",
        "Route Worker",
        "desktop",
        {"cpu_cores": 8, "memory_mb": 16384},
    )
    created = await fog_bridge.create_task(
        FogTaskCreate(
            task_type=TaskType.COMPUTE,
            priority=TaskPriority.NORMAL,
            payload={"job": "route-flow"},
            retry_count=1,
        ),
        device_id="worker-route",
    )
    assert created.status.value == "PENDING"

    leased = await fog_bridge.lease_task(TaskLeaseRequest(), device_id="worker-route")
    assert leased is not None
    assert leased.status.value == "LEASED"
    assert leased.attempt_id is not None
    assert leased.lease_id is not None

    started = await fog_bridge.start_task(
        leased.task_id,
        TaskStartRequest(attempt_id=leased.attempt_id, lease_id=leased.lease_id),
        device_id="worker-route",
    )
    assert started.status.value == "RUNNING"

    renewed = await fog_bridge.renew_task_lease(
        leased.task_id,
        TaskLeaseRenewRequest(
            attempt_id=leased.attempt_id,
            lease_id=leased.lease_id,
            lease_ttl_seconds=120,
        ),
        device_id="worker-route",
    )
    assert renewed.lease_expires_at is not None

    completed = await fog_bridge.submit_task_result(
        leased.task_id,
        TaskResultSubmit(
            task_id=leased.task_id,
            device_id="worker-route",
            attempt_id=leased.attempt_id,
            lease_id=leased.lease_id,
            success=True,
            result={"ok": True},
            execution_time_ms=25,
        ),
        device_id="worker-route",
    )
    assert completed.status.value == "SUCCEEDED"
    assert completed.result == {"ok": True}


@pytest.mark.asyncio
async def test_device_info_reports_plural_active_ownership():
    await fog_task_control_plane.register_worker(
        "worker-multi-route",
        "Route Multi Worker",
        "desktop",
        {"cpu_cores": 8, "memory_mb": 16384},
    )
    await fog_task_control_plane.update_worker_quota("worker-multi-route", max_concurrent_tasks=2)

    first = await fog_bridge.create_task(
        FogTaskCreate(
            task_type=TaskType.COMPUTE,
            priority=TaskPriority.NORMAL,
            payload={"job": "multi-a"},
            retry_count=1,
        ),
        device_id="worker-multi-route",
    )
    second = await fog_bridge.create_task(
        FogTaskCreate(
            task_type=TaskType.COMPUTE,
            priority=TaskPriority.NORMAL,
            payload={"job": "multi-b"},
            retry_count=1,
        ),
        device_id="worker-multi-route",
    )

    first_lease = await fog_bridge.lease_task(
        TaskLeaseRequest(preferred_task_id=first.task_id),
        device_id="worker-multi-route",
    )
    second_lease = await fog_bridge.lease_task(
        TaskLeaseRequest(preferred_task_id=second.task_id),
        device_id="worker-multi-route",
    )

    assert first_lease is not None
    assert second_lease is not None

    device = await fog_bridge.get_current_device_info(device_id="worker-multi-route")
    assert device.active_task_count == 2
    assert set(device.active_task_ids) == {first.task_id, second.task_id}
    assert set(device.active_attempt_ids) == {first_lease.attempt_id, second_lease.attempt_id}
    assert set(device.active_lease_ids) == {first_lease.lease_id, second_lease.lease_id}
    assert device.current_task_id is None


@pytest.mark.asyncio
async def test_readiness_route_reports_missing_schema_guarantees():
    async with engine.begin() as conn:
        await conn.exec_driver_sql("DROP INDEX IF EXISTS ix_cp_leases_active_task")

    readiness = await fog_bridge.readiness_check()
    assert readiness.ready is False
    assert readiness.failure_mode == "schema_guarantees_missing"
    assert readiness.details["schema"]["ready"] is False
    assert any(
        item["index"] == "ix_cp_leases_active_task"
        for item in readiness.details["schema"]["missing_indexes"]
    )
