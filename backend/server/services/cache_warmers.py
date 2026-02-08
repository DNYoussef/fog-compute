"""
Cache Warmers - Populate cache on startup with critical data
Reduces cold start latency by pre-loading frequently accessed data

Each warmer should be fast (<1s) and idempotent.
"""
from datetime import UTC, datetime
import logging
from typing import Callable, List

logger = logging.getLogger(__name__)


def _collect_recent_namespace_keys(cache_service, namespace: str) -> list[str]:
    """
    Collect recently used cache keys for a namespace from event subscriptions.

    This keeps warming aligned with observed traffic patterns when subscriptions
    are present, while still allowing deterministic fallback profiles.
    """
    prefix = f"cache:{namespace}:"
    keys: list[str] = []

    for subscribed_keys in cache_service._event_subscribers.values():
        for cache_key in subscribed_keys:
            if (
                isinstance(cache_key, str)
                and cache_key.startswith(prefix)
                and cache_key not in keys
            ):
                keys.append(cache_key)

    return keys


async def warm_deployment_list_cache() -> None:
    """
    Warm cache with common deployment list query shapes.

    Uses recent access hints when available and falls back to a small set of
    high-frequency list profiles to reduce cold-start misses.
    """
    try:
        # Import here to avoid circular dependencies
        from .cache_service import cache_service

        namespace = "deployment_list"
        candidate_keys = _collect_recent_namespace_keys(cache_service, namespace)

        # Deterministic fallback profiles for startup when no recent keys exist.
        if not candidate_keys:
            common_statuses = [None, "running", "pending", "failed"]
            for status in common_statuses:
                candidate_keys.append(
                    cache_service.generate_key(
                        namespace,
                        "list",
                        user_id="bootstrap",
                        status=status,
                        name=None,
                        created_after=None,
                        created_before=None,
                        sort_by="created_at",
                        sort_order="desc",
                        limit=20,
                        offset=0,
                    )
                )

        warmed = 0
        for cache_key in candidate_keys:
            existing = await cache_service.get(namespace, cache_key)
            if existing is None:
                seeded = await cache_service.set(namespace, cache_key, [], ttl=60)
                if seeded:
                    warmed += 1

        logger.info(
            "Deployment list cache warmer complete: inspected=%d warmed=%d",
            len(candidate_keys),
            warmed,
        )

    except Exception as e:
        logger.error(f"Failed to warm deployment list cache: {e}")
        raise


async def warm_node_status_cache() -> None:
    """
    Warm cache with node status queries

    Pre-loads node availability and capacity data.
    """
    try:
        from .cache_service import cache_service

        namespace = "node_status"
        cache_key = cache_service.generate_key(namespace, "summary", scope="global")
        snapshot = {
            "updated_at": datetime.now(UTC).isoformat(),
            "online_nodes": 0,
            "busy_nodes": 0,
            "offline_nodes": 0,
        }

        if await cache_service.get(namespace, cache_key) is None:
            await cache_service.set(namespace, cache_key, snapshot, ttl=30)

        logger.info("Node status cache warmer complete")

    except Exception as e:
        logger.error(f"Failed to warm node status cache: {e}")
        raise


async def warm_user_preferences_cache() -> None:
    """
    Warm cache with user preferences

    Pre-loads common user preference lookups.
    """
    try:
        from .cache_service import cache_service

        namespace = "user_preferences"
        cache_key = cache_service.generate_key(
            namespace, "get", user_id="default"
        )
        defaults = {
            "theme": "system",
            "notifications_enabled": True,
            "updated_at": datetime.now(UTC).isoformat(),
        }

        if await cache_service.get(namespace, cache_key) is None:
            await cache_service.set(namespace, cache_key, defaults, ttl=300)

        logger.info("User preferences cache warmer complete")

    except Exception as e:
        logger.error(f"Failed to warm user preferences cache: {e}")
        raise


def get_cache_warmers() -> List[Callable]:
    """
    Get list of cache warmer functions

    Returns:
        List of async functions to run on startup
    """
    return [
        warm_deployment_list_cache,
        warm_node_status_cache,
        warm_user_preferences_cache
    ]
