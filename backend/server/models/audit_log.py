"""
Audit Log Model
Immutable audit trail for security compliance
Tracks all sensitive operations and access events
"""
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from .database import Base


class AuditLog(Base):
    """
    Audit Log Entry (Immutable)
    Records all security-relevant events for compliance and forensics

    CRITICAL: This table is append-only. No UPDATE or DELETE operations allowed.
    """
    __tablename__ = 'audit_logs'
    __table_args__ = (
        # Compound indexes for efficient querying
        Index('idx_audit_timestamp', 'timestamp'),
        Index('idx_audit_user_id', 'user_id'),
        Index('idx_audit_event_type', 'event_type'),
        Index('idx_audit_resource', 'resource_type', 'resource_id'),
        Index('idx_audit_status', 'status'),
        Index('idx_audit_correlation', 'correlation_id'),
        Index('idx_audit_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_audit_event_timestamp', 'event_type', 'timestamp'),
        {'extend_existing': True}
    )

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Timestamp (with timezone)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Event classification
    event_type = Column(String(100), nullable=False, index=True)
    # Event types: login, logout, login_failed, data_access, data_modify,
    #              data_delete, admin_action, permission_denied, api_key_used,
    #              password_change, user_created, user_deleted, config_change

    # User information (optional for anonymous events)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, index=True)

    # Request metadata
    ip_address = Column(String(45), nullable=False)  # IPv4 (15) or IPv6 (45)
    user_agent = Column(String(500), nullable=True)

    # Resource information
    resource_type = Column(String(100), nullable=True, index=True)
    # Resource types: user, job, node, deployment, circuit, token, dao_proposal, etc.
    resource_id = Column(String(255), nullable=True, index=True)

    # Action performed
    action = Column(String(50), nullable=False)
    # Actions: create, read, update, delete, execute, approve, reject

    # Data change tracking (for updates)
    old_value = Column(JSON, nullable=True)  # Previous state
    new_value = Column(JSON, nullable=True)  # New state

    # Request outcome
    status = Column(String(50), nullable=False, index=True)
    # Status: success, failure, denied

    # Request correlation
    correlation_id = Column(String(100), nullable=True, index=True)

    # Additional context
    metadata = Column(JSON, nullable=True)
    # Metadata can include: request_method, endpoint, response_time_ms,
    #                       error_message, session_id, api_key_id, etc.

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': str(self.id),
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'event_type': self.event_type,
            'user_id': str(self.user_id) if self.user_id else None,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'action': self.action,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'status': self.status,
            'correlation_id': self.correlation_id,
            'metadata': self.metadata,
        }
