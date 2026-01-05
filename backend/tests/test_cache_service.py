"""
Tests for Cache Service - PERF-03
Tests caching layer functionality, decorator behavior, and cache warming
"""
import pytest
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from server.services.cache_service import CacheService, cache, cache_service
from server.services.cache_warmers import (
    get_cache_warmers,
    warm_deployment_list_cache,
    warm_node_status_cache,
    warm_user_preferences_cache,
)


class TestCacheService:
    """Unit tests for CacheService"""

    @pytest.fixture
    def service(self):
        """Fresh CacheService instance for each test"""
        return CacheService()

    def test_generate_key_basic(self, service):
        """Test basic cache key generation"""
        key = service.generate_key("deployments", "list")
        assert key.startswith("cache:deployments:list:")
        assert len(key) > len("cache:deployments:list:")

    def test_generate_key_with_args(self, service):
        """Test key generation with positional arguments"""
        key1 = service.generate_key("deployments", "get", "123")
        key2 = service.generate_key("deployments", "get", "123")
        key3 = service.generate_key("deployments", "get", "456")

        # Same args should produce same key
        assert key1 == key2
        # Different args should produce different keys
        assert key1 != key3

    def test_generate_key_with_kwargs(self, service):
        """Test key generation with keyword arguments"""
        key1 = service.generate_key("deployments", "list", user_id="123", status="active")
        key2 = service.generate_key("deployments", "list", status="active", user_id="123")
        key3 = service.generate_key("deployments", "list", user_id="456", status="active")

        # Order of kwargs should not matter (sorted)
        assert key1 == key2
        # Different values should produce different keys
        assert key1 != key3

    def test_generate_key_deterministic(self, service):
        """Test that key generation is deterministic"""
        keys = [
            service.generate_key("ns", "base", "arg1", key="value")
            for _ in range(100)
        ]
        assert len(set(keys)) == 1  # All keys should be identical


class TestCacheServiceOperations:
    """Integration tests for cache operations (requires mocked Redis)"""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis service"""
        mock = AsyncMock()
        mock._connected = True
        mock.get = AsyncMock(return_value=None)
        mock.set = AsyncMock(return_value=True)
        mock.delete = AsyncMock(return_value=1)
        mock.cache_clear_namespace = AsyncMock(return_value=5)
        return mock

    @pytest.fixture
    def service_with_redis(self, mock_redis):
        """CacheService with mocked Redis"""
        service = CacheService()
        with patch("server.services.cache_service.redis_service", mock_redis):
            yield service, mock_redis

    @pytest.mark.asyncio
    async def test_get_cache_miss(self, service_with_redis):
        """Test cache get returns None on miss"""
        service, mock_redis = service_with_redis
        mock_redis.get = AsyncMock(return_value=None)

        with patch("server.services.cache_service.redis_service", mock_redis):
            result = await service.get("test_ns", "cache:test:key")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_cache_hit(self, service_with_redis):
        """Test cache get returns deserialized value on hit"""
        service, mock_redis = service_with_redis
        cached_data = {"status": "running", "count": 5}
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_data))

        with patch("server.services.cache_service.redis_service", mock_redis):
            result = await service.get("test_ns", "cache:test:key")

        assert result == cached_data

    @pytest.mark.asyncio
    async def test_set_cache_success(self, service_with_redis):
        """Test cache set stores serialized value"""
        service, mock_redis = service_with_redis

        with patch("server.services.cache_service.redis_service", mock_redis):
            with patch("server.services.cache_service.settings") as mock_settings:
                mock_settings.CACHE_TTL = 300
                result = await service.set("test_ns", "cache:test:key", {"data": "value"})

        assert result is True
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_cache(self, service_with_redis):
        """Test cache delete removes key"""
        service, mock_redis = service_with_redis

        with patch("server.services.cache_service.redis_service", mock_redis):
            result = await service.delete("test_ns", "cache:test:key")

        assert result == 1
        mock_redis.delete.assert_called_once_with("cache:test:key")

    @pytest.mark.asyncio
    async def test_clear_namespace(self, service_with_redis):
        """Test clearing all keys in namespace"""
        service, mock_redis = service_with_redis

        with patch("server.services.cache_service.redis_service", mock_redis):
            result = await service.clear_namespace("deployments")

        assert result == 5
        mock_redis.cache_clear_namespace.assert_called_once_with("deployments")


class TestCacheDecorator:
    """Tests for @cache decorator"""

    @pytest.mark.asyncio
    async def test_cache_decorator_miss_then_hit(self):
        """Test decorator caches function result"""
        call_count = 0

        @cache(namespace="test", key="counter")
        async def expensive_function():
            nonlocal call_count
            call_count += 1
            return {"result": call_count}

        # Mock cache service with stampede prevention pattern:
        # First decorated call: get #1 (miss) -> get #2 after lock (miss) -> function runs
        # Second decorated call: get #1 (hit) -> returns cached value
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(side_effect=[None, None, {"result": 1}])
        mock_cache.set = AsyncMock(return_value=True)
        mock_cache.generate_key = MagicMock(return_value="cache:test:counter:abc123")
        mock_cache.lock = MagicMock()
        mock_cache.lock.return_value.__aenter__ = AsyncMock()
        mock_cache.lock.return_value.__aexit__ = AsyncMock()
        mock_cache.subscribe_to_event = MagicMock()

        with patch("server.services.cache_service.cache_service", mock_cache):
            # First call - cache miss
            result1 = await expensive_function()
            # Second call - cache hit
            result2 = await expensive_function()

        assert result1 == {"result": 1}
        assert result2 == {"result": 1}
        # Function should only be called once (second call hits cache)
        assert call_count == 1


class TestCacheWarmers:
    """Tests for cache warming functions"""

    def test_get_cache_warmers_returns_list(self):
        """Test that get_cache_warmers returns a list of callables"""
        warmers = get_cache_warmers()

        assert isinstance(warmers, list)
        assert len(warmers) == 3
        for warmer in warmers:
            assert callable(warmer)

    @pytest.mark.asyncio
    async def test_warm_deployment_list_cache(self):
        """Test deployment list cache warmer runs without error"""
        # Warmers use lazy import - just run them (they only log)
        await warm_deployment_list_cache()
        # Should complete without raising

    @pytest.mark.asyncio
    async def test_warm_node_status_cache(self):
        """Test node status cache warmer runs without error"""
        await warm_node_status_cache()
        # Should complete without raising

    @pytest.mark.asyncio
    async def test_warm_user_preferences_cache(self):
        """Test user preferences cache warmer runs without error"""
        await warm_user_preferences_cache()
        # Should complete without raising

    @pytest.mark.asyncio
    async def test_warm_cache_with_all_warmers(self):
        """Test CacheService.warm_cache runs all warmers"""
        service = CacheService()

        # Mock warmers
        successful_warmer = AsyncMock()
        failing_warmer = AsyncMock(side_effect=Exception("Warmer failed"))

        warmers = [successful_warmer, successful_warmer, failing_warmer]

        result = await service.warm_cache(warmers)

        assert result["warmers_run"] == 2
        assert result["warmers_failed"] == 1
        assert result["success"] is False
        assert "duration_seconds" in result


class TestEventBasedInvalidation:
    """Tests for event-based cache invalidation"""

    def test_subscribe_to_event(self):
        """Test subscribing cache key to invalidation event"""
        service = CacheService()

        service.subscribe_to_event("deployment.create", "cache:deployments:list:abc")
        service.subscribe_to_event("deployment.create", "cache:deployments:status:def")
        service.subscribe_to_event("deployment.delete", "cache:deployments:list:abc")

        assert "deployment.create" in service._event_subscribers
        assert len(service._event_subscribers["deployment.create"]) == 2
        assert len(service._event_subscribers["deployment.delete"]) == 1

    @pytest.mark.asyncio
    async def test_publish_event_invalidates_keys(self):
        """Test publishing event invalidates subscribed keys"""
        service = CacheService()

        # Subscribe keys
        service.subscribe_to_event("deployment.create", "cache:deployments:list:abc")
        service.subscribe_to_event("deployment.create", "cache:deployments:status:def")

        # Mock Redis delete
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(return_value=1)

        with patch("server.services.cache_service.redis_service", mock_redis):
            invalidated = await service.publish_event("deployment.create")

        assert invalidated == 2
        assert mock_redis.delete.call_count == 2

    @pytest.mark.asyncio
    async def test_publish_unknown_event(self):
        """Test publishing unknown event returns 0"""
        service = CacheService()

        invalidated = await service.publish_event("unknown.event")

        assert invalidated == 0


class TestCacheMetrics:
    """Tests for cache metrics collection"""

    @pytest.mark.asyncio
    async def test_get_metrics_connected(self):
        """Test getting metrics when Redis is connected"""
        service = CacheService()

        mock_redis = AsyncMock()
        mock_redis._connected = True
        mock_redis._client = AsyncMock()
        mock_redis._client.info = AsyncMock(return_value={
            "total_commands_processed": 1000,
            "keyspace_hits": 800,
            "keyspace_misses": 200,
        })

        with patch("server.services.cache_service.redis_service", mock_redis):
            metrics = await service.get_metrics()

        assert metrics["redis_connected"] is True
        assert metrics["redis_commands_processed"] == 1000
        assert metrics["redis_keyspace_hits"] == 800
        assert metrics["redis_keyspace_misses"] == 200

    @pytest.mark.asyncio
    async def test_get_metrics_error(self):
        """Test getting metrics handles errors gracefully"""
        service = CacheService()

        mock_redis = AsyncMock()
        mock_redis._connected = False

        with patch("server.services.cache_service.redis_service", mock_redis):
            # Force an exception
            mock_redis._client = None
            metrics = await service.get_metrics()

        assert metrics["redis_connected"] is False
        assert "error" in metrics
