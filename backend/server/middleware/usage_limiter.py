"""
Usage Limit Enforcement Middleware
Provides decorators and middleware for enforcing daily usage limits
"""
from functools import wraps
from typing import Callable, Optional
from fastapi import HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from ..database import get_db
from ..services.usage_tracking import usage_tracking_service
from ..auth.dependencies import get_current_user
from ..models.database import User

logger = logging.getLogger(__name__)


def require_usage_limit(
    metric: str,
    amount: float = 1.0,
    auto_increment: bool = True
):
    """
    Decorator to enforce usage limits on endpoints

    Args:
        metric: Metric to check (deployments, api_calls, compute_hours, storage)
        amount: Amount to check/increment (default 1.0)
        auto_increment: Automatically increment counter if check passes (default True)

    Usage:
        @router.post("/deploy")
        @require_usage_limit("deployments", 1.0)
        async def deploy_app(user: User = Depends(get_current_user)):
            ...

    Raises:
        HTTPException(429): When limit is exceeded
        HTTPException(503): When usage service is unavailable
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract dependencies from kwargs
            user: Optional[User] = kwargs.get('user') or kwargs.get('current_user')
            db: Optional[AsyncSession] = kwargs.get('db')

            if not user:
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required for usage tracking"
                )

            if not db:
                raise HTTPException(
                    status_code=500,
                    detail="Database session not available"
                )

            if not usage_tracking_service.initialized:
                raise HTTPException(
                    status_code=503,
                    detail="Usage tracking service not available"
                )

            try:
                # Check limit
                limit_check = await usage_tracking_service.check_limit(
                    db=db,
                    user_id=str(user.id),
                    metric=metric,
                    amount=amount
                )

                if not limit_check['allowed']:
                    logger.warning(
                        f"Usage limit exceeded for user {user.id}: {limit_check['reason']}"
                    )
                    raise HTTPException(
                        status_code=429,
                        detail={
                            'error': 'Usage limit exceeded',
                            'message': limit_check['reason'],
                            'current': limit_check['current'],
                            'limit': limit_check['limit'],
                            'tier': user.tier,
                            'metric': metric
                        }
                    )

                # Auto-increment if enabled
                if auto_increment:
                    await usage_tracking_service.increment_usage(
                        db=db,
                        user_id=str(user.id),
                        metric=metric,
                        amount=amount
                    )
                    logger.debug(f"Incremented {metric} by {amount} for user {user.id}")

                # Call original function
                return await func(*args, **kwargs)

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Usage limit check failed: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Usage limit check failed: {str(e)}"
                )

        return wrapper
    return decorator


async def check_usage_limit_dependency(
    metric: str,
    amount: float = 1.0
) -> Callable:
    """
    FastAPI dependency for checking usage limits without auto-increment

    Args:
        metric: Metric to check
        amount: Amount to check

    Returns:
        Dependency function

    Usage:
        @router.post("/deploy")
        async def deploy_app(
            user: User = Depends(get_current_user),
            db: AsyncSession = Depends(get_db),
            _: None = Depends(check_usage_limit_dependency("deployments", 1.0))
        ):
            # Manually increment later
            await usage_tracking_service.increment_usage(db, str(user.id), "deployments")
            ...
    """
    async def dependency(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        if not usage_tracking_service.initialized:
            raise HTTPException(
                status_code=503,
                detail="Usage tracking service not available"
            )

        limit_check = await usage_tracking_service.check_limit(
            db=db,
            user_id=str(user.id),
            metric=metric,
            amount=amount
        )

        if not limit_check['allowed']:
            logger.warning(
                f"Usage limit exceeded for user {user.id}: {limit_check['reason']}"
            )
            raise HTTPException(
                status_code=429,
                detail={
                    'error': 'Usage limit exceeded',
                    'message': limit_check['reason'],
                    'current': limit_check['current'],
                    'limit': limit_check['limit'],
                    'tier': user.tier,
                    'metric': metric
                }
            )

        return None

    return dependency


async def increment_usage(
    db: AsyncSession,
    user_id: str,
    metric: str,
    amount: float = 1.0
):
    """
    Helper function to manually increment usage

    Args:
        db: Database session
        user_id: User UUID
        metric: Metric to increment
        amount: Amount to add

    Usage:
        await increment_usage(db, str(user.id), "api_calls", 1.0)
    """
    try:
        await usage_tracking_service.increment_usage(
            db=db,
            user_id=user_id,
            metric=metric,
            amount=amount
        )
    except ValueError as e:
        logger.error(f"Failed to increment usage: {e}")
        raise HTTPException(
            status_code=429,
            detail=str(e)
        )
