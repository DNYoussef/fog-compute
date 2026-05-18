import asyncio
import pytest
from datetime import UTC, datetime, timedelta
from sqlalchemy import text

from backend.server.database import engine, get_alembic_head_revisions
from backend.server.models.database import Base
from backend.server.models.control_plane import (
    ControlPlaneTask,
    ControlPlaneTaskAttempt,
    ControlPlaneTaskLease,
    ControlPlaneTaskState,
    ControlPlaneWorker,
    PipelineRecord,
)
from backend.server.services.fog_task_control_plane import (
    ControlPlaneConflictError,
    ControlPlaneSchemaError,
    FogTaskControlPlaneService,
)
from backend.server.services.acurast_cargo import FOG_RESULT_TRUST_KEY


CONTROL_PLANE_TABLES = [
    ControlPlaneWorker.__table__,
    ControlPlaneTask.__table__,
    ControlPlaneTaskAttempt.__table__,
    ControlPlaneTaskLease.__table__,
    PipelineRecord.__table__,
]


async def _prepare_control_plane_tables() -> None:
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


@pytest.fixture
async def control_plane():
    service = FogTaskControlPlaneService(lease_ttl_seconds=5)
    await _prepare_control_plane_tables()
    await service.reset_state_for_tests()
    yield service
    await service.reset_state_for_tests()


@pytest.mark.asyncio
async def test_duplicate_assignment_rejected(control_plane: FogTaskControlPlaneService):
    await control_plane.register_worker("worker-1", "Worker 1", "desktop", {"cpu_cores": 4, "memory_mb": 4096})
    await control_plane.register_worker("worker-2", "Worker 2", "desktop", {"cpu_cores": 4, "memory_mb": 4096})
    await control_plane.create_task(
        task_id="task-1",
        task_type="compute",
        priority="NORMAL",
        payload={"op": "add"},
    )

    grant = await control_plane.lease_task("worker-1")
    assert grant is not None
    assert grant.task.task_id == "task-1"

    duplicate = await control_plane.lease_task("worker-2")
    assert duplicate is None

    task = await control_plane.get_task("task-1")
    assert task is not None
    assert task.status == ControlPlaneTaskState.LEASED.value


@pytest.mark.asyncio
async def test_stale_lease_expiry_and_reassignment(control_plane: FogTaskControlPlaneService):
    now = datetime.now(UTC)
    await control_plane.register_worker("worker-1", "Worker 1", "desktop", {"cpu_cores": 4, "memory_mb": 4096})
    await control_plane.register_worker("worker-2", "Worker 2", "desktop", {"cpu_cores": 4, "memory_mb": 4096})
    await control_plane.create_task(
        task_id="task-expire",
        task_type="compute",
        priority="NORMAL",
        payload={"op": "mul"},
        max_retries=2,
    )

    first = await control_plane.lease_task("worker-1", preferred_task_id="task-expire", now=now)
    assert first is not None
    await control_plane.start_task(
        "task-expire",
        worker_id="worker-1",
        attempt_id=first.attempt.attempt_id,
        lease_id=first.lease.lease_id,
    )

    expired = await control_plane.expire_stale_leases(now=now + timedelta(seconds=10))
    assert expired == 1

    expired_task = await control_plane.get_task("task-expire")
    assert expired_task is not None
    assert expired_task.status == ControlPlaneTaskState.EXPIRED.value

    requeued = await control_plane.requeue_task("task-expire", reason="retry after expiry")
    assert requeued is not None
    assert requeued.status == ControlPlaneTaskState.PENDING.value

    second = await control_plane.lease_task("worker-2", preferred_task_id="task-expire", now=now + timedelta(seconds=11))
    assert second is not None
    assert second.attempt.attempt_id != first.attempt.attempt_id
    assert second.lease.lease_id != first.lease.lease_id


@pytest.mark.asyncio
async def test_duplicate_completion_is_idempotent_and_stale_completion_is_rejected(control_plane: FogTaskControlPlaneService):
    await control_plane.register_worker("worker-1", "Worker 1", "desktop", {"cpu_cores": 4, "memory_mb": 4096})
    await control_plane.create_task(
        task_id="task-complete",
        task_type="compute",
        priority="NORMAL",
        payload={"op": "ok"},
    )
    grant = await control_plane.lease_task("worker-1", preferred_task_id="task-complete")
    assert grant is not None
    await control_plane.start_task(
        "task-complete",
        worker_id="worker-1",
        attempt_id=grant.attempt.attempt_id,
        lease_id=grant.lease.lease_id,
    )

    completed, duplicate = await control_plane.complete_task(
        "task-complete",
        worker_id="worker-1",
        attempt_id=grant.attempt.attempt_id,
        lease_id=grant.lease.lease_id,
        success=True,
        result={"value": 42},
        error=None,
        execution_time_ms=5,
    )
    assert duplicate is False
    assert completed.status == ControlPlaneTaskState.SUCCEEDED.value

    completed_again, duplicate_again = await control_plane.complete_task(
        "task-complete",
        worker_id="worker-1",
        attempt_id=grant.attempt.attempt_id,
        lease_id=grant.lease.lease_id,
        success=True,
        result={"value": 42},
        error=None,
        execution_time_ms=5,
    )
    assert duplicate_again is True
    assert completed_again.status == ControlPlaneTaskState.SUCCEEDED.value

    await control_plane.register_worker("worker-2", "Worker 2", "desktop", {"cpu_cores": 4, "memory_mb": 4096})
    await control_plane.create_task(
        task_id="task-stale",
        task_type="compute",
        priority="NORMAL",
        payload={"op": "stale"},
        max_retries=2,
    )
    first = await control_plane.lease_task("worker-1", preferred_task_id="task-stale", now=datetime.now(UTC))
    assert first is not None
    await control_plane.expire_stale_leases(now=datetime.now(UTC) + timedelta(seconds=10))
    await control_plane.requeue_task("task-stale", reason="expired")
    second = await control_plane.lease_task("worker-2", preferred_task_id="task-stale")
    assert second is not None

    with pytest.raises(ControlPlaneConflictError):
        await control_plane.complete_task(
            "task-stale",
            worker_id="worker-1",
            attempt_id=first.attempt.attempt_id,
            lease_id=first.lease.lease_id,
            success=True,
            result={"value": 1},
            error=None,
            execution_time_ms=5,
        )


@pytest.mark.asyncio
async def test_acurast_cargo_completion_without_receipt_is_recorded_untrusted(
    control_plane: FogTaskControlPlaneService,
):
    await control_plane.register_worker("worker-acurast", "Worker Acurast", "desktop", {"cpu_cores": 4, "memory_mb": 4096})
    await control_plane.create_task(
        task_id="task-acurast-missing-receipt",
        task_type="compute",
        priority="NORMAL",
        payload={"op": "sum"},
    )
    grant = await control_plane.lease_task("worker-acurast", preferred_task_id="task-acurast-missing-receipt")
    assert grant is not None

    completed, duplicate = await control_plane.complete_task(
        "task-acurast-missing-receipt",
        worker_id="worker-acurast",
        attempt_id=grant.attempt.attempt_id,
        lease_id=grant.lease.lease_id,
        success=True,
        result={
            "schema_version": "fog.acurast-cargo.result.v1",
            "task_id": "task-acurast-missing-receipt",
            "execution": {
                "provider": "acurast_cargo",
                "deployment_id": "Acurast:test:1",
            },
            "result": {"value": 29, "value_type": "number"},
        },
        error=None,
        execution_time_ms=5,
    )

    assert duplicate is False
    trust = completed.result_json[FOG_RESULT_TRUST_KEY]
    assert trust["provider"] == "acurast_cargo"
    assert trust["trusted"] is False
    assert trust["receipt_state"] == "missing"


@pytest.mark.asyncio
async def test_acurast_cargo_completion_with_malformed_receipt_is_recorded_untrusted(
    control_plane: FogTaskControlPlaneService,
):
    await control_plane.register_worker("worker-acurast", "Worker Acurast", "desktop", {"cpu_cores": 4, "memory_mb": 4096})
    await control_plane.create_task(
        task_id="task-acurast-bad-receipt",
        task_type="compute",
        priority="NORMAL",
        payload={"op": "sum"},
    )
    grant = await control_plane.lease_task("worker-acurast", preferred_task_id="task-acurast-bad-receipt")
    assert grant is not None

    completed, duplicate = await control_plane.complete_task(
        "task-acurast-bad-receipt",
        worker_id="worker-acurast",
        attempt_id=grant.attempt.attempt_id,
        lease_id=grant.lease.lease_id,
        success=True,
        result={
            "schema_version": "fog.acurast-cargo.result.v1",
            "task_id": "task-acurast-bad-receipt",
            "execution": {
                "provider": "acurast_cargo",
                "deployment_id": "Acurast:test:2",
                "receipt": {"kind": "bridge"},
            },
            "result": {"value": 29, "value_type": "number"},
        },
        error=None,
        execution_time_ms=5,
    )

    assert duplicate is False
    trust = completed.result_json[FOG_RESULT_TRUST_KEY]
    assert trust["trusted"] is False
    assert trust["receipt_state"] == "malformed"
    assert "payload_hash" in trust["reason"]


@pytest.mark.asyncio
async def test_worker_crash_before_completion_clears_ownership(control_plane: FogTaskControlPlaneService):
    now = datetime.now(UTC)
    await control_plane.register_worker("worker-1", "Worker 1", "desktop", {"cpu_cores": 4, "memory_mb": 4096})
    await control_plane.create_task(
        task_id="task-crash",
        task_type="compute",
        priority="NORMAL",
        payload={"op": "sleep"},
        max_retries=1,
    )
    grant = await control_plane.lease_task("worker-1", preferred_task_id="task-crash", now=now)
    assert grant is not None
    await control_plane.start_task(
        "task-crash",
        worker_id="worker-1",
        attempt_id=grant.attempt.attempt_id,
        lease_id=grant.lease.lease_id,
    )

    await control_plane.expire_stale_leases(now=now + timedelta(seconds=10))

    worker = await control_plane.get_worker("worker-1")
    task = await control_plane.get_task("task-crash")
    assert worker is not None
    assert task is not None
    assert worker.current_task_id is None
    assert task.status == ControlPlaneTaskState.EXPIRED.value


@pytest.mark.asyncio
async def test_restart_reconciliation_expires_leased_and_running_work(control_plane: FogTaskControlPlaneService):
    now = datetime.now(UTC)
    await control_plane.register_worker("worker-1", "Worker 1", "desktop", {"cpu_cores": 4, "memory_mb": 4096})
    await control_plane.create_task(
        task_id="task-restart",
        task_type="compute",
        priority="NORMAL",
        payload={"op": "restart"},
    )
    grant = await control_plane.lease_task("worker-1", preferred_task_id="task-restart", now=now)
    assert grant is not None
    await control_plane.start_task(
        "task-restart",
        worker_id="worker-1",
        attempt_id=grant.attempt.attempt_id,
        lease_id=grant.lease.lease_id,
    )

    restarted_service = FogTaskControlPlaneService(lease_ttl_seconds=5)
    result = await restarted_service.reconcile_startup(now=now + timedelta(seconds=10))
    assert result["expired_leases"] == 1

    task = await restarted_service.get_task("task-restart")
    assert task is not None
    assert task.status == ControlPlaneTaskState.EXPIRED.value


@pytest.mark.asyncio
async def test_two_workers_polling_same_task_yields_single_lease(control_plane: FogTaskControlPlaneService):
    await control_plane.register_worker("worker-a", "Worker A", "desktop", {"cpu_cores": 4, "memory_mb": 4096})
    await control_plane.register_worker("worker-b", "Worker B", "desktop", {"cpu_cores": 4, "memory_mb": 4096})
    await control_plane.create_task(
        task_id="task-contended-lease",
        task_type="compute",
        priority="NORMAL",
        payload={"op": "lease-race"},
    )

    first, second = await asyncio.gather(
        control_plane.lease_task("worker-a", preferred_task_id="task-contended-lease"),
        control_plane.lease_task("worker-b", preferred_task_id="task-contended-lease"),
    )

    grants = [grant for grant in (first, second) if grant is not None]
    assert len(grants) == 1
    history = await control_plane.get_attempt_history("task-contended-lease")
    assert len(history) == 1


@pytest.mark.asyncio
async def test_lease_expiry_race_with_renew_keeps_single_outcome(control_plane: FogTaskControlPlaneService):
    now = datetime.now(UTC)
    await control_plane.register_worker("worker-renew", "Worker Renew", "desktop", {"cpu_cores": 4, "memory_mb": 4096})
    await control_plane.create_task(
        task_id="task-renew-race",
        task_type="compute",
        priority="NORMAL",
        payload={"op": "renew-race"},
    )
    grant = await control_plane.lease_task("worker-renew", preferred_task_id="task-renew-race", now=now)
    assert grant is not None
    await control_plane.start_task(
        "task-renew-race",
        worker_id="worker-renew",
        attempt_id=grant.attempt.attempt_id,
        lease_id=grant.lease.lease_id,
    )

    async def attempt_renew():
        try:
            task = await control_plane.renew_lease(
                "task-renew-race",
                worker_id="worker-renew",
                attempt_id=grant.attempt.attempt_id,
                lease_id=grant.lease.lease_id,
                lease_ttl_seconds=20,
                now=now + timedelta(seconds=4),
            )
            return ("renewed", task)
        except ControlPlaneConflictError:
            return ("conflict", None)

    renew_result, expired_count = await asyncio.gather(
        attempt_renew(),
        control_plane.expire_stale_leases(now=now + timedelta(seconds=6)),
    )
    task = await control_plane.get_task("task-renew-race")
    assert task is not None
    if renew_result[0] == "renewed":
        assert expired_count == 0
        assert task.status == ControlPlaneTaskState.RUNNING.value
        assert task.current_lease_id == grant.lease.lease_id
    else:
        assert task.status == ControlPlaneTaskState.EXPIRED.value
        assert task.current_lease_id is None


@pytest.mark.asyncio
async def test_duplicate_result_submission_under_contention_is_idempotent(control_plane: FogTaskControlPlaneService):
    await control_plane.register_worker("worker-result", "Worker Result", "desktop", {"cpu_cores": 4, "memory_mb": 4096})
    await control_plane.create_task(
        task_id="task-result-race",
        task_type="compute",
        priority="NORMAL",
        payload={"op": "complete-race"},
    )
    grant = await control_plane.lease_task("worker-result", preferred_task_id="task-result-race")
    assert grant is not None
    await control_plane.start_task(
        "task-result-race",
        worker_id="worker-result",
        attempt_id=grant.attempt.attempt_id,
        lease_id=grant.lease.lease_id,
    )

    results = await asyncio.gather(
        control_plane.complete_task(
            "task-result-race",
            worker_id="worker-result",
            attempt_id=grant.attempt.attempt_id,
            lease_id=grant.lease.lease_id,
            success=True,
            result={"value": 7},
            error=None,
            execution_time_ms=3,
        ),
        control_plane.complete_task(
            "task-result-race",
            worker_id="worker-result",
            attempt_id=grant.attempt.attempt_id,
            lease_id=grant.lease.lease_id,
            success=True,
            result={"value": 7},
            error=None,
            execution_time_ms=3,
        ),
    )

    duplicate_flags = sorted(duplicate for _task, duplicate in results)
    assert duplicate_flags == [False, True]
    task = await control_plane.get_task("task-result-race")
    assert task is not None
    assert task.status == ControlPlaneTaskState.SUCCEEDED.value


@pytest.mark.asyncio
async def test_concurrent_restart_recovery_expires_single_lease_once(control_plane: FogTaskControlPlaneService):
    now = datetime.now(UTC)
    await control_plane.register_worker("worker-recover", "Worker Recover", "desktop", {"cpu_cores": 4, "memory_mb": 4096})
    await control_plane.create_task(
        task_id="task-recover-race",
        task_type="compute",
        priority="NORMAL",
        payload={"op": "recover-race"},
    )
    grant = await control_plane.lease_task("worker-recover", preferred_task_id="task-recover-race", now=now)
    assert grant is not None
    await control_plane.start_task(
        "task-recover-race",
        worker_id="worker-recover",
        attempt_id=grant.attempt.attempt_id,
        lease_id=grant.lease.lease_id,
    )

    first = FogTaskControlPlaneService(lease_ttl_seconds=5)
    second = FogTaskControlPlaneService(lease_ttl_seconds=5)
    result_a, result_b = await asyncio.gather(
        first.reconcile_startup(now=now + timedelta(seconds=10)),
        second.reconcile_startup(now=now + timedelta(seconds=10)),
    )

    assert result_a["expired_leases"] + result_b["expired_leases"] == 1
    task = await control_plane.get_task("task-recover-race")
    assert task is not None
    assert task.status == ControlPlaneTaskState.EXPIRED.value


@pytest.mark.asyncio
async def test_schema_readiness_fails_when_active_lease_index_missing(control_plane: FogTaskControlPlaneService):
    async with engine.begin() as conn:
        await conn.exec_driver_sql("DROP INDEX IF EXISTS ix_cp_leases_active_task")

    readiness = await control_plane.get_readiness_snapshot(force_refresh=True)
    assert readiness["ready"] is False
    assert readiness["failure_mode"] == "schema_guarantees_missing"
    assert any(
        item["index"] == "ix_cp_leases_active_task"
        for item in readiness["details"]["schema"]["missing_indexes"]
    )

    with pytest.raises(ControlPlaneSchemaError):
        await control_plane.create_task(
            task_id="task-schema-missing",
            task_type="compute",
            priority="NORMAL",
            payload={"op": "schema-check"},
        )


@pytest.mark.asyncio
async def test_schema_readiness_fails_when_unique_attempt_index_missing(control_plane: FogTaskControlPlaneService):
    async with engine.begin() as conn:
        await conn.exec_driver_sql("DROP INDEX IF EXISTS ix_cp_attempts_task_number")

    readiness = await control_plane.get_readiness_snapshot(force_refresh=True)
    assert readiness["ready"] is False
    assert readiness["failure_mode"] == "schema_guarantees_missing"
    assert any(
        item["index"] == "ix_cp_attempts_task_number"
        for item in readiness["details"]["schema"]["missing_indexes"]
    )


@pytest.mark.asyncio
async def test_worker_multi_task_reporting_uses_plural_active_leases(control_plane: FogTaskControlPlaneService):
    await control_plane.register_worker("worker-multi", "Worker Multi", "desktop", {"cpu_cores": 8, "memory_mb": 16384})
    await control_plane.update_worker_quota("worker-multi", max_concurrent_tasks=2)
    await control_plane.create_task(
        task_id="task-multi-a",
        task_type="compute",
        priority="NORMAL",
        payload={"op": "a"},
    )
    await control_plane.create_task(
        task_id="task-multi-b",
        task_type="compute",
        priority="NORMAL",
        payload={"op": "b"},
    )

    grant_a = await control_plane.lease_task("worker-multi", preferred_task_id="task-multi-a")
    grant_b = await control_plane.lease_task("worker-multi", preferred_task_id="task-multi-b")

    assert grant_a is not None
    assert grant_b is not None

    active_leases = await control_plane.get_worker_active_leases("worker-multi")
    assert {lease.task_id for lease in active_leases} == {"task-multi-a", "task-multi-b"}

    worker = await control_plane.get_worker("worker-multi")
    assert worker is not None
    assert worker.current_task_id is None

    metrics = await control_plane.get_metrics()
    assert metrics["workers_busy"] == 1


@pytest.mark.asyncio
async def test_metrics_expose_lease_and_reassignment_counters(control_plane: FogTaskControlPlaneService):
    now = datetime.now(UTC)
    await control_plane.register_worker("worker-metrics-a", "Worker Metrics A", "desktop", {"cpu_cores": 4, "memory_mb": 4096})
    await control_plane.register_worker("worker-metrics-b", "Worker Metrics B", "desktop", {"cpu_cores": 4, "memory_mb": 4096})

    await control_plane.create_task(
        task_id="task-metrics-success",
        task_type="compute",
        priority="NORMAL",
        payload={"op": "success"},
    )
    success_grant = await control_plane.lease_task("worker-metrics-a", preferred_task_id="task-metrics-success", now=now)
    assert success_grant is not None
    await control_plane.start_task(
        "task-metrics-success",
        worker_id="worker-metrics-a",
        attempt_id=success_grant.attempt.attempt_id,
        lease_id=success_grant.lease.lease_id,
    )
    await control_plane.renew_lease(
        "task-metrics-success",
        worker_id="worker-metrics-a",
        attempt_id=success_grant.attempt.attempt_id,
        lease_id=success_grant.lease.lease_id,
        lease_ttl_seconds=30,
        now=now + timedelta(seconds=1),
    )
    await control_plane.complete_task(
        "task-metrics-success",
        worker_id="worker-metrics-a",
        attempt_id=success_grant.attempt.attempt_id,
        lease_id=success_grant.lease.lease_id,
        success=True,
        result={"ok": True},
        error=None,
        execution_time_ms=4,
        now=now + timedelta(seconds=2),
    )
    await control_plane.complete_task(
        "task-metrics-success",
        worker_id="worker-metrics-a",
        attempt_id=success_grant.attempt.attempt_id,
        lease_id=success_grant.lease.lease_id,
        success=True,
        result={"ok": True},
        error=None,
        execution_time_ms=4,
        now=now + timedelta(seconds=2),
    )

    await control_plane.create_task(
        task_id="task-metrics-expired",
        task_type="compute",
        priority="NORMAL",
        payload={"op": "expired"},
        max_retries=2,
    )
    expired_grant = await control_plane.lease_task("worker-metrics-a", preferred_task_id="task-metrics-expired", now=now)
    assert expired_grant is not None
    await control_plane.start_task(
        "task-metrics-expired",
        worker_id="worker-metrics-a",
        attempt_id=expired_grant.attempt.attempt_id,
        lease_id=expired_grant.lease.lease_id,
    )
    await control_plane.expire_stale_leases(now=now + timedelta(seconds=10))
    await control_plane.requeue_task("task-metrics-expired", reason="retry after expiry", now=now + timedelta(seconds=11))
    replacement_grant = await control_plane.lease_task("worker-metrics-b", preferred_task_id="task-metrics-expired", now=now + timedelta(seconds=12))
    assert replacement_grant is not None

    with pytest.raises(ControlPlaneConflictError):
        await control_plane.complete_task(
            "task-metrics-expired",
            worker_id="worker-metrics-a",
            attempt_id=expired_grant.attempt.attempt_id,
            lease_id=expired_grant.lease.lease_id,
            success=True,
            result={"ok": False},
            error=None,
            execution_time_ms=4,
            now=now + timedelta(seconds=12),
        )

    metrics = await control_plane.get_metrics()
    assert metrics["fog_task_control_plane_lease_acquire_attempts_total"] >= 3
    assert metrics["fog_task_control_plane_lease_acquire_grants_total"] >= 3
    assert metrics["fog_task_control_plane_lease_renew_success_total"] >= 1
    assert metrics["fog_task_control_plane_lease_expiry_total"] >= 1
    assert metrics["fog_task_control_plane_task_reassignment_total"] >= 1
    assert metrics["fog_task_control_plane_stale_completion_rejections_total"] >= 1
    assert metrics["fog_task_control_plane_duplicate_result_total"] >= 1
