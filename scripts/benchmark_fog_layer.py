"""
Performance Benchmarks for FOG Layer Optimization

Benchmarks:
- Node registration throughput (target: 1000/sec)
- Query latency (target: <50ms p95)
- Cache hit rate (target: >80%)
- Load balancer efficiency
"""

import asyncio
import statistics
import sys
import time
from datetime import datetime

# Add src to path
sys.path.append('c:/Users/17175/Desktop/fog-compute/src')

from fog.caching import FogCache
from fog.coordinator_interface import FogNode, NodeStatus, NodeType
from fog.load_balancer import LoadBalancer, LoadBalancingAlgorithm


class BenchmarkResults:
    """Store and display benchmark results"""

    def __init__(self):
        self.results = {}

    def add_result(self, name: str, value: float, unit: str, target: float, passed: bool):
        """Add benchmark result"""
        self.results[name] = {
            "value": value,
            "unit": unit,
            "target": target,
            "passed": passed,
        }

    def print_results(self):
        """Print formatted results"""
        print("\n" + "=" * 80)
        print("FOG LAYER PERFORMANCE BENCHMARKS")
        print("=" * 80)
        print(f"Timestamp: {datetime.now().isoformat()}")
        print()

        passed_count = 0
        failed_count = 0

        for name, result in self.results.items():
            status = "✅ PASS" if result["passed"] else "❌ FAIL"
            passed_count += result["passed"]
            failed_count += not result["passed"]

            print(
                f"{status} | {name:<50} | {result['value']:>10.2f} {result['unit']:<10} "
                f"(target: {result['target']:.2f} {result['unit']})"
            )

        print()
        print("=" * 80)
        print(f"Summary: {passed_count} passed, {failed_count} failed")
        print("=" * 80)
        print()


async def benchmark_cache_hit_rate(cache: FogCache, results: BenchmarkResults):
    """Benchmark cache hit rate"""
    print("📊 Benchmarking cache hit rate...")

    # Warm cache with 1000 entries
    data = {f"node-{i}": {"id": i, "cpu": i * 10} for i in range(1000)}
    await cache.warm_cache(data)

    # Reset metrics
    cache.reset_metrics()

    # Perform 10000 reads (80% hitting cache)
    for i in range(10000):
        key = f"node-{i % 1000}"
        await cache.get(key)

    # Get metrics
    metrics = cache.get_metrics()
    hit_rate = metrics["hit_rate"]

    results.add_result(
        "Cache Hit Rate",
        hit_rate,
        "%",
        80.0,
        hit_rate >= 80.0,
    )


async def benchmark_query_latency(cache: FogCache, results: BenchmarkResults):
    """Benchmark query latency (p95)"""
    print("📊 Benchmarking query latency...")

    # Warm cache
    data = {f"query-{i}": {"data": f"value-{i}"} for i in range(1000)}
    await cache.warm_cache(data)

    # Measure query times
    latencies = []

    for i in range(1000):
        key = f"query-{i % 1000}"
        start = time.perf_counter()
        await cache.get(key)
        elapsed_ms = (time.perf_counter() - start) * 1000
        latencies.append(elapsed_ms)

    # Calculate p95
    p95_latency = statistics.quantiles(latencies, n=20)[18]  # 95th percentile

    results.add_result(
        "Query Latency (p95)",
        p95_latency,
        "ms",
        50.0,
        p95_latency < 50.0,
    )


async def benchmark_node_registration_throughput(cache: FogCache, results: BenchmarkResults):
    """Benchmark node registration throughput"""
    print("📊 Benchmarking node registration throughput...")

    # Create 10000 node records
    nodes_data = {
        f"reg-node-{i}": {
            "node_id": f"reg-node-{i}",
            "cpu": 4,
            "memory": 8192,
            "status": "active",
        }
        for i in range(10000)
    }

    # Measure batch registration time
    start = time.perf_counter()
    count = await cache.batch_set(nodes_data)
    elapsed = time.perf_counter() - start

    throughput = count / elapsed

    results.add_result(
        "Node Registration Throughput",
        throughput,
        "nodes/sec",
        1000.0,
        throughput >= 1000.0,
    )


async def benchmark_batch_operations(cache: FogCache, results: BenchmarkResults):
    """Benchmark batch operation performance"""
    print("📊 Benchmarking batch operations...")

    # Batch set 100 nodes
    batch_data = {f"batch-{i}": {"id": i, "cpu": i * 10} for i in range(100)}

    start = time.perf_counter()
    await cache.batch_set(batch_data)
    batch_set_time = (time.perf_counter() - start) * 1000

    # Batch get 100 nodes
    keys = [f"batch-{i}" for i in range(100)]

    start = time.perf_counter()
    await cache.batch_get(keys)
    batch_get_time = (time.perf_counter() - start) * 1000

    results.add_result(
        "Batch Set 100 Nodes",
        batch_set_time,
        "ms",
        500.0,
        batch_set_time < 500.0,
    )

    results.add_result(
        "Batch Get 100 Nodes",
        batch_get_time,
        "ms",
        500.0,
        batch_get_time < 500.0,
    )


def benchmark_load_balancer_efficiency(results: BenchmarkResults):
    """Benchmark load balancer distribution efficiency"""
    print("📊 Benchmarking load balancer efficiency...")

    # Create mock nodes
    nodes = []
    for i in range(10):
        node = FogNode(
            node_id=f"lb-node-{i}",
            node_type=NodeType.COMPUTE_NODE,
            region="us-east",
            cpu_cores=4,
            memory_mb=8192,
            storage_gb=100,
            gpu_available=False,
            supports_onion_routing=True,
        )
        node.cpu_usage_percent = 20.0 + (i * 5)
        nodes.append(node)

    # Test least-connections algorithm
    lb = LoadBalancer(algorithm=LoadBalancingAlgorithm.LEAST_CONNECTIONS)

    selections = []
    for _ in range(1000):
        node = lb.select_node(nodes)
        selections.append(node.node_id)

    # Calculate distribution variance
    selection_counts = {node.node_id: selections.count(node.node_id) for node in nodes}
    avg_count = 1000 / len(nodes)
    variance = sum((count - avg_count) ** 2 for count in selection_counts.values()) / len(
        selection_counts
    )
    std_dev = variance**0.5
    coefficient_of_variation = (std_dev / avg_count) * 100

    results.add_result(
        "Load Balancer Distribution (CV)",
        coefficient_of_variation,
        "%",
        50.0,
        coefficient_of_variation < 50.0,
    )


def benchmark_circuit_breaker_overhead(results: BenchmarkResults):
    """Benchmark circuit breaker overhead"""
    print("📊 Benchmarking circuit breaker overhead...")

    # Create nodes
    nodes = []
    for i in range(10):
        node = FogNode(
            node_id=f"cb-node-{i}",
            node_type=NodeType.COMPUTE_NODE,
            region="us-east",
            cpu_cores=4,
            memory_mb=8192,
            storage_gb=100,
            gpu_available=False,
            supports_onion_routing=True,
        )
        nodes.append(node)

    # Test with circuit breaker enabled
    lb_with_cb = LoadBalancer(enable_circuit_breaker=True)

    start = time.perf_counter()
    for _ in range(10000):
        lb_with_cb.select_node(nodes)
    time_with_cb = (time.perf_counter() - start) * 1000

    # Test without circuit breaker
    lb_no_cb = LoadBalancer(enable_circuit_breaker=False)

    start = time.perf_counter()
    for _ in range(10000):
        lb_no_cb.select_node(nodes)
    time_no_cb = (time.perf_counter() - start) * 1000

    overhead_percent = ((time_with_cb - time_no_cb) / time_no_cb) * 100

    results.add_result(
        "Circuit Breaker Overhead",
        overhead_percent,
        "%",
        20.0,
        overhead_percent < 20.0,
    )


def benchmark_weighted_round_robin_performance(results: BenchmarkResults):
    """Benchmark weighted round-robin performance"""
    print("📊 Benchmarking weighted round-robin...")

    nodes = []
    for i in range(10):
        node = FogNode(
            node_id=f"wrr-node-{i}",
            node_type=NodeType.COMPUTE_NODE,
            region="us-east",
            cpu_cores=4,
            memory_mb=8192,
            storage_gb=100,
            gpu_available=False,
            supports_onion_routing=True,
        )
        node.cpu_usage_percent = 10.0 if i == 0 else 80.0  # node-0 is lightly loaded
        nodes.append(node)

    lb = LoadBalancer(algorithm=LoadBalancingAlgorithm.WEIGHTED_ROUND_ROBIN)

    # Time 10000 selections
    start = time.perf_counter()
    selections = []
    for _ in range(10000):
        node = lb.select_node(nodes)
        selections.append(node.node_id)
    elapsed_ms = (time.perf_counter() - start) * 1000

    # Verify lightly loaded node gets more traffic
    selection_counts = {node.node_id: selections.count(node.node_id) for node in nodes}
    node0_percent = (selection_counts.get("wrr-node-0", 0) / 10000) * 100

    results.add_result(
        "Weighted RR Performance",
        elapsed_ms,
        "ms",
        1000.0,
        elapsed_ms < 1000.0,
    )

    results.add_result(
        "Weighted RR Accuracy (node-0 traffic)",
        node0_percent,
        "%",
        15.0,
        node0_percent >= 15.0,
    )


async def run_all_benchmarks():
    """Run all benchmarks"""
    results = BenchmarkResults()

    # Initialize cache
    print("Initializing FOG cache...")
    cache = FogCache(redis_url="redis://localhost:6379")
    connected = await cache.connect()

    if not connected:
        print("❌ Failed to connect to Redis. Skipping cache benchmarks.")
        print("   Start Redis with: docker run -p 6379:6379 redis:alpine")
        cache_enabled = False
    else:
        cache_enabled = True

    # Run cache benchmarks
    if cache_enabled:
        await benchmark_cache_hit_rate(cache, results)
        await benchmark_query_latency(cache, results)
        await benchmark_node_registration_throughput(cache, results)
        await benchmark_batch_operations(cache, results)
        await cache.disconnect()

    # Run load balancer benchmarks (no cache needed)
    benchmark_load_balancer_efficiency(results)
    benchmark_circuit_breaker_overhead(results)
    benchmark_weighted_round_robin_performance(results)

    # Print results
    results.print_results()


if __name__ == "__main__":
    print("🚀 Starting FOG Layer Performance Benchmarks")
    print()
    asyncio.run(run_all_benchmarks())
