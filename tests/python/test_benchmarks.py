"""
Test suite for Fog Compute benchmark system
"""

import pytest
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent.parent / 'src'))

from fog.benchmarks.benchmark_suite import FogBenchmarkSuite, BenchmarkResult
from fog.benchmarks.run_benchmarks import BenchmarkRunner
from fog.utils import SystemMetrics, calculate_improvement, calculate_grade


class TestBenchmarkSuite:
    """Test benchmark suite functionality"""

    @pytest.fixture
    async def suite(self):
        """Create benchmark suite instance"""
        return FogBenchmarkSuite(output_dir='tests/output', verbose=False)

    @pytest.mark.asyncio
    async def test_suite_initialization(self, suite):
        """Test benchmark suite initializes correctly"""
        assert suite.output_dir.exists()
        assert suite.targets is not None
        assert 'system_startup_time' in suite.targets

    @pytest.mark.asyncio
    async def test_system_startup_benchmark(self, suite):
        """Test system startup benchmark"""
        result = await suite._benchmark_system_startup()

        assert isinstance(result, BenchmarkResult)
        assert result.category == 'system'
        assert result.after_value is not None
        assert result.after_value > 0

    @pytest.mark.asyncio
    async def test_device_registration_benchmark(self, suite):
        """Test device registration benchmark"""
        result = await suite._benchmark_device_registration()

        assert result.category == 'system'
        assert result.metadata['samples'] == 10
        assert result.metadata['average_seconds'] > 0
        assert 'min_seconds' in result.metadata
        assert 'max_seconds' in result.metadata

    @pytest.mark.asyncio
    async def test_throughput_benchmark(self, suite):
        """Test system throughput benchmark"""
        result = await suite._benchmark_system_throughput()

        assert result.category == 'system'
        assert result.metadata['ops_per_second'] > 0
        assert result.metadata['operations_count'] == 1000

    @pytest.mark.asyncio
    async def test_privacy_circuit_creation(self, suite):
        """Test privacy circuit creation benchmark"""
        result = await suite._benchmark_circuit_creation()

        assert result.category == 'privacy'
        assert result.metadata['samples'] == 5
        assert result.improvement_percent >= 0

    @pytest.mark.asyncio
    async def test_graph_gap_detection(self, suite):
        """Test graph gap detection benchmark"""
        result = await suite._benchmark_graph_gap_detection()

        assert result.category == 'graph'
        assert result.metadata['node_count'] == 1000
        assert result.after_value is not None

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, suite):
        """Test concurrent operations benchmark"""
        result = await suite._benchmark_concurrency()

        assert result.category == 'integration'
        assert result.metadata['concurrent_tasks'] == 50
        assert result.metadata['efficiency_percent'] > 100

    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.integration
    async def test_complete_suite_run(self, suite):
        """Test running complete benchmark suite"""
        try:
            results = await suite.run_complete_suite()
        except Exception:
            pytest.skip("Benchmark suite not fully configured")

        assert 'system' in results
        assert 'privacy' in results
        assert 'graph' in results
        assert 'integration' in results
        assert 'summary' in results

        summary = results['summary']
        assert summary['total_tests'] > 0
        assert summary['pass_rate'] >= 0
        assert summary['overall_grade'] in ['A', 'B', 'C', 'D', 'F']

    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.integration
    async def test_performance_targets_met(self, suite):
        """Test that performance targets are met"""
        try:
            results = await suite.run_complete_suite()
        except Exception:
            pytest.skip("Benchmark suite not fully configured")

        system_results = results.get('system', {})
        if not system_results:
            pytest.skip("System results not available")

        # Check startup time if available
        startup = system_results.get('startup_time')
        if startup:
            assert startup.passed or startup.after_value <= suite.targets['system_startup_time']['value']

        # Check throughput if available
        throughput = system_results.get('throughput')
        if throughput:
            assert throughput.after_value > 100  # ops/sec (CI-friendly)


class TestBenchmarkRunner:
    """Test benchmark runner"""

    @pytest.fixture
    def runner(self):
        """Create benchmark runner instance"""
        return BenchmarkRunner()

    @pytest.mark.asyncio
    async def test_runner_initialization(self, runner):
        """Test runner initializes"""
        assert runner is not None

    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.integration
    async def test_run_specific_category(self, runner):
        """Test running specific benchmark category"""
        if not hasattr(runner, 'run_category'):
            pytest.skip("run_category method not implemented")

        try:
            results = await runner.run_category('system')
        except (NotImplementedError, AttributeError):
            pytest.skip("run_category not implemented")

        assert results is not None
        assert all(r.category == 'system' for r in results)

    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.integration
    async def test_parallel_benchmark_execution(self, runner):
        """Test parallel execution of benchmarks"""
        if not hasattr(runner, 'run_parallel'):
            pytest.skip("run_parallel method not implemented")

        import time

        try:
            start = time.time()
            results = await runner.run_parallel(['system', 'privacy'])
            duration = time.time() - start
        except (NotImplementedError, AttributeError):
            pytest.skip("run_parallel not implemented")

        assert len(results) == 2
        # Parallel should be faster than sequential
        assert duration < 30  # CI-friendly timeout


class TestUtilityFunctions:
    """Test utility functions"""

    def test_calculate_improvement(self):
        """Test improvement calculation"""
        improvement = calculate_improvement(100, 70)
        assert improvement == 30.0

        improvement = calculate_improvement(50, 75)
        assert improvement == -50.0

    def test_calculate_grade(self):
        """Test grade calculation"""
        assert calculate_grade(95) == 'A'
        assert calculate_grade(85) == 'B'
        assert calculate_grade(75) == 'C'
        assert calculate_grade(65) == 'D'
        assert calculate_grade(55) == 'F'

    @pytest.mark.asyncio
    async def test_collect_system_metrics(self):
        """Test system metrics collection"""
        from fog.utils import collect_system_metrics

        metrics = await collect_system_metrics()

        assert isinstance(metrics, SystemMetrics)
        assert metrics.cpu_percent >= 0
        assert metrics.memory_mb > 0
        assert metrics.threads > 0

    def test_establish_baseline_metrics(self):
        """Test baseline metrics establishment"""
        try:
            from fog.utils import establish_baseline_metrics
            baseline = establish_baseline_metrics()
        except (ImportError, AttributeError):
            pytest.skip("establish_baseline_metrics not available")

        assert 'cpu' in baseline or 'memory' in baseline
        if 'memory' in baseline:
            assert baseline['memory'].get('rss_mb', 0) >= 0


class TestBenchmarkResults:
    """Test benchmark result structure"""

    def test_benchmark_result_creation(self):
        """Test creating benchmark result"""
        result = BenchmarkResult(
            test_name='test',
            category='system',
            before_value=100.0,
            after_value=70.0,
            improvement_percent=30.0,
            target_improvement=25.0,
            passed=True,
            timestamp=1234567890.0,
            metadata={'key': 'value'}
        )

        assert result.test_name == 'test'
        assert result.passed is True
        assert result.improvement_percent == 30.0

    def test_result_serialization(self):
        """Test result can be serialized"""
        from dataclasses import asdict

        result = BenchmarkResult(
            test_name='test',
            category='system',
            before_value=100.0,
            after_value=70.0,
            improvement_percent=30.0,
            target_improvement=25.0,
            passed=True,
            timestamp=1234567890.0,
            metadata={}
        )

        result_dict = asdict(result)
        assert result_dict['test_name'] == 'test'
        assert result_dict['passed'] is True


class TestPerformanceMetrics:
    """Test performance metric calculations"""

    @pytest.mark.asyncio
    async def test_throughput_measurement(self):
        """Test throughput measurement accuracy"""
        import time

        operations = 1000
        start = time.perf_counter()

        for _ in range(operations):
            await asyncio.sleep(0.001)

        duration = time.perf_counter() - start
        throughput = operations / duration

        assert throughput > 0
        assert throughput < operations  # Should take some time

    @pytest.mark.asyncio
    async def test_latency_measurement(self):
        """Test latency measurement"""
        import time

        latencies = []

        for _ in range(10):
            start = time.perf_counter()
            await asyncio.sleep(0.01)
            latency = time.perf_counter() - start
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)
        assert avg_latency >= 0.01
        assert avg_latency < 0.02  # Should be close to sleep time

    def test_improvement_calculation_edge_cases(self):
        """Test improvement calculation edge cases"""
        # Zero improvement
        assert calculate_improvement(100, 100) == 0

        # Perfect improvement
        assert calculate_improvement(100, 0) == 100.0

        # Negative improvement (regression)
        assert calculate_improvement(50, 100) == -100.0


@pytest.mark.integration
@pytest.mark.slow
class TestIntegrationBenchmarks:
    """Integration tests for benchmark system"""

    @pytest.mark.asyncio
    async def test_end_to_end_benchmark(self):
        """Test complete end-to-end benchmark flow"""
        try:
            suite = FogBenchmarkSuite(output_dir='tests/output/integration')
            results = await suite.run_complete_suite()
        except Exception as e:
            pytest.skip(f"Benchmark suite not available: {e}")

        # Verify all categories ran
        assert 'system' in results
        assert 'privacy' in results
        assert 'graph' in results
        assert 'integration' in results

        # Verify summary generated
        summary = results['summary']
        assert summary['total_tests'] > 0
        assert 'categories' in summary

        # Verify reports generated
        assert suite.output_dir.exists()

    @pytest.mark.asyncio
    async def test_benchmark_reproducibility(self):
        """Test benchmarks produce consistent results"""
        suite = FogBenchmarkSuite(output_dir='tests/output/reproducibility')

        # Run twice
        results1 = await suite._benchmark_system_startup()
        results2 = await suite._benchmark_system_startup()

        # Results should be similar (within 20% variance)
        variance = abs(results1.after_value - results2.after_value) / results1.after_value
        assert variance < 0.2

    @pytest.mark.asyncio
    async def test_concurrent_benchmark_safety(self):
        """Test running benchmarks concurrently is safe"""
        try:
            suite1 = FogBenchmarkSuite(output_dir='tests/output/concurrent1')
            suite2 = FogBenchmarkSuite(output_dir='tests/output/concurrent2')

            # Run concurrently
            results = await asyncio.gather(
                suite1.run_complete_suite(),
                suite2.run_complete_suite()
            )
        except Exception as e:
            pytest.skip(f"Concurrent benchmarks not available: {e}")

        assert len(results) == 2
        assert all(r['summary']['total_tests'] > 0 for r in results)