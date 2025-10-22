"""
Redis Caching Layer for FOG Coordinator

Provides high-performance caching with:
- LRU cache for node registry (5000 node capacity)
- TTL-based cache invalidation (300s default)
- Cache warming on startup
- Hit rate metrics tracking (target: >80%)
- Batch cache operations for efficiency
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import redis.asyncio as aioredis
from cachetools import LRUCache, TTLCache

logger = logging.getLogger(__name__)


class CacheMetrics:
    """Track cache performance metrics"""

    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.deletes = 0
        self.errors = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate percentage"""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Export metrics as dictionary"""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "deletes": self.deletes,
            "errors": self.errors,
            "hit_rate": round(self.hit_rate, 2),
            "total_requests": self.hits + self.misses,
        }

    def reset(self):
        """Reset all metrics"""
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.deletes = 0
        self.errors = 0


class FogCache:
    """
    High-performance caching layer for FOG Coordinator.

    Uses hybrid approach:
    - Redis for distributed caching
    - LRU cache for hot data (local memory)
    - TTL-based expiration
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        default_ttl: int = 300,
        lru_capacity: int = 5000,
        key_prefix: str = "fog:",
    ):
        """
        Initialize caching layer.

        Args:
            redis_url: Redis connection URL
            default_ttl: Default TTL in seconds (300s = 5min)
            lru_capacity: LRU cache capacity (5000 nodes)
            key_prefix: Redis key prefix for namespacing
        """
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self.key_prefix = key_prefix

        # Redis connection
        self.redis: Optional[aioredis.Redis] = None
        self._connected = False

        # Local LRU cache for hot data
        self.lru_cache: LRUCache = LRUCache(maxsize=lru_capacity)

        # TTL cache for time-sensitive data
        self.ttl_cache: TTLCache = TTLCache(maxsize=1000, ttl=default_ttl)

        # Metrics tracking
        self.metrics = CacheMetrics()

        logger.info(
            f"FogCache initialized: ttl={default_ttl}s, "
            f"lru_capacity={lru_capacity}, prefix={key_prefix}"
        )

    async def connect(self) -> bool:
        """Connect to Redis server"""
        try:
            self.redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=50,
            )
            # Test connection
            await self.redis.ping()
            self._connected = True
            logger.info(f"Connected to Redis: {self.redis_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._connected = False
            return False

    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis:
            await self.redis.close()
            self._connected = False
            logger.info("Disconnected from Redis")

    def _make_key(self, key: str) -> str:
        """Generate prefixed cache key"""
        return f"{self.key_prefix}{key}"

    async def get(self, key: str, use_lru: bool = True) -> Optional[Any]:
        """
        Get value from cache (checks LRU -> Redis).

        Args:
            key: Cache key
            use_lru: Check LRU cache first

        Returns:
            Cached value or None
        """
        try:
            # Check local LRU first (fastest)
            if use_lru and key in self.lru_cache:
                self.metrics.hits += 1
                return self.lru_cache[key]

            # Check Redis
            if self._connected and self.redis:
                redis_key = self._make_key(key)
                value = await self.redis.get(redis_key)

                if value is not None:
                    # Deserialize JSON
                    data = json.loads(value)
                    # Update LRU cache
                    if use_lru:
                        self.lru_cache[key] = data
                    self.metrics.hits += 1
                    return data

            self.metrics.misses += 1
            return None

        except Exception as e:
            logger.error(f"Cache get error for key '{key}': {e}")
            self.metrics.errors += 1
            self.metrics.misses += 1
            return None

    async def set(
        self, key: str, value: Any, ttl: Optional[int] = None, use_lru: bool = True
    ) -> bool:
        """
        Set value in cache (updates both LRU and Redis).

        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (None = default)
            use_lru: Also update LRU cache

        Returns:
            Success status
        """
        try:
            # Update local LRU
            if use_lru:
                self.lru_cache[key] = value

            # Update Redis
            if self._connected and self.redis:
                redis_key = self._make_key(key)
                serialized = json.dumps(value)
                ttl_value = ttl or self.default_ttl

                await self.redis.setex(redis_key, ttl_value, serialized)

            self.metrics.sets += 1
            return True

        except Exception as e:
            logger.error(f"Cache set error for key '{key}': {e}")
            self.metrics.errors += 1
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete key from cache (both LRU and Redis).

        Args:
            key: Cache key to delete

        Returns:
            Success status
        """
        try:
            # Delete from LRU
            self.lru_cache.pop(key, None)

            # Delete from Redis
            if self._connected and self.redis:
                redis_key = self._make_key(key)
                await self.redis.delete(redis_key)

            self.metrics.deletes += 1
            return True

        except Exception as e:
            logger.error(f"Cache delete error for key '{key}': {e}")
            self.metrics.errors += 1
            return False

    async def batch_get(self, keys: list[str]) -> dict[str, Any]:
        """
        Batch get multiple keys efficiently.

        Args:
            keys: List of cache keys

        Returns:
            Dictionary of key-value pairs
        """
        result = {}

        if not keys:
            return result

        try:
            # Check LRU first
            lru_hits = {k: self.lru_cache[k] for k in keys if k in self.lru_cache}
            result.update(lru_hits)

            # Get remaining from Redis
            remaining_keys = [k for k in keys if k not in lru_hits]
            if remaining_keys and self._connected and self.redis:
                redis_keys = [self._make_key(k) for k in remaining_keys]
                values = await self.redis.mget(redis_keys)

                for key, value in zip(remaining_keys, values):
                    if value is not None:
                        data = json.loads(value)
                        result[key] = data
                        # Update LRU
                        self.lru_cache[key] = data

            # Update metrics
            self.metrics.hits += len(result)
            self.metrics.misses += len(keys) - len(result)

        except Exception as e:
            logger.error(f"Batch get error: {e}")
            self.metrics.errors += 1

        return result

    async def batch_set(
        self, items: dict[str, Any], ttl: Optional[int] = None
    ) -> int:
        """
        Batch set multiple key-value pairs efficiently.

        Args:
            items: Dictionary of key-value pairs
            ttl: TTL in seconds (None = default)

        Returns:
            Number of successfully set items
        """
        if not items:
            return 0

        success_count = 0

        try:
            # Update LRU cache
            self.lru_cache.update(items)

            # Update Redis with pipeline
            if self._connected and self.redis:
                ttl_value = ttl or self.default_ttl
                pipeline = self.redis.pipeline()

                for key, value in items.items():
                    redis_key = self._make_key(key)
                    serialized = json.dumps(value)
                    pipeline.setex(redis_key, ttl_value, serialized)

                await pipeline.execute()
                success_count = len(items)

            self.metrics.sets += success_count

        except Exception as e:
            logger.error(f"Batch set error: {e}")
            self.metrics.errors += 1

        return success_count

    async def batch_delete(self, keys: list[str]) -> int:
        """
        Batch delete multiple keys efficiently.

        Args:
            keys: List of cache keys to delete

        Returns:
            Number of successfully deleted items
        """
        if not keys:
            return 0

        success_count = 0

        try:
            # Delete from LRU
            for key in keys:
                self.lru_cache.pop(key, None)

            # Delete from Redis
            if self._connected and self.redis:
                redis_keys = [self._make_key(k) for k in keys]
                deleted = await self.redis.delete(*redis_keys)
                success_count = deleted

            self.metrics.deletes += success_count

        except Exception as e:
            logger.error(f"Batch delete error: {e}")
            self.metrics.errors += 1

        return success_count

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            # Check LRU first
            if key in self.lru_cache:
                return True

            # Check Redis
            if self._connected and self.redis:
                redis_key = self._make_key(key)
                return await self.redis.exists(redis_key) > 0

            return False

        except Exception as e:
            logger.error(f"Cache exists error for key '{key}': {e}")
            return False

    async def clear(self, pattern: Optional[str] = None):
        """
        Clear cache entries.

        Args:
            pattern: Optional pattern to match keys (e.g., "node:*")
        """
        try:
            # Clear LRU
            if pattern:
                # Pattern matching for LRU
                to_delete = [k for k in self.lru_cache.keys() if pattern in k]
                for key in to_delete:
                    self.lru_cache.pop(key, None)
            else:
                self.lru_cache.clear()

            # Clear Redis
            if self._connected and self.redis:
                if pattern:
                    full_pattern = self._make_key(pattern)
                    cursor = 0
                    while True:
                        cursor, keys = await self.redis.scan(
                            cursor, match=full_pattern, count=100
                        )
                        if keys:
                            await self.redis.delete(*keys)
                        if cursor == 0:
                            break
                else:
                    # Clear all keys with prefix
                    await self.redis.flushdb()

            logger.info(f"Cache cleared (pattern={pattern or 'all'})")

        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            self.metrics.errors += 1

    async def warm_cache(self, data: dict[str, Any]) -> int:
        """
        Warm cache with initial data on startup.

        Args:
            data: Dictionary of key-value pairs to preload

        Returns:
            Number of warmed entries
        """
        logger.info(f"Warming cache with {len(data)} entries...")
        warmed = await self.batch_set(data)
        logger.info(f"Cache warmed: {warmed}/{len(data)} entries loaded")
        return warmed

    def get_metrics(self) -> dict[str, Any]:
        """Get cache performance metrics"""
        metrics = self.metrics.to_dict()
        metrics.update(
            {
                "connected": self._connected,
                "lru_size": len(self.lru_cache),
                "lru_capacity": self.lru_cache.maxsize,
                "ttl_cache_size": len(self.ttl_cache),
            }
        )
        return metrics

    def reset_metrics(self):
        """Reset cache metrics"""
        self.metrics.reset()
        logger.info("Cache metrics reset")
