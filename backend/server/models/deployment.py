"""
Deployment Database Models
SQLAlchemy models for fog-compute deployment system
Handles deployments, replicas, resources, and status tracking
"""
from __future__ import annotations

from datetime import datetime, timezone
import enum
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import DateTime, Enum as SQLEnum, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

if TYPE_CHECKING:
    from .database import Node, User


def utc_now() -> datetime:
    """Return timezone-aware UTC datetime for SQLAlchemy defaults."""
    return datetime.now(timezone.utc)


class DeploymentStatus(str, enum.Enum):
    """Deployment lifecycle status"""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    DELETED = "deleted"


class ReplicaStatus(str, enum.Enum):
    """Individual replica status"""
    PENDING = "pending"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class Deployment(Base):
    """
    Main deployment record
    Tracks service deployments with their configuration and lifecycle
    """
    __tablename__ = 'deployments'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    container_image: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[DeploymentStatus] = mapped_column(SQLEnum(DeploymentStatus), default=DeploymentStatus.PENDING, nullable=False, index=True)
    target_replicas: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)  # Soft delete

    # Relationships
    replicas: Mapped[list["DeploymentReplica"]] = relationship("DeploymentReplica", back_populates="deployment", cascade="all, delete-orphan")
    resources: Mapped["DeploymentResource | None"] = relationship("DeploymentResource", back_populates="deployment", cascade="all, delete-orphan", uselist=False)
    status_history: Mapped[list["DeploymentStatusHistory"]] = relationship("DeploymentStatusHistory", back_populates="deployment", cascade="all, delete-orphan")

    def to_dict(self) -> dict[str, str | int | None]:
        """Convert to dictionary for API responses"""
        return {
            'id': str(self.id),
            'name': self.name,
            'user_id': str(self.user_id),
            'container_image': self.container_image,
            'status': self.status.value if isinstance(self.status, DeploymentStatus) else self.status,
            'target_replicas': self.target_replicas,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None,
        }


class DeploymentReplica(Base):
    """
    Individual replica instance
    Tracks each container replica with its node assignment and status
    """
    __tablename__ = 'deployment_replicas'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deployment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('deployments.id'), nullable=False, index=True)
    node_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('nodes.id'), nullable=True, index=True)
    status: Mapped[ReplicaStatus] = mapped_column(SQLEnum(ReplicaStatus), default=ReplicaStatus.PENDING, nullable=False, index=True)
    container_id: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Docker/container runtime ID

    # Timestamps
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    deployment: Mapped["Deployment"] = relationship("Deployment", back_populates="replicas")

    def to_dict(self) -> dict[str, str | None]:
        """Convert to dictionary for API responses"""
        return {
            'id': str(self.id),
            'deployment_id': str(self.deployment_id),
            'node_id': str(self.node_id) if self.node_id else None,
            'status': self.status.value if isinstance(self.status, ReplicaStatus) else self.status,
            'container_id': self.container_id,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'stopped_at': self.stopped_at.isoformat() if self.stopped_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class DeploymentResource(Base):
    """
    Resource allocation for deployment
    Tracks CPU, memory, GPU, and storage allocations
    """
    __tablename__ = 'deployment_resources'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deployment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('deployments.id'), nullable=False, unique=True, index=True)
    cpu_cores: Mapped[float] = mapped_column(Float, nullable=False)  # Decimal for fractional cores (e.g., 0.5, 1.5)
    memory_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    gpu_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # Optional GPU allocation
    storage_gb: Mapped[int] = mapped_column(Integer, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    deployment: Mapped["Deployment"] = relationship("Deployment", back_populates="resources")

    def to_dict(self) -> dict[str, str | float | int | None]:
        """Convert to dictionary for API responses"""
        return {
            'id': str(self.id),
            'deployment_id': str(self.deployment_id),
            'cpu_cores': self.cpu_cores,
            'memory_mb': self.memory_mb,
            'gpu_units': self.gpu_units,
            'storage_gb': self.storage_gb,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class DeploymentStatusHistory(Base):
    """
    Audit trail for deployment status changes
    Tracks who changed status, when, and why
    """
    __tablename__ = 'deployment_status_history'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deployment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('deployments.id'), nullable=False, index=True)
    old_status: Mapped[str] = mapped_column(String(50), nullable=False)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, index=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)  # Optional reason for status change

    # Relationships
    deployment: Mapped["Deployment"] = relationship("Deployment", back_populates="status_history")

    def to_dict(self) -> dict[str, str | None]:
        """Convert to dictionary for API responses"""
        return {
            'id': str(self.id),
            'deployment_id': str(self.deployment_id),
            'old_status': self.old_status,
            'new_status': self.new_status,
            'changed_by': str(self.changed_by) if self.changed_by else None,
            'changed_at': self.changed_at.isoformat() if self.changed_at else None,
            'reason': self.reason,
        }
