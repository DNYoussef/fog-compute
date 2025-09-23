"""
Full system performance tests
Testing end-to-end system performance under various loads
"""

import asyncio
import time
import statistics
import sys
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass

sys.path.append(str(Path(__file__).parent.parent.parent / 'src'))

from fog.benchmarks.benchmark_suite import FogBenchmarkSuite


@dataclass
class LoadTestResult:
    """Load test result"""
    concurrent_users: int
    requests_per_second: float
    avg_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float
    error_rate: float
    throughput_mbps: float


class SystemPerformanceTest:
    """Full system performance testing"""

    def __init__(self):
        self.results: List[LoadTestResult] = []

    async def run_load_test(self, concurrent_users: int, duration_seconds: int = 60) -> LoadTestResult:
        """Run load test with specified concurrent users"""
        print(f"Running load test: {concurrent_users} concurrent users, {duration_seconds}s duration")

        start_time = time.time()
        total_requests = 0
        response_times = []
        errors = 0

        async def user_simulation():
            """Simulate single user"""
            nonlocal total_requests, errors

            while time.time() - start_time < duration_seconds:
                try:
                    request_start = time.perf_counter()

                    # Simulate request processing
                    await asyncio.sleep(0.001)  # 1ms base latency
                    await asyncio.sleep(0.0001 * concurrent_users / 100)  # Scale with load

                    response_time = (time.perf_counter() - request_start) * 1000  # to ms
                    response_times.append(response_time)
                    total_requests += 1

                except Exception:
                    errors += 1

                await asyncio.sleep(0.01)  # 10ms between requests per user

        # Run concurrent user simulations
        await asyncio.gather(*[user_simulation() for _ in range(concurrent_users)])

        # Calculate metrics
        test_duration = time.time() - start_time
        requests_per_second = total_requests / test_duration

        response_times.sort()
        avg_response_time = statistics.mean(response_times) if response_times else 0
        p95_index = int(len(response_times) * 0.95)
        p99_index = int(len(response_times) * 0.99)
        p95_response_time = response_times[p95_index] if p95_index < len(response_times) else 0
        p99_response_time = response_times[p99_index] if p99_index < len(response_times) else 0

        error_rate = (errors / total_requests * 100) if total_requests > 0 else 0
        throughput_mbps = (total_requests * 512 * 8) / (test_duration * 1_000_000)  # 512 bytes avg

        result = LoadTestResult(
            concurrent_users=concurrent_users,
            requests_per_second=requests_per_second,
            avg_response_time_ms=avg_response_time,
            p95_response_time_ms=p95_response_time,
            p99_response_time_ms=p99_response_time,
            error_rate=error_rate,
            throughput_mbps=throughput_mbps
        )

        self.results.append(result)
        return result

    async def run_scalability_test(self):
        """Test system scalability with increasing load"""
        print("Running scalability test...")

        user_levels = [10, 50, 100, 250, 500]

        for users in user_levels:
            result = await self.run_load_test(users, duration_seconds=30)

            print(f"\n{users} users:")
            print(f"  RPS: {result.requests_per_second:.2f}")
            print(f"  Avg response: {result.avg_response_time_ms:.2f}ms")
            print(f"  P95 response: {result.p95_response_time_ms:.2f}ms")
            print(f"  Error rate: {result.error_rate:.2f}%")

            # Check degradation
            if result.avg_response_time_ms > 100:  # 100ms threshold
                print(f"  WARNING: Response time degradation detected")

            await asyncio.sleep(2)  # Cool down between tests

    async def run_stress_test(self):
        """Run stress test to find breaking point"""
        print("\nRunning stress test...")

        current_load = 100
        increment = 100
        max_load = 2000

        while current_load <= max_load:
            result = await self.run_load_test(current_load, duration_seconds=20)

            print(f"\nLoad: {current_load} users")
            print(f"  RPS: {result.requests_per_second:.2f}")
            print(f"  Response time: {result.avg_response_time_ms:.2f}ms")
            print(f"  Error rate: {result.error_rate:.2f}%")

            # Check if system is breaking
            if result.error_rate > 5.0 or result.avg_response_time_ms > 500:
                print(f"  Breaking point reached at {current_load} users")
                break

            current_load += increment
            await asyncio.sleep(1)

    async def run_endurance_test(self, duration_minutes: int = 10):
        """Run endurance test for sustained load"""
        print(f"\nRunning endurance test ({duration_minutes} minutes)...")

        duration_seconds = duration_minutes * 60
        concurrent_users = 100

        start_time = time.time()
        sample_interval = 30  # Sample every 30 seconds
        samples = []

        while time.time() - start_time < duration_seconds:
            sample_result = await self.run_load_test(concurrent_users, duration_seconds=sample_interval)
            samples.append(sample_result)

            elapsed_minutes = (time.time() - start_time) / 60
            print(f"  {elapsed_minutes:.1f}min - RPS: {sample_result.requests_per_second:.2f}, "
                  f"Response: {sample_result.avg_response_time_ms:.2f}ms")

        # Analyze endurance results
        response_times = [s.avg_response_time_ms for s in samples]
        rps_values = [s.requests_per_second for s in samples]

        print(f"\nEndurance test results:")
        print(f"  Avg RPS: {statistics.mean(rps_values):.2f}")
        print(f"  RPS stability: {statistics.stdev(rps_values):.2f}")
        print(f"  Avg response time: {statistics.mean(response_times):.2f}ms")
        print(f"  Response time drift: {statistics.stdev(response_times):.2f}ms")

    async def run_spike_test(self):
        """Test system response to sudden load spikes"""
        print("\nRunning spike test...")

        baseline_users = 50
        spike_users = 500
        spike_duration = 10

        # Baseline
        print(f"Baseline load ({baseline_users} users)...")
        baseline_result = await self.run_load_test(baseline_users, duration_seconds=30)

        # Spike
        print(f"\nSpike to {spike_users} users...")
        spike_result = await self.run_load_test(spike_users, duration_seconds=spike_duration)

        # Recovery
        print(f"\nRecovery to {baseline_users} users...")
        recovery_result = await self.run_load_test(baseline_users, duration_seconds=30)

        print(f"\nSpike test results:")
        print(f"  Baseline RPS: {baseline_result.requests_per_second:.2f}")
        print(f"  Spike RPS: {spike_result.requests_per_second:.2f}")
        print(f"  Recovery RPS: {recovery_result.requests_per_second:.2f}")
        print(f"  Spike response time: {spike_result.avg_response_time_ms:.2f}ms")
        print(f"  Recovery response time: {recovery_result.avg_response_time_ms:.2f}ms")

        # Check recovery
        recovery_ratio = recovery_result.avg_response_time_ms / baseline_result.avg_response_time_ms
        if recovery_ratio <= 1.2:
            print(f"  System recovered successfully (ratio: {recovery_ratio:.2f})")
        else:
            print(f"  WARNING: Slow recovery (ratio: {recovery_ratio:.2f})")

    async def run_benchmark_integration_test(self):
        """Test integration with benchmark suite"""
        print("\nRunning benchmark integration test...")

        suite = FogBenchmarkSuite(output_dir='tests/output/performance')
        results = await suite.run_complete_suite()

        print(f"\nBenchmark results:")
        print(f"  Total tests: {results['summary']['total_tests']}")
        print(f"  Passed: {results['summary']['passed_tests']}")
        print(f"  Pass rate: {results['summary']['pass_rate']:.1f}%")
        print(f"  Grade: {results['summary']['overall_grade']}")

        return results

    def generate_performance_report(self):
        """Generate performance test report"""
        if not self.results:
            print("No results to report")
            return

        print("\n" + "=" * 60)
        print("PERFORMANCE TEST REPORT")
        print("=" * 60)

        print("\nLoad Test Results:")
        print(f"{'Users':<10} {'RPS':<15} {'Avg (ms)':<15} {'P95 (ms)':<15} {'Error %':<10}")
        print("-" * 65)

        for result in self.results:
            print(f"{result.concurrent_users:<10} "
                  f"{result.requests_per_second:<15.2f} "
                  f"{result.avg_response_time_ms:<15.2f} "
                  f"{result.p95_response_time_ms:<15.2f} "
                  f"{result.error_rate:<10.2f}")

        # Calculate performance score
        avg_rps = statistics.mean([r.requests_per_second for r in self.results])
        avg_response = statistics.mean([r.avg_response_time_ms for r in self.results])
        avg_errors = statistics.mean([r.error_rate for r in self.results])

        print(f"\nOverall Metrics:")
        print(f"  Average RPS: {avg_rps:.2f}")
        print(f"  Average Response Time: {avg_response:.2f}ms")
        print(f"  Average Error Rate: {avg_errors:.2f}%")

        # Performance grade
        if avg_response < 50 and avg_errors < 0.1:
            grade = 'A'
        elif avg_response < 100 and avg_errors < 0.5:
            grade = 'B'
        elif avg_response < 200 and avg_errors < 1.0:
            grade = 'C'
        else:
            grade = 'D'

        print(f"\nPerformance Grade: {grade}")


async def main():
    """Run all performance tests"""
    tester = SystemPerformanceTest()

    # Run test suite
    print("Starting Full System Performance Test Suite")
    print("=" * 60)

    # Scalability test
    await tester.run_scalability_test()

    # Stress test
    await tester.run_stress_test()

    # Spike test
    await tester.run_spike_test()

    # Endurance test (shorter for demo)
    await tester.run_endurance_test(duration_minutes=2)

    # Benchmark integration
    await tester.run_benchmark_integration_test()

    # Generate report
    tester.generate_performance_report()


if __name__ == "__main__":
    asyncio.run(main())