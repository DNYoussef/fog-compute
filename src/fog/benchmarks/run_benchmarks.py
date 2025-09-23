"""
Main benchmark runner for fog compute infrastructure.
Supports multiple execution modes: full, quick, validation, and demo.
"""

import asyncio
import time
import argparse
import json
from pathlib import Path
from typing import Dict, Any
import sys

sys.path.append(str(Path(__file__).parent.parent))

from benchmark_suite import FogBenchmarkSuite
from utils import setup_logging


class BenchmarkRunner:
    """Orchestrator for fog compute benchmarks"""

    def __init__(self, output_dir: str = None, verbose: bool = False):
        self.output_dir = Path(output_dir or "fog-compute/reports")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.logger = setup_logging(self.output_dir, 'benchmark_runner', verbose)
        self.benchmark_suite = FogBenchmarkSuite(str(self.output_dir), verbose)

    async def run_full_suite(self) -> Dict[str, Any]:
        """Run complete benchmark validation"""
        self.logger.info("=" * 80)
        self.logger.info("FOG COMPUTE PERFORMANCE BENCHMARK SUITE - FULL MODE")
        self.logger.info("=" * 80)

        start_time = time.time()

        try:
            results = await self.benchmark_suite.run_complete_suite()

            execution_time = time.time() - start_time
            self._print_summary(results, execution_time)

            return {
                'mode': 'full',
                'success': True,
                'results': results,
                'execution_time': execution_time
            }

        except Exception as e:
            self.logger.error(f"Full suite failed: {e}")
            return {
                'mode': 'full',
                'success': False,
                'error': str(e),
                'execution_time': time.time() - start_time
            }

    async def run_quick_validation(self) -> Dict[str, Any]:
        """Run quick validation with core benchmarks only"""
        self.logger.info("=" * 80)
        self.logger.info("FOG COMPUTE QUICK VALIDATION MODE")
        self.logger.info("=" * 80)

        start_time = time.time()

        try:
            # Run subset of critical benchmarks
            results = await self.benchmark_suite.run_complete_suite()

            execution_time = time.time() - start_time

            return {
                'mode': 'quick',
                'success': True,
                'results': results,
                'execution_time': execution_time
            }

        except Exception as e:
            self.logger.error(f"Quick validation failed: {e}")
            return {
                'mode': 'quick',
                'success': False,
                'error': str(e),
                'execution_time': time.time() - start_time
            }

    async def run_demo_mode(self) -> Dict[str, Any]:
        """Run demo mode with simulated results"""
        self.logger.info("=" * 80)
        self.logger.info("FOG COMPUTE DEMO MODE")
        self.logger.info("=" * 80)

        print("\nRunning demo benchmarks...")
        print("-" * 40)

        demo_results = {
            'system': {
                'fog_coordinator': {'improvement': 72.5, 'target': 70.0, 'passed': True},
                'startup_time': {'value': 25.3, 'target': 30.0, 'passed': True},
                'device_registration': {'value': 1.65, 'target': 2.0, 'passed': True}
            },
            'privacy': {
                'onion_coordinator': {'improvement': 42.8, 'target': 40.0, 'passed': True},
                'task_routing': {'value': 2.8, 'target': 3.0, 'passed': True}
            },
            'graph': {
                'gap_detection': {'improvement': 55.2, 'target': 50.0, 'passed': True},
                'semantic_similarity': {'improvement': 63.4, 'target': 50.0, 'passed': True}
            },
            'integration': {
                'cross_service_latency': {'value': 42.3, 'target': 50.0, 'passed': True},
                'coordination_overhead': {'value': 8.7, 'target': 10.0, 'passed': True}
            }
        }

        await asyncio.sleep(1)  # Simulate processing

        self._print_demo_summary(demo_results)

        return {
            'mode': 'demo',
            'success': True,
            'demo_results': demo_results,
            'execution_time': 1.0
        }

    def _print_summary(self, results: Dict[str, Any], execution_time: float):
        """Print execution summary"""
        summary = results['summary']

        print("\n" + "=" * 80)
        print("BENCHMARK EXECUTION SUMMARY")
        print("=" * 80)

        print(f"Overall Grade: {summary['overall_grade']}")
        print(f"Tests Passed: {summary['passed_tests']}/{summary['total_tests']} ({summary['pass_rate']:.1f}%)")
        print(f"Total Execution Time: {execution_time:.1f} seconds")

        print(f"\nResults by Category:")
        for category, stats in summary['categories'].items():
            print(f"  {category.upper()}: {stats['passed']}/{stats['total']} passed, "
                  f"avg improvement: {stats['avg_improvement']:.1f}%")

        print("\n" + "=" * 80)

    def _print_demo_summary(self, demo_results: Dict[str, Any]):
        """Print demo execution summary"""
        print("\n" + "=" * 80)
        print("DEMO EXECUTION SUMMARY")
        print("=" * 80)

        print("\nKey Performance Achievements:")
        print(f"  - Fog Coordinator: 72.5% improvement (target: 70%)")
        print(f"  - Privacy Coordinator: 42.8% improvement (target: 40%)")
        print(f"  - Graph Processing: 55.2% improvement (target: 50%)")
        print(f"  - System Startup: 25.3s (target: <30s)")
        print(f"  - Device Registration: 1.65s (target: <2s)")

        print("\nOverall: All demo benchmarks PASSED")
        print("\n" + "=" * 80)
        print("Demo completed successfully!")
        print("Run full benchmark suite: python run_benchmarks.py --mode full")
        print("=" * 80)


async def main():
    """Main entry point"""

    parser = argparse.ArgumentParser(description='Fog Compute Performance Benchmarks')
    parser.add_argument('--mode', '-m', type=str, default='full',
                       choices=['full', 'quick', 'demo'],
                       help='Benchmark execution mode')
    parser.add_argument('--output-dir', '-o', type=str,
                       help='Output directory for benchmark results')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')

    args = parser.parse_args()

    runner = BenchmarkRunner(
        output_dir=args.output_dir,
        verbose=args.verbose
    )

    try:
        if args.mode == 'full':
            results = await runner.run_full_suite()
        elif args.mode == 'quick':
            results = await runner.run_quick_validation()
        elif args.mode == 'demo':
            results = await runner.run_demo_mode()

        if results['success']:
            print(f"\nBenchmark execution completed successfully!")
            if 'results' in results and 'summary' in results['results']:
                print(f"Overall Grade: {results['results']['summary']['overall_grade']}")
            sys.exit(0)
        else:
            print(f"\nBenchmark execution failed: {results.get('error', 'Unknown error')}")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\nBenchmark execution interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())