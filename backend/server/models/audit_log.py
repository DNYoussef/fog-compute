"""
Audit Log Model
Immutable audit trail for security compliance
Tracks all sensitive operations and access events
"""
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Index, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime, timezone
import uuid

from .database import Base


def utc_now():
    """Return timezone-aware UTC datetime for SQLAlchemy defaults."""
    return datetime.now(timezone.utc)


class AuditLog(Base):
    """
    Audit Log Entry (Immutable)
    Records all security-relevant events for compliance and forensics

    CRITICAL: This table is append-only. No UPDATE or DELETE operations allowed.
    Immutability enforced via database trigger (see migration).
    """
    __tablename__ = 'audit_logs'
    __table_args__ = (
        # Compound indexes for efficient querying
        Index('idx_audit_timestamp', 'timestamp'),
        Index('idx_audit_user_id', 'user_id'),
        Index('idx_audit_action', 'action'),
        Index('idx_audit_resource', 'resource_type', 'resource_id'),
        Index('idx_audit_correlation', 'correlation_id'),
        Index('idx_audit_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_audit_action_timestamp', 'action', 'timestamp'),
        {'extend_existing': True}
    )

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Timestamp (with timezone) - indexed for time-range queries
    timestamp = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    # User information (nullable for anonymous/system events)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, index=True)

    # Action performed - primary classification
    action = Column(String(100), nullable=False, index=True)
    # Actions: login, logout, deploy, delete, create, read, update, execute, etc.

    # Resource information
    resource_type = Column(String(100), nullable=True)
    # Resource types: deployment, user, node, job, circuit, api_key, dao_proposal, etc.
    resource_id = Column(UUID(as_uuid=True), nullable=True)

    # Request metadata
    ip_address = Column(String(45), nullable=False)  # IPv4 (15) or IPv6 (45)
    user_agent = Column(String(500), nullable=True)

    # Request correlation for tracing
    correlation_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    # HTTP request details
    request_method = Column(String(10), nullable=True)  # GET, POST, PUT, DELETE, PATCH
    request_path = Column(String(500), nullable=True)

    # Response details
    response_status = Column(Integer, nullable=True)  # HTTP status code

    # Performance tracking
    duration_ms = Column(Integer, nullable=True)  # Request duration in milliseconds

    # Additional flexible context (JSONB for efficient querying)
    context = Column('metadata', JSONB, nullable=True)
    # Context can include: event_type, old_value, new_value, error_message,
    #                      session_id, api_key_id, custom_fields, etc.

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': str(self.id),
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'user_id': str(self.user_id) if self.user_id else None,
            'action': self.action,
            'resource_type': self.resource_type,
            'resource_id': str(self.resource_id) if self.resource_id else None,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'correlation_id': str(self.correlation_id) if self.correlation_id else None,
            'request_method': self.request_method,
            'request_path': self.request_path,
            'response_status': self.response_status,
            'duration_ms': self.duration_ms,
            'metadata': self.context,
        }
