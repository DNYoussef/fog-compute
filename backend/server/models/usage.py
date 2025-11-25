"""
Usage Tracking Database Models
Tracks daily usage limits and consumption per user
"""
from sqlalchemy import Column, String, Integer, Date, DateTime, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, date
import uuid

from .database import Base


class DailyUsage(Base):
    """
    Daily Usage Tracking
    Tracks user consumption by day with automatic reset at midnight UTC
    """
    __tablename__ = 'daily_usage'
    __table_args__ = (
        UniqueConstraint('user_id', 'date', name='uq_user_date'),
        {'extend_existing': True}
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    date = Column(Date, nullable=False, default=date.today, index=True)

    # Usage counters
    deployments_created = Column(Integer, default=0, nullable=False)
    api_calls = Column(Integer, default=0, nullable=False)
    compute_hours = Column(Numeric(10, 2), default=0.0, nullable=False)
    storage_gb_hours = Column(Numeric(10, 2), default=0.0, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'date': self.date.isoformat() if self.date else None,
            'deployments_created': self.deployments_created,
            'api_calls': self.api_calls,
            'compute_hours': float(self.compute_hours) if self.compute_hours else 0.0,
            'storage_gb_hours': float(self.storage_gb_hours) if self.storage_gb_hours else 0.0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class UsageLimit(Base):
    """
    Usage Limits by Tier
    Defines maximum allowed usage per tier (free, pro, enterprise)
    """
    __tablename__ = 'usage_limits'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tier = Column(String(50), unique=True, nullable=False, index=True)

    # Daily limits
    max_deployments_per_day = Column(Integer, nullable=True)  # None = unlimited
    max_api_calls_per_day = Column(Integer, nullable=True)
    max_compute_hours_per_day = Column(Numeric(10, 2), nullable=True)
    max_storage_gb = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': str(self.id),
            'tier': self.tier,
            'max_deployments_per_day': self.max_deployments_per_day,
            'max_api_calls_per_day': self.max_api_calls_per_day,
            'max_compute_hours_per_day': float(self.max_compute_hours_per_day) if self.max_compute_hours_per_day else None,
            'max_storage_gb': self.max_storage_gb,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
