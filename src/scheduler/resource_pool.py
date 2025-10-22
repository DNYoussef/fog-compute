"""
Resource Pool Manager - Object pooling for expensive resources

Features:
- Connection pooling (database, Redis)
- Worker thread pooling
- Memory buffer pooling
- Resource lifecycle tracking
- Automatic cleanup and reuse (>90% target)
"""

import asyncio
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar
from contextlib import asynccontextmanager, contextmanager

logger = logging.getLogger(__name__)

T = TypeVar('T')


class PoolType(Enum):
    """Types of resource pools"""
    CONNECTION = "connection"
    WORKER = "worker"
    MEMORY = "memory"
    GENERIC = "generic"


class ResourceState(Enum):
    """Resource lifecycle states"""
    CREATED = "created"
    IN_USE = "in_use"
    IDLE = "idle"
    DESTROYED = "destroyed"


@dataclass
class ResourceMetrics:
    """Metrics for a pooled resource"""
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime = field(default_factory=datetime.now)
    use_count: int = 0
    total_time_in_use: float = 0.0
    errors: int = 0
    state: ResourceState = ResourceState.CREATED


@dataclass
class PooledResource(Generic[T]):
    """Wrapper for a pooled resource with tracking"""
    resource: T
    resource_id: str
    pool_type: PoolType
    metrics: ResourceMetrics = field(default_factory=ResourceMetrics)
    _checkout_time: Optional[float] = None

    def checkout(self) -> None:
        """Mark resource as checked out"""
        self.metrics.state = ResourceState.IN_USE
        self.metrics.use_count += 1
        self.metrics.last_used = datetime.now()
        self._checkout_time = time.time()

    def checkin(self) -> None:
        """Mark resource as returned to pool"""
        if self._checkout_time:
            duration = time.time() - self._checkout_time
            self.metrics.total_time_in_use += duration
            self._checkout_time = None
        self.metrics.state = ResourceState.IDLE

    def record_error(self) -> None:
        """Record an error with this resource"""
        self.metrics.errors += 1


class ResourcePool(Generic[T]):
    """Generic resource pool with lifecycle management"""

    def __init__(
        self,
        pool_type: PoolType,
        factory: Callable[[], T],
        destructor: Optional[Callable[[T], None]] = None,
        min_size: int = 2,
        max_size: int = 10,
        max_idle_time: int = 300,  # 5 minutes
        validation_fn: Optional[Callable[[T], bool]] = None,
    ):
        self.pool_type = pool_type
        self.factory = factory
        self.destructor = destructor
        self.min_size = min_size
        self.max_size = max_size
        self.max_idle_time = max_idle_time
        self.validation_fn = validation_fn

        self._available: deque[PooledResource[T]] = deque()
        self._in_use: Dict[str, PooledResource[T]] = {}
        self._lock = threading.RLock()
        self._next_id = 0
        self._total_created = 0
        self._total_reused = 0
        self._cleanup_task: Optional[asyncio.Task] = None

        # Pre-create minimum resources
        self._initialize_pool()

    def _initialize_pool(self) -> None:
        """Create minimum number of resources"""
        with self._lock:
            for _ in range(self.min_size):
                resource = self._create_resource()
                if resource:
                    self._available.append(resource)

    def _create_resource(self) -> Optional[PooledResource[T]]:
        """Create a new pooled resource"""
        try:
            with self._lock:
                if len(self._available) + len(self._in_use) >= self.max_size:
                    return None

                self._next_id += 1
                resource_id = f"{self.pool_type.value}_{self._next_id}"

                raw_resource = self.factory()
                pooled = PooledResource(
                    resource=raw_resource,
                    resource_id=resource_id,
                    pool_type=self.pool_type,
                )
                pooled.metrics.state = ResourceState.IDLE

                self._total_created += 1
                logger.debug(f"Created resource {resource_id}")
                return pooled

        except Exception as e:
            logger.error(f"Failed to create resource: {e}")
            return None

    def _validate_resource(self, pooled: PooledResource[T]) -> bool:
        """Validate a resource is still usable"""
        if self.validation_fn:
            try:
                return self.validation_fn(pooled.resource)
            except Exception as e:
                logger.warning(f"Resource validation failed: {e}")
                return False
        return True

    def acquire(self, timeout: float = 5.0) -> Optional[PooledResource[T]]:
        """Acquire a resource from the pool"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            with self._lock:
                # Try to get from available pool
                while self._available:
                    pooled = self._available.popleft()

                    # Validate resource
                    if not self._validate_resource(pooled):
                        self._destroy_resource(pooled)
                        continue

                    # Check if idle too long
                    idle_time = (datetime.now() - pooled.metrics.last_used).total_seconds()
                    if idle_time > self.max_idle_time:
                        self._destroy_resource(pooled)
                        continue

                    # Resource is good, check it out
                    pooled.checkout()
                    self._in_use[pooled.resource_id] = pooled
                    self._total_reused += 1
                    logger.debug(f"Acquired resource {pooled.resource_id} (reuse)")
                    return pooled

                # No available resources, try to create new one
                new_resource = self._create_resource()
                if new_resource:
                    new_resource.checkout()
                    self._in_use[new_resource.resource_id] = new_resource
                    logger.debug(f"Acquired resource {new_resource.resource_id} (new)")
                    return new_resource

            # Pool is full, wait a bit
            time.sleep(0.01)

        logger.warning(f"Failed to acquire resource within {timeout}s timeout")
        return None

    def release(self, pooled: PooledResource[T]) -> None:
        """Release a resource back to the pool"""
        with self._lock:
            if pooled.resource_id not in self._in_use:
                logger.warning(f"Attempted to release unknown resource {pooled.resource_id}")
                return

            pooled.checkin()
            del self._in_use[pooled.resource_id]

            # If too many idle resources, destroy this one
            if len(self._available) >= self.min_size:
                self._destroy_resource(pooled)
            else:
                self._available.append(pooled)

            logger.debug(f"Released resource {pooled.resource_id}")

    def _destroy_resource(self, pooled: PooledResource[T]) -> None:
        """Destroy a resource"""
        try:
            if self.destructor:
                self.destructor(pooled.resource)
            pooled.metrics.state = ResourceState.DESTROYED
            logger.debug(f"Destroyed resource {pooled.resource_id}")
        except Exception as e:
            logger.error(f"Error destroying resource {pooled.resource_id}: {e}")

    async def cleanup_idle_resources(self) -> None:
        """Periodic cleanup of idle resources"""
        while True:
            await asyncio.sleep(60)  # Run every minute

            with self._lock:
                now = datetime.now()
                to_remove = []

                for pooled in self._available:
                    idle_time = (now - pooled.metrics.last_used).total_seconds()
                    if idle_time > self.max_idle_time:
                        to_remove.append(pooled)

                for pooled in to_remove:
                    try:
                        self._available.remove(pooled)
                        self._destroy_resource(pooled)
                    except ValueError:
                        pass  # Already removed

                if to_remove:
                    logger.info(f"Cleaned up {len(to_remove)} idle resources")

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics"""
        with self._lock:
            total_resources = len(self._available) + len(self._in_use)
            reuse_rate = (
                (self._total_reused / (self._total_created + self._total_reused) * 100)
                if (self._total_created + self._total_reused) > 0
                else 0.0
            )

            return {
                "pool_type": self.pool_type.value,
                "total_resources": total_resources,
                "available": len(self._available),
                "in_use": len(self._in_use),
                "total_created": self._total_created,
                "total_reused": self._total_reused,
                "reuse_rate_percent": round(reuse_rate, 2),
                "min_size": self.min_size,
                "max_size": self.max_size,
            }

    def shutdown(self) -> None:
        """Shutdown the pool and destroy all resources"""
        with self._lock:
            # Destroy all available resources
            while self._available:
                pooled = self._available.popleft()
                self._destroy_resource(pooled)

            # Warn about in-use resources
            if self._in_use:
                logger.warning(f"Shutting down pool with {len(self._in_use)} resources still in use")

            logger.info(f"Pool shutdown complete. Stats: {self.get_stats()}")


class ResourcePoolManager:
    """Centralized manager for all resource pools"""

    def __init__(self):
        self._pools: Dict[str, ResourcePool] = {}
        self._lock = threading.RLock()
        logger.info("ResourcePoolManager initialized")

    def create_pool(
        self,
        name: str,
        pool_type: PoolType,
        factory: Callable[[], T],
        destructor: Optional[Callable[[T], None]] = None,
        min_size: int = 2,
        max_size: int = 10,
        max_idle_time: int = 300,
        validation_fn: Optional[Callable[[T], bool]] = None,
    ) -> ResourcePool[T]:
        """Create a new resource pool"""
        with self._lock:
            if name in self._pools:
                raise ValueError(f"Pool '{name}' already exists")

            pool = ResourcePool(
                pool_type=pool_type,
                factory=factory,
                destructor=destructor,
                min_size=min_size,
                max_size=max_size,
                max_idle_time=max_idle_time,
                validation_fn=validation_fn,
            )

            self._pools[name] = pool
            logger.info(f"Created pool '{name}' of type {pool_type.value}")
            return pool

    def get_pool(self, name: str) -> Optional[ResourcePool]:
        """Get a pool by name"""
        return self._pools.get(name)

    @contextmanager
    def acquire(self, pool_name: str, timeout: float = 5.0):
        """Context manager to acquire and release a resource"""
        pool = self.get_pool(pool_name)
        if not pool:
            raise ValueError(f"Pool '{pool_name}' not found")

        pooled = pool.acquire(timeout=timeout)
        if not pooled:
            raise TimeoutError(f"Failed to acquire resource from pool '{pool_name}'")

        try:
            yield pooled.resource
        except Exception as e:
            pooled.record_error()
            raise
        finally:
            pool.release(pooled)

    @asynccontextmanager
    async def acquire_async(self, pool_name: str, timeout: float = 5.0):
        """Async context manager to acquire and release a resource"""
        pool = self.get_pool(pool_name)
        if not pool:
            raise ValueError(f"Pool '{pool_name}' not found")

        # Run acquire in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        pooled = await loop.run_in_executor(None, pool.acquire, timeout)

        if not pooled:
            raise TimeoutError(f"Failed to acquire resource from pool '{pool_name}'")

        try:
            yield pooled.resource
        except Exception as e:
            pooled.record_error()
            raise
        finally:
            await loop.run_in_executor(None, pool.release, pooled)

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all pools"""
        with self._lock:
            return {name: pool.get_stats() for name, pool in self._pools.items()}

    def shutdown_all(self) -> None:
        """Shutdown all pools"""
        with self._lock:
            for name, pool in self._pools.items():
                logger.info(f"Shutting down pool '{name}'")
                pool.shutdown()

            self._pools.clear()
            logger.info("All pools shut down")


# Singleton instance
_manager = ResourcePoolManager()


def get_resource_pool_manager() -> ResourcePoolManager:
    """Get the singleton ResourcePoolManager instance"""
    return _manager
