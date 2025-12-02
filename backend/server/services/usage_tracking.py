"""
Usage Tracking Service
Manages daily usage tracking, limit enforcement, and automatic resets
"""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Dict, Optional, Any
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from ..models.usage import DailyUsage, UsageLimit
from ..models.database import User

logger = logging.getLogger(__name__)


class UsageTrackingService:
    """
    Service for tracking and enforcing daily usage limits

    Features:
    - Track deployments, API calls, compute hours, storage usage
    - Enforce tier-based limits
    - Automatic daily reset at midnight UTC
    - Usage status queries
    """

    def __init__(self):
        self.initialized = False

    async def initialize(self):
        """Initialize the usage tracking service"""
        logger.info("Initializing usage tracking service...")
        self.initialized = True
        logger.info("Usage tracking service initialized")

    async def get_or_create_daily_usage(
        self,
        db: AsyncSession,
        user_id: str,
        usage_date: Optional[date] = None
    ) -> DailyUsage:
        """
        Get or create daily usage record for user

        Args:
            db: Database session
            user_id: User UUID
            usage_date: Date to track (defaults to today)

        Returns:
            DailyUsage record
        """
        if usage_date is None:
            usage_date = date.today()

        # Try to find existing record
        result = await db.execute(
            select(DailyUsage).where(
                and_(
                    DailyUsage.user_id == user_id,
                    DailyUsage.date == usage_date
                )
            )
        )
        daily_usage = result.scalar_one_or_none()

        # Create if doesn't exist
        if not daily_usage:
            daily_usage = DailyUsage(
                user_id=user_id,
                date=usage_date,
                deployments_created=0,
                api_calls=0,
                compute_hours=Decimal('0.0'),
                storage_gb_hours=Decimal('0.0')
            )
            db.add(daily_usage)
            await db.commit()
            await db.refresh(daily_usage)
            logger.info(f"Created daily usage record for user {user_id} on {usage_date}")

        return daily_usage

    async def get_usage_limits(
        self,
        db: AsyncSession,
        tier: str
    ) -> Optional[UsageLimit]:
        """
        Get usage limits for a tier

        Args:
            db: Database session
            tier: Tier name (free, pro, enterprise)

        Returns:
            UsageLimit record or None
        """
        result = await db.execute(
            select(UsageLimit).where(UsageLimit.tier == tier)
        )
        return result.scalar_one_or_none()

    async def check_limit(
        self,
        db: AsyncSession,
        user_id: str,
        metric: str,
        amount: float = 1.0
    ) -> Dict[str, Any]:
        """
        Check if user can perform action without exceeding limits

        Args:
            db: Database session
            user_id: User UUID
            metric: Metric to check (deployments, api_calls, compute_hours, storage)
            amount: Amount to add (default 1.0)

        Returns:
            {
                'allowed': bool,
                'reason': str (if not allowed),
                'current': float,
                'limit': float or None,
                'remaining': float or None
            }
        """
        # Get user tier
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return {
                'allowed': False,
                'reason': 'User not found',
                'current': 0,
                'limit': None,
                'remaining': None
            }

        # Get usage limits for tier
        limits = await self.get_usage_limits(db, user.tier)

        if not limits:
            # No limits defined = unlimited (enterprise tier)
            return {
                'allowed': True,
                'current': 0,
                'limit': None,
                'remaining': None
            }

        # Get current usage
        daily_usage = await self.get_or_create_daily_usage(db, user_id)

        # Map metric to column and limit
        metric_mapping = {
            'deployments': {
                'current': daily_usage.deployments_created,
                'limit': limits.max_deployments_per_day
            },
            'api_calls': {
                'current': daily_usage.api_calls,
                'limit': limits.max_api_calls_per_day
            },
            'compute_hours': {
                'current': float(daily_usage.compute_hours),
                'limit': float(limits.max_compute_hours_per_day) if limits.max_compute_hours_per_day else None
            },
            'storage': {
                'current': float(daily_usage.storage_gb_hours),
                'limit': limits.max_storage_gb
            }
        }

        if metric not in metric_mapping:
            return {
                'allowed': False,
                'reason': f'Unknown metric: {metric}',
                'current': 0,
                'limit': None,
                'remaining': None
            }

        current = metric_mapping[metric]['current']
        limit = metric_mapping[metric]['limit']

        # Check if limit exists (None = unlimited)
        if limit is None:
            return {
                'allowed': True,
                'current': current,
                'limit': None,
                'remaining': None
            }

        # Check if adding amount would exceed limit
        new_value = current + amount
        allowed = new_value <= limit

        return {
            'allowed': allowed,
            'reason': f'Daily {metric} limit exceeded' if not allowed else None,
            'current': current,
            'limit': limit,
            'remaining': max(0, limit - current)
        }

    async def increment_usage(
        self,
        db: AsyncSession,
        user_id: str,
        metric: str,
        amount: float = 1.0
    ) -> DailyUsage:
        """
        Increment usage counter for user

        Args:
            db: Database session
            user_id: User UUID
            metric: Metric to increment (deployments, api_calls, compute_hours, storage)
            amount: Amount to add (default 1.0)

        Returns:
            Updated DailyUsage record

        Raises:
            ValueError: If limit would be exceeded
        """
        # Check limit first
        limit_check = await self.check_limit(db, user_id, metric, amount)

        if not limit_check['allowed']:
            raise ValueError(limit_check['reason'])

        # Get or create usage record
        daily_usage = await self.get_or_create_daily_usage(db, user_id)

        # Increment appropriate counter
        if metric == 'deployments':
            daily_usage.deployments_created += int(amount)
        elif metric == 'api_calls':
            daily_usage.api_calls += int(amount)
        elif metric == 'compute_hours':
            daily_usage.compute_hours += Decimal(str(amount))
        elif metric == 'storage':
            daily_usage.storage_gb_hours += Decimal(str(amount))
        else:
            raise ValueError(f'Unknown metric: {metric}')

        daily_usage.updated_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(daily_usage)

        logger.debug(f"Incremented {metric} by {amount} for user {user_id}")

        return daily_usage

    async def get_usage_status(
        self,
        db: AsyncSession,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get comprehensive usage status for user

        Args:
            db: Database session
            user_id: User UUID

        Returns:
            {
                'user_id': str,
                'date': str,
                'tier': str,
                'usage': {...},
                'limits': {...},
                'remaining': {...}
            }
        """
        # Get user
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError('User not found')

        # Get usage and limits
        daily_usage = await self.get_or_create_daily_usage(db, user_id)
        limits = await self.get_usage_limits(db, user.tier)

        # Build response
        usage = {
            'deployments_created': daily_usage.deployments_created,
            'api_calls': daily_usage.api_calls,
            'compute_hours': float(daily_usage.compute_hours),
            'storage_gb_hours': float(daily_usage.storage_gb_hours)
        }

        if limits:
            limits_dict = {
                'max_deployments': limits.max_deployments_per_day,
                'max_api_calls': limits.max_api_calls_per_day,
                'max_compute_hours': float(limits.max_compute_hours_per_day) if limits.max_compute_hours_per_day else None,
                'max_storage_gb': limits.max_storage_gb
            }

            remaining = {
                'deployments': limits.max_deployments_per_day - daily_usage.deployments_created if limits.max_deployments_per_day else None,
                'api_calls': limits.max_api_calls_per_day - daily_usage.api_calls if limits.max_api_calls_per_day else None,
                'compute_hours': float(limits.max_compute_hours_per_day) - float(daily_usage.compute_hours) if limits.max_compute_hours_per_day else None,
                'storage_gb': limits.max_storage_gb - float(daily_usage.storage_gb_hours) if limits.max_storage_gb else None
            }
        else:
            # Enterprise tier - no limits
            limits_dict = {
                'max_deployments': None,
                'max_api_calls': None,
                'max_compute_hours': None,
                'max_storage_gb': None
            }
            remaining = {
                'deployments': None,
                'api_calls': None,
                'compute_hours': None,
                'storage_gb': None
            }

        return {
            'user_id': str(user_id),
            'date': daily_usage.date.isoformat(),
            'tier': user.tier,
            'usage': usage,
            'limits': limits_dict,
            'remaining': remaining
        }

    async def reset_daily_usage(self, db: AsyncSession) -> int:
        """
        Reset all daily usage counters (called at midnight UTC)

        This doesn't delete records - historical data is preserved.
        New day = new records created on-demand.

        Args:
            db: Database session

        Returns:
            Number of records processed (for logging)
        """
        yesterday = date.today() - timedelta(days=1)

        result = await db.execute(
            select(DailyUsage).where(DailyUsage.date == yesterday)
        )
        records = result.scalars().all()

        logger.info(f"Daily usage reset: {len(records)} records from {yesterday} now historical")

        return len(records)


# Global service instance
usage_tracking_service = UsageTrackingService()
