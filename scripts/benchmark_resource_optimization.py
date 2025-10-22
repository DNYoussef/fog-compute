"""
Benchmark Suite for Resource Optimization

Benchmarks:
1. Memory allocation (with/without pooling)
2. Scheduler performance (tasks/sec)
3. Resource utilization efficiency
4. Before/after comparison
"""

import asyncio
import time
import statistics
from typing import List, Dict, Any
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from scheduler.resource_pool import ResourcePoolManager, PoolType
from scheduler.memory_optimizer import MemoryOptimizer, MemoryArena
from scheduler.intelligent_scheduler import (
    IntelligentScheduler,
    SchedulingStrategy,
    TaskPriority,
    ResourceRequirements,
)
from scheduler.profiler import PerformanceProfiler, ProfilerMode


class BenchmarkResults:
    """Store and format benchmark results"""

    def __init__(self):
        self.results: Dict[str, Dict[str, Any]] = {}

    def add_result(self, name: str, data: Dict[str, Any]):
        """Add a benchmark result"""
        self.results[name] = data

    def print_summary(self):
        """Print formatted summary"""
        print("\n" + "=" * 80)
        print("RESOURCE OPTIMIZATION BENCHMARK RESULTS")
        print("=" * 80)

        for name, data in self.results.items():
            print(f"\n{name}")
            print("-" * 80)

            for key, value in data.items():
                if isinstance(value, float):
                    print(f"  {key}: {value:.4f}")
                elif isinstance(value, list):
                    print(f"  {key}: {value}")
                else:
                    print(f"  {key}: {value}")

        print("\n" + "=" * 80)


class MemoryAllocationBenchmark:
    """Benchmark memory allocation with and without pooling"""

    @staticmethod
    def benchmark_without_pool(iterations: int = 10000) -> Dict[str, Any]:
        """Benchmark standard allocation"""
        print(f"Benchmarking standard allocation ({iterations} iterations)...")

        allocations = []
        start_time = time.time()

        for i in range(iterations):
            # Simulate standard allocation
            data = bytearray(1024)  # 1 KB
            allocations.append(data)

            # Simulate deallocation
            if i % 100 == 0:
                allocations = allocations[-50:]  # Keep only recent

        end_time = time.time()
        duration = end_time - start_time

        return {
            "duration_seconds": duration,
            "iterations": iterations,
            "allocations_per_second": iterations / duration,
            "avg_time_ms": (duration / iterations) * 1000,
        }

    @staticmethod
    def benchmark_with_arena(iterations: int = 10000) -> Dict[str, Any]:
        """Benchmark arena allocation"""
        print(f"Benchmarking arena allocation ({iterations} iterations)...")

        arena = MemoryArena(size_bytes=100 * 1024 * 1024)  # 100 MB
        allocations = []
        start_time = time.time()

        for i in range(iterations):
            # Allocate from arena
            buf = arena.allocate(1024)
            if buf:
                allocations.append(buf)

            # Simulate deallocation
            if i % 100 == 0 and allocations:
                for buf in allocations[:50]:
                    arena.deallocate(buf)
                allocations = allocations[50:]

        end_time = time.time()
        duration = end_time - start_time

        stats = arena.get_stats()
        arena.shutdown()

        return {
            "duration_seconds": duration,
            "iterations": iterations,
            "allocations_per_second": iterations / duration,
            "avg_time_ms": (duration / iterations) * 1000,
            "arena_utilization_percent": stats["utilization_percent"],
        }

    @staticmethod
    def benchmark_with_pool(iterations: int = 10000) -> Dict[str, Any]:
        """Benchmark resource pool allocation"""
        print(f"Benchmarking pool allocation ({iterations} iterations)...")

        manager = ResourcePoolManager()

        def create_buffer():
            return bytearray(1024)

        manager.create_pool(
            name="buffer_pool",
            pool_type=PoolType.MEMORY,
            factory=create_buffer,
            min_size=10,
            max_size=50,
        )

        start_time = time.time()

        for i in range(iterations):
            with manager.acquire("buffer_pool", timeout=1.0) as buf:
                # Use buffer
                pass

        end_time = time.time()
        duration = end_time - start_time

        stats = manager.get_all_stats()["buffer_pool"]
        manager.shutdown_all()

        return {
            "duration_seconds": duration,
            "iterations": iterations,
            "allocations_per_second": iterations / duration,
            "avg_time_ms": (duration / iterations) * 1000,
            "reuse_rate_percent": stats["reuse_rate_percent"],
            "total_created": stats["total_created"],
            "total_reused": stats["total_reused"],
        }

    @staticmethod
    def run_all() -> Dict[str, Any]:
        """Run all memory benchmarks"""
        iterations = 10000

        standard = MemoryAllocationBenchmark.benchmark_without_pool(iterations)
        arena = MemoryAllocationBenchmark.benchmark_with_arena(iterations)
        pool = MemoryAllocationBenchmark.benchmark_with_pool(iterations)

        # Calculate improvements
        arena_speedup = standard["allocations_per_second"] / arena["allocations_per_second"]
        pool_speedup = standard["allocations_per_second"] / pool["allocations_per_second"]

        return {
            "standard": standard,
            "arena": arena,
            "pool": pool,
            "arena_speedup": arena_speedup,
            "pool_speedup": pool_speedup,
            "pool_reuse_rate": pool["reuse_rate_percent"],
            "allocation_reduction_percent": (
                (1 - pool["total_created"] / iterations) * 100
                if iterations > 0 else 0
            ),
        }


class SchedulerPerformanceBenchmark:
    """Benchmark scheduler performance"""

    @staticmethod
    async def benchmark_task_throughput(
        num_tasks: int = 1000,
        num_workers: int = 5,
        strategy: SchedulingStrategy = SchedulingStrategy.ML_ADAPTIVE,
    ) -> Dict[str, Any]:
        """Benchmark scheduler task throughput"""
        print(f"Benchmarking scheduler with {num_tasks} tasks, {num_workers} workers...")

        scheduler = IntelligentScheduler(strategy=strategy)

        # Register workers
        for i in range(num_workers):
            scheduler.register_worker(
                f"worker{i}",
                cpu_cores=4,
                memory_mb=8192,
            )

        # Submit tasks
        submission_start = time.time()

        for i in range(num_tasks):
            scheduler.submit_task(
                f"task{i}",
                priority=TaskPriority.MEDIUM,
                requirements=ResourceRequirements(cpu_cores=1, memory_mb=512),
            )

        submission_time = time.time() - submission_start

        # Start scheduler
        await scheduler.start()

        # Wait for all tasks to complete
        execution_start = time.time()

        while True:
            stats = scheduler.get_stats()
            active = stats["active_tasks"]
            pending = stats["pending_tasks"]

            if active == 0 and pending == 0:
                break

            await asyncio.sleep(0.1)

            # Timeout after 30 seconds
            if time.time() - execution_start > 30:
                break

        execution_time = time.time() - execution_start

        stats = scheduler.get_stats()
        total_executed = sum(w["total_executed"] for w in stats["worker_stats"].values())

        await scheduler.stop()

        return {
            "num_tasks": num_tasks,
            "num_workers": num_workers,
            "strategy": strategy.value,
            "submission_time_seconds": submission_time,
            "execution_time_seconds": execution_time,
            "total_time_seconds": submission_time + execution_time,
            "tasks_executed": total_executed,
            "tasks_per_second": total_executed / execution_time if execution_time > 0 else 0,
            "submission_rate": num_tasks / submission_time if submission_time > 0 else 0,
        }

    @staticmethod
    async def benchmark_scheduler_strategies() -> Dict[str, Any]:
        """Benchmark different scheduler strategies"""
        strategies = [
            SchedulingStrategy.FIFO,
            SchedulingStrategy.PRIORITY,
            SchedulingStrategy.ML_ADAPTIVE,
        ]

        results = {}

        for strategy in strategies:
            result = await SchedulerPerformanceBenchmark.benchmark_task_throughput(
                num_tasks=500,
                num_workers=4,
                strategy=strategy,
            )
            results[strategy.value] = result

            # Small delay between benchmarks
            await asyncio.sleep(1.0)

        return results


class ResourceUtilizationBenchmark:
    """Benchmark resource utilization efficiency"""

    @staticmethod
    async def benchmark_system_load(duration_seconds: int = 10) -> Dict[str, Any]:
        """Benchmark system under load"""
        print(f"Benchmarking resource utilization for {duration_seconds} seconds...")

        # Initialize components
        pool_manager = ResourcePoolManager()
        optimizer = MemoryOptimizer(arena_size_gb=0.1)
        scheduler = IntelligentScheduler(strategy=SchedulingStrategy.ML_ADAPTIVE)
        profiler = PerformanceProfiler(output_dir="benchmark_profiling")

        # Create resource pool
        def create_resource():
            return {"id": time.time()}

        pool_manager.create_pool(
            name="benchmark_pool",
            pool_type=PoolType.GENERIC,
            factory=create_resource,
            min_size=5,
            max_size=20,
        )

        # Register workers
        for i in range(4):
            scheduler.register_worker(f"worker{i}", cpu_cores=4, memory_mb=4096)

        # Start profiling
        profiler.start(ProfilerMode.ALL)

        # Start scheduler
        await scheduler.start()

        # Generate load
        start_time = time.time()
        task_count = 0

        while time.time() - start_time < duration_seconds:
            # Submit tasks
            for i in range(10):
                scheduler.submit_task(
                    f"task_{task_count}_{i}",
                    priority=TaskPriority.MEDIUM,
                    requirements=ResourceRequirements(cpu_cores=1, memory_mb=512),
                )
                task_count += 1

            # Use resource pool
            for i in range(5):
                with pool_manager.acquire("benchmark_pool", timeout=1.0):
                    pass

            await asyncio.sleep(0.1)

        # Stop components
        await scheduler.stop()
        profile_results = profiler.stop()

        # Gather stats
        pool_stats = pool_manager.get_all_stats()["benchmark_pool"]
        scheduler_stats = scheduler.get_stats()
        memory_stats = optimizer.get_memory_stats()

        # Cleanup
        pool_manager.shutdown_all()
        optimizer.shutdown()

        return {
            "duration_seconds": duration_seconds,
            "tasks_submitted": task_count,
            "tasks_executed": sum(w["total_executed"] for w in scheduler_stats["worker_stats"].values()),
            "pool_reuse_rate_percent": pool_stats["reuse_rate_percent"],
            "pool_resources_created": pool_stats["total_created"],
            "memory_arena_utilization": memory_stats["arena"]["utilization_percent"],
            "bottlenecks_detected": len(profile_results.get("bottlenecks", [])),
        }


def print_comparison(name: str, baseline: float, optimized: float, unit: str = ""):
    """Print before/after comparison"""
    improvement = ((baseline - optimized) / baseline * 100) if baseline > 0 else 0
    print(f"{name}:")
    print(f"  Baseline: {baseline:.4f} {unit}")
    print(f"  Optimized: {optimized:.4f} {unit}")
    print(f"  Improvement: {improvement:.2f}%")


async def main():
    """Run all benchmarks"""
    results = BenchmarkResults()

    print("\n" + "=" * 80)
    print("STARTING RESOURCE OPTIMIZATION BENCHMARKS")
    print("=" * 80 + "\n")

    # 1. Memory Allocation Benchmarks
    print("\n1. MEMORY ALLOCATION BENCHMARKS")
    print("-" * 80)
    memory_results = MemoryAllocationBenchmark.run_all()
    results.add_result("Memory Allocation", memory_results)

    print("\nComparison:")
    print_comparison(
        "Allocation Speed",
        memory_results["standard"]["allocations_per_second"],
        memory_results["pool"]["allocations_per_second"],
        "ops/sec",
    )
    print(f"\nPool Reuse Rate: {memory_results['pool_reuse_rate']:.2f}%")
    print(f"Allocation Reduction: {memory_results['allocation_reduction_percent']:.2f}%")

    # 2. Scheduler Performance Benchmarks
    print("\n\n2. SCHEDULER PERFORMANCE BENCHMARKS")
    print("-" * 80)
    scheduler_results = await SchedulerPerformanceBenchmark.benchmark_scheduler_strategies()
    results.add_result("Scheduler Strategies", scheduler_results)

    print("\nStrategy Comparison:")
    for strategy, data in scheduler_results.items():
        print(f"\n{strategy}:")
        print(f"  Tasks/sec: {data['tasks_per_second']:.2f}")
        print(f"  Total time: {data['total_time_seconds']:.4f}s")
        print(f"  Tasks executed: {data['tasks_executed']}")

    # 3. Resource Utilization Benchmark
    print("\n\n3. RESOURCE UTILIZATION BENCHMARK")
    print("-" * 80)
    utilization_results = await ResourceUtilizationBenchmark.benchmark_system_load(duration_seconds=10)
    results.add_result("Resource Utilization", utilization_results)

    print("\nUtilization Results:")
    print(f"  Tasks executed: {utilization_results['tasks_executed']}")
    print(f"  Pool reuse rate: {utilization_results['pool_reuse_rate_percent']:.2f}%")
    print(f"  Pool resources created: {utilization_results['pool_resources_created']}")
    print(f"  Memory arena utilization: {utilization_results['memory_arena_utilization']:.2f}%")
    print(f"  Bottlenecks detected: {utilization_results['bottlenecks_detected']}")

    # Print final summary
    results.print_summary()

    # Success criteria
    print("\n" + "=" * 80)
    print("SUCCESS CRITERIA VERIFICATION")
    print("=" * 80)

    checks = [
        ("Pool Reuse Rate > 90%", memory_results["pool_reuse_rate"] > 90.0),
        ("Allocation Reduction > 80%", memory_results["allocation_reduction_percent"] > 80.0),
        ("Scheduler Functional", scheduler_results["ml_adaptive"]["tasks_executed"] > 0),
        ("Resource Monitoring Works", utilization_results["tasks_executed"] > 0),
    ]

    all_passed = True
    for check_name, passed in checks:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} - {check_name}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 80)
    if all_passed:
        print("ALL BENCHMARKS PASSED!")
    else:
        print("SOME BENCHMARKS FAILED - Review results above")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
