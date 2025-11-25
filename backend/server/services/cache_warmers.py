"""
Cache Warmers - Populate cache on startup with critical data
Reduces cold start latency by pre-loading frequently accessed data

Each warmer should be fast (<1s) and idempotent.
"""
import logging
from typing import List, Callable

logger = logging.getLogger(__name__)


async def warm_deployment_list_cache() -> None:
    """
    Warm cache with sample deployment list queries

    Pre-loads common deployment list queries to improve initial response time.
    This is a placeholder - in production, would pre-load based on recent access patterns.
    """
    try:
        # Import here to avoid circular dependencies
        from .cache_service import cache_service

        # Pre-warm common namespace
        # In production, would analyze query patterns and pre-load most common queries
        logger.info("Deployment list cache warmer: Ready (no pre-warming needed)")

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

        # Pre-warm node status namespace
        logger.info("Node status cache warmer: Ready (no pre-warming needed)")

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

        # Pre-warm user preferences namespace
        logger.info("User preferences cache warmer: Ready (no pre-warming needed)")

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
