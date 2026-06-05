"""
API Key Authentication Middleware
Validates X-API-Key header and enforces rate limits per key
"""
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any
import logging
import os
import sqlite3
import tempfile
import time

from ..auth.api_key import APIKeyManager
from ..database import get_db
from ..models.database import User

logger = logging.getLogger(__name__)

# Header scheme for API key
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _invalid_key_log_context(api_key: str) -> str:
    """Return non-reusable invalid-key metadata for audit logs."""
    return f"length={len(api_key)}"


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
        logger.warning("Invalid API key attempt (%s)", _invalid_key_log_context(api_key))
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
        logger.warning("Invalid API key attempt (%s)", _invalid_key_log_context(api_key))
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

    def __init__(self, storage_path: Optional[str] = None, window_size: int = 3600):
        self.window_size = window_size  # 1 hour window (matching rate_limit field)
        self.storage_path = storage_path or os.environ.get(
            "FOG_API_KEY_RATE_LIMIT_DB",
            os.path.join(tempfile.gettempdir(), "fog_compute_api_key_rate_limits.sqlite3"),
        )

    def _connect(self) -> sqlite3.Connection:
        parent_dir = os.path.dirname(os.path.abspath(self.storage_path))
        os.makedirs(parent_dir, exist_ok=True)
        conn = sqlite3.connect(self.storage_path, timeout=5.0, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS api_key_rate_limit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_id TEXT NOT NULL,
                requested_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_api_key_rate_limit_events_key_time
            ON api_key_rate_limit_events (key_id, requested_at)
            """
        )
        return conn

    def is_allowed(self, key_id: str, rate_limit: int) -> tuple[bool, int, int]:
        """
        Check if request is allowed under API key's rate limit

        Args:
            key_id: API key ID
            rate_limit: Maximum requests per hour for this key

        Returns:
            Tuple of (is_allowed, current_count, time_until_reset)
        """
        try:
            rate_limit = int(rate_limit)
        except (TypeError, ValueError):
            return False, 0, self.window_size

        if rate_limit <= 0:
            return False, 0, self.window_size

        current_time = time.time()
        window_start = current_time - self.window_size

        try:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    "DELETE FROM api_key_rate_limit_events WHERE requested_at <= ?",
                    (window_start,),
                )
                row = conn.execute(
                    """
                    SELECT COUNT(*), MIN(requested_at)
                    FROM api_key_rate_limit_events
                    WHERE key_id = ? AND requested_at > ?
                    """,
                    (key_id, window_start),
                ).fetchone()

                current_count = int(row[0] or 0)
                oldest_request = row[1]
                time_until_reset = self.window_size
                if oldest_request is not None:
                    time_until_reset = max(1, int(self.window_size - (current_time - float(oldest_request))))

                if current_count >= rate_limit:
                    conn.commit()
                    return False, current_count, time_until_reset

                conn.execute(
                    "INSERT INTO api_key_rate_limit_events (key_id, requested_at) VALUES (?, ?)",
                    (key_id, current_time),
                )
                conn.commit()
                return True, current_count + 1, time_until_reset
        except sqlite3.Error:
            logger.exception("API key rate limiter storage unavailable; failing closed")
            return False, rate_limit, self.window_size


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
