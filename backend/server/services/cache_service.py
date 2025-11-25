"""
Cache Service - Application-level caching layer with Redis backend
Provides decorator-based caching, invalidation strategies, and metrics

Features:
- Cache decorator for easy function caching (@cache)
- TTL-based and event-based invalidation
- Cache stampede prevention with distributed locks
- Prometheus metrics for hit/miss rates
- Cache warming on startup
- Consistent key generation with namespace support
"""
import asyncio
import hashlib
import json
import logging
import time
from typing import Any, Callable, Optional, Union, List, Dict
from functools import wraps
from contextlib import asynccontextmanager
from datetime import datetime

from redis.exceptions import RedisError, LockError
from prometheus_client import Counter, Histogram, Gauge

from .redis_service import redis_service
from ..config import settings

logger = logging.getLogger(__name__)


# ============================================================================
# Prometheus Metrics
# ============================================================================

cache_hits = Counter(
    'cache_hits_total',
    'Total number of cache hits',
    ['namespace', 'key']
)

cache_misses = Counter(
    'cache_misses_total',
    'Total number of cache misses',
    ['namespace', 'key']
)

cache_errors = Counter(
    'cache_errors_total',
    'Total number of cache errors',
    ['namespace', 'operation']
)

cache_latency = Histogram(
    'cache_operation_latency_seconds',
    'Cache operation latency in seconds',
    ['namespace', 'operation']
)

cache_size = Gauge(
    'cache_entries_total',
    'Total number of cached entries',
    ['namespace']
)

cache_invalidations = Counter(
    'cache_invalidations_total',
    'Total number of cache invalidations',
    ['namespace', 'reason']
)


# ============================================================================
# Cache Service
# ============================================================================

class CacheService:
    """
    Application-level caching service with Redis backend

    Provides:
    - Decorator-based caching
    - Automatic key generation
    - TTL and event-based invalidation
    - Cache stampede prevention
    - Metrics collection
    """

    def __init__(self):
        self._event_subscribers: Dict[str, List[str]] = {}  # event -> [cache_keys]
        self._lock_timeout = 10  # seconds for distributed lock

    async def initialize(self) -> None:
        """Initialize cache service (called during app startup)"""
        try:
            # Ensure Redis is connected
            if not redis_service._connected:
                await redis_service.connect()

            logger.info("Cache service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize cache service: {e}")
            raise

    # ========================================================================
    # Key Generation
    # ========================================================================

    def generate_key(
        self,
        namespace: str,
        base_key: str,
        *args,
        **kwargs
    ) -> str:
        """
        Generate consistent cache key with namespace prefix

        Uses MD5 hash of arguments for consistency across invocations.

        Args:
            namespace: Cache namespace (e.g., 'deployments', 'nodes')
            base_key: Base key name (e.g., 'list', 'status')
            *args: Positional arguments to include in key
            **kwargs: Keyword arguments to include in key

        Returns:
            Cache key in format: cache:{namespace}:{base_key}:{hash}

        Example:
            generate_key('deployments', 'list', user_id='123')
            -> 'cache:deployments:list:a3f8d9...'
        """
        # Create deterministic string from args/kwargs
        key_parts = [str(arg) for arg in args]
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        key_string = "|".join(key_parts)

        # Hash for consistency
        key_hash = hashlib.md5(key_string.encode()).hexdigest()[:12]

        return f"cache:{namespace}:{base_key}:{key_hash}"

    # ========================================================================
    # Cache Operations
    # ========================================================================

    async def get(
        self,
        namespace: str,
        cache_key: str
    ) -> Optional[Any]:
        """
        Get value from cache with metrics

        Args:
            namespace: Cache namespace
            cache_key: Full cache key

        Returns:
            Cached value (deserialized) or None if not found
        """
        start_time = time.time()

        try:
            raw_value = await redis_service.get(cache_key)

            if raw_value is None:
                cache_misses.labels(namespace=namespace, key=cache_key).inc()
                return None

            # Deserialize JSON
            value = json.loads(raw_value)

            cache_hits.labels(namespace=namespace, key=cache_key).inc()
            cache_latency.labels(namespace=namespace, operation='get').observe(
                time.time() - start_time
            )

            return value

        except json.JSONDecodeError as e:
            logger.error(f"Cache deserialization failed for {cache_key}: {e}")
            cache_errors.labels(namespace=namespace, operation='get').inc()
            return None
        except RedisError as e:
            logger.error(f"Cache get failed for {cache_key}: {e}")
            cache_errors.labels(namespace=namespace, operation='get').inc()
            return None

    async def set(
        self,
        namespace: str,
        cache_key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in cache with optional TTL

        Args:
            namespace: Cache namespace
            cache_key: Full cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time to live in seconds (uses settings.CACHE_TTL if not provided)

        Returns:
            True if successful
        """
        start_time = time.time()

        try:
            # Serialize to JSON
            raw_value = json.dumps(value, default=str)  # default=str handles datetime

            # Use default TTL if not specified
            ttl = ttl or settings.CACHE_TTL

            success = await redis_service.set(cache_key, raw_value, expire=ttl)

            cache_latency.labels(namespace=namespace, operation='set').observe(
                time.time() - start_time
            )

            return success

        except (TypeError, ValueError) as e:
            logger.error(f"Cache serialization failed for {cache_key}: {e}")
            cache_errors.labels(namespace=namespace, operation='set').inc()
            return False
        except RedisError as e:
            logger.error(f"Cache set failed for {cache_key}: {e}")
            cache_errors.labels(namespace=namespace, operation='set').inc()
            return False

    async def delete(self, namespace: str, cache_key: str) -> int:
        """
        Delete key from cache

        Args:
            namespace: Cache namespace
            cache_key: Full cache key

        Returns:
            Number of keys deleted (0 or 1)
        """
        try:
            deleted = await redis_service.delete(cache_key)
            cache_invalidations.labels(namespace=namespace, reason='manual').inc()
            return deleted
        except RedisError as e:
            logger.error(f"Cache delete failed for {cache_key}: {e}")
            cache_errors.labels(namespace=namespace, operation='delete').inc()
            return 0

    async def clear_namespace(self, namespace: str) -> int:
        """
        Clear all cache entries in namespace

        Args:
            namespace: Cache namespace to clear

        Returns:
            Number of keys deleted
        """
        try:
            deleted = await redis_service.cache_clear_namespace(namespace)
            cache_invalidations.labels(namespace=namespace, reason='namespace_clear').inc()
            logger.info(f"Cleared {deleted} keys from cache namespace: {namespace}")
            return deleted
        except RedisError as e:
            logger.error(f"Cache namespace clear failed for {namespace}: {e}")
            cache_errors.labels(namespace=namespace, operation='clear').inc()
            return 0

    # ========================================================================
    # Cache Stampede Prevention
    # ========================================================================

    @asynccontextmanager
    async def lock(self, lock_key: str, timeout: Optional[int] = None):
        """
        Distributed lock for cache stampede prevention

        Usage:
            async with cache_service.lock(f"lock:{key}"):
                # Only one process can execute this block
                value = await expensive_computation()
                await cache_service.set(namespace, key, value)

        Args:
            lock_key: Unique lock identifier
            timeout: Lock timeout in seconds (default: 10s)

        Yields:
            Redis lock object

        Raises:
            LockError: If lock cannot be acquired
        """
        timeout = timeout or self._lock_timeout
        lock = None

        try:
            # Acquire Redis distributed lock
            lock = redis_service._client.lock(
                f"lock:{lock_key}",
                timeout=timeout,
                blocking_timeout=timeout
            )

            acquired = await lock.acquire()

            if not acquired:
                raise LockError(f"Failed to acquire lock: {lock_key}")

            yield lock

        finally:
            if lock:
                try:
                    await lock.release()
                except LockError:
                    # Lock already released or expired
                    pass

    # ========================================================================
    # Event-Based Invalidation
    # ========================================================================

    def subscribe_to_event(self, event: str, cache_key: str) -> None:
        """
        Subscribe cache key to invalidation event

        Args:
            event: Event name (e.g., 'deployment.create')
            cache_key: Cache key to invalidate when event occurs
        """
        if event not in self._event_subscribers:
            self._event_subscribers[event] = []

        if cache_key not in self._event_subscribers[event]:
            self._event_subscribers[event].append(cache_key)

    async def publish_event(self, event: str) -> int:
        """
        Publish invalidation event

        Invalidates all cache keys subscribed to this event.

        Args:
            event: Event name (e.g., 'deployment.create')

        Returns:
            Number of keys invalidated
        """
        if event not in self._event_subscribers:
            return 0

        invalidated = 0
        for cache_key in self._event_subscribers[event]:
            try:
                await redis_service.delete(cache_key)
                invalidated += 1
            except RedisError as e:
                logger.error(f"Failed to invalidate {cache_key} for event {event}: {e}")

        if invalidated > 0:
            cache_invalidations.labels(namespace='global', reason=f'event:{event}').inc(invalidated)
            logger.info(f"Invalidated {invalidated} cache keys for event: {event}")

        return invalidated

    # ========================================================================
    # Cache Warming
    # ========================================================================

    async def warm_cache(self, warmers: List[Callable]) -> Dict[str, Any]:
        """
        Warm cache on startup with critical data

        Args:
            warmers: List of async functions that populate cache

        Returns:
            Dictionary with warming results
        """
        start_time = time.time()
        results = {
            'success': True,
            'warmers_run': 0,
            'warmers_failed': 0,
            'duration_seconds': 0
        }

        logger.info(f"Starting cache warming with {len(warmers)} warmers...")

        for warmer in warmers:
            try:
                await warmer()
                results['warmers_run'] += 1
            except Exception as e:
                logger.error(f"Cache warmer failed ({warmer.__name__}): {e}")
                results['warmers_failed'] += 1
                results['success'] = False

        results['duration_seconds'] = round(time.time() - start_time, 2)

        logger.info(
            f"Cache warming complete: "
            f"{results['warmers_run']} succeeded, "
            f"{results['warmers_failed']} failed, "
            f"{results['duration_seconds']}s elapsed"
        )

        return results

    # ========================================================================
    # Metrics
    # ========================================================================

    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get cache metrics for monitoring

        Returns:
            Dictionary with cache statistics
        """
        try:
            # Get hit/miss rates from Prometheus counters
            # Note: In production, query Prometheus API for accurate rates

            info = await redis_service._client.info('stats')

            return {
                'redis_connected': redis_service._connected,
                'redis_commands_processed': info.get('total_commands_processed', 0),
                'redis_keyspace_hits': info.get('keyspace_hits', 0),
                'redis_keyspace_misses': info.get('keyspace_misses', 0),
                'cache_latency_available': True,
                'event_subscribers': len(self._event_subscribers)
            }
        except Exception as e:
            logger.error(f"Failed to get cache metrics: {e}")
            return {
                'redis_connected': False,
                'error': str(e)
            }


# ============================================================================
# Cache Decorator
# ============================================================================

def cache(
    namespace: str,
    key: Optional[str] = None,
    ttl: Optional[int] = None,
    invalidate_on: Optional[List[str]] = None
):
    """
    Decorator for automatic function caching

    Usage:
        @cache(namespace="deployments", key="list", ttl=60, invalidate_on=["deployment.create"])
        async def list_deployments(user_id: str) -> List[Deployment]:
            # Expensive database query
            return deployments

    Args:
        namespace: Cache namespace (e.g., 'deployments', 'nodes')
        key: Base key name (default: function name)
        ttl: Time to live in seconds (default: settings.CACHE_TTL)
        invalidate_on: List of events that should invalidate this cache

    Features:
        - Automatic cache key generation from function arguments
        - Cache stampede prevention with distributed locks
        - Event-based invalidation subscription
        - Prometheus metrics
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Use function name as default key
            base_key = key or func.__name__

            # Generate cache key from arguments
            cache_key = cache_service.generate_key(
                namespace,
                base_key,
                *args,
                **kwargs
            )

            # Try to get from cache
            cached_value = await cache_service.get(namespace, cache_key)

            if cached_value is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_value

            # Cache miss - acquire lock to prevent stampede
            logger.debug(f"Cache miss: {cache_key}")

            try:
                async with cache_service.lock(cache_key):
                    # Double-check cache after acquiring lock
                    cached_value = await cache_service.get(namespace, cache_key)

                    if cached_value is not None:
                        logger.debug(f"Cache hit after lock: {cache_key}")
                        return cached_value

                    # Execute expensive function
                    result = await func(*args, **kwargs)

                    # Store in cache
                    await cache_service.set(namespace, cache_key, result, ttl=ttl)

                    # Subscribe to invalidation events
                    if invalidate_on:
                        for event in invalidate_on:
                            cache_service.subscribe_to_event(event, cache_key)

                    return result

            except LockError as e:
                # Lock timeout - execute anyway without caching
                logger.warning(f"Lock timeout for {cache_key}, executing without cache: {e}")
                return await func(*args, **kwargs)

        return wrapper
    return decorator


# ============================================================================
# Global Cache Service Instance
# ============================================================================

cache_service = CacheService()
