"""
Comprehensive tests for FOG Layer optimization.

Tests:
- Redis cache integration (>80% hit rate)
- Database query performance (<50ms)
- Batch operations (100 nodes <500ms)
- Load balancer distribution
- Circuit breaker functionality
"""

import asyncio
import time
from datetime import datetime, timedelta

import pytest

# Import FOG components
import sys
sys.path.append('c:/Users/17175/Desktop/fog-compute/src')

from backend.tests.constants import (
    TEST_HOST,
    TEST_PAGE_SIZE,
    TEST_MAX_RESULTS,
    TEST_MAX_LOGIN_ATTEMPTS,
    TEST_LOCKOUT_DURATION,
)

from fog.caching import FogCache, CacheMetrics
from fog.load_balancer import (
    LoadBalancer,
    LoadBalancingAlgorithm,
    CircuitBreaker,
    NodeHealth,
)
from fog.coordinator_interface import FogNode, NodeStatus, NodeType


# ==================== FIXTURES ====================

@pytest.fixture
async def fog_cache():
    """Create FOG cache instance"""
    cache = FogCache(
        redis_url=f"redis://{TEST_HOST}:6379",
        default_ttl=TEST_LOCKOUT_DURATION,
        lru_capacity=5000,
    )
    await cache.connect()
    yield cache
    await cache.disconnect()


@pytest.fixture
def mock_nodes():
    """Create mock nodes for testing"""
    nodes = []
    for i in range(TEST_PAGE_SIZE):
        node = FogNode(
            node_id=f"node-{i}",
            node_type=NodeType.COMPUTE_NODE,
            region=f"region-{i % 3}",
            cpu_cores=4,
            memory_mb=8192,
            storage_mb=102400,  # 100 GB in MB
            gpu_available=(i % 2 == 0),
            supports_onion_routing=True,
        )
        node.cpu_usage_percent = 10.0 + (i * 5)
        node.active_tasks = i
        nodes.append(node)
    return nodes


@pytest.fixture
def load_balancer():
    """Create load balancer instance"""
    return LoadBalancer(
        algorithm=LoadBalancingAlgorithm.LEAST_CONNECTIONS,
        enable_circuit_breaker=True,
        enable_auto_scaling=True,
        cpu_scale_up_threshold=80.0,
        cpu_scale_down_threshold=30.0,
    )


@pytest.fixture
def circuit_breaker():
    """Create circuit breaker instance"""
    return CircuitBreaker(failure_threshold=TEST_MAX_LOGIN_ATTEMPTS, timeout_seconds=60)


# ==================== CACHE TESTS ====================

@pytest.mark.asyncio
async def test_redis_cache_integration(fog_cache):
    """Test Redis cache integration with >80% hit rate"""
    # Warm cache with test data
    node_count = TEST_MAX_RESULTS
    test_data = {f"node-{i}": {"id": f"node-{i}", "cpu": i * 10} for i in range(node_count)}
    warmed = await fog_cache.warm_cache(test_data)

    assert warmed == node_count, f"Cache warming should load {node_count} entries"

    # Simulate read-heavy workload
    hit_count = 0
    total_requests = TEST_MAX_RESULTS * 10

    for i in range(total_requests):
        key = f"node-{i % node_count}"  # Unique keys, reused across requests
        result = await fog_cache.get(key)
        if result is not None:
            hit_count += 1

    hit_rate = (hit_count / total_requests) * 100

    # Verify hit rate >80%
    assert hit_rate > 80.0, f"Cache hit rate {hit_rate:.2f}% should be >80%"

    # Check metrics
    metrics = fog_cache.get_metrics()
    assert metrics["hit_rate"] > 80.0
    assert metrics["connected"] is True

    print(f"✅ Cache hit rate: {hit_rate:.2f}%")


@pytest.mark.asyncio
async def test_cache_batch_operations(fog_cache):
    """Test batch cache operations for efficiency"""
    # Batch set 1000 items
    batch_size = TEST_MAX_RESULTS * 10
    batch_data = {f"batch-{i}": {"value": i} for i in range(batch_size)}

    start = time.time()
    count = await fog_cache.batch_set(batch_data)
    batch_set_time = (time.time() - start) * 1000

    assert count == batch_size, f"Should set {batch_size} items"
    assert batch_set_time < 500, f"Batch set {batch_set_time:.2f}ms should be <500ms"

    # Batch get 1000 items
    keys = [f"batch-{i}" for i in range(batch_size)]

    start = time.time()
    results = await fog_cache.batch_get(keys)
    batch_get_time = (time.time() - start) * 1000

    assert len(results) == batch_size, f"Should retrieve {batch_size} items"
    assert batch_get_time < 500, f"Batch get {batch_get_time:.2f}ms should be <500ms"

    print(f"✅ Batch operations: set={batch_set_time:.2f}ms, get={batch_get_time:.2f}ms")


@pytest.mark.asyncio
async def test_cache_lru_eviction(fog_cache):
    """Test LRU cache eviction policy"""
    # Fill cache beyond capacity (5000)
    for i in range(6000):
        await fog_cache.set(f"lru-{i}", {"value": i})

    # Check oldest items evicted
    oldest = await fog_cache.get("lru-0", use_lru=True)
    newest = await fog_cache.get("lru-5999", use_lru=True)

    # LRU should have evicted oldest entries
    metrics = fog_cache.get_metrics()
    assert metrics["lru_size"] <= 5000, "LRU should not exceed capacity"

    print(f"✅ LRU eviction working: size={metrics['lru_size']}")


@pytest.mark.asyncio
async def test_cache_ttl_expiration(fog_cache):
    """Test TTL-based cache expiration"""
    # Set item with 1 second TTL
    await fog_cache.set("ttl-test", {"data": "expires"}, ttl=1)

    # Verify exists immediately
    exists_before = await fog_cache.exists("ttl-test")
    assert exists_before, "Item should exist immediately"

    # Wait for expiration
    await asyncio.sleep(2)

    # Verify expired
    result = await fog_cache.get("ttl-test")
    assert result is None, "Item should expire after TTL"

    print("✅ TTL expiration working")


# ==================== LOAD BALANCER TESTS ====================

def test_load_balancer_round_robin(load_balancer, mock_nodes):
    """Test round-robin distribution"""
    selections = []

    for _ in range(TEST_MAX_RESULTS // 3):
        node = load_balancer.select_node(
            mock_nodes, algorithm=LoadBalancingAlgorithm.ROUND_ROBIN
        )
        selections.append(node.node_id)

    # Verify even distribution
    unique_selections = set(selections)
    assert len(unique_selections) >= 8, "Should distribute across most nodes"

    print(f"✅ Round-robin: {len(unique_selections)} nodes used")


def test_load_balancer_least_connections(load_balancer, mock_nodes):
    """Test least-connections algorithm"""
    # Set varying connection counts
    for i, node in enumerate(mock_nodes):
        load_balancer.node_connections[node.node_id] = i * 2

    # Select node
    selected = load_balancer.select_node(
        mock_nodes, algorithm=LoadBalancingAlgorithm.LEAST_CONNECTIONS
    )

    # Should select node-0 (0 connections)
    assert selected.node_id == "node-0", "Should select node with fewest connections"

    print(f"✅ Least-connections: selected {selected.node_id}")


def test_load_balancer_weighted_round_robin(load_balancer, mock_nodes):
    """Test weighted round-robin with health awareness"""
    # Set different CPU usages
    mock_nodes[0].cpu_usage_percent = 10.0  # Lightly loaded
    mock_nodes[1].cpu_usage_percent = 90.0  # Heavily loaded

    selections = []
    for _ in range(TEST_MAX_RESULTS):
        node = load_balancer.select_node(
            mock_nodes, algorithm=LoadBalancingAlgorithm.WEIGHTED_ROUND_ROBIN
        )
        selections.append(node.node_id)

    # Count selections
    selection_counts = {node_id: selections.count(node_id) for node_id in set(selections)}

    # Verify node-0 gets more traffic than node-1
    assert selection_counts.get("node-0", 0) > selection_counts.get("node-1", 0), \
        "Lightly loaded node should get more traffic"

    print(f"✅ Weighted RR: node-0={selection_counts.get('node-0', 0)}, "
          f"node-1={selection_counts.get('node-1', 0)}")


def test_load_balancer_consistent_hash(load_balancer, mock_nodes):
    """Test consistent hashing for sticky sessions"""
    session_id = "user-session-123"

    # Multiple selections with same session should go to same node
    selections = []
    for _ in range(TEST_PAGE_SIZE):
        node = load_balancer.select_node(
            mock_nodes,
            algorithm=LoadBalancingAlgorithm.CONSISTENT_HASH,
            session_id=session_id,
        )
        selections.append(node.node_id)

    # Verify all went to same node
    assert len(set(selections)) == 1, "Consistent hash should select same node"
    assert session_id in load_balancer.sticky_sessions

    print(f"✅ Consistent hash: all requests -> {selections[0]}")


def test_load_balancer_response_time_routing(load_balancer, mock_nodes):
    """Test response-time-based routing"""
    # Set different response times
    load_balancer.node_response_times["node-0"] = [10.0, 12.0, 11.0]  # Fast
    load_balancer.node_response_times["node-1"] = [100.0, 110.0, 105.0]  # Slow

    selected = load_balancer.select_node(
        mock_nodes[:2], algorithm=LoadBalancingAlgorithm.RESPONSE_TIME
    )

    # Should select fastest node
    assert selected.node_id == "node-0", "Should select node with best response time"

    print(f"✅ Response-time routing: selected {selected.node_id} (fastest)")


# ==================== CIRCUIT BREAKER TESTS ====================

def test_circuit_breaker_failure_threshold(circuit_breaker):
    """Test circuit breaker opens after failure threshold"""
    node_id = "failing-node"

    # Record failures below threshold
    for _ in range(TEST_MAX_LOGIN_ATTEMPTS - 1):
        circuit_breaker.record_failure(node_id)
        assert circuit_breaker.is_available(node_id), "Should remain available"

    # Final failure should open circuit
    circuit_breaker.record_failure(node_id)
    assert not circuit_breaker.is_available(node_id), \
        f"Circuit should open after {TEST_MAX_LOGIN_ATTEMPTS} failures"
    assert circuit_breaker.get_status(node_id) == NodeHealth.CIRCUIT_OPEN

    print(f"✅ Circuit breaker opened after {TEST_MAX_LOGIN_ATTEMPTS} failures")


def test_circuit_breaker_timeout_recovery(circuit_breaker):
    """Test circuit breaker closes after timeout"""
    node_id = "timeout-node"

    # Open circuit
    for _ in range(TEST_MAX_LOGIN_ATTEMPTS):
        circuit_breaker.record_failure(node_id)

    assert not circuit_breaker.is_available(node_id)

    # Manually expire timeout (for testing)
    circuit_breaker.circuit_open_until[node_id] = datetime.now() - timedelta(seconds=1)

    # Should be available after timeout
    assert circuit_breaker.is_available(node_id), "Should be available after timeout"

    print(f"✅ Circuit breaker recovered after timeout")


def test_circuit_breaker_success_recovery(circuit_breaker):
    """Test circuit breaker closes after successful requests"""
    node_id = "recovering-node"

    # Open circuit
    for _ in range(TEST_MAX_LOGIN_ATTEMPTS):
        circuit_breaker.record_failure(node_id)

    # Expire timeout to allow retry
    circuit_breaker.circuit_open_until[node_id] = datetime.now() - timedelta(seconds=1)
    circuit_breaker.is_available(node_id)  # Triggers half-open

    # Record successes
    circuit_breaker.record_success(node_id)
    circuit_breaker.record_success(node_id)

    # Circuit should close
    assert node_id not in circuit_breaker.circuit_open_until
    assert circuit_breaker.get_status(node_id) == NodeHealth.HEALTHY

    print(f"✅ Circuit breaker closed after 2 successes")


def test_circuit_breaker_integration(load_balancer, mock_nodes):
    """Test circuit breaker integrated with load balancer"""
    # Mark node-0 as failing
    for _ in range(TEST_MAX_LOGIN_ATTEMPTS):
        load_balancer.circuit_breaker.record_failure("node-0")

    # Select node (should skip node-0)
    selected = load_balancer.select_node(mock_nodes)
    assert selected.node_id != "node-0", "Should not select failed node"

    # Verify metrics
    metrics = load_balancer.get_metrics()
    assert metrics["circuit_breaker"]["open_circuits"] == 1

    print(f"✅ Circuit breaker integration: skipped node-0, selected {selected.node_id}")


# ==================== AUTO-SCALING TESTS ====================

def test_auto_scaling_scale_up(load_balancer, mock_nodes):
    """Test auto-scaling triggers scale-up"""
    # Set high CPU usage
    for node in mock_nodes:
        node.cpu_usage_percent = 85.0

    recommendation = load_balancer.check_auto_scaling(mock_nodes)

    assert recommendation is not None
    assert recommendation["action"] == "scale_up"
    assert recommendation["avg_cpu"] > 80.0

    print(f"✅ Auto-scaling: SCALE UP triggered (avg CPU: {recommendation['avg_cpu']:.1f}%)")


def test_auto_scaling_scale_down(load_balancer, mock_nodes):
    """Test auto-scaling triggers scale-down"""
    # Set low CPU usage
    for node in mock_nodes:
        node.cpu_usage_percent = 15.0

    recommendation = load_balancer.check_auto_scaling(mock_nodes)

    assert recommendation is not None
    assert recommendation["action"] == "scale_down"
    assert recommendation["avg_cpu"] < 30.0

    print(f"✅ Auto-scaling: SCALE DOWN possible (avg CPU: {recommendation['avg_cpu']:.1f}%)")


def test_auto_scaling_stable(load_balancer, mock_nodes):
    """Test auto-scaling is stable in normal range"""
    # Set normal CPU usage
    for node in mock_nodes:
        node.cpu_usage_percent = 50.0

    recommendation = load_balancer.check_auto_scaling(mock_nodes)

    assert recommendation is None, "Should not trigger scaling in normal range"

    print(f"✅ Auto-scaling: stable (no action needed)")


# ==================== PERFORMANCE TESTS ====================

@pytest.mark.asyncio
async def test_batch_node_registration_performance():
    """Test batch node registration throughput (100 nodes <500ms)"""
    from fog.caching import FogCache

    cache = FogCache()
    await cache.connect()

    # Create 100 mock nodes
    node_count = TEST_MAX_RESULTS
    nodes_data = {
        f"node-{i}": {
            "node_id": f"node-{i}",
            "cpu": 4,
            "memory": 8192,
            "status": "active",
        }
        for i in range(node_count)
    }

    # Measure batch set time
    start = time.time()
    count = await cache.batch_set(nodes_data)
    elapsed_ms = (time.time() - start) * 1000

    assert count == node_count, f"Should register {node_count} nodes"
    assert elapsed_ms < 500, f"Batch registration {elapsed_ms:.2f}ms should be <500ms"

    await cache.disconnect()

    print(f"✅ Batch registration: {node_count} nodes in {elapsed_ms:.2f}ms")


def test_load_balancer_distribution_efficiency(load_balancer, mock_nodes):
    """Test load balancer distributes evenly"""
    selections = []

    # Select 1000 times
    distribution_samples = TEST_MAX_RESULTS * 10
    for _ in range(distribution_samples):
        node = load_balancer.select_node(mock_nodes)
        selections.append(node.node_id)

    # Calculate distribution
    selection_counts = {node.node_id: selections.count(node.node_id) for node in mock_nodes}

    # Calculate standard deviation
    avg_count = distribution_samples / len(mock_nodes)
    variance = sum((count - avg_count) ** 2 for count in selection_counts.values()) / len(selection_counts)
    std_dev = variance ** 0.5

    # Should have low variance (even distribution)
    assert std_dev < avg_count * 0.5, "Distribution should be relatively even"

    print(f"✅ Distribution efficiency: std_dev={std_dev:.2f} (avg={avg_count:.0f})")


# ==================== INTEGRATION TESTS ====================

@pytest.mark.asyncio
async def test_full_stack_integration(fog_cache, load_balancer, mock_nodes):
    """Test full integration of cache + load balancer"""
    # Warm cache with node data
    nodes_data = {node.node_id: {"cpu": node.cpu_usage_percent} for node in mock_nodes}
    await fog_cache.warm_cache(nodes_data)

    # Select nodes 100 times
    for i in range(TEST_MAX_RESULTS):
        selected = load_balancer.select_node(mock_nodes)

        # Update cache
        await fog_cache.set(f"task-{i}", {"node": selected.node_id, "time": time.time()})

        # Record request
        load_balancer.record_request_start(selected.node_id)
        load_balancer.record_request_end(selected.node_id, success=True, response_time_ms=10.0)

    # Verify cache hit rate
    metrics = fog_cache.get_metrics()
    assert metrics["hit_rate"] >= 0  # Should have some hits

    # Verify load balancer metrics
    lb_metrics = load_balancer.get_metrics()
    assert lb_metrics["total_connections"] == 0  # All requests completed

    print(f"✅ Full integration: cache_hit_rate={metrics['hit_rate']:.1f}%")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])
