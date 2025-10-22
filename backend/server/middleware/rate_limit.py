"""
Rate Limiting Middleware
Prevents API abuse through request throttling
"""
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Tuple, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import time
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    In-memory rate limiter using sliding window algorithm

    Tracks request counts per identifier (IP/user) per endpoint
    """

    def __init__(self):
        # Structure: {identifier: {endpoint: [(timestamp, count)]}}
        self.requests: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
        self.window_size = 60  # 1 minute window
        self.cleanup_interval = 300  # Cleanup every 5 minutes
        self.last_cleanup = time.time()

    def _cleanup_old_entries(self):
        """Remove expired entries to prevent memory bloat"""
        current_time = time.time()
        if current_time - self.last_cleanup < self.cleanup_interval:
            return

        cutoff_time = current_time - self.window_size
        for identifier in list(self.requests.keys()):
            for endpoint in list(self.requests[identifier].keys()):
                # Remove old timestamps
                self.requests[identifier][endpoint] = [
                    (ts, count) for ts, count in self.requests[identifier][endpoint]
                    if ts > cutoff_time
                ]
                # Remove empty endpoints
                if not self.requests[identifier][endpoint]:
                    del self.requests[identifier][endpoint]

            # Remove empty identifiers
            if not self.requests[identifier]:
                del self.requests[identifier]

        self.last_cleanup = current_time
        logger.debug("Rate limiter cleanup completed")

    def is_allowed(self, identifier: str, endpoint: str, limit: int) -> Tuple[bool, int, int]:
        """
        Check if request is allowed under rate limit

        Args:
            identifier: IP address or user ID
            endpoint: API endpoint path
            limit: Maximum requests allowed in window

        Returns:
            Tuple of (is_allowed, current_count, time_until_reset)
        """
        self._cleanup_old_entries()

        current_time = time.time()
        window_start = current_time - self.window_size

        # Get requests in current window
        endpoint_requests = self.requests[identifier][endpoint]
        requests_in_window = [
            (ts, count) for ts, count in endpoint_requests
            if ts > window_start
        ]

        # Calculate total requests
        total_requests = sum(count for _, count in requests_in_window)

        # Update request log
        self.requests[identifier][endpoint] = requests_in_window + [(current_time, 1)]

        # Calculate time until reset
        if requests_in_window:
            oldest_request = min(ts for ts, _ in requests_in_window)
            time_until_reset = int(self.window_size - (current_time - oldest_request))
        else:
            time_until_reset = int(self.window_size)

        is_allowed = total_requests < limit
        return is_allowed, total_requests + 1, time_until_reset


# Global rate limiter instance
rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for request rate limiting

    Applies different rate limits based on endpoint and authentication
    """

    # Rate limits per endpoint category (requests per minute)
    LIMITS = {
        "default": 60,  # 60 req/min for general endpoints
        "auth": 10,  # 10 req/min for auth endpoints (prevent brute force)
        "write": 30,  # 30 req/min for POST/PUT/DELETE
        "read": 100,  # 100 req/min for GET requests
        "admin": 200,  # 200 req/min for admin users
    }

    # Exempt endpoints (no rate limiting)
    EXEMPT_PATHS = [
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
    ]

    async def dispatch(self, request: Request, call_next):
        """Process each request with rate limiting"""

        # Skip rate limiting for exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Get identifier (IP address or user ID)
        identifier = self._get_identifier(request)

        # Determine rate limit
        limit = self._get_limit(request)

        # Check rate limit
        is_allowed, current_count, time_until_reset = rate_limiter.is_allowed(
            identifier, request.url.path, limit
        )

        # Add rate limit headers
        headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(max(0, limit - current_count)),
            "X-RateLimit-Reset": str(time_until_reset),
        }

        if not is_allowed:
            logger.warning(
                f"Rate limit exceeded: {identifier} on {request.url.path} "
                f"({current_count}/{limit})"
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "detail": f"Too many requests. Try again in {time_until_reset} seconds",
                    "retry_after": time_until_reset
                },
                headers={**headers, "Retry-After": str(time_until_reset)}
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        for key, value in headers.items():
            response.headers[key] = value

        return response

    def _get_identifier(self, request: Request) -> str:
        """
        Get unique identifier for rate limiting

        Uses user ID if authenticated, otherwise IP address
        """
        # Check for authenticated user
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            # In production, decode token to get user ID
            # For now, use token hash as identifier
            token = auth_header[7:]
            return f"user_{hash(token) % 100000}"

        # Use client IP
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        return request.client.host if request.client else "unknown"

    def _get_limit(self, request: Request) -> int:
        """
        Determine rate limit based on endpoint and method

        Different limits for:
        - Auth endpoints (lower)
        - Write operations (moderate)
        - Read operations (higher)
        - Admin users (highest)
        """
        path = request.url.path
        method = request.method

        # Auth endpoints (login, register) - strict limits
        if path.startswith("/api/auth"):
            return self.LIMITS["auth"]

        # Write operations - moderate limits
        if method in ["POST", "PUT", "DELETE", "PATCH"]:
            return self.LIMITS["write"]

        # Read operations - higher limits
        if method == "GET":
            return self.LIMITS["read"]

        # Default limit
        return self.LIMITS["default"]


def rate_limit(limit: int = 60):
    """
    Decorator for custom rate limiting on specific endpoints

    Usage:
        @app.get("/expensive-operation")
        @rate_limit(limit=10)
        async def expensive_operation():
            ...

    Args:
        limit: Maximum requests allowed per minute
    """
    def decorator(func):
        func.__rate_limit__ = limit
        return func
    return decorator
