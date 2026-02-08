"""
SQLAlchemy Models for Device Mesh Persistence
Implements SEC-CRIT-01: Token Persistence in SQLite

PHASE0-SEC-001 (lg03): Token Persistence in SQLite
- Replaces in-memory token storage with SQLite persistence
- Tokens survive server restarts
- Enables token revocation and expiry tracking
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING
import uuid

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, utc_now


class MeshToken(Base):
    """
    Mesh Device Authentication Token

    Stores hashed tokens for device authentication.
    Tokens are hashed (never stored plaintext) for security.

    SEC-CRIT-01: Replaces in-memory _device_tokens dict
    """
    __tablename__ = 'mesh_tokens'
    __table_args__ = (
        Index('ix_mesh_tokens_device_id', 'device_id'),
        Index('ix_mesh_tokens_token_hash', 'token_hash', unique=True),
        Index('ix_mesh_tokens_expires_at', 'expires_at'),
        {'extend_existing': True}
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)  # SHA-256 hash
    device_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Token lifecycle
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # None = no expiry
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Token metadata
    token_type: Mapped[str] = mapped_column(String(50), default='mesh_auth', nullable=False)  # mesh_auth, refresh, enrollment
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Usage tracking
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    @property
    def is_valid(self) -> bool:
        """Check if token is currently valid (not expired, not revoked)"""
        now = datetime.now(timezone.utc)
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and self.expires_at < now:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': str(self.id),
            'device_id': self.device_id,
            'token_type': self.token_type,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'revoked_at': self.revoked_at.isoformat() if self.revoked_at else None,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'use_count': self.use_count,
            'is_valid': self.is_valid,
        }


class MeshDevice(Base):
    """
    Mesh Device Registry

    Persistent storage for mesh device state.
    Replaces in-memory _devices dict.

    SEC-CRIT-01: Enables device state persistence across restarts
    """
    __tablename__ = 'mesh_devices'
    __table_args__ = (
        Index('ix_mesh_devices_zone', 'zone'),
        Index('ix_mesh_devices_status', 'status'),
        Index('ix_mesh_devices_role', 'role'),
        Index('ix_mesh_devices_last_heartbeat', 'last_heartbeat'),
        {'extend_existing': True}
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    device_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Role and status
    role: Mapped[str] = mapped_column(String(50), default='worker', nullable=False)  # primary, secondary, worker, mobile, edge
    status: Mapped[str] = mapped_column(String(50), default='online', nullable=False)  # online, offline, idle, busy, draining, maintenance
    zone: Mapped[str] = mapped_column(String(100), default='default', nullable=False)

    # Profile stored as JSON (DeviceProfile schema)
    profile_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    # Hardware summary (denormalized for queries)
    cpu_cores: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    ram_gb: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    max_concurrent_tasks: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Current state
    current_load: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    active_tasks_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    pending_sync_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Liveness tracking
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consecutive_misses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    consecutive_successes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_heartbeat_latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Security
    public_key: Mapped[str | None] = mapped_column(Text, nullable=True)  # For secure communication

    # Ownership
    owner_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # Timestamps
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    @property
    def is_healthy(self) -> bool:
        """Check if device is healthy based on liveness"""
        return self.consecutive_misses < 3 and self.status not in ('offline', 'maintenance')

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': str(self.id),
            'device_id': self.device_id,
            'device_name': self.device_name,
            'role': self.role,
            'status': self.status,
            'zone': self.zone,
            'profile': self.profile_json,
            'cpu_cores': self.cpu_cores,
            'ram_gb': self.ram_gb,
            'max_concurrent_tasks': self.max_concurrent_tasks,
            'current_load': self.current_load,
            'active_tasks': self.active_tasks_json,
            'pending_sync_count': self.pending_sync_count,
            'is_healthy': self.is_healthy,
            'joined_at': self.joined_at.isoformat() if self.joined_at else None,
            'last_heartbeat': self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            'owner_id': self.owner_id,
        }


class MeshEnrollmentCode(Base):
    """
    One-Time Enrollment Codes

    SEC-CRIT-02: Replaces shared fog_secret with one-time codes.
    Each device gets a unique enrollment code that can only be used once.

    Note: This is for PHASE0-SEC-002 (ua7k) but created now for schema completeness.
    """
    __tablename__ = 'mesh_enrollment_codes'
    __table_args__ = (
        Index('ix_mesh_enrollment_code_hash', 'code_hash', unique=True),
        Index('ix_mesh_enrollment_created_by', 'created_by_device_id'),
        {'extend_existing': True}
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)  # SHA-256 hash

    # Who created this code
    created_by_device_id: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Primary device that generated it
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Expiration
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Usage
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    used_by_device_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Metadata
    intended_device_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    intended_role: Mapped[str] = mapped_column(String(50), default='worker', nullable=False)

    @property
    def is_valid(self) -> bool:
        """Check if code is currently valid (not expired, not used)"""
        now = datetime.now(timezone.utc)
        if self.used_at is not None:
            return False
        if self.expires_at < now:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': str(self.id),
            'created_by_device_id': self.created_by_device_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'used_at': self.used_at.isoformat() if self.used_at else None,
            'used_by_device_id': self.used_by_device_id,
            'intended_device_name': self.intended_device_name,
            'intended_role': self.intended_role,
            'is_valid': self.is_valid,
        }
