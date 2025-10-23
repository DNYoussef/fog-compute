#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive Performance Benchmarking Suite
Tests BetaNet, FOG, VPN, and overall system performance
"""
import asyncio
import time
import statistics
import sys
import os
from pathlib import Path
from datetime import datetime

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Results storage
results = {}


async def benchmark_vpn_circuits():
    """Benchmark VPN circuit creation and data throughput"""
    from vpn.onion_routing import OnionRouter, NodeType

    print("\n" + "="*60)
    print("🔒 VPN CIRCUIT BENCHMARKS")
    print("="*60)

    router = OnionRouter(
        node_id="benchmark-router",
        node_types={NodeType.GUARD, NodeType.MIDDLE},
        enable_hidden_services=True,
        num_guards=3,
    )

    # Fetch consensus
    await router.fetch_consensus()

    # Benchmark 1: Circuit creation time
    print("\n1️⃣ Circuit Creation Performance")
    creation_times = []
    circuits = []

    for i in range(10):
        start = time.time()
        circuit = await router.build_circuit(path_length=3)
        elapsed = (time.time() - start) * 1000
        creation_times.append(elapsed)
        if circuit:
            circuits.append(circuit)
        print(f"  Circuit {i+1}: {elapsed:.2f}ms")

    avg_creation = statistics.mean(creation_times)
    print(f"\n  Average: {avg_creation:.2f}ms")
    print(f"  Min: {min(creation_times):.2f}ms")
    print(f"  Max: {max(creation_times):.2f}ms")
    print(f"  Success Rate: {len(circuits)}/10 ({len(circuits)*10}%)")

    results['vpn_circuit_creation_ms'] = avg_creation
    results['vpn_circuit_success_rate'] = len(circuits) / 10

    # Benchmark 2: Data transmission throughput
    if circuits:
        print("\n2️⃣ Data Transmission Throughput")
        circuit = circuits[0]

        # Test different payload sizes
        payload_sizes = [1024, 4096, 16384, 65536]
        for size in payload_sizes:
            payload = b"X" * size

            # Run many iterations for better timing accuracy
            iterations = 1000
            start = time.perf_counter()
            for _ in range(iterations):
                encrypted = router._onion_encrypt(circuit, payload)
            elapsed = time.perf_counter() - start

            # Calculate throughput
            bytes_processed = size * iterations
            throughput_mbps = (bytes_processed * 8) / (elapsed * 1000000)

            print(f"  {size:>6} bytes: {throughput_mbps:.2f} Mbps ({iterations} iterations in {elapsed:.2f}s)")

            results[f'vpn_throughput_{size}b_mbps'] = throughput_mbps

    # Clean up
    for circuit in circuits:
        await router.close_circuit(circuit.circuit_id)

    print("\n✅ VPN benchmarks complete")


def benchmark_resource_optimization():
    """Benchmark resource pooling and optimization"""
    from scheduler.resource_pool import ResourcePoolManager, PoolType
    from scheduler.memory_optimizer import MemoryOptimizer, get_memory_optimizer

    print("\n" + "="*60)
    print("⚡ RESOURCE OPTIMIZATION BENCHMARKS")
    print("="*60)

    # Benchmark 1: Resource pool reuse rate
    print("\n1️⃣ Resource Pool Performance")
    manager = ResourcePoolManager()

    def create_resource():
        return {"id": time.time(), "data": b"x" * 1024}

    manager.create_pool(
        name="benchmark_pool",
        pool_type=PoolType.GENERIC,
        factory=create_resource,
        min_size=10,
        max_size=50,
    )

    # Warm up pool
    for _ in range(100):
        with manager.acquire("benchmark_pool", timeout=1.0):
            pass

    # Measure acquisition time
    acquisition_times = []
    for _ in range(1000):
        start = time.time()
        with manager.acquire("benchmark_pool", timeout=1.0) as resource:
            elapsed = (time.time() - start) * 1000
            acquisition_times.append(elapsed)

    stats = manager.get_all_stats()["benchmark_pool"]
    reuse_rate = stats["reuse_rate_percent"]
    avg_acquisition = statistics.mean(acquisition_times)

    print(f"  Reuse Rate: {reuse_rate:.1f}%")
    print(f"  Avg Acquisition Time: {avg_acquisition:.3f}ms")
    print(f"  Total Resources Created: {stats['total_created']}")
    print(f"  Currently Available: {stats.get('available', 'N/A')}")

    results['resource_pool_reuse_rate'] = reuse_rate
    results['resource_pool_acquisition_ms'] = avg_acquisition

    manager.shutdown_all()

    # Benchmark 2: Memory optimizer
    print("\n2️⃣ Memory Optimizer Performance")
    optimizer = get_memory_optimizer()

    # Test arena allocation speed
    arena_times = []
    for _ in range(100):
        start = time.time()
        buffer = optimizer.arena.allocate(4096)
        elapsed = (time.time() - start) * 1000
        arena_times.append(elapsed)
        if buffer:
            optimizer.arena.deallocate(buffer)

    avg_arena = statistics.mean(arena_times)
    print(f"  Avg Arena Allocation: {avg_arena:.3f}ms")

    arena_stats = optimizer.arena.get_stats()
    print(f"  Arena Utilization: {arena_stats['utilization_percent']:.1f}%")
    print(f"  Free Blocks: {arena_stats['free_blocks']}")

    results['memory_arena_allocation_ms'] = avg_arena
    results['memory_arena_utilization'] = arena_stats['utilization_percent']

    print("\n✅ Resource optimization benchmarks complete")


async def benchmark_intelligent_scheduler():
    """Benchmark intelligent task scheduler"""
    from scheduler.intelligent_scheduler import (
        IntelligentScheduler,
        TaskPriority,
        ResourceRequirements,
        SchedulingStrategy,
    )

    print("\n" + "="*60)
    print("🧠 INTELLIGENT SCHEDULER BENCHMARKS")
    print("="*60)

    scheduler = IntelligentScheduler()

    # Add workers
    for i in range(5):
        scheduler.register_worker(
            f"worker-{i}",
            cpu_cores=4,
            memory_mb=8192,
        )

    # Benchmark task submission and scheduling
    print("\n1️⃣ Task Throughput")

    submission_times = []
    start_time = time.time()

    # Submit 1000 tasks
    for i in range(1000):
        sub_start = time.time()
        scheduler.submit_task(
            f"task-{i}",
            priority=TaskPriority.MEDIUM,
            requirements=ResourceRequirements(cpu_cores=1, memory_mb=512),
        )
        submission_times.append((time.time() - sub_start) * 1000)

    total_time = time.time() - start_time
    throughput = 1000 / total_time
    avg_submission = statistics.mean(submission_times)

    print(f"  Tasks Submitted: 1000")
    print(f"  Total Time: {total_time:.2f}s")
    print(f"  Throughput: {throughput:.1f} tasks/sec")
    print(f"  Avg Submission Time: {avg_submission:.3f}ms")

    results['scheduler_throughput_tasks_per_sec'] = throughput
    results['scheduler_submission_ms'] = avg_submission

    # Start scheduler and measure execution
    await scheduler.start()
    await asyncio.sleep(5.0)  # Let tasks execute

    stats = scheduler.get_stats()
    total_executed = sum(w["total_executed"] for w in stats["worker_stats"].values())

    print(f"  Tasks Executed (5s): {total_executed}")
    print(f"  Pending: {stats['pending_tasks']}")

    results['scheduler_execution_rate'] = total_executed / 5.0

    await scheduler.stop()

    print("\n✅ Scheduler benchmarks complete")


def benchmark_profiler():
    """Benchmark performance profiler overhead"""
    from scheduler.profiler import PerformanceProfiler, ProfilerMode

    print("\n" + "="*60)
    print("📊 PROFILER OVERHEAD BENCHMARKS")
    print("="*60)

    profiler = PerformanceProfiler(output_dir="benchmark_profiling")

    def cpu_work():
        result = 0
        for i in range(100000):
            result += i ** 2
        return result

    # Baseline without profiling
    print("\n1️⃣ Baseline Performance (No Profiling)")
    baseline_times = []
    for _ in range(10):
        start = time.time()
        cpu_work()
        elapsed = (time.time() - start) * 1000
        baseline_times.append(elapsed)

    avg_baseline = statistics.mean(baseline_times)
    print(f"  Average: {avg_baseline:.3f}ms")

    # With CPU profiling
    print("\n2️⃣ With CPU Profiling")
    profiled_times = []
    for _ in range(10):
        start = time.time()
        profiler.start(ProfilerMode.CPU)
        cpu_work()
        profiler.stop()
        elapsed = (time.time() - start) * 1000
        profiled_times.append(elapsed)

    avg_profiled = statistics.mean(profiled_times)
    overhead = ((avg_profiled - avg_baseline) / avg_baseline) * 100

    print(f"  Average: {avg_profiled:.3f}ms")
    print(f"  Overhead: {overhead:.1f}%")

    results['profiler_overhead_percent'] = overhead

    print("\n✅ Profiler benchmarks complete")


def print_summary():
    """Print benchmark summary"""
    print("\n" + "="*60)
    print("📈 BENCHMARK SUMMARY")
    print("="*60)

    print("\n🔒 VPN Performance:")
    if 'vpn_circuit_creation_ms' in results:
        print(f"  Circuit Creation: {results['vpn_circuit_creation_ms']:.2f}ms")
        print(f"  Success Rate: {results['vpn_circuit_success_rate']*100:.0f}%")
        if 'vpn_throughput_65536b_mbps' in results:
            print(f"  Throughput (64KB): {results['vpn_throughput_65536b_mbps']:.2f} Mbps")

    print("\n⚡ Resource Optimization:")
    if 'resource_pool_reuse_rate' in results:
        print(f"  Pool Reuse Rate: {results['resource_pool_reuse_rate']:.1f}%")
        print(f"  Acquisition Time: {results['resource_pool_acquisition_ms']:.3f}ms")
        print(f"  Arena Allocation: {results['memory_arena_allocation_ms']:.3f}ms")

    print("\n🧠 Scheduler Performance:")
    if 'scheduler_throughput_tasks_per_sec' in results:
        print(f"  Submission Rate: {results['scheduler_throughput_tasks_per_sec']:.1f} tasks/sec")
        print(f"  Execution Rate: {results['scheduler_execution_rate']:.1f} tasks/sec")

    print("\n📊 Profiler Overhead:")
    if 'profiler_overhead_percent' in results:
        print(f"  CPU Profiling: {results['profiler_overhead_percent']:.1f}%")

    print("\n" + "="*60)
    print(f"✅ Benchmarks completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)


async def main():
    """Run all benchmarks"""
    print("\n" + "="*60)
    print("🚀 FOG COMPUTE COMPREHENSIVE BENCHMARK SUITE")
    print("="*60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        await benchmark_vpn_circuits()
        benchmark_resource_optimization()
        await benchmark_intelligent_scheduler()
        benchmark_profiler()

        print_summary()

        # Save results to file
        import json
        results_file = Path("benchmark_results.json")
        results['timestamp'] = datetime.now().isoformat()
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"\n💾 Results saved to: {results_file}")

    except Exception as e:
        print(f"\n❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
