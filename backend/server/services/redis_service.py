"""
Redis Service - Async Redis client wrapper
Provides connection pooling, health checks, and lifecycle management for caching and token blacklist
"""
import asyncio
import logging
from typing import Optional, Any, Union
from contextlib import asynccontextmanager
from datetime import timedelta

import redis.asyncio as aioredis
from redis.asyncio import Redis, ConnectionPool
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError

from ..config import settings

logger = logging.getLogger(__name__)


class RedisService:
    """
    Async Redis client wrapper with connection pooling and health checks

    Features:
    - Connection pool management (10 connections default)
    - Automatic reconnection on failure
    - Health check integration
    - Graceful shutdown
    - Type-safe operations

    Usage:
        redis_service = RedisService()
        await redis_service.connect()

        # Set/Get operations
        await redis_service.set("key", "value", expire=60)
        value = await redis_service.get("key")

        # Cleanup
        await redis_service.disconnect()
    """

    def __init__(self):
        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[Redis] = None
        self._connected: bool = False
        self._health_check_task: Optional[asyncio.Task] = None

    async def connect(self) -> None:
        """
        Initialize Redis connection pool

        Creates connection pool with configuration from settings.
        Validates connection with PING command.

        Raises:
            RedisConnectionError: If connection fails
        """
        if self._connected:
            logger.warning("Redis already connected")
            return

        try:
            # Parse Redis URL and create connection pool
            self._pool = ConnectionPool.from_url(
                settings.REDIS_URL,
                max_connections=settings.REDIS_POOL_SIZE,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
                health_check_interval=30
            )

            self._client = Redis(connection_pool=self._pool)

            # Validate connection
            await self._client.ping()
            self._connected = True

            logger.info(
                f"Redis connected successfully - "
                f"Pool size: {settings.REDIS_POOL_SIZE}, "
                f"URL: {settings.REDIS_URL.split('@')[-1]}"  # Hide password
            )

        except RedisConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error connecting to Redis: {e}")
            raise

    async def disconnect(self) -> None:
        """
        Close Redis connections gracefully

        Closes all connections in pool and cleans up resources.
        Safe to call multiple times.
        """
        if not self._connected:
            return

        try:
            if self._health_check_task:
                self._health_check_task.cancel()
                try:
                    await self._health_check_task
                except asyncio.CancelledError:
                    pass

            if self._client:
                await self._client.close()

            if self._pool:
                await self._pool.disconnect()

            self._connected = False
            logger.info("Redis disconnected successfully")

        except Exception as e:
            logger.error(f"Error during Redis disconnect: {e}")

    async def health_check(self) -> dict[str, Any]:
        """
        Check Redis connection health

        Returns:
            dict: Health check result with status, latency, and connection info

        Example:
            {
                "healthy": True,
                "latency_ms": 1.23,
                "connected": True,
                "pool_size": 10
            }
        """
        if not self._connected or not self._client:
            return {
                "healthy": False,
                "connected": False,
                "error": "Redis not connected"
            }

        try:
            import time
            start = time.perf_counter()
            await self._client.ping()
            latency = (time.perf_counter() - start) * 1000

            return {
                "healthy": True,
                "latency_ms": round(latency, 2),
                "connected": True,
                "pool_size": settings.REDIS_POOL_SIZE
            }

        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                "healthy": False,
                "connected": False,
                "error": str(e)
            }

    # Cache Operations

    async def get(self, key: str) -> Optional[str]:
        """
        Get value from Redis

        Args:
            key: Redis key

        Returns:
            Value as string or None if key doesn't exist
        """
        if not self._client:
            raise RedisError("Redis not connected")

        try:
            return await self._client.get(key)
        except RedisError as e:
            logger.error(f"Redis GET failed for key {key}: {e}")
            raise

    async def set(
        self,
        key: str,
        value: str,
        expire: Optional[int] = None
    ) -> bool:
        """
        Set value in Redis with optional expiration

        Args:
            key: Redis key
            value: Value to store
            expire: Expiration time in seconds (optional)

        Returns:
            True if successful
        """
        if not self._client:
            raise RedisError("Redis not connected")

        try:
            if expire:
                return await self._client.setex(key, expire, value)
            else:
                return await self._client.set(key, value)
        except RedisError as e:
            logger.error(f"Redis SET failed for key {key}: {e}")
            raise

    async def delete(self, key: str) -> int:
        """
        Delete key from Redis

        Args:
            key: Redis key to delete

        Returns:
            Number of keys deleted (0 or 1)
        """
        if not self._client:
            raise RedisError("Redis not connected")

        try:
            return await self._client.delete(key)
        except RedisError as e:
            logger.error(f"Redis DELETE failed for key {key}: {e}")
            raise

    async def exists(self, key: str) -> bool:
        """
        Check if key exists in Redis

        Args:
            key: Redis key

        Returns:
            True if key exists
        """
        if not self._client:
            raise RedisError("Redis not connected")

        try:
            return await self._client.exists(key) > 0
        except RedisError as e:
            logger.error(f"Redis EXISTS failed for key {key}: {e}")
            raise

    async def expire(self, key: str, seconds: int) -> bool:
        """
        Set expiration time on key

        Args:
            key: Redis key
            seconds: Expiration time in seconds

        Returns:
            True if timeout was set
        """
        if not self._client:
            raise RedisError("Redis not connected")

        try:
            return await self._client.expire(key, seconds)
        except RedisError as e:
            logger.error(f"Redis EXPIRE failed for key {key}: {e}")
            raise

    async def ttl(self, key: str) -> int:
        """
        Get time to live for key

        Args:
            key: Redis key

        Returns:
            TTL in seconds, -1 if no expiration, -2 if key doesn't exist
        """
        if not self._client:
            raise RedisError("Redis not connected")

        try:
            return await self._client.ttl(key)
        except RedisError as e:
            logger.error(f"Redis TTL failed for key {key}: {e}")
            raise

    # Token Blacklist Operations (for SEC-03)

    async def blacklist_token(self, token_jti: str, expire_seconds: int) -> bool:
        """
        Add JWT token to blacklist

        Args:
            token_jti: JWT token ID (jti claim)
            expire_seconds: Token expiration time (should match JWT exp)

        Returns:
            True if successful
        """
        key = f"blacklist:token:{token_jti}"
        return await self.set(key, "1", expire=expire_seconds)

    async def is_token_blacklisted(self, token_jti: str) -> bool:
        """
        Check if JWT token is blacklisted

        Args:
            token_jti: JWT token ID (jti claim)

        Returns:
            True if token is blacklisted
        """
        key = f"blacklist:token:{token_jti}"
        return await self.exists(key)

    # Cache Helper Methods (for PERF-02)

    async def cache_get(self, namespace: str, cache_key: str) -> Optional[str]:
        """
        Get cached value with namespace prefix

        Args:
            namespace: Cache namespace (e.g., 'api', 'dashboard')
            cache_key: Cache key

        Returns:
            Cached value or None
        """
        key = f"cache:{namespace}:{cache_key}"
        return await self.get(key)

    async def cache_set(
        self,
        namespace: str,
        cache_key: str,
        value: str,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set cached value with namespace prefix

        Args:
            namespace: Cache namespace
            cache_key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (uses settings.CACHE_TTL if not provided)

        Returns:
            True if successful
        """
        key = f"cache:{namespace}:{cache_key}"
        expire_time = ttl or settings.CACHE_TTL
        return await self.set(key, value, expire=expire_time)

    async def cache_delete(self, namespace: str, cache_key: str) -> int:
        """
        Delete cached value

        Args:
            namespace: Cache namespace
            cache_key: Cache key

        Returns:
            Number of keys deleted
        """
        key = f"cache:{namespace}:{cache_key}"
        return await self.delete(key)

    async def cache_clear_namespace(self, namespace: str) -> int:
        """
        Clear all cache entries in namespace

        Args:
            namespace: Cache namespace to clear

        Returns:
            Number of keys deleted
        """
        if not self._client:
            raise RedisError("Redis not connected")

        try:
            pattern = f"cache:{namespace}:*"
            keys = []
            async for key in self._client.scan_iter(match=pattern, count=100):
                keys.append(key)

            if keys:
                return await self._client.delete(*keys)
            return 0

        except RedisError as e:
            logger.error(f"Redis cache clear failed for namespace {namespace}: {e}")
            raise


# Global Redis service instance
redis_service = RedisService()


@asynccontextmanager
async def get_redis():
    """
    Dependency injection for Redis service

    Usage in FastAPI:
        @app.get("/health/redis")
        async def redis_health():
            async with get_redis() as redis:
                return await redis.health_check()
    """
    if not redis_service._connected:
        await redis_service.connect()
    yield redis_service
