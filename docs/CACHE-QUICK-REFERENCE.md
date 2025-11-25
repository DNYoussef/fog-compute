# Cache Layer - Quick Reference

## Common Operations

### Add Caching to Endpoint

```python
from ..services.cache_service import cache_service

@router.get("/my-endpoint")
async def my_endpoint(user_id: str):
    # 1. Generate cache key
    cache_key = cache_service.generate_key(
        "my_namespace",
        "operation_name",
        user_id=user_id,
        other_param="value"
    )

    # 2. Try cache first
    cached = await cache_service.get("my_namespace", cache_key)
    if cached:
        return cached

    # 3. Expensive operation
    result = await expensive_database_query()

    # 4. Store in cache
    await cache_service.set(
        "my_namespace",
        cache_key,
        result,
        ttl=60  # seconds
    )

    # 5. Subscribe to invalidation events
    cache_service.subscribe_to_event(
        f"my_resource.create.user.{user_id}",
        cache_key
    )

    return result
```

### Invalidate Cache on Mutation

```python
@router.post("/my-resource")
async def create_resource(user_id: str):
    # Create resource
    resource = await create_in_database()

    # Invalidate affected caches
    await cache_service.publish_event(f"my_resource.create.user.{user_id}")

    return resource
```

### Check Cache Metrics

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/deployment/cache/metrics
```

### Clear Cache (Emergency)

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/deployment/cache/clear
```

## Cache Strategy Cheatsheet

| Data Type | TTL | Invalidation Strategy |
|-----------|-----|----------------------|
| Lists (paginated) | 60s | Event on create/delete |
| Single resource | 30s | Event on update |
| User preferences | 300s | Event on user update |
| Static data | 3600s | Manual clear only |

## Prometheus Queries

```promql
# Cache hit rate
sum(rate(cache_hits_total[5m])) /
(sum(rate(cache_hits_total[5m])) + sum(rate(cache_misses_total[5m])))

# P95 latency
histogram_quantile(0.95, cache_operation_latency_seconds)

# Cache size
sum by (namespace) (cache_entries_total)
```

## Troubleshooting

### Low hit rate?
1. Check TTL (too short?)
2. Check invalidation frequency (too often?)
3. Verify cache warming on startup
4. Check cache key consistency

### Stale data?
1. Add event-based invalidation
2. Reduce TTL
3. Manual cache clear

### Redis errors?
1. Check `docker-compose logs redis`
2. Verify REDIS_URL
3. Check Redis memory usage
