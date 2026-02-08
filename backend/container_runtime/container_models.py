"""
SQLAlchemy Models for Container Runtime Persistence
Implements FOG-SEC-003: Container State Persistence

Provides database models for:
- ContainerRecord: Full container state with spec as JSON
- PendingQueueRecord: Ordered queue of pending container IDs
- SchedulerStatsRecord: Scheduler statistics for recovery
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import DateTime, Float, Integer, JSON, String, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

# Handle both package and standalone import scenarios
try:
    from ..server.models.database import Base, utc_now
except ImportError:
    from backend.server.models.database import Base, utc_now


class ContainerRecord(Base):
    """
    Container Runtime State Record

    FOG-SEC-003: Persists full container state for recovery.
    Spec is stored as JSON for flexibility.
    """
    __tablename__ = 'container_records'
    __table_args__ = (
        Index('ix_container_records_status', 'status'),
        Index('ix_container_records_node_id', 'node_id'),
        Index('ix_container_records_created_at', 'created_at'),
        {'extend_existing': True}
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    container_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)

    # Container spec stored as JSON
    spec_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    # Status
    status: Mapped[str] = mapped_column(String(50), nullable=False, default='pending')
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Placement
    node_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Runtime info
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    # Health
    health_status: Mapped[str] = mapped_column(String(50), default='unknown', nullable=False)
    last_health_check: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    health_check_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Resource usage
    cpu_usage_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    memory_usage_mb: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    network_rx_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    network_tx_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Restart tracking
    restart_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            'id': str(self.id),
            'container_id': self.container_id,
            'spec': self.spec_json,
            'status': self.status,
            'exit_code': self.exit_code,
            'error': self.error,
            'node_id': self.node_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'finished_at': self.finished_at.isoformat() if self.finished_at else None,
            'pid': self.pid,
            'ip_address': self.ip_address,
            'health_status': self.health_status,
            'last_health_check': self.last_health_check.isoformat() if self.last_health_check else None,
            'health_check_failures': self.health_check_failures,
            'cpu_usage_percent': self.cpu_usage_percent,
            'memory_usage_mb': self.memory_usage_mb,
            'network_rx_bytes': self.network_rx_bytes,
            'network_tx_bytes': self.network_tx_bytes,
            'restart_count': self.restart_count,
        }


class PendingQueueRecord(Base):
    """
    Pending Container Queue Record

    FOG-SEC-003: Persists the order of pending containers.
    Position determines scheduling order.
    """
    __tablename__ = 'pending_queue_records'
    __table_args__ = (
        Index('ix_pending_queue_position', 'position'),
        {'extend_existing': True}
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    container_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            'id': str(self.id),
            'container_id': self.container_id,
            'position': self.position,
            'added_at': self.added_at.isoformat() if self.added_at else None,
        }


class SchedulerStatsRecord(Base):
    """
    Scheduler Statistics Record

    FOG-SEC-003: Persists scheduler statistics for recovery.
    Single row (id=1) holds all stats.
    """
    __tablename__ = 'scheduler_stats_records'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    containers_scheduled: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    containers_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    scheduling_latency_ms_avg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    auth_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            'containers_scheduled': self.containers_scheduled,
            'containers_failed': self.containers_failed,
            'scheduling_latency_ms_avg': self.scheduling_latency_ms_avg,
            'auth_failures': self.auth_failures,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
