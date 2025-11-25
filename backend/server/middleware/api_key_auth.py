"""
API Key Authentication Middleware
Validates X-API-Key header and enforces rate limits per key
"""
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any
import logging

from ..auth.api_key import APIKeyManager
from ..database import get_db
from ..models.database import User

logger = logging.getLogger(__name__)

# Header scheme for API key
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_api_key_user(
    api_key: Optional[str] = Depends(api_key_header),
    db: AsyncSession = Depends(get_db)
) -> Optional[Dict[str, Any]]:
    """
    Validate API key from X-API-Key header

    Args:
        api_key: API key from X-API-Key header
        db: Database session

    Returns:
        Dictionary with user and key metadata if valid, None otherwise

    Note:
        This dependency returns None if no API key is provided or if invalid.
        Use require_api_key() for endpoints that mandate API key auth.
    """
    if not api_key:
        return None

    # Validate key
    key_data = await APIKeyManager.validate_key(api_key, db)

    if not key_data:
        logger.warning(f"Invalid API key attempt: {api_key[:15]}...")
        return None

    logger.info(f"API key authenticated: {key_data['key_name']} (user: {key_data['user'].username})")
    return key_data


async def require_api_key(
    api_key: Optional[str] = Depends(api_key_header),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Require valid API key authentication

    Args:
        api_key: API key from X-API-Key header
        db: Database session

    Returns:
        Dictionary with user and key metadata

    Raises:
        HTTPException: If API key is missing or invalid
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    # Validate key
    key_data = await APIKeyManager.validate_key(api_key, db)

    if not key_data:
        logger.warning(f"Invalid API key attempt: {api_key[:15]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    logger.info(f"API key authenticated: {key_data['key_name']} (user: {key_data['user'].username})")
    return key_data


async def get_current_user_hybrid(
    api_key_data: Optional[Dict[str, Any]] = Depends(get_api_key_user),
) -> Optional[User]:
    """
    Get current user from either JWT or API key

    This dependency allows endpoints to accept both authentication methods.
    It first checks for API key, then falls back to JWT if no API key.

    Args:
        api_key_data: API key validation result (None if no key)

    Returns:
        User object if authenticated, None otherwise

    Note:
        This is a flexible auth dependency. For stricter auth, use
        require_api_key() or the JWT-based get_current_user().
    """
    # Check API key first
    if api_key_data:
        return api_key_data['user']

    # If no API key, return None (caller should check for JWT separately)
    return None


class APIKeyRateLimiter:
    """
    Rate limiter specifically for API keys

    Enforces per-key rate limits defined in the API key metadata
    """

    def __init__(self):
        # Structure: {key_id: [(timestamp, count)]}
        from collections import defaultdict
        self.requests: Dict[str, list] = defaultdict(list)
        self.window_size = 3600  # 1 hour window (matching rate_limit field)

    def is_allowed(self, key_id: str, rate_limit: int) -> tuple[bool, int, int]:
        """
        Check if request is allowed under API key's rate limit

        Args:
            key_id: API key ID
            rate_limit: Maximum requests per hour for this key

        Returns:
            Tuple of (is_allowed, current_count, time_until_reset)
        """
        import time

        current_time = time.time()
        window_start = current_time - self.window_size

        # Get requests in current window
        key_requests = self.requests[key_id]
        requests_in_window = [
            (ts, count) for ts, count in key_requests
            if ts > window_start
        ]

        # Calculate total requests
        total_requests = sum(count for _, count in requests_in_window)

        # Update request log
        self.requests[key_id] = requests_in_window + [(current_time, 1)]

        # Calculate time until reset
        if requests_in_window:
            oldest_request = min(ts for ts, _ in requests_in_window)
            time_until_reset = int(self.window_size - (current_time - oldest_request))
        else:
            time_until_reset = int(self.window_size)

        is_allowed = total_requests < rate_limit
        return is_allowed, total_requests + 1, time_until_reset


# Global rate limiter for API keys
api_key_rate_limiter = APIKeyRateLimiter()


async def check_api_key_rate_limit(
    request: Request,
    key_data: Dict[str, Any] = Depends(require_api_key)
) -> Dict[str, Any]:
    """
    Enforce rate limit for API key requests

    Args:
        request: FastAPI request object
        key_data: Validated API key data

    Returns:
        API key data if allowed

    Raises:
        HTTPException: If rate limit is exceeded
    """
    key_id = str(key_data['key_id'])
    rate_limit = key_data['rate_limit']

    # Check rate limit
    is_allowed, current_count, time_until_reset = api_key_rate_limiter.is_allowed(
        key_id, rate_limit
    )

    # Add rate limit headers to response
    request.state.rate_limit_headers = {
        "X-RateLimit-Limit": str(rate_limit),
        "X-RateLimit-Remaining": str(max(0, rate_limit - current_count)),
        "X-RateLimit-Reset": str(time_until_reset),
    }

    if not is_allowed:
        logger.warning(
            f"API key rate limit exceeded: {key_data['key_name']} "
            f"({current_count}/{rate_limit})"
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={
                "X-RateLimit-Limit": str(rate_limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(time_until_reset),
                "Retry-After": str(time_until_reset)
            },
            detail={
                "error": "Rate limit exceeded",
                "message": f"API key rate limit exceeded. Try again in {time_until_reset} seconds",
                "retry_after": time_until_reset
            }
        )

    return key_data
