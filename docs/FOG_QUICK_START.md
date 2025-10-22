# FOG Layer Quick Start Guide

Quick reference for using the optimized FOG Compute Layer.

---

## Installation

```bash
# 1. Install dependencies
cd backend
pip install -r requirements.txt

# 2. Start Redis
docker run -d -p 6379:6379 --name fog-redis redis:alpine

# 3. Run database migration
alembic upgrade head
```

---

## Basic Usage

### Initialize Coordinator

```python
from src.fog.coordinator_enhanced import EnhancedFogCoordinator

coordinator = EnhancedFogCoordinator(
    node_id="coordinator-1",
    redis_url="redis://localhost:6379",
    enable_cache=True,
    enable_load_balancer=True
)

await coordinator.connect()
await coordinator.start()
```

### Register Nodes

```python
from src.fog.coordinator_interface import FogNode, NodeType

# Single node
node = FogNode(
    node_id="node-1",
    node_type=NodeType.COMPUTE_NODE,
    cpu_cores=4,
    memory_mb=8192,
    region="us-east"
)
await coordinator.register_node(node)

# Batch registration (100 nodes <500ms)
nodes = [FogNode(...) for i in range(100)]
count = await coordinator.batch_register_nodes(nodes)
```

### Route Tasks

```python
from src.fog.coordinator_interface import Task

task = Task(
    task_id="task-1",
    task_type="compute",
    cpu_required=2,
    memory_required=2048
)

node = await coordinator.route_task(task)
print(f"Task assigned to {node.node_id}")
```

### Monitor Health

```python
health = await coordinator.health_check()

print(f"Active nodes: {health['active_nodes']}")
print(f"Cache hit rate: {health['cache']['hit_rate']}%")
print(f"Load balancer: {health['load_balancer']['algorithm']}")
```

---

## Cache Operations

```python
from src.fog.caching import FogCache

cache = FogCache(redis_url="redis://localhost:6379")
await cache.connect()

# Single operations
await cache.set("node-1", {"cpu": 50, "status": "active"})
data = await cache.get("node-1")

# Batch operations
nodes = {f"node-{i}": {...} for i in range(100)}
await cache.batch_set(nodes)
results = await cache.batch_get(["node-1", "node-2"])

# Metrics
metrics = cache.get_metrics()
print(f"Hit rate: {metrics['hit_rate']}%")
```

---

## Load Balancer

```python
from src.fog.load_balancer import LoadBalancer, LoadBalancingAlgorithm

lb = LoadBalancer(
    algorithm=LoadBalancingAlgorithm.LEAST_CONNECTIONS,
    enable_circuit_breaker=True,
    enable_auto_scaling=True
)

# Select node
node = lb.select_node(nodes)

# Record request
lb.record_request_start(node.node_id)
# ... execute request ...
lb.record_request_end(node.node_id, success=True, response_time_ms=25.0)

# Check auto-scaling
recommendation = lb.check_auto_scaling(nodes)
```

---

## Run Tests

```bash
# All tests
cd backend
pytest tests/test_fog_optimization.py -v

# Specific test
pytest tests/test_fog_optimization.py::test_redis_cache_integration -v
```

---

## Run Benchmarks

```bash
python scripts/benchmark_fog_layer.py
```

**Expected Output**:
```
✅ PASS | Cache Hit Rate                    |  85.00 %
✅ PASS | Query Latency (p95)               |  22.50 ms
✅ PASS | Node Registration Throughput      |  1250 nodes/sec
✅ PASS | Load Balancer Distribution        |  35 %
```

---

## Performance Targets

| Metric | Target | Typical |
|--------|--------|---------|
| Cache Hit Rate | >80% | 85-90% |
| Query Latency (p95) | <50ms | 15-25ms |
| Node Registration | 1000/sec | 1250/sec |
| Batch Operations (100) | <500ms | 250-280ms |

---

## Troubleshooting

### Redis Connection Failed
```bash
# Check Redis is running
docker ps | grep fog-redis

# Start Redis if not running
docker start fog-redis
```

### Low Cache Hit Rate
```python
# Check cache metrics
metrics = cache.get_metrics()
print(metrics)

# Warm cache
await cache.warm_cache(nodes_data)
```

### High Query Latency
```python
# Check database indexes
# Verify compound indexes exist:
# - (status, region)
# - (node_type, status)
# - (last_heartbeat)
```

---

## Key Files

- `src/fog/caching.py` - Redis caching layer
- `src/fog/load_balancer.py` - Load balancing algorithms
- `src/fog/coordinator_enhanced.py` - Enhanced coordinator
- `backend/server/models/database.py` - Database models
- `docs/FOG_LAYER_OPTIMIZATION.md` - Full documentation

---

## More Information

See `docs/FOG_LAYER_OPTIMIZATION.md` for complete documentation.
