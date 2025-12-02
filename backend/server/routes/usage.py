"""
Usage Tracking API Routes
Handles usage status queries and limit information
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.database import User
from ..auth.dependencies import get_current_user
from ..services.usage_tracking import usage_tracking_service
from ..services.usage_scheduler import usage_scheduler

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/usage", tags=["usage"])


class UsageStatusResponse(BaseModel):
    """Response model for usage status"""
    user_id: str
    date: str
    tier: str
    usage: Dict[str, Any]
    limits: Dict[str, Any]
    remaining: Dict[str, Any]


class LimitCheckRequest(BaseModel):
    """Request model for limit checking"""
    metric: str
    amount: float = 1.0


class LimitCheckResponse(BaseModel):
    """Response model for limit check"""
    allowed: bool
    reason: Optional[str] = None
    current: float
    limit: Optional[float] = None
    remaining: Optional[float] = None


@router.get("/status", response_model=UsageStatusResponse)
async def get_usage_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get current usage status for authenticated user

    Returns:
        - user_id: User UUID
        - date: Current date (YYYY-MM-DD)
        - tier: User tier (free, pro, enterprise)
        - usage: Current usage counters
        - limits: Maximum allowed per tier
        - remaining: Remaining quota

    Example Response:
        {
            "user_id": "123e4567-e89b-12d3-a456-426614174000",
            "date": "2025-11-25",
            "tier": "free",
            "usage": {
                "deployments_created": 5,
                "api_calls": 1000,
                "compute_hours": 2.5,
                "storage_gb_hours": 1.2
            },
            "limits": {
                "max_deployments": 10,
                "max_api_calls": 5000,
                "max_compute_hours": 10.0,
                "max_storage_gb": 5
            },
            "remaining": {
                "deployments": 5,
                "api_calls": 4000,
                "compute_hours": 7.5,
                "storage_gb": 3.8
            }
        }
    """
    if not usage_tracking_service.initialized:
        raise HTTPException(
            status_code=503,
            detail="Usage tracking service not available"
        )

    try:
        status = await usage_tracking_service.get_usage_status(
            db=db,
            user_id=str(current_user.id)
        )
        return status

    except ValueError as e:
        logger.error(f"Error getting usage status: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting usage status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check-limit", response_model=LimitCheckResponse)
async def check_limit(
    request: LimitCheckRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Check if user can perform action without exceeding limits

    Args:
        metric: Metric to check (deployments, api_calls, compute_hours, storage)
        amount: Amount to check (default 1.0)

    Returns:
        - allowed: Whether action is allowed
        - reason: Reason if not allowed
        - current: Current usage
        - limit: Maximum allowed (None if unlimited)
        - remaining: Remaining quota (None if unlimited)

    Example Request:
        {
            "metric": "deployments",
            "amount": 1.0
        }

    Example Response:
        {
            "allowed": true,
            "reason": null,
            "current": 5,
            "limit": 10,
            "remaining": 5
        }
    """
    if not usage_tracking_service.initialized:
        raise HTTPException(
            status_code=503,
            detail="Usage tracking service not available"
        )

    try:
        result = await usage_tracking_service.check_limit(
            db=db,
            user_id=str(current_user.id),
            metric=request.metric,
            amount=request.amount
        )
        return result

    except Exception as e:
        logger.error(f"Error checking limit: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/limits/{tier}")
async def get_tier_limits(
    tier: str,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get usage limits for a specific tier

    Args:
        tier: Tier name (free, pro, enterprise)

    Returns:
        Limit configuration for the tier

    Example Response:
        {
            "tier": "free",
            "max_deployments_per_day": 10,
            "max_api_calls_per_day": 5000,
            "max_compute_hours_per_day": 10.0,
            "max_storage_gb": 5
        }
    """
    if not usage_tracking_service.initialized:
        raise HTTPException(
            status_code=503,
            detail="Usage tracking service not available"
        )

    try:
        limits = await usage_tracking_service.get_usage_limits(db, tier)

        if not limits:
            raise HTTPException(
                status_code=404,
                detail=f"No limits found for tier: {tier}"
            )

        return limits.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tier limits: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all-limits")
async def get_all_limits(
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get usage limits for all tiers

    Returns:
        Dictionary mapping tier names to their limits

    Example Response:
        {
            "free": {
                "max_deployments_per_day": 10,
                "max_api_calls_per_day": 5000,
                "max_compute_hours_per_day": 10.0,
                "max_storage_gb": 5
            },
            "pro": {
                "max_deployments_per_day": 50,
                "max_api_calls_per_day": 50000,
                "max_compute_hours_per_day": 100.0,
                "max_storage_gb": 50
            },
            "enterprise": {
                "max_deployments_per_day": null,
                "max_api_calls_per_day": null,
                "max_compute_hours_per_day": null,
                "max_storage_gb": null
            }
        }
    """
    if not usage_tracking_service.initialized:
        raise HTTPException(
            status_code=503,
            detail="Usage tracking service not available"
        )

    try:
        tiers = ['free', 'pro', 'enterprise']
        all_limits = {}

        for tier in tiers:
            limits = await usage_tracking_service.get_usage_limits(db, tier)
            if limits:
                all_limits[tier] = limits.to_dict()

        return all_limits

    except Exception as e:
        logger.error(f"Error getting all limits: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/manual-reset")
async def manual_reset(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Manually trigger usage reset (admin only)

    Requires admin privileges

    Returns:
        Result of manual reset

    Example Response:
        {
            "success": true,
            "records_processed": 42,
            "timestamp": "2025-11-25T00:00:00Z"
        }
    """
    # Check admin privileges
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required"
        )

    try:
        record_count = await usage_scheduler.manual_reset()

        return {
            "success": True,
            "records_processed": record_count,
            "timestamp": datetime.now(timezone.utc).isoformat() + 'Z'
        }

    except Exception as e:
        logger.error(f"Manual reset failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Manual reset failed: {str(e)}"
        )


@router.get("/scheduler/status")
async def get_scheduler_status(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get usage scheduler status

    Returns:
        Scheduler status information

    Example Response:
        {
            "running": true,
            "next_reset": "2025-11-26T00:00:00Z"
        }
    """
    from datetime import datetime, time, timedelta, timezone

    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).date()
    next_midnight = datetime.combine(tomorrow, time(0, 0, 0), tzinfo=timezone.utc)

    return {
        "running": usage_scheduler.is_running,
        "next_reset": next_midnight.isoformat() + 'Z',
        "current_time": now.isoformat() + 'Z'
    }
