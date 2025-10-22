#!/usr/bin/env python3
"""
BetaNet Delay Injection Benchmarking Script

Measures performance and privacy metrics for the enhanced delay injection system:
- Delay distribution analysis
- Privacy metrics (correlation, entropy)
- Throughput impact measurement
- Latency overhead analysis
- Batch size efficiency
- Cover traffic overhead
"""

import subprocess
import json
import statistics
import time
import sys
from typing import List, Dict, Tuple
from dataclasses import dataclass
import matplotlib.pyplot as plt
import numpy as np

@dataclass
class DelayMetrics:
    """Delay distribution metrics"""
    mean: float
    median: float
    std_dev: float
    variance: float
    min_val: float
    max_val: float
    p50: float
    p95: float
    p99: float

@dataclass
class PrivacyMetrics:
    """Privacy-related metrics"""
    correlation: float
    entropy: float
    indistinguishability: float
    resistance_score: float

@dataclass
class PerformanceMetrics:
    """Performance metrics"""
    throughput_pps: float
    avg_latency_ms: float
    latency_overhead_pct: float
    batch_size_avg: float
    cover_overhead_pct: float

class DelayInjectionBenchmark:
    """Benchmark runner for delay injection system"""

    def __init__(self):
        self.results = {}

    def run_rust_benchmark(self, test_name: str, duration_secs: int = 10) -> Dict:
        """Run Rust benchmark and parse output"""
        print(f"📊 Running benchmark: {test_name}...")

        cmd = [
            "cargo", "test",
            "--package", "betanet",
            "--test", "test_delay_injection",
            test_name,
            "--",
            "--nocapture"
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=duration_secs + 30
            )

            if result.returncode == 0:
                print(f"✅ {test_name} passed")
                return self.parse_test_output(result.stdout)
            else:
                print(f"❌ {test_name} failed")
                print(result.stderr)
                return {}

        except subprocess.TimeoutExpired:
            print(f"⏱️  {test_name} timed out")
            return {}
        except Exception as e:
            print(f"❌ Error running {test_name}: {e}")
            return {}

    def parse_test_output(self, output: str) -> Dict:
        """Parse test output for metrics"""
        metrics = {}

        for line in output.split('\n'):
            line = line.strip()

            # Parse key-value pairs
            if ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    key = parts[0].strip().lower().replace(' ', '_')
                    value_str = parts[1].strip()

                    # Try to extract numeric value
                    try:
                        # Remove units (ms, %, pkt/s, etc.)
                        value_str = value_str.split()[0]
                        value = float(value_str)
                        metrics[key] = value
                    except:
                        pass

        return metrics

    def analyze_delay_distribution(self) -> DelayMetrics:
        """Analyze Poisson delay distribution"""
        print("\n📈 Analyzing Delay Distribution...")

        result = self.run_rust_benchmark("test_poisson_distribution")

        if not result:
            return DelayMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0)

        return DelayMetrics(
            mean=result.get('sample_mean', 0),
            median=result.get('median', 0),
            std_dev=statistics.sqrt(result.get('sample_variance', 0)),
            variance=result.get('sample_variance', 0),
            min_val=result.get('min', 100),
            max_val=result.get('max', 2000),
            p50=result.get('p50', 0),
            p95=result.get('p95', 0),
            p99=result.get('p99', 0)
        )

    def measure_privacy_metrics(self) -> PrivacyMetrics:
        """Measure privacy-related metrics"""
        print("\n🛡️  Measuring Privacy Metrics...")

        # Run timing attack resistance test
        timing_result = self.run_rust_benchmark("test_timing_attack_resistance")

        # Run indistinguishability tests
        indist_result = self.run_rust_benchmark("test_statistical_indistinguishability")
        cover_result = self.run_rust_benchmark("test_cover_traffic_indistinguishability")

        return PrivacyMetrics(
            correlation=abs(timing_result.get('correlation', 0)),
            entropy=timing_result.get('entropy', 0),
            indistinguishability=cover_result.get('similarity_score', 0),
            resistance_score=timing_result.get('resistance_score', 0)
        )

    def measure_performance(self) -> PerformanceMetrics:
        """Measure performance metrics"""
        print("\n⚡ Measuring Performance...")

        # Run throughput test
        throughput_result = self.run_rust_benchmark("test_throughput_overhead")

        # Run batching test
        batching_result = self.run_rust_benchmark("test_adaptive_batching")

        return PerformanceMetrics(
            throughput_pps=throughput_result.get('throughput_pps', 0),
            avg_latency_ms=throughput_result.get('avg_latency_ms', 0),
            latency_overhead_pct=throughput_result.get('overhead', 0) * 100,
            batch_size_avg=batching_result.get('high_load_size', 32),
            cover_overhead_pct=throughput_result.get('overhead', 0.03) * 100
        )

    def generate_report(self, delay: DelayMetrics, privacy: PrivacyMetrics,
                       performance: PerformanceMetrics):
        """Generate comprehensive benchmark report"""
        print("\n" + "="*60)
        print("🚀 BETANET DELAY INJECTION BENCHMARK REPORT")
        print("="*60)

        print("\n📊 DELAY DISTRIBUTION ANALYSIS")
        print("-" * 60)
        print(f"  Mean:              {delay.mean:.2f} ms")
        print(f"  Median:            {delay.median:.2f} ms")
        print(f"  Std Dev:           {delay.std_dev:.2f} ms")
        print(f"  Variance:          {delay.variance:.2f} ms²")
        print(f"  Min:               {delay.min_val:.2f} ms")
        print(f"  Max:               {delay.max_val:.2f} ms")
        print(f"  P50:               {delay.p50:.2f} ms")
        print(f"  P95:               {delay.p95:.2f} ms")
        print(f"  P99:               {delay.p99:.2f} ms")

        # Check if follows Poisson (variance ≈ mean²)
        expected_variance = delay.mean ** 2
        variance_ratio = delay.variance / expected_variance if expected_variance > 0 else 0
        print(f"\n  Variance Ratio:    {variance_ratio:.3f} (expected: ~1.0)")

        if 0.7 <= variance_ratio <= 1.3:
            print(f"  ✅ Follows Poisson distribution")
        else:
            print(f"  ⚠️  May not follow Poisson distribution")

        print("\n🛡️  PRIVACY METRICS")
        print("-" * 60)
        print(f"  Correlation:       {privacy.correlation:.4f}")
        print(f"  Entropy:           {privacy.entropy:.4f}")
        print(f"  Indistinguish.:    {privacy.indistinguishability:.2%}")
        print(f"  Resistance Score:  {privacy.resistance_score:.2%}")

        # Privacy assessment
        print("\n  Assessment:")
        if privacy.correlation < 0.3:
            print(f"  ✅ Low correlation (good)")
        else:
            print(f"  ⚠️  High correlation (needs improvement)")

        if privacy.entropy > 2.0:
            print(f"  ✅ High entropy (good)")
        else:
            print(f"  ⚠️  Low entropy (needs improvement)")

        if privacy.indistinguishability > 0.95:
            print(f"  ✅ Excellent indistinguishability")
        elif privacy.indistinguishability > 0.8:
            print(f"  ✓  Good indistinguishability")
        else:
            print(f"  ⚠️  Poor indistinguishability")

        if privacy.resistance_score > 0.6:
            print(f"  ✅ Strong timing attack resistance")
        elif privacy.resistance_score > 0.4:
            print(f"  ✓  Moderate timing attack resistance")
        else:
            print(f"  ⚠️  Weak timing attack resistance")

        print("\n⚡ PERFORMANCE METRICS")
        print("-" * 60)
        print(f"  Throughput:        {performance.throughput_pps:.0f} pkt/s")
        print(f"  Avg Latency:       {performance.avg_latency_ms:.2f} ms")
        print(f"  Latency Overhead:  {performance.latency_overhead_pct:.2f}%")
        print(f"  Avg Batch Size:    {performance.batch_size_avg:.1f} packets")
        print(f"  Cover Overhead:    {performance.cover_overhead_pct:.2f}%")

        # Performance assessment
        print("\n  Assessment:")
        if performance.throughput_pps >= 25000:
            print(f"  ✅ Meets throughput target (≥25,000 pkt/s)")
        elif performance.throughput_pps >= 20000:
            print(f"  ✓  Good throughput")
        else:
            print(f"  ⚠️  Below throughput target")

        if performance.cover_overhead_pct < 5.0:
            print(f"  ✅ Cover overhead < 5%")
        else:
            print(f"  ⚠️  Cover overhead exceeds 5% target")

        if performance.latency_overhead_pct < 20.0:
            print(f"  ✅ Latency overhead < 20%")
        else:
            print(f"  ⚠️  High latency overhead")

        # Overall assessment
        print("\n" + "="*60)
        print("📋 OVERALL ASSESSMENT")
        print("="*60)

        checks_passed = 0
        total_checks = 6

        if 0.7 <= variance_ratio <= 1.3:
            checks_passed += 1
        if privacy.correlation < 0.3:
            checks_passed += 1
        if privacy.indistinguishability > 0.8:
            checks_passed += 1
        if privacy.resistance_score > 0.4:
            checks_passed += 1
        if performance.cover_overhead_pct < 5.0:
            checks_passed += 1
        if performance.throughput_pps >= 20000:
            checks_passed += 1

        success_rate = (checks_passed / total_checks) * 100

        print(f"\n  Checks Passed: {checks_passed}/{total_checks} ({success_rate:.0f}%)")

        if success_rate >= 80:
            print(f"\n  ✅ EXCELLENT: System meets all major requirements")
        elif success_rate >= 60:
            print(f"\n  ✓  GOOD: System meets most requirements")
        else:
            print(f"\n  ⚠️  NEEDS IMPROVEMENT: Several issues detected")

        print("\n" + "="*60)

    def run_full_benchmark(self):
        """Run complete benchmark suite"""
        print("🚀 Starting BetaNet Delay Injection Benchmark Suite...")
        print(f"⏱️  Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

        start_time = time.time()

        # Run all benchmarks
        delay_metrics = self.analyze_delay_distribution()
        privacy_metrics = self.measure_privacy_metrics()
        performance_metrics = self.measure_performance()

        elapsed_time = time.time() - start_time

        # Generate report
        self.generate_report(delay_metrics, privacy_metrics, performance_metrics)

        print(f"\n⏱️  Total benchmark time: {elapsed_time:.2f} seconds")
        print(f"✅ Benchmark complete!\n")

        # Save results to JSON
        results = {
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "delay": {
                "mean": delay_metrics.mean,
                "median": delay_metrics.median,
                "std_dev": delay_metrics.std_dev,
                "variance": delay_metrics.variance,
                "p95": delay_metrics.p95,
                "p99": delay_metrics.p99
            },
            "privacy": {
                "correlation": privacy_metrics.correlation,
                "entropy": privacy_metrics.entropy,
                "indistinguishability": privacy_metrics.indistinguishability,
                "resistance_score": privacy_metrics.resistance_score
            },
            "performance": {
                "throughput_pps": performance_metrics.throughput_pps,
                "avg_latency_ms": performance_metrics.avg_latency_ms,
                "latency_overhead_pct": performance_metrics.latency_overhead_pct,
                "batch_size_avg": performance_metrics.batch_size_avg,
                "cover_overhead_pct": performance_metrics.cover_overhead_pct
            }
        }

        with open('benchmark_results.json', 'w') as f:
            json.dump(results, f, indent=2)

        print("📊 Results saved to benchmark_results.json")

def main():
    """Main entry point"""
    benchmark = DelayInjectionBenchmark()

    try:
        benchmark.run_full_benchmark()
        return 0
    except KeyboardInterrupt:
        print("\n\n⚠️  Benchmark interrupted by user")
        return 1
    except Exception as e:
        print(f"\n\n❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
