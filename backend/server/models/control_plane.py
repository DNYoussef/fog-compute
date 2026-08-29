"""
Durable control-plane models for fog task orchestration.

This module defines the authoritative task/lease/attempt state used by the
fog bridge request path and the pipeline scheduler. It intentionally replaces
process-local ownership tracking.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, utc_now


class ControlPlaneTaskState(str, Enum):
    """Canonical task state vocabulary."""

    PENDING = "PENDING"
    LEASED = "LEASED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class ControlPlaneWorkerStatus(str, Enum):
    """Worker lifecycle states tracked by the control plane."""

    ONLINE = "online"
    OFFLINE = "offline"
    IDLE = "idle"
    BUSY = "busy"
    MAINTENANCE = "maintenance"


class ControlPlaneLeaseStatus(str, Enum):
    """Durable lease lifecycle."""

    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class ControlPlaneWorker(Base):
    """Authoritative worker/device registry used for task leasing."""

    __tablename__ = "control_plane_workers"
    __table_args__ = (
        Index("ix_cp_workers_status", "status"),
        Index("ix_cp_workers_owner", "owner_id"),
        Index("ix_cp_workers_last_heartbeat", "last_heartbeat_at"),
    )

    worker_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    device_name: Mapped[str] = mapped_column(String(100), nullable=False)
    device_type: Mapped[str] = mapped_column(String(50), nullable=False)
    owner_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    capabilities_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        default=ControlPlaneWorkerStatus.IDLE.value,
        nullable=False,
    )
    # Deprecated singular ownership aliases retained for compatibility only.
    current_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_attempt_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_lease_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cpu_usage_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    memory_usage_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    storage_usage_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    network_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tasks_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reputation_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    max_concurrent_tasks: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    daily_task_limit: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    tasks_today: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quota_reset_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class ControlPlaneTask(Base):
    """Durable task row with active ownership and result state."""

    __tablename__ = "control_plane_tasks"
    __table_args__ = (
        Index("ix_cp_tasks_status", "status"),
        Index("ix_cp_tasks_worker", "worker_id"),
        Index("ix_cp_tasks_worker_status", "worker_id", "status"),
        Index("ix_cp_tasks_pipeline", "pipeline_id"),
        Index("ix_cp_tasks_stage", "stage_id"),
        Index("ix_cp_tasks_idempotency", "idempotency_key", unique=True),
        Index("ix_cp_tasks_created_at", "created_at"),
    )

    task_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    priority: Mapped[str] = mapped_column(String(50), default="NORMAL", nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    resource_requirements_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    target_worker_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_device_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=3600, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    callback_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_worker_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pipeline_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stage_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        default=ControlPlaneTaskState.PENDING.value,
        nullable=False,
    )
    worker_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_attempt_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_lease_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_time_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class ControlPlaneTaskAttempt(Base):
    """Immutable attempt history for each task execution try."""

    __tablename__ = "control_plane_task_attempts"
    __table_args__ = (
        Index("ix_cp_attempts_task", "task_id"),
        Index("ix_cp_attempts_worker", "worker_id"),
        Index("ix_cp_attempts_status", "status"),
        Index("ix_cp_attempts_lease", "lease_id", unique=True),
        Index("ix_cp_attempts_task_number", "task_id", "attempt_number", unique=True),
    )

    attempt_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("control_plane_tasks.task_id", ondelete="CASCADE"),
        nullable=False,
    )
    worker_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lease_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_time_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class ControlPlaneTaskLease(Base):
    """Durable lease record. Exactly one lease row exists per attempt."""

    __tablename__ = "control_plane_task_leases"
    __table_args__ = (
        Index("ix_cp_leases_task", "task_id"),
        Index("ix_cp_leases_worker", "worker_id"),
        Index("ix_cp_leases_status", "status"),
        Index("ix_cp_leases_expires_at", "expires_at"),
        Index("ix_cp_leases_status_expires_at", "status", "expires_at"),
        Index("ix_cp_leases_attempt", "attempt_id", unique=True),
        Index(
            "ix_cp_leases_active_task",
            "task_id",
            unique=True,
            sqlite_where=text("status = 'ACTIVE'"),
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    lease_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("control_plane_tasks.task_id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("control_plane_task_attempts.attempt_id", ondelete="CASCADE"),
        nullable=False,
    )
    worker_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        default=ControlPlaneLeaseStatus.ACTIVE.value,
        nullable=False,
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    renewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class PipelineRecord(Base):
    """Durable pipeline execution state for restart-safe recovery."""

    __tablename__ = "pipeline_records"
    __table_args__ = (
        Index("ix_pipeline_records_status", "status"),
        Index("ix_pipeline_records_updated_at", "updated_at"),
    )

    pipeline_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    definition_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    callback_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
