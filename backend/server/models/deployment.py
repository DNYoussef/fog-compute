"""
Deployment Database Models
SQLAlchemy models for fog-compute deployment system
Handles deployments, replicas, resources, and status tracking
"""
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from .database import Base


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

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    container_image = Column(String(500), nullable=False)
    status = Column(SQLEnum(DeploymentStatus), default=DeploymentStatus.PENDING, nullable=False, index=True)
    target_replicas = Column(Integer, default=1, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True, index=True)  # Soft delete

    # Relationships
    replicas = relationship("DeploymentReplica", back_populates="deployment", cascade="all, delete-orphan")
    resources = relationship("DeploymentResource", back_populates="deployment", cascade="all, delete-orphan", uselist=False)
    status_history = relationship("DeploymentStatusHistory", back_populates="deployment", cascade="all, delete-orphan")

    def to_dict(self):
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

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deployment_id = Column(UUID(as_uuid=True), ForeignKey('deployments.id'), nullable=False, index=True)
    node_id = Column(UUID(as_uuid=True), ForeignKey('nodes.id'), nullable=True, index=True)
    status = Column(SQLEnum(ReplicaStatus), default=ReplicaStatus.PENDING, nullable=False, index=True)
    container_id = Column(String(255), nullable=True)  # Docker/container runtime ID

    # Timestamps
    started_at = Column(DateTime, nullable=True)
    stopped_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    deployment = relationship("Deployment", back_populates="replicas")

    def to_dict(self):
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

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deployment_id = Column(UUID(as_uuid=True), ForeignKey('deployments.id'), nullable=False, unique=True, index=True)
    cpu_cores = Column(Float, nullable=False)  # Decimal for fractional cores (e.g., 0.5, 1.5)
    memory_mb = Column(Integer, nullable=False)
    gpu_units = Column(Integer, default=0, nullable=False)  # Optional GPU allocation
    storage_gb = Column(Integer, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    deployment = relationship("Deployment", back_populates="resources")

    def to_dict(self):
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

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deployment_id = Column(UUID(as_uuid=True), ForeignKey('deployments.id'), nullable=False, index=True)
    old_status = Column(String(50), nullable=False)
    new_status = Column(String(50), nullable=False)
    changed_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, index=True)
    changed_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    reason = Column(String(500), nullable=True)  # Optional reason for status change

    # Relationships
    deployment = relationship("Deployment", back_populates="status_history")

    def to_dict(self):
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
