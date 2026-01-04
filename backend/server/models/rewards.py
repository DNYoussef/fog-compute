"""
Reward Distribution Database Models

Tracks reward distributions, pending rewards, and distribution history
for audit and recovery purposes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
import uuid

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base

if TYPE_CHECKING:
    from .deployment import Deployment


def utc_now() -> datetime:
    """Return timezone-aware UTC datetime for SQLAlchemy defaults."""
    return datetime.now(timezone.utc)


class RewardDistribution(Base):
    """
    Record of reward distribution events
    Provides audit trail for all reward distributions
    """
    __tablename__ = 'reward_distributions'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reward_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    account_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, index=True)
    deployment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('deployments.id'), nullable=True, index=True)

    # Amount details
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    reward_type: Mapped[str] = mapped_column(String(50), nullable=False)  # staking, deployment_runtime, task_completion, etc.

    # Distribution status
    status: Mapped[str] = mapped_column(String(50), default='pending', nullable=False, index=True)
    # Status values: pending, distributed, failed, rolled_back

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    distributed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Additional context data (named 'context' to avoid SQLAlchemy reserved 'metadata')
    context: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Transaction tracking
    transfer_tx_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rollback_tx_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            'id': str(self.id),
            'reward_id': self.reward_id,
            'account_id': self.account_id,
            'user_id': str(self.user_id) if self.user_id else None,
            'deployment_id': str(self.deployment_id) if self.deployment_id else None,
            'amount': self.amount,
            'reason': self.reason,
            'reward_type': self.reward_type,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'distributed_at': self.distributed_at.isoformat() if self.distributed_at else None,
            'rolled_back_at': self.rolled_back_at.isoformat() if self.rolled_back_at else None,
            'metadata': self.metadata,
        }


class PendingRewardQueue(Base):
    """
    Queue of pending rewards awaiting distribution
    Used for deferred distribution and recovery scenarios
    """
    __tablename__ = 'pending_reward_queue'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reward_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    account_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, index=True)
    deployment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('deployments.id'), nullable=True, index=True)

    # Reward details
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    reward_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Queue status
    status: Mapped[str] = mapped_column(String(50), default='queued', nullable=False, index=True)
    # Status values: queued, processing, completed, failed

    priority: Mapped[str] = mapped_column(String(50), default='normal', nullable=False)
    # Priority values: low, normal, high, critical

    # Retry tracking
    retry_count: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    max_retries: Mapped[float] = mapped_column(Float, default=3, nullable=False)
    last_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Timestamps
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    # Error tracking
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    context: Mapped[Any | None] = mapped_column(JSON, nullable=True)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            'id': str(self.id),
            'reward_id': self.reward_id,
            'account_id': self.account_id,
            'user_id': str(self.user_id) if self.user_id else None,
            'deployment_id': str(self.deployment_id) if self.deployment_id else None,
            'amount': self.amount,
            'reason': self.reason,
            'reward_type': self.reward_type,
            'status': self.status,
            'priority': self.priority,
            'retry_count': self.retry_count,
            'queued_at': self.queued_at.isoformat() if self.queued_at else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
        }


class RewardDistributionBatch(Base):
    """
    Batch of reward distributions for atomic operations
    Tracks multiple related distributions that must succeed or fail together
    """
    __tablename__ = 'reward_distribution_batches'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)

    # Batch metadata
    batch_type: Mapped[str] = mapped_column(String(50), nullable=False)  # deployment_cleanup, system_cleanup, manual
    trigger_event: Mapped[str | None] = mapped_column(String(255), nullable=True)  # deployment_deletion, service_shutdown, etc.
    deployment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('deployments.id'), nullable=True, index=True)

    # Batch status
    status: Mapped[str] = mapped_column(String(50), default='pending', nullable=False, index=True)
    # Status values: pending, processing, completed, failed, rolled_back

    # Batch statistics
    total_rewards: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    total_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    successful_distributions: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    failed_distributions: Mapped[float] = mapped_column(Float, default=0, nullable=False)

    # Rollback tracking
    rollback_performed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rollback_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Associated distributions (stored as JSON for simplicity)
    reward_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)  # List of reward_id strings
    context: Mapped[Any | None] = mapped_column(JSON, nullable=True)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            'id': str(self.id),
            'batch_id': self.batch_id,
            'batch_type': self.batch_type,
            'trigger_event': self.trigger_event,
            'deployment_id': str(self.deployment_id) if self.deployment_id else None,
            'status': self.status,
            'total_rewards': self.total_rewards,
            'total_amount': self.total_amount,
            'successful_distributions': self.successful_distributions,
            'failed_distributions': self.failed_distributions,
            'rollback_performed': self.rollback_performed,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


class RewardDistributionAuditLog(Base):
    """
    Comprehensive audit log for all reward distribution events
    Immutable record for compliance and debugging
    """
    __tablename__ = 'reward_distribution_audit_log'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)

    # Event details
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # Event types: distribution_attempted, distribution_success, distribution_failed,
    #              rollback_attempted, rollback_success, rollback_failed

    reward_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    batch_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # Actor information
    account_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, index=True)

    # Event data
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    from_account: Mapped[str | None] = mapped_column(String(255), nullable=True)
    to_account: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Status and result
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Transaction tracking
    transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Timestamp
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    # Full event details (immutable JSON)
    event_data: Mapped[Any | None] = mapped_column(JSON, nullable=True)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            'id': str(self.id),
            'event_id': self.event_id,
            'event_type': self.event_type,
            'reward_id': self.reward_id,
            'batch_id': self.batch_id,
            'account_id': self.account_id,
            'user_id': str(self.user_id) if self.user_id else None,
            'amount': self.amount,
            'success': self.success,
            'error_message': self.error_message,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
        }
