"""
Fog task control-plane implementation.

Authoritative request-path imports should use
``backend.server.services.fog_task_control_plane``. This module keeps the
implementation so older imports do not break immediately.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Any, Optional
import logging
import uuid

from sqlalchemy import case, delete, func, inspect, or_, select, update

from ..database import AsyncSessionLocal, get_database_migration_state
from ..models.control_plane import (
    ControlPlaneLeaseStatus,
    ControlPlaneTask,
    ControlPlaneTaskAttempt,
    ControlPlaneTaskLease,
    ControlPlaneTaskState,
    ControlPlaneWorker,
    ControlPlaneWorkerStatus,
    PipelineRecord,
)
from .fog_task_control_plane_metrics import FogTaskControlPlaneMetrics

logger = logging.getLogger(__name__)


DEFAULT_LEASE_TTL_SECONDS = 60
HEARTBEAT_STALENESS_SECONDS = 120
SCHEMA_CACHE_TTL_SECONDS = 30
TASK_PRIORITY_ORDER = {
    "CRITICAL": 0,
    "HIGH": 1,
    "NORMAL": 2,
    "LOW": 3,
    "BACKGROUND": 4,
}
TERMINAL_TASK_STATES = {
    ControlPlaneTaskState.SUCCEEDED.value,
    ControlPlaneTaskState.FAILED.value,
    ControlPlaneTaskState.CANCELLED.value,
}
ACTIVE_TASK_STATES = {
    ControlPlaneTaskState.LEASED.value,
    ControlPlaneTaskState.RUNNING.value,
}
REQUIRED_CONTROL_PLANE_TABLES = {
    "control_plane_workers",
    "control_plane_tasks",
    "control_plane_task_attempts",
    "control_plane_task_leases",
    "pipeline_records",
}
REQUIRED_CONTROL_PLANE_INDEXES = {
    "control_plane_tasks": {
        "ix_cp_tasks_status",
        "ix_cp_tasks_worker",
        "ix_cp_tasks_worker_status",
        "ix_cp_tasks_pipeline",
        "ix_cp_tasks_created_at",
    },
    "control_plane_task_attempts": {
        "ix_cp_attempts_task",
        "ix_cp_attempts_lease",
        "ix_cp_attempts_task_number",
    },
    "control_plane_task_leases": {
        "ix_cp_leases_task",
        "ix_cp_leases_status",
        "ix_cp_leases_expires_at",
        "ix_cp_leases_status_expires_at",
        "ix_cp_leases_attempt",
        "ix_cp_leases_active_task",
    },
}
FOG_TASK_CONTROL_PLANE_COUNTER_NAMES = (
    "fog_task_control_plane_lease_acquire_attempts_total",
    "fog_task_control_plane_lease_acquire_grants_total",
    "fog_task_control_plane_lease_contention_total",
    "fog_task_control_plane_lease_renew_success_total",
    "fog_task_control_plane_lease_renew_conflict_total",
    "fog_task_control_plane_lease_expiry_total",
    "fog_task_control_plane_task_reassignment_total",
    "fog_task_control_plane_stale_completion_rejections_total",
    "fog_task_control_plane_duplicate_result_total",
    "fog_task_control_plane_startup_recovery_expired_total",
)


def _coerce_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class ControlPlaneError(RuntimeError):
    """Base control-plane error."""


class ControlPlaneNotFoundError(ControlPlaneError):
    """Raised when a requested control-plane row does not exist."""


class ControlPlaneConflictError(ControlPlaneError):
    """Raised when a stale or conflicting state transition is attempted."""


class ControlPlaneValidationError(ControlPlaneError):
    """Raised when an invalid request is made against the control plane."""


class ControlPlaneSchemaError(ControlPlaneError):
    """Raised when required DB guarantees are missing."""


class ControlPlaneMigrationError(ControlPlaneSchemaError):
    """Raised when Alembic migration state is missing or behind head."""


@dataclass(frozen=True)
class LeaseGrant:
    """Lease result returned to workers."""

    task: ControlPlaneTask
    attempt: ControlPlaneTaskAttempt
    lease: ControlPlaneTaskLease


@dataclass(frozen=True)
class WorkerActiveLease:
    """Authoritative active ownership record for a worker."""

    task_id: str
    attempt_id: str
    lease_id: str
    status: str
    assigned_at: Optional[datetime]
    lease_expires_at: Optional[datetime]


class FogTaskControlPlaneService:
    """Durable DB-backed ownership service for fog task execution."""

    def __init__(
        self,
        lease_ttl_seconds: int = DEFAULT_LEASE_TTL_SECONDS,
        heartbeat_staleness_seconds: int = HEARTBEAT_STALENESS_SECONDS,
    ) -> None:
        self.lease_ttl_seconds = max(1, int(lease_ttl_seconds))
        self.heartbeat_staleness_seconds = max(1, int(heartbeat_staleness_seconds))
        self._metrics = FogTaskControlPlaneMetrics(FOG_TASK_CONTROL_PLANE_COUNTER_NAMES)
        self._schema_cache: Optional[dict[str, Any]] = None
        self._schema_cache_checked_at: float = 0.0
        self._migration_cache: Optional[dict[str, Any]] = None
        self._migration_cache_checked_at: float = 0.0

    @staticmethod
    def _supports_skip_locked(session) -> bool:
        bind = session.get_bind()
        return bind is not None and bind.dialect.name == "postgresql"

    async def _get_worker_for_update(self, session, worker_id: str) -> Optional[ControlPlaneWorker]:
        query = select(ControlPlaneWorker).where(ControlPlaneWorker.worker_id == worker_id)
        if self._supports_skip_locked(session):
            query = query.with_for_update()
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def _get_task_for_update(self, session, task_id: str) -> Optional[ControlPlaneTask]:
        query = select(ControlPlaneTask).where(ControlPlaneTask.task_id == task_id)
        if self._supports_skip_locked(session):
            query = query.with_for_update()
        result = await session.execute(query)
        return result.scalar_one_or_none()

    def _bump_metric(self, name: str, value: int = 1) -> None:
        self._metrics.bump(name, value)

    def _log_task_event(
        self,
        level: int,
        message: str,
        *,
        task_id: Optional[str] = None,
        attempt_id: Optional[str] = None,
        lease_id: Optional[str] = None,
        worker_id: Optional[str] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> None:
        payload = {
            "task_id": task_id,
            "attempt_id": attempt_id,
            "lease_id": lease_id,
            "worker_id": worker_id,
        }
        if extra:
            payload.update(extra)
        details = ", ".join(f"{key}={value}" for key, value in payload.items() if value is not None)
        logger.log(level, "%s%s", message, f" [{details}]" if details else "")

    async def _get_schema_report(self, *, force_refresh: bool = False) -> dict[str, Any]:
        now = monotonic()
        if (
            not force_refresh
            and self._schema_cache is not None
            and now - self._schema_cache_checked_at < SCHEMA_CACHE_TTL_SECONDS
        ):
            return self._schema_cache

        async with AsyncSessionLocal() as session:
            connection = await session.connection()
            report = await connection.run_sync(self._collect_schema_report)

        self._schema_cache = report
        self._schema_cache_checked_at = now
        return report

    async def _get_migration_report(self, *, force_refresh: bool = False) -> dict[str, Any]:
        now = monotonic()
        if (
            not force_refresh
            and self._migration_cache is not None
            and now - self._migration_cache_checked_at < SCHEMA_CACHE_TTL_SECONDS
        ):
            return self._migration_cache

        report = await get_database_migration_state()
        self._migration_cache = report
        self._migration_cache_checked_at = now
        return report

    def _collect_schema_report(self, sync_connection) -> dict[str, Any]:
        inspector = inspect(sync_connection)
        tables = set(inspector.get_table_names())
        report: dict[str, Any] = {
            "ready": True,
            "dialect": sync_connection.dialect.name,
            "missing_tables": [],
            "missing_indexes": [],
            "invalid_indexes": [],
        }

        report["missing_tables"] = sorted(REQUIRED_CONTROL_PLANE_TABLES - tables)
        if report["missing_tables"]:
            report["ready"] = False
            return report

        for table_name, required_indexes in REQUIRED_CONTROL_PLANE_INDEXES.items():
            indexes = {index["name"]: index for index in inspector.get_indexes(table_name)}
            missing = sorted(required_indexes - set(indexes))
            if missing:
                report["missing_indexes"].extend(
                    {"table": table_name, "index": index_name}
                    for index_name in missing
                )

        partial_sql = ""
        dialect_name = sync_connection.dialect.name
        if dialect_name == "postgresql":
            rows = sync_connection.exec_driver_sql(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = current_schema()
                  AND tablename = 'control_plane_task_leases'
                """
            ).mappings()
            partial_sql = next(
                (row["indexdef"] for row in rows if row["indexname"] == "ix_cp_leases_active_task"),
                "",
            )
        elif dialect_name == "sqlite":
            rows = sync_connection.exec_driver_sql(
                """
                SELECT name, sql
                FROM sqlite_master
                WHERE type = 'index'
                  AND tbl_name = 'control_plane_task_leases'
                """
            ).mappings()
            partial_sql = next(
                (row["sql"] or "" for row in rows if row["name"] == "ix_cp_leases_active_task"),
                "",
            )

        if "ACTIVE" not in (partial_sql or ""):
            report["invalid_indexes"].append(
                {
                    "table": "control_plane_task_leases",
                    "index": "ix_cp_leases_active_task",
                    "reason": "partial unique ACTIVE lease predicate missing",
                }
            )

        if report["missing_indexes"] or report["invalid_indexes"]:
            report["ready"] = False

        return report

    async def _ensure_runtime_ready(self) -> None:
        migration_report = await self._get_migration_report()
        if not migration_report["ready"]:
            raise ControlPlaneMigrationError(
                "Fog task control-plane migration state is not ready: "
                f"state={migration_report['state']}, "
                f"expected_heads={migration_report['expected_head_revisions']}, "
                f"current_revisions={migration_report['current_revisions']}"
            )

        report = await self._get_schema_report()
        if report["ready"]:
            return
        raise ControlPlaneSchemaError(
            "Fog task control-plane schema is not ready: "
            f"missing_tables={report['missing_tables']}, "
            f"missing_indexes={report['missing_indexes']}, "
                f"invalid_indexes={report['invalid_indexes']}"
        )

    async def ensure_ready(self, *, force_refresh: bool = False) -> None:
        """Public readiness fence for request handlers that read control-plane state."""
        if force_refresh:
            self._migration_cache = None
            self._migration_cache_checked_at = 0.0
            self._schema_cache = None
            self._schema_cache_checked_at = 0.0
        await self._ensure_runtime_ready()

    async def register_worker(
        self,
        worker_id: str,
        device_name: str,
        device_type: str,
        capabilities: dict[str, Any],
        *,
        region: Optional[str] = None,
        timezone: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> ControlPlaneWorker:
        """Register or refresh a worker record."""
        now = datetime.now(UTC)
        next_reset = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

        async with AsyncSessionLocal() as session:
            worker = await session.get(ControlPlaneWorker, worker_id)
            if worker is None:
                worker = ControlPlaneWorker(
                    worker_id=worker_id,
                    device_name=device_name,
                    device_type=device_type,
                    owner_id=owner_id,
                    region=region,
                    timezone=timezone,
                    capabilities_json=dict(capabilities or {}),
                    status=ControlPlaneWorkerStatus.IDLE.value,
                    quota_reset_at=next_reset,
                    registered_at=now,
                    updated_at=now,
                )
                session.add(worker)
            else:
                worker.device_name = device_name
                worker.device_type = device_type
                worker.owner_id = owner_id
                worker.region = region
                worker.timezone = timezone
                worker.capabilities_json = dict(capabilities or {})
                if worker.status == ControlPlaneWorkerStatus.OFFLINE.value:
                    worker.status = ControlPlaneWorkerStatus.IDLE.value
                worker.updated_at = now
            await session.commit()
            await session.refresh(worker)
            return worker

    async def get_worker(self, worker_id: str) -> Optional[ControlPlaneWorker]:
        async with AsyncSessionLocal() as session:
            return await session.get(ControlPlaneWorker, worker_id)

    async def get_worker_active_leases(self, worker_id: str) -> list[WorkerActiveLease]:
        active_by_worker = await self.list_worker_active_leases([worker_id])
        return active_by_worker.get(worker_id, [])

    async def list_worker_active_leases(
        self,
        worker_ids: list[str],
    ) -> dict[str, list[WorkerActiveLease]]:
        if not worker_ids:
            return {}

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ControlPlaneTask)
                .where(
                    ControlPlaneTask.worker_id.in_(worker_ids),
                    ControlPlaneTask.status.in_(sorted(ACTIVE_TASK_STATES)),
                )
                .order_by(ControlPlaneTask.worker_id, ControlPlaneTask.assigned_at)
            )
            mapping: dict[str, list[WorkerActiveLease]] = {worker_id: [] for worker_id in worker_ids}
            for task in result.scalars().all():
                if task.worker_id is None or task.current_attempt_id is None or task.current_lease_id is None:
                    continue
                mapping.setdefault(task.worker_id, []).append(
                    WorkerActiveLease(
                        task_id=task.task_id,
                        attempt_id=task.current_attempt_id,
                        lease_id=task.current_lease_id,
                        status=task.status,
                        assigned_at=task.assigned_at,
                        lease_expires_at=task.lease_expires_at,
                    )
                )
            return mapping

    async def list_workers(
        self,
        *,
        status: Optional[str] = None,
        device_type: Optional[str] = None,
        owner_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ControlPlaneWorker]:
        async with AsyncSessionLocal() as session:
            query = select(ControlPlaneWorker)
            if status is not None:
                query = query.where(ControlPlaneWorker.status == status)
            if device_type is not None:
                query = query.where(ControlPlaneWorker.device_type == device_type)
            if owner_id is not None:
                query = query.where(ControlPlaneWorker.owner_id == owner_id)
            query = query.order_by(ControlPlaneWorker.registered_at).offset(offset).limit(limit)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def unregister_worker(self, worker_id: str) -> bool:
        async with AsyncSessionLocal() as session:
            worker = await session.get(ControlPlaneWorker, worker_id)
            if worker is None:
                return False
            worker.status = ControlPlaneWorkerStatus.OFFLINE.value
            await session.commit()
            return True

    async def update_worker_quota(
        self,
        worker_id: str,
        *,
        max_concurrent_tasks: Optional[int] = None,
        daily_task_limit: Optional[int] = None,
    ) -> Optional[ControlPlaneWorker]:
        async with AsyncSessionLocal() as session:
            worker = await session.get(ControlPlaneWorker, worker_id)
            if worker is None:
                return None
            if max_concurrent_tasks is not None:
                worker.max_concurrent_tasks = max_concurrent_tasks
            if daily_task_limit is not None:
                worker.daily_task_limit = daily_task_limit
            await session.commit()
            await session.refresh(worker)
            return worker

    async def update_worker_heartbeat(
        self,
        worker_id: str,
        *,
        cpu_usage_percent: float,
        memory_usage_percent: float,
        storage_usage_percent: float,
        network_latency_ms: Optional[float],
        error_count: int,
    ) -> ControlPlaneWorker:
        """Persist worker liveness without mutating task ownership."""
        now = datetime.now(UTC)

        async with AsyncSessionLocal() as session:
            worker = await session.get(ControlPlaneWorker, worker_id)
            if worker is None:
                raise ControlPlaneNotFoundError(f"Worker {worker_id} not found")

            await self._reset_quota_if_needed(worker, now)
            active_count = await self._count_active_worker_tasks(session, worker_id)
            worker.last_heartbeat_at = now
            worker.cpu_usage_percent = cpu_usage_percent
            worker.memory_usage_percent = memory_usage_percent
            worker.storage_usage_percent = storage_usage_percent
            worker.network_latency_ms = network_latency_ms
            worker.error_count = error_count
            worker.status = (
                ControlPlaneWorkerStatus.BUSY.value
                if active_count > 0
                else ControlPlaneWorkerStatus.IDLE.value
                if cpu_usage_percent < 10 and memory_usage_percent < 30
                else ControlPlaneWorkerStatus.ONLINE.value
            )
            worker.current_task_id = None
            worker.current_attempt_id = None
            worker.current_lease_id = None
            await session.commit()
            await session.refresh(worker)
            return worker

    async def create_task(
        self,
        *,
        task_type: str,
        priority: str,
        payload: dict[str, Any],
        resource_requirements: Optional[dict[str, Any]] = None,
        target_worker_id: Optional[str] = None,
        target_device_type: Optional[str] = None,
        timeout_seconds: int = 3600,
        max_retries: int = 3,
        callback_url: Optional[str] = None,
        created_by_worker_id: Optional[str] = None,
        task_id: Optional[str] = None,
        pipeline_id: Optional[str] = None,
        stage_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> ControlPlaneTask:
        """Create a durable task or return the existing idempotent row."""
        task_id = task_id or f"task-{uuid.uuid4().hex[:12]}"
        priority = priority.upper()
        await self._ensure_runtime_ready()

        async with AsyncSessionLocal() as session:
            existing = None
            if idempotency_key:
                result = await session.execute(
                    select(ControlPlaneTask).where(ControlPlaneTask.idempotency_key == idempotency_key)
                )
                existing = result.scalar_one_or_none()
            if existing is None:
                existing = await session.get(ControlPlaneTask, task_id)
            if existing is not None:
                return existing

            task = ControlPlaneTask(
                task_id=task_id,
                task_type=task_type,
                priority=priority,
                payload_json=dict(payload or {}),
                resource_requirements_json=dict(resource_requirements or {}) if resource_requirements else None,
                target_worker_id=target_worker_id,
                target_device_type=target_device_type,
                timeout_seconds=max(1, int(timeout_seconds)),
                max_retries=max(0, int(max_retries)),
                callback_url=callback_url,
                created_by_worker_id=created_by_worker_id,
                idempotency_key=idempotency_key,
                pipeline_id=pipeline_id,
                stage_id=stage_id,
                status=ControlPlaneTaskState.PENDING.value,
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)
            return task

    async def get_task(self, task_id: str) -> Optional[ControlPlaneTask]:
        async with AsyncSessionLocal() as session:
            return await session.get(ControlPlaneTask, task_id)

    async def list_tasks(
        self,
        *,
        status: Optional[str] = None,
        worker_id: Optional[str] = None,
        pipeline_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ControlPlaneTask]:
        async with AsyncSessionLocal() as session:
            query = select(ControlPlaneTask)
            if status is not None:
                query = query.where(ControlPlaneTask.status == status)
            if worker_id is not None:
                query = query.where(ControlPlaneTask.worker_id == worker_id)
            if pipeline_id is not None:
                query = query.where(ControlPlaneTask.pipeline_id == pipeline_id)
            query = query.order_by(ControlPlaneTask.created_at.desc()).offset(offset).limit(limit)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def list_pipeline_tasks(self, pipeline_id: str) -> list[ControlPlaneTask]:
        return await self.list_tasks(pipeline_id=pipeline_id, limit=10_000, offset=0)

    async def get_attempt_history(self, task_id: str) -> list[ControlPlaneTaskAttempt]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ControlPlaneTaskAttempt)
                .where(ControlPlaneTaskAttempt.task_id == task_id)
                .order_by(ControlPlaneTaskAttempt.attempt_number)
            )
            return list(result.scalars().all())

    async def lease_task(
        self,
        worker_id: str,
        *,
        preferred_task_id: Optional[str] = None,
        lease_ttl_seconds: Optional[int] = None,
        now: Optional[datetime] = None,
    ) -> Optional[LeaseGrant]:
        """Grant a lease for the next eligible pending task."""
        now = _coerce_utc(now or datetime.now(UTC))
        lease_ttl_seconds = max(1, int(lease_ttl_seconds or self.lease_ttl_seconds))
        await self._ensure_runtime_ready()
        self._bump_metric("fog_task_control_plane_lease_acquire_attempts_total")

        async with AsyncSessionLocal() as session:
            granted_ids: Optional[tuple[str, str, str]] = None

            async with session.begin():
                await self._expire_stale_leases_in_session(session, now)

                worker = await self._get_worker_for_update(session, worker_id)
                if worker is None:
                    raise ControlPlaneNotFoundError(f"Worker {worker_id} not found")

                await self._reset_quota_if_needed(worker, now)

                active_count = await self._count_active_worker_tasks(session, worker_id)
                if active_count >= worker.max_concurrent_tasks:
                    return None
                if worker.tasks_today >= worker.daily_task_limit:
                    return None

                candidates = await self._select_candidate_tasks(
                    session,
                    worker=worker,
                    preferred_task_id=preferred_task_id,
                    active_task_count=active_count,
                )
                for candidate in candidates:
                    attempt_number = await self._next_attempt_number(session, candidate.task_id)
                    attempt_id = f"attempt-{uuid.uuid4().hex[:12]}"
                    lease_id = f"lease-{uuid.uuid4().hex[:12]}"
                    expires_at = now + timedelta(seconds=lease_ttl_seconds)

                    claimed = await session.execute(
                        update(ControlPlaneTask)
                        .execution_options(synchronize_session=False)
                        .where(
                            ControlPlaneTask.task_id == candidate.task_id,
                            ControlPlaneTask.status == ControlPlaneTaskState.PENDING.value,
                            ControlPlaneTask.current_attempt_id.is_(None),
                            ControlPlaneTask.current_lease_id.is_(None),
                        )
                        .values(
                            status=ControlPlaneTaskState.LEASED.value,
                            worker_id=worker_id,
                            current_attempt_id=attempt_id,
                            current_lease_id=lease_id,
                            assigned_at=now,
                            lease_expires_at=expires_at,
                            error=None,
                        )
                    )
                    if claimed.rowcount != 1:
                        continue

                    session.add(
                        ControlPlaneTaskAttempt(
                            attempt_id=attempt_id,
                            task_id=candidate.task_id,
                            worker_id=worker_id,
                            lease_id=lease_id,
                            attempt_number=attempt_number,
                            status=ControlPlaneTaskState.LEASED.value,
                            assigned_at=now,
                            idempotency_key=candidate.idempotency_key,
                        )
                    )
                    session.add(
                        ControlPlaneTaskLease(
                            lease_id=lease_id,
                            task_id=candidate.task_id,
                            attempt_id=attempt_id,
                            worker_id=worker_id,
                            status=ControlPlaneLeaseStatus.ACTIVE.value,
                            assigned_at=now,
                            expires_at=expires_at,
                        )
                    )
                    worker.status = ControlPlaneWorkerStatus.BUSY.value
                    worker.current_task_id = None
                    worker.current_attempt_id = None
                    worker.current_lease_id = None
                    worker.tasks_today += 1
                    granted_ids = (candidate.task_id, attempt_id, lease_id)
                    break

            if granted_ids is None:
                if candidates:
                    self._bump_metric("fog_task_control_plane_lease_contention_total")
                return None

            task = await session.get(ControlPlaneTask, granted_ids[0])
            attempt = await session.get(ControlPlaneTaskAttempt, granted_ids[1])
            lease = await session.get(ControlPlaneTaskLease, granted_ids[2])
            if task is None or attempt is None or lease is None:
                raise ControlPlaneConflictError("Lease transaction committed without durable ownership rows")
            await session.refresh(task)
            await session.refresh(attempt)
            await session.refresh(lease)
            self._bump_metric("fog_task_control_plane_lease_acquire_grants_total")
            self._log_task_event(
                logging.INFO,
                "Fog task lease granted",
                task_id=task.task_id,
                attempt_id=attempt.attempt_id,
                lease_id=lease.lease_id,
                worker_id=worker_id,
                extra={"lease_expires_at": lease.expires_at.isoformat()},
            )
            return LeaseGrant(task=task, attempt=attempt, lease=lease)

    async def start_task(
        self,
        task_id: str,
        *,
        worker_id: str,
        attempt_id: str,
        lease_id: str,
    ) -> ControlPlaneTask:
        """Transition a leased task to running for the active attempt."""
        await self._ensure_runtime_ready()
        async with AsyncSessionLocal() as session:
            now = datetime.now(UTC)
            async with session.begin():
                await self._expire_stale_leases_in_session(session, now)
                started = await session.execute(
                    update(ControlPlaneTask)
                    .execution_options(synchronize_session=False)
                    .where(
                        ControlPlaneTask.task_id == task_id,
                        ControlPlaneTask.worker_id == worker_id,
                        ControlPlaneTask.current_attempt_id == attempt_id,
                        ControlPlaneTask.current_lease_id == lease_id,
                        ControlPlaneTask.status == ControlPlaneTaskState.LEASED.value,
                        ControlPlaneTask.lease_expires_at.is_not(None),
                        ControlPlaneTask.lease_expires_at >= now,
                    )
                    .values(
                        status=ControlPlaneTaskState.RUNNING.value,
                        started_at=now,
                    )
                )
                if started.rowcount == 1:
                    await session.execute(
                        update(ControlPlaneTaskAttempt)
                        .execution_options(synchronize_session=False)
                        .where(
                            ControlPlaneTaskAttempt.attempt_id == attempt_id,
                            ControlPlaneTaskAttempt.task_id == task_id,
                            ControlPlaneTaskAttempt.worker_id == worker_id,
                            ControlPlaneTaskAttempt.lease_id == lease_id,
                            ControlPlaneTaskAttempt.status == ControlPlaneTaskState.LEASED.value,
                        )
                        .values(
                            status=ControlPlaneTaskState.RUNNING.value,
                            started_at=now,
                        )
                    )

            task = await session.get(ControlPlaneTask, task_id)
            if task is None:
                raise ControlPlaneNotFoundError(f"Task {task_id} not found")
            if (
                task.worker_id == worker_id
                and task.current_attempt_id == attempt_id
                and task.current_lease_id == lease_id
                and task.status == ControlPlaneTaskState.RUNNING.value
            ):
                self._log_task_event(
                    logging.INFO,
                    "Fog task execution started",
                    task_id=task_id,
                    attempt_id=attempt_id,
                    lease_id=lease_id,
                    worker_id=worker_id,
                )
                return task
            raise ControlPlaneConflictError("Start rejected by active lease fence")

    async def renew_lease(
        self,
        task_id: str,
        *,
        worker_id: str,
        attempt_id: str,
        lease_id: str,
        lease_ttl_seconds: Optional[int] = None,
        now: Optional[datetime] = None,
    ) -> ControlPlaneTask:
        """Renew the current active lease explicitly."""
        now = _coerce_utc(now or datetime.now(UTC))
        lease_ttl_seconds = max(1, int(lease_ttl_seconds or self.lease_ttl_seconds))
        await self._ensure_runtime_ready()

        async with AsyncSessionLocal() as session:
            new_expiry = now + timedelta(seconds=lease_ttl_seconds)
            async with session.begin():
                await self._expire_stale_leases_in_session(session, now)
                renewed = await session.execute(
                    update(ControlPlaneTaskLease)
                    .execution_options(synchronize_session=False)
                    .where(
                        ControlPlaneTaskLease.lease_id == lease_id,
                        ControlPlaneTaskLease.task_id == task_id,
                        ControlPlaneTaskLease.attempt_id == attempt_id,
                        ControlPlaneTaskLease.worker_id == worker_id,
                        ControlPlaneTaskLease.status == ControlPlaneLeaseStatus.ACTIVE.value,
                        ControlPlaneTaskLease.expires_at >= now,
                    )
                    .values(
                        expires_at=new_expiry,
                        renewed_at=now,
                    )
                )
                if renewed.rowcount == 1:
                    task_update = await session.execute(
                        update(ControlPlaneTask)
                        .execution_options(synchronize_session=False)
                        .where(
                            ControlPlaneTask.task_id == task_id,
                            ControlPlaneTask.worker_id == worker_id,
                            ControlPlaneTask.current_attempt_id == attempt_id,
                            ControlPlaneTask.current_lease_id == lease_id,
                            ControlPlaneTask.status.in_(
                                [
                                    ControlPlaneTaskState.LEASED.value,
                                    ControlPlaneTaskState.RUNNING.value,
                                ]
                            ),
                            ControlPlaneTask.lease_expires_at.is_not(None),
                            ControlPlaneTask.lease_expires_at >= now,
                        )
                        .values(lease_expires_at=new_expiry)
                    )
                    if task_update.rowcount != 1:
                        self._bump_metric("fog_task_control_plane_lease_renew_conflict_total")
                        raise ControlPlaneConflictError("Lease renewal rejected by task fence")
                    await session.execute(
                        update(ControlPlaneTaskAttempt)
                        .execution_options(synchronize_session=False)
                        .where(
                            ControlPlaneTaskAttempt.attempt_id == attempt_id,
                            ControlPlaneTaskAttempt.task_id == task_id,
                            ControlPlaneTaskAttempt.worker_id == worker_id,
                            ControlPlaneTaskAttempt.lease_id == lease_id,
                            ControlPlaneTaskAttempt.status.in_(
                                [
                                    ControlPlaneTaskState.LEASED.value,
                                    ControlPlaneTaskState.RUNNING.value,
                                ]
                            ),
                        )
                        .values(updated_at=now)
                    )

            task = await session.get(ControlPlaneTask, task_id)
            if task is None:
                raise ControlPlaneNotFoundError(f"Task {task_id} not found")
            if (
                task.worker_id == worker_id
                and task.current_attempt_id == attempt_id
                and task.current_lease_id == lease_id
                and task.status in {
                    ControlPlaneTaskState.LEASED.value,
                    ControlPlaneTaskState.RUNNING.value,
                }
                and _coerce_utc(task.lease_expires_at) is not None
                and _coerce_utc(task.lease_expires_at) >= now
            ):
                self._bump_metric("fog_task_control_plane_lease_renew_success_total")
                self._log_task_event(
                    logging.DEBUG,
                    "Fog task lease renewed",
                    task_id=task_id,
                    attempt_id=attempt_id,
                    lease_id=lease_id,
                    worker_id=worker_id,
                    extra={"lease_expires_at": task.lease_expires_at.isoformat() if task.lease_expires_at else None},
                )
                return task
            self._bump_metric("fog_task_control_plane_lease_renew_conflict_total")
            self._log_task_event(
                logging.WARNING,
                "Fog task lease renewal rejected",
                task_id=task_id,
                attempt_id=attempt_id,
                lease_id=lease_id,
                worker_id=worker_id,
            )
            raise ControlPlaneConflictError("Lease renewal rejected by active lease fence")

    async def complete_task(
        self,
        task_id: str,
        *,
        worker_id: str,
        attempt_id: str,
        lease_id: str,
        success: bool,
        result: Optional[dict[str, Any]],
        error: Optional[str],
        execution_time_ms: int,
        now: Optional[datetime] = None,
    ) -> tuple[ControlPlaneTask, bool]:
        """
        Complete an active attempt.

        Returns:
            (task, idempotent_duplicate)
        """
        now = _coerce_utc(now or datetime.now(UTC))
        terminal_state = (
            ControlPlaneTaskState.SUCCEEDED.value
            if success
            else ControlPlaneTaskState.FAILED.value
        )
        await self._ensure_runtime_ready()

        async with AsyncSessionLocal() as session:
            async with session.begin():
                await self._expire_stale_leases_in_session(session, now)

                task = await session.get(ControlPlaneTask, task_id)
                if task is None:
                    raise ControlPlaneNotFoundError(f"Task {task_id} not found")

                attempt = await session.get(ControlPlaneTaskAttempt, attempt_id)
                lease = await session.get(ControlPlaneTaskLease, lease_id)
                worker = await session.get(ControlPlaneWorker, worker_id)

                if worker is None:
                    raise ControlPlaneNotFoundError(f"Worker {worker_id} not found")
                if attempt is None or lease is None:
                    raise ControlPlaneConflictError("Unknown attempt or lease")
                if attempt.task_id != task_id or lease.task_id != task_id:
                    raise ControlPlaneConflictError("Attempt or lease does not belong to task")
                if attempt.worker_id != worker_id or lease.worker_id != worker_id:
                    raise ControlPlaneConflictError("Attempt or lease does not belong to worker")
                if attempt.lease_id != lease_id:
                    raise ControlPlaneConflictError("Attempt fence mismatch")

                if (
                    task.status == terminal_state
                    and attempt.status == terminal_state
                    and lease.status == ControlPlaneLeaseStatus.RELEASED.value
                ):
                    self._bump_metric("fog_task_control_plane_duplicate_result_total")
                    self._log_task_event(
                        logging.DEBUG,
                        "Fog task duplicate result accepted idempotently",
                        task_id=task_id,
                        attempt_id=attempt_id,
                        lease_id=lease_id,
                        worker_id=worker_id,
                    )
                    return task, True

                released = await session.execute(
                    update(ControlPlaneTaskLease)
                    .execution_options(synchronize_session=False)
                    .where(
                        ControlPlaneTaskLease.lease_id == lease_id,
                        ControlPlaneTaskLease.task_id == task_id,
                        ControlPlaneTaskLease.attempt_id == attempt_id,
                        ControlPlaneTaskLease.worker_id == worker_id,
                        ControlPlaneTaskLease.status == ControlPlaneLeaseStatus.ACTIVE.value,
                        ControlPlaneTaskLease.expires_at >= now,
                    )
                    .values(
                        status=ControlPlaneLeaseStatus.RELEASED.value,
                        released_at=now,
                    )
                )
                if released.rowcount != 1:
                    await session.refresh(task)
                    await session.refresh(attempt)
                    await session.refresh(lease)
                    if (
                        task.status == terminal_state
                        and attempt.status == terminal_state
                        and lease.status == ControlPlaneLeaseStatus.RELEASED.value
                    ):
                        self._bump_metric("fog_task_control_plane_duplicate_result_total")
                        self._log_task_event(
                            logging.DEBUG,
                            "Fog task duplicate result accepted after lease release",
                            task_id=task_id,
                            attempt_id=attempt_id,
                            lease_id=lease_id,
                            worker_id=worker_id,
                        )
                        return task, True
                    self._bump_metric("fog_task_control_plane_stale_completion_rejections_total")
                    self._log_task_event(
                        logging.WARNING,
                        "Fog task stale completion rejected by lease fence",
                        task_id=task_id,
                        attempt_id=attempt_id,
                        lease_id=lease_id,
                        worker_id=worker_id,
                    )
                    raise ControlPlaneConflictError("Stale completion rejected by active lease fence")

                completed = await session.execute(
                    update(ControlPlaneTask)
                    .execution_options(synchronize_session=False)
                    .where(
                        ControlPlaneTask.task_id == task_id,
                        ControlPlaneTask.worker_id == worker_id,
                        ControlPlaneTask.current_attempt_id == attempt_id,
                        ControlPlaneTask.current_lease_id == lease_id,
                        ControlPlaneTask.status.in_(
                            [
                                ControlPlaneTaskState.LEASED.value,
                                ControlPlaneTaskState.RUNNING.value,
                            ]
                        ),
                        ControlPlaneTask.lease_expires_at.is_not(None),
                        ControlPlaneTask.lease_expires_at >= now,
                    )
                    .values(
                        status=terminal_state,
                        completed_at=now,
                        result_json=result,
                        error=error,
                        execution_time_ms=execution_time_ms,
                        progress_percent=100.0 if success else ControlPlaneTask.progress_percent,
                        current_attempt_id=None,
                        current_lease_id=None,
                    )
                )
                if completed.rowcount != 1:
                    await session.refresh(task)
                    await session.refresh(attempt)
                    await session.refresh(lease)
                    if (
                        task.status == terminal_state
                        and attempt.status == terminal_state
                        and lease.status == ControlPlaneLeaseStatus.RELEASED.value
                    ):
                        self._bump_metric("fog_task_control_plane_duplicate_result_total")
                        self._log_task_event(
                            logging.DEBUG,
                            "Fog task duplicate result accepted after task completion",
                            task_id=task_id,
                            attempt_id=attempt_id,
                            lease_id=lease_id,
                            worker_id=worker_id,
                        )
                        return task, True
                    self._bump_metric("fog_task_control_plane_stale_completion_rejections_total")
                    self._log_task_event(
                        logging.WARNING,
                        "Fog task stale completion rejected by attempt fence",
                        task_id=task_id,
                        attempt_id=attempt_id,
                        lease_id=lease_id,
                        worker_id=worker_id,
                    )
                    raise ControlPlaneConflictError("Stale completion rejected by active attempt fence")

                await session.execute(
                    update(ControlPlaneTaskAttempt)
                    .execution_options(synchronize_session=False)
                    .where(
                        ControlPlaneTaskAttempt.attempt_id == attempt_id,
                        ControlPlaneTaskAttempt.task_id == task_id,
                        ControlPlaneTaskAttempt.worker_id == worker_id,
                        ControlPlaneTaskAttempt.lease_id == lease_id,
                        ControlPlaneTaskAttempt.status.in_(
                            [
                                ControlPlaneTaskState.LEASED.value,
                                ControlPlaneTaskState.RUNNING.value,
                            ]
                        ),
                    )
                    .values(
                        status=terminal_state,
                        completed_at=now,
                        result_json=result,
                        error=error,
                        execution_time_ms=execution_time_ms,
                    )
                )

                if success:
                    worker.total_tasks_completed += 1
                await self._refresh_worker_execution_state(session, worker_id)

            task = await session.get(ControlPlaneTask, task_id)
            if task is None:
                raise ControlPlaneNotFoundError(f"Task {task_id} not found")
            await session.refresh(task)
            self._log_task_event(
                logging.INFO,
                "Fog task execution completed",
                task_id=task_id,
                attempt_id=attempt_id,
                lease_id=lease_id,
                worker_id=worker_id,
                extra={"success": success},
            )
            return task, False

    async def cancel_task(self, task_id: str) -> ControlPlaneTask:
        """Cancel a non-terminal task."""
        now = datetime.now(UTC)
        await self._ensure_runtime_ready()

        async with AsyncSessionLocal() as session:
            async with session.begin():
                task = await self._get_task_for_update(session, task_id)
                if task is None:
                    raise ControlPlaneNotFoundError(f"Task {task_id} not found")
                if task.status in TERMINAL_TASK_STATES | {ControlPlaneTaskState.EXPIRED.value}:
                    return task

                current_attempt_id = task.current_attempt_id
                current_lease_id = task.current_lease_id
                current_worker_id = task.worker_id

                await session.execute(
                    update(ControlPlaneTask)
                    .execution_options(synchronize_session=False)
                    .where(
                        ControlPlaneTask.task_id == task_id,
                        ControlPlaneTask.status.notin_(
                            [
                                *sorted(TERMINAL_TASK_STATES),
                                ControlPlaneTaskState.EXPIRED.value,
                            ]
                        ),
                    )
                    .values(
                        status=ControlPlaneTaskState.CANCELLED.value,
                        completed_at=now,
                        error="Task cancelled",
                        current_attempt_id=None,
                        current_lease_id=None,
                    )
                )

                if current_attempt_id:
                    await session.execute(
                        update(ControlPlaneTaskAttempt)
                        .execution_options(synchronize_session=False)
                        .where(
                            ControlPlaneTaskAttempt.attempt_id == current_attempt_id,
                            ControlPlaneTaskAttempt.status.in_(
                                [
                                    ControlPlaneTaskState.LEASED.value,
                                    ControlPlaneTaskState.RUNNING.value,
                                ]
                            ),
                        )
                        .values(
                            status=ControlPlaneTaskState.CANCELLED.value,
                            completed_at=now,
                            error="Task cancelled",
                        )
                    )
                if current_lease_id:
                    await session.execute(
                        update(ControlPlaneTaskLease)
                        .execution_options(synchronize_session=False)
                        .where(
                            ControlPlaneTaskLease.lease_id == current_lease_id,
                            ControlPlaneTaskLease.status == ControlPlaneLeaseStatus.ACTIVE.value,
                        )
                        .values(
                            status=ControlPlaneLeaseStatus.CANCELLED.value,
                            revoked_at=now,
                        )
                    )
                if current_worker_id:
                    await self._refresh_worker_execution_state(session, current_worker_id)

            task = await session.get(ControlPlaneTask, task_id)
            if task is None:
                raise ControlPlaneNotFoundError(f"Task {task_id} not found")
            await session.refresh(task)
            self._log_task_event(logging.INFO, "Fog task cancelled", task_id=task_id, worker_id=task.worker_id)
            return task

    async def expire_stale_leases(self, *, now: Optional[datetime] = None) -> int:
        """Expire any lease whose TTL has elapsed."""
        now = _coerce_utc(now or datetime.now(UTC))
        await self._ensure_runtime_ready()
        async with AsyncSessionLocal() as session:
            async with session.begin():
                count = await self._expire_stale_leases_in_session(session, now)
            return count

    async def requeue_task(
        self,
        task_id: str,
        *,
        reason: str,
        now: Optional[datetime] = None,
    ) -> Optional[ControlPlaneTask]:
        """Reset an expired or failed task back to pending."""
        now = _coerce_utc(now or datetime.now(UTC))
        await self._ensure_runtime_ready()

        async with AsyncSessionLocal() as session:
            async with session.begin():
                task = await self._get_task_for_update(session, task_id)
                if task is None:
                    return None
                if task.status not in {ControlPlaneTaskState.EXPIRED.value, ControlPlaneTaskState.FAILED.value}:
                    return task
                if task.retry_count >= task.max_retries:
                    return task

                requeued = await session.execute(
                    update(ControlPlaneTask)
                    .execution_options(synchronize_session=False)
                    .where(
                        ControlPlaneTask.task_id == task_id,
                        ControlPlaneTask.status.in_(
                            [
                                ControlPlaneTaskState.EXPIRED.value,
                                ControlPlaneTaskState.FAILED.value,
                            ]
                        ),
                        ControlPlaneTask.retry_count < ControlPlaneTask.max_retries,
                    )
                    .values(
                        retry_count=ControlPlaneTask.retry_count + 1,
                        status=ControlPlaneTaskState.PENDING.value,
                        worker_id=None,
                        current_attempt_id=None,
                        current_lease_id=None,
                        assigned_at=None,
                        lease_expires_at=None,
                        started_at=None,
                        completed_at=None,
                        result_json=None,
                        error=reason,
                        execution_time_ms=0,
                        progress_percent=0.0,
                    )
                )
                if requeued.rowcount == 0:
                    return task

            refreshed = await session.get(ControlPlaneTask, task_id)
            if refreshed is not None:
                await session.refresh(refreshed)
                if refreshed.status == ControlPlaneTaskState.PENDING.value:
                    self._bump_metric("fog_task_control_plane_task_reassignment_total")
                    self._log_task_event(
                        logging.INFO,
                        "Fog task requeued for reassignment",
                        task_id=task_id,
                        worker_id=refreshed.worker_id,
                        extra={"reason": reason, "retry_count": refreshed.retry_count},
                    )
            return refreshed

    async def reconcile_startup(self, *, now: Optional[datetime] = None) -> dict[str, int]:
        """Expire stale leases so restart does not preserve fake ownership."""
        expired = await self.expire_stale_leases(now=now)
        self._bump_metric("fog_task_control_plane_startup_recovery_expired_total", expired)
        logger.info("Fog task control-plane startup reconciliation complete [expired_leases=%s]", expired)
        return {"expired_leases": expired}

    async def save_pipeline_record(
        self,
        *,
        pipeline_id: str,
        name: str,
        status: str,
        definition_json: dict[str, Any],
        created_by: Optional[str] = None,
        callback_url: Optional[str] = None,
        error: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> PipelineRecord:
        """Persist the current pipeline definition/runtime snapshot."""
        async with AsyncSessionLocal() as session:
            record = await session.get(PipelineRecord, pipeline_id)
            if record is None:
                record = PipelineRecord(
                    pipeline_id=pipeline_id,
                    name=name,
                    status=status,
                    definition_json=definition_json,
                    created_by=created_by,
                    callback_url=callback_url,
                    error=error,
                    started_at=started_at,
                    completed_at=completed_at,
                )
                session.add(record)
            else:
                record.name = name
                record.status = status
                record.definition_json = definition_json
                record.created_by = created_by
                record.callback_url = callback_url
                record.error = error
                record.started_at = started_at
                record.completed_at = completed_at
            await session.commit()
            await session.refresh(record)
            return record

    async def get_pipeline_record(self, pipeline_id: str) -> Optional[PipelineRecord]:
        async with AsyncSessionLocal() as session:
            return await session.get(PipelineRecord, pipeline_id)

    async def list_pipeline_records(
        self,
        *,
        statuses: Optional[set[str]] = None,
    ) -> list[PipelineRecord]:
        async with AsyncSessionLocal() as session:
            query = select(PipelineRecord)
            if statuses:
                query = query.where(PipelineRecord.status.in_(sorted(statuses)))
            query = query.order_by(PipelineRecord.created_at)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_health_snapshot(self) -> dict[str, Any]:
        """Return the single health source for the task control plane."""
        now = datetime.now(UTC)
        migration_report = await self._get_migration_report(force_refresh=True)
        schema_report = await self._get_schema_report(force_refresh=True)
        if schema_report["missing_tables"]:
            return {
                "status": "unhealthy",
                "workers": 0,
                "active_tasks": 0,
                "services": {
                    "database": {"status": "healthy"},
                    "migrations": {
                        "status": "healthy" if migration_report["ready"] else "unhealthy",
                        "state": migration_report["state"],
                        "expected_head_revisions": migration_report["expected_head_revisions"],
                        "current_revisions": migration_report["current_revisions"],
                    },
                    "tasks": {"status": "unhealthy", "total": 0},
                    "schema": {
                        "status": "unhealthy",
                        "missing_tables": schema_report["missing_tables"],
                        "missing_indexes": schema_report["missing_indexes"],
                        "invalid_indexes": schema_report["invalid_indexes"],
                    },
                },
            }
        try:
            async with AsyncSessionLocal() as session:
                workers = list((await session.execute(select(ControlPlaneWorker))).scalars().all())
                tasks = list((await session.execute(select(ControlPlaneTask))).scalars().all())
        except Exception as exc:  # pragma: no cover - direct DB failure path
            logger.error("Control-plane health query failed: %s", exc)
            return {
                "status": "unhealthy",
                "workers": 0,
                "active_tasks": 0,
                "services": {"database": {"status": "unhealthy", "error": str(exc)}},
            }

        connected = sum(
            1
            for worker in workers
            if _coerce_utc(worker.last_heartbeat_at) is not None
            and (now - _coerce_utc(worker.last_heartbeat_at)).total_seconds() <= self.heartbeat_staleness_seconds
        )
        active_tasks = sum(
            1
            for task in tasks
            if task.status in {
                ControlPlaneTaskState.PENDING.value,
                ControlPlaneTaskState.LEASED.value,
                ControlPlaneTaskState.RUNNING.value,
            }
        )
        operationally_unhealthy = not migration_report["ready"] or not schema_report["ready"]
        degraded = any(task.status == ControlPlaneTaskState.EXPIRED.value for task in tasks)
        return {
            "status": "unhealthy" if operationally_unhealthy else "degraded" if degraded else "healthy",
            "workers": connected,
            "active_tasks": active_tasks,
            "services": {
                "database": {"status": "healthy"},
                "migrations": {
                    "status": "healthy" if migration_report["ready"] else "unhealthy",
                    "state": migration_report["state"],
                    "expected_head_revisions": migration_report["expected_head_revisions"],
                    "current_revisions": migration_report["current_revisions"],
                },
                "tasks": {
                    "status": "unhealthy" if operationally_unhealthy else "degraded" if degraded else "healthy",
                    "total": len(tasks),
                },
                "schema": {
                    "status": "healthy" if schema_report["ready"] else "unhealthy",
                    "missing_tables": schema_report["missing_tables"],
                    "missing_indexes": schema_report["missing_indexes"],
                    "invalid_indexes": schema_report["invalid_indexes"],
                },
            },
        }

    async def get_readiness_snapshot(self, *, force_refresh: bool = False) -> dict[str, Any]:
        """Return the single readiness source for the task control plane."""
        try:
            migration_report = await self._get_migration_report(force_refresh=force_refresh)
            schema_report = await self._get_schema_report(force_refresh=force_refresh)
        except Exception as exc:  # pragma: no cover - direct DB failure path
            return {"ready": False, "failure_mode": "database_unavailable", "reason": str(exc)}

        details = {
            "migration": migration_report,
            "schema": schema_report,
        }
        if schema_report["missing_tables"]:
            return {
                "ready": False,
                "failure_mode": "schema_missing",
                "reason": "Required fog task control-plane tables are missing",
                "details": details,
            }
        if not migration_report["ready"]:
            failure_mode = {
                "missing_version_table": "migration_state_missing",
                "missing_version_row": "migration_state_missing",
                "behind_head": "migration_state_behind_head",
            }.get(migration_report["state"], "migration_state_invalid")
            return {
                "ready": False,
                "failure_mode": failure_mode,
                "reason": "Alembic migration state is missing or behind the application head",
                "details": details,
            }
        if not schema_report["ready"]:
            return {
                "ready": False,
                "failure_mode": "schema_guarantees_missing",
                "reason": "Required fog task control-plane schema guarantees are missing",
                "details": details,
            }
        return {"ready": True, "details": details}

    async def get_topology_snapshot(self) -> dict[str, Any]:
        """Summarize worker and task state from the durable store."""
        now = datetime.now(UTC)
        workers = await self.list_workers(limit=10_000, offset=0)
        tasks = await self.list_tasks(limit=10_000, offset=0)
        active_leases = await self.list_worker_active_leases([worker.worker_id for worker in workers])

        devices_by_type: dict[str, int] = {}
        devices_by_status: dict[str, int] = {}
        devices_by_region: dict[str, int] = {}
        total_cpu = 0
        available_cpu = 0
        total_memory = 0
        available_memory = 0

        for worker in workers:
            devices_by_type[worker.device_type] = devices_by_type.get(worker.device_type, 0) + 1
            active_count = len(active_leases.get(worker.worker_id, []))
            status_key = (
                ControlPlaneWorkerStatus.BUSY.value
                if active_count > 0 and worker.status not in {ControlPlaneWorkerStatus.OFFLINE.value, ControlPlaneWorkerStatus.MAINTENANCE.value}
                else worker.status
            )
            devices_by_status[status_key] = devices_by_status.get(status_key, 0) + 1
            region = worker.region or "unknown"
            devices_by_region[region] = devices_by_region.get(region, 0) + 1

            caps = worker.capabilities_json or {}
            cpu_cores = int(caps.get("cpu_cores", 0) or 0)
            memory_mb = int(caps.get("memory_mb", 0) or 0)
            total_cpu += cpu_cores
            total_memory += memory_mb
            if status_key in {ControlPlaneWorkerStatus.IDLE.value, ControlPlaneWorkerStatus.ONLINE.value}:
                available_cpu += int(cpu_cores * (1 - worker.cpu_usage_percent / 100))
                available_memory += int(memory_mb * (1 - worker.memory_usage_percent / 100))

        completed_cutoff = now - timedelta(hours=24)
        return {
            "total_devices": len(workers),
            "devices_by_type": devices_by_type,
            "devices_by_status": devices_by_status,
            "devices_by_region": devices_by_region,
            "total_cpu_cores": total_cpu,
            "available_cpu_cores": available_cpu,
            "total_memory_mb": total_memory,
            "available_memory_mb": available_memory,
            "queued_tasks": sum(1 for task in tasks if task.status == ControlPlaneTaskState.PENDING.value),
            "running_tasks": sum(1 for task in tasks if task.status in {ControlPlaneTaskState.LEASED.value, ControlPlaneTaskState.RUNNING.value}),
            "completed_tasks_24h": sum(
                1
                for task in tasks
                if task.status == ControlPlaneTaskState.SUCCEEDED.value
                and _coerce_utc(task.completed_at) is not None
                and _coerce_utc(task.completed_at) > completed_cutoff
            ),
            "snapshot_time": now,
        }

    async def get_metrics(self) -> dict[str, Any]:
        """Aggregate lightweight queue/task metrics for monitoring."""
        migration_report = await self._get_migration_report()
        schema_report = await self._get_schema_report()
        if schema_report["missing_tables"]:
            return {
                "tasks_total": 0,
                "tasks_pending": 0,
                "tasks_leased": 0,
                "tasks_running": 0,
                "tasks_succeeded": 0,
                "tasks_failed": 0,
                "tasks_expired": 0,
                "workers_total": 0,
                "workers_busy": 0,
                "fog_task_control_plane_migration_ready": int(migration_report["ready"]),
                "fog_task_control_plane_schema_ready": int(schema_report["ready"]),
                "fog_task_control_plane_schema_missing_tables_total": len(schema_report["missing_tables"]),
                "fog_task_control_plane_schema_missing_indexes_total": len(schema_report["missing_indexes"]),
                "fog_task_control_plane_schema_invalid_indexes_total": len(schema_report["invalid_indexes"]),
                **self._metrics.snapshot(),
            }

        tasks = await self.list_tasks(limit=10_000, offset=0)
        workers = await self.list_workers(limit=10_000, offset=0)
        active_leases = await self.list_worker_active_leases([worker.worker_id for worker in workers])
        return {
            "tasks_total": len(tasks),
            "tasks_pending": sum(1 for task in tasks if task.status == ControlPlaneTaskState.PENDING.value),
            "tasks_leased": sum(1 for task in tasks if task.status == ControlPlaneTaskState.LEASED.value),
            "tasks_running": sum(1 for task in tasks if task.status == ControlPlaneTaskState.RUNNING.value),
            "tasks_succeeded": sum(1 for task in tasks if task.status == ControlPlaneTaskState.SUCCEEDED.value),
            "tasks_failed": sum(1 for task in tasks if task.status == ControlPlaneTaskState.FAILED.value),
            "tasks_expired": sum(1 for task in tasks if task.status == ControlPlaneTaskState.EXPIRED.value),
            "workers_total": len(workers),
            "workers_busy": sum(1 for worker in workers if active_leases.get(worker.worker_id)),
            "fog_task_control_plane_migration_ready": int(migration_report["ready"]),
            "fog_task_control_plane_schema_ready": int(schema_report["ready"]),
            "fog_task_control_plane_schema_missing_tables_total": len(schema_report["missing_tables"]),
            "fog_task_control_plane_schema_missing_indexes_total": len(schema_report["missing_indexes"]),
            "fog_task_control_plane_schema_invalid_indexes_total": len(schema_report["invalid_indexes"]),
            **self._metrics.snapshot(),
        }

    async def reset_state_for_tests(self) -> None:
        """Best-effort cleanup for focused control-plane tests."""
        async with AsyncSessionLocal() as session:
            await session.execute(delete(ControlPlaneTaskLease))
            await session.execute(delete(ControlPlaneTaskAttempt))
            await session.execute(delete(ControlPlaneTask))
            await session.execute(delete(PipelineRecord))
            await session.execute(delete(ControlPlaneWorker))
            await session.commit()
        self._schema_cache = None
        self._schema_cache_checked_at = 0.0
        self._migration_cache = None
        self._migration_cache_checked_at = 0.0
        self._metrics.reset()

    async def _select_candidate_tasks(
        self,
        session,
        *,
        worker: ControlPlaneWorker,
        preferred_task_id: Optional[str],
        active_task_count: int,
    ) -> list[ControlPlaneTask]:
        priority_order = case(
            *[
                (ControlPlaneTask.priority == priority, rank)
                for priority, rank in TASK_PRIORITY_ORDER.items()
            ],
            else_=TASK_PRIORITY_ORDER["NORMAL"],
        )
        query = (
            select(ControlPlaneTask)
            .where(
                ControlPlaneTask.status == ControlPlaneTaskState.PENDING.value,
                or_(
                    ControlPlaneTask.target_worker_id.is_(None),
                    ControlPlaneTask.target_worker_id == worker.worker_id,
                ),
                or_(
                    ControlPlaneTask.target_device_type.is_(None),
                    ControlPlaneTask.target_device_type == worker.device_type,
                ),
            )
            .order_by(priority_order, ControlPlaneTask.created_at)
            .limit(32)
        )
        if preferred_task_id is not None:
            query = query.where(ControlPlaneTask.task_id == preferred_task_id)
        if self._supports_skip_locked(session):
            query = query.with_for_update(skip_locked=True)
        result = await session.execute(query)
        return [
            task
            for task in result.scalars().all()
            if self._worker_can_lease_task(worker, task, active_task_count=active_task_count)
        ]

    async def _expire_stale_leases_in_session(self, session, now: datetime) -> int:
        """Expire active leases older than their deadline."""
        query = select(ControlPlaneTaskLease).where(
            ControlPlaneTaskLease.status == ControlPlaneLeaseStatus.ACTIVE.value,
            ControlPlaneTaskLease.expires_at < now,
        )
        if self._supports_skip_locked(session):
            query = query.with_for_update(skip_locked=True)
        result = await session.execute(query)
        leases = list(result.scalars().all())
        expired = 0

        for lease in leases:
            expired_lease = await session.execute(
                update(ControlPlaneTaskLease)
                .execution_options(synchronize_session=False)
                .where(
                    ControlPlaneTaskLease.lease_id == lease.lease_id,
                    ControlPlaneTaskLease.status == ControlPlaneLeaseStatus.ACTIVE.value,
                    ControlPlaneTaskLease.expires_at < now,
                )
                .values(
                    status=ControlPlaneLeaseStatus.EXPIRED.value,
                    revoked_at=now,
                )
            )
            if expired_lease.rowcount != 1:
                continue

            await session.execute(
                update(ControlPlaneTaskAttempt)
                .execution_options(synchronize_session=False)
                .where(
                    ControlPlaneTaskAttempt.attempt_id == lease.attempt_id,
                    ControlPlaneTaskAttempt.status.in_(
                        [
                            ControlPlaneTaskState.LEASED.value,
                            ControlPlaneTaskState.RUNNING.value,
                        ]
                    ),
                )
                .values(
                    status=ControlPlaneTaskState.EXPIRED.value,
                    completed_at=now,
                    error="Lease expired",
                )
            )
            task_expired = await session.execute(
                update(ControlPlaneTask)
                .execution_options(synchronize_session=False)
                .where(
                    ControlPlaneTask.task_id == lease.task_id,
                    ControlPlaneTask.current_attempt_id == lease.attempt_id,
                    ControlPlaneTask.current_lease_id == lease.lease_id,
                    ControlPlaneTask.status.in_(
                        [
                            ControlPlaneTaskState.LEASED.value,
                            ControlPlaneTaskState.RUNNING.value,
                        ]
                    ),
                )
                .values(
                    status=ControlPlaneTaskState.EXPIRED.value,
                    completed_at=now,
                    error="Lease expired",
                    worker_id=None,
                    current_attempt_id=None,
                    current_lease_id=None,
                    lease_expires_at=lease.expires_at,
                )
            )
            if task_expired.rowcount == 1:
                await self._refresh_worker_execution_state(session, lease.worker_id)
                self._bump_metric("fog_task_control_plane_lease_expiry_total")
                self._log_task_event(
                    logging.WARNING,
                    "Fog task lease expired",
                    task_id=lease.task_id,
                    attempt_id=lease.attempt_id,
                    lease_id=lease.lease_id,
                    worker_id=lease.worker_id,
                )
            expired += 1

        return expired

    async def _next_attempt_number(self, session, task_id: str) -> int:
        result = await session.execute(
            select(func.max(ControlPlaneTaskAttempt.attempt_number)).where(
                ControlPlaneTaskAttempt.task_id == task_id
            )
        )
        current = result.scalar_one()
        return int(current or 0) + 1

    async def _count_active_worker_tasks(self, session, worker_id: str) -> int:
        result = await session.execute(
            select(func.count())
            .select_from(ControlPlaneTask)
            .where(
                ControlPlaneTask.worker_id == worker_id,
                ControlPlaneTask.status.in_(sorted(ACTIVE_TASK_STATES)),
            )
        )
        return int(result.scalar_one() or 0)

    async def _refresh_worker_execution_state(self, session, worker_id: str) -> int:
        worker = await session.get(ControlPlaneWorker, worker_id)
        if worker is None:
            return 0
        active_count = await self._count_active_worker_tasks(session, worker_id)
        worker.current_task_id = None
        worker.current_attempt_id = None
        worker.current_lease_id = None
        if worker.status not in {
            ControlPlaneWorkerStatus.OFFLINE.value,
            ControlPlaneWorkerStatus.MAINTENANCE.value,
        }:
            worker.status = (
                ControlPlaneWorkerStatus.BUSY.value
                if active_count > 0
                else ControlPlaneWorkerStatus.IDLE.value
                if worker.cpu_usage_percent < 10 and worker.memory_usage_percent < 30
                else ControlPlaneWorkerStatus.ONLINE.value
            )
        return active_count

    async def _reset_quota_if_needed(self, worker: ControlPlaneWorker, now: datetime) -> None:
        quota_reset_at = _coerce_utc(worker.quota_reset_at)
        if quota_reset_at is not None and quota_reset_at <= now:
            worker.tasks_today = 0
            worker.quota_reset_at = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

    def _worker_can_lease_task(
        self,
        worker: ControlPlaneWorker,
        task: ControlPlaneTask,
        *,
        active_task_count: int,
    ) -> bool:
        if task.target_worker_id and task.target_worker_id != worker.worker_id:
            return False
        if task.target_device_type and task.target_device_type != worker.device_type:
            return False
        if worker.status in {
            ControlPlaneWorkerStatus.MAINTENANCE.value,
            ControlPlaneWorkerStatus.OFFLINE.value,
        }:
            return False
        last_heartbeat_at = _coerce_utc(worker.last_heartbeat_at)
        if last_heartbeat_at is not None:
            age = (datetime.now(UTC) - last_heartbeat_at).total_seconds()
            if age > self.heartbeat_staleness_seconds and active_task_count == 0:
                return False
        requirements = task.resource_requirements_json or {}
        capabilities = worker.capabilities_json or {}
        if int(capabilities.get("cpu_cores", 0) or 0) < int(requirements.get("cpu_cores", 0) or 0):
            return False
        if int(capabilities.get("memory_mb", 0) or 0) < int(requirements.get("memory_mb", 0) or 0):
            return False
        if bool(requirements.get("gpu_available")) and not bool(capabilities.get("gpu_available")):
            return False
        return True
fog_task_control_plane = FogTaskControlPlaneService()
