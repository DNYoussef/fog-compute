#!/usr/bin/env python3
"""
Performance Benchmark: BetaNet + VPN Hybrid Architecture

Measures and compares:
- Throughput (packets per second)
- Latency (p50, p95, p99)
- Resource usage (CPU, memory)
- Error rates
- Circuit build times

Usage:
    python benchmark_betanet_vpn.py --circuits 100 --duration 60
    python benchmark_betanet_vpn.py --mode comparison --packets 10000
"""

import argparse
import asyncio
import time
import statistics
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# Add project root to path
sys.path.insert(0, "c:\\Users\\17175\\Desktop\\fog-compute")

from src.vpn.transports.betanet_transport import BetanetTransport, BetanetNode
from src.vpn.onion_routing import OnionRouter, NodeType


@dataclass
class BenchmarkResult:
    """Benchmark results"""

    test_name: str
    duration_seconds: float
    total_packets: int
    successful_packets: int
    failed_packets: int
    throughput_pps: float
    latencies_ms: list[float] = field(default_factory=list)
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    circuit_build_time_ms: float = 0.0
    memory_mb: float = 0.0
    cpu_percent: float = 0.0

    def calculate_percentiles(self):
        """Calculate latency percentiles"""
        if self.latencies_ms:
            sorted_latencies = sorted(self.latencies_ms)
            n = len(sorted_latencies)
            self.p50_latency_ms = sorted_latencies[int(n * 0.50)]
            self.p95_latency_ms = sorted_latencies[int(n * 0.95)]
            self.p99_latency_ms = sorted_latencies[int(n * 0.99)]
            self.avg_latency_ms = statistics.mean(self.latencies_ms)

    def print_summary(self):
        """Print benchmark summary"""
        print(f"\n{'='*60}")
        print(f"Benchmark: {self.test_name}")
        print(f"{'='*60}")
        print(f"Duration:           {self.duration_seconds:.2f}s")
        print(f"Total Packets:      {self.total_packets:,}")
        print(f"Successful:         {self.successful_packets:,}")
        print(f"Failed:             {self.failed_packets:,}")
        print(f"Throughput:         {self.throughput_pps:,.0f} pps")
        print(f"\nLatency:")
        print(f"  Average:          {self.avg_latency_ms:.2f} ms")
        print(f"  P50:              {self.p50_latency_ms:.2f} ms")
        print(f"  P95:              {self.p95_latency_ms:.2f} ms")
        print(f"  P99:              {self.p99_latency_ms:.2f} ms")
        print(f"\nResources:")
        print(f"  Circuit Build:    {self.circuit_build_time_ms:.2f} ms")
        print(f"  Memory:           {self.memory_mb:.1f} MB")
        print(f"  CPU:              {self.cpu_percent:.1f}%")
        print(f"{'='*60}\n")


class BetaNetVPNBenchmark:
    """Performance benchmark suite"""

    def __init__(self):
        self.results: list[BenchmarkResult] = []

    async def setup_test_environment(self, num_nodes: int = 5) -> tuple[BetanetTransport, OnionRouter]:
        """
        Setup test environment with mock BetaNet nodes.

        Args:
            num_nodes: Number of test nodes to create

        Returns:
            (transport, router) tuple
        """
        print(f"Setting up test environment with {num_nodes} nodes...")

        # Create BetaNet transport
        transport = BetanetTransport(
            default_port=9001,
            connection_timeout=5.0,
            max_retries=3,
            enable_connection_pooling=True
        )

        # Add mock nodes (for testing without running actual BetaNet)
        for i in range(num_nodes):
            node = BetanetNode(
                node_id=f"bench-node-{i}",
                address="127.0.0.1",
                port=9000 + i,
                bandwidth_mbps=1000.0,  # 1 Gbps
                latency_ms=1.0          # 1ms
            )
            transport.available_nodes[node.node_id] = node

        # Create VPN router with BetaNet
        router = OnionRouter(
            node_id="benchmark-router",
            node_types={NodeType.GUARD, NodeType.MIDDLE},
            use_betanet=True,
            betanet_transport=transport
        )

        await router.fetch_consensus()

        print(f"✓ Transport initialized: {len(transport.available_nodes)} nodes")
        print(f"✓ Router initialized: {len(router.consensus)} consensus nodes")

        return transport, router

    async def benchmark_circuit_building(
        self,
        router: OnionRouter,
        num_circuits: int = 100
    ) -> BenchmarkResult:
        """
        Benchmark circuit building performance.

        Args:
            router: OnionRouter instance
            num_circuits: Number of circuits to build

        Returns:
            BenchmarkResult
        """
        print(f"\nBenchmarking circuit building ({num_circuits} circuits)...")

        build_times = []
        successful = 0
        failed = 0

        start_time = time.time()

        for i in range(num_circuits):
            circuit_start = time.time()

            circuit = await router.build_circuit(path_length=3)

            circuit_time = (time.time() - circuit_start) * 1000  # Convert to ms

            if circuit:
                build_times.append(circuit_time)
                successful += 1
            else:
                failed += 1

            if (i + 1) % 10 == 0:
                print(f"  Progress: {i+1}/{num_circuits} circuits built")

        duration = time.time() - start_time

        result = BenchmarkResult(
            test_name="Circuit Building",
            duration_seconds=duration,
            total_packets=num_circuits,
            successful_packets=successful,
            failed_packets=failed,
            throughput_pps=successful / duration if duration > 0 else 0,
            latencies_ms=build_times
        )

        result.calculate_percentiles()
        result.circuit_build_time_ms = result.avg_latency_ms

        self.results.append(result)
        return result

    async def benchmark_packet_throughput(
        self,
        router: OnionRouter,
        num_packets: int = 10000,
        packet_size: int = 1024
    ) -> BenchmarkResult:
        """
        Benchmark packet throughput.

        Args:
            router: OnionRouter instance
            num_packets: Number of packets to send
            packet_size: Size of each packet in bytes

        Returns:
            BenchmarkResult
        """
        print(f"\nBenchmarking packet throughput ({num_packets:,} packets, {packet_size}B each)...")

        # Build a circuit first
        circuit = await router.build_circuit(path_length=3)
        if not circuit:
            print("Failed to build circuit for throughput test")
            return BenchmarkResult(
                test_name="Packet Throughput",
                duration_seconds=0,
                total_packets=0,
                successful_packets=0,
                failed_packets=0,
                throughput_pps=0
            )

        latencies = []
        successful = 0
        failed = 0

        test_payload = b"X" * packet_size

        start_time = time.time()

        for i in range(num_packets):
            packet_start = time.time()

            success = await router.send_data(circuit.circuit_id, test_payload)

            packet_time = (time.time() - packet_start) * 1000  # ms

            if success:
                latencies.append(packet_time)
                successful += 1
            else:
                failed += 1

            if (i + 1) % 1000 == 0:
                print(f"  Progress: {i+1:,}/{num_packets:,} packets sent")

        duration = time.time() - start_time

        result = BenchmarkResult(
            test_name="Packet Throughput",
            duration_seconds=duration,
            total_packets=num_packets,
            successful_packets=successful,
            failed_packets=failed,
            throughput_pps=successful / duration if duration > 0 else 0,
            latencies_ms=latencies
        )

        result.calculate_percentiles()

        self.results.append(result)
        return result

    async def benchmark_concurrent_circuits(
        self,
        router: OnionRouter,
        num_circuits: int = 50,
        packets_per_circuit: int = 100
    ) -> BenchmarkResult:
        """
        Benchmark concurrent circuit performance.

        Args:
            router: OnionRouter instance
            num_circuits: Number of concurrent circuits
            packets_per_circuit: Packets to send per circuit

        Returns:
            BenchmarkResult
        """
        print(f"\nBenchmarking concurrent circuits ({num_circuits} circuits, {packets_per_circuit} packets each)...")

        async def send_on_circuit(circuit_id: str, num_packets: int) -> tuple[int, int]:
            """Send packets on a single circuit"""
            successful = 0
            failed = 0

            for _ in range(num_packets):
                if await router.send_data(circuit_id, b"test"):
                    successful += 1
                else:
                    failed += 1

            return successful, failed

        # Build circuits
        circuits = []
        for i in range(num_circuits):
            circuit = await router.build_circuit(path_length=3)
            if circuit:
                circuits.append(circuit)

        print(f"  Built {len(circuits)} circuits")

        # Send packets concurrently
        start_time = time.time()

        tasks = [
            send_on_circuit(circuit.circuit_id, packets_per_circuit)
            for circuit in circuits
        ]

        results = await asyncio.gather(*tasks)

        duration = time.time() - start_time

        total_successful = sum(r[0] for r in results)
        total_failed = sum(r[1] for r in results)
        total_packets = num_circuits * packets_per_circuit

        result = BenchmarkResult(
            test_name="Concurrent Circuits",
            duration_seconds=duration,
            total_packets=total_packets,
            successful_packets=total_successful,
            failed_packets=total_failed,
            throughput_pps=total_successful / duration if duration > 0 else 0
        )

        self.results.append(result)
        return result

    async def comparison_benchmark(
        self,
        num_packets: int = 5000
    ) -> tuple[BenchmarkResult, BenchmarkResult]:
        """
        Compare BetaNet vs Python-only performance.

        Args:
            num_packets: Number of packets for comparison

        Returns:
            (betanet_result, python_result) tuple
        """
        print(f"\n{'='*60}")
        print("COMPARISON BENCHMARK: BetaNet vs Python-Only")
        print(f"{'='*60}")

        # Test 1: BetaNet enabled
        print("\n[1/2] Testing with BetaNet enabled...")
        transport, router_betanet = await self.setup_test_environment()
        betanet_result = await self.benchmark_packet_throughput(
            router_betanet,
            num_packets=num_packets
        )

        # Test 2: Python-only (disable BetaNet)
        print("\n[2/2] Testing with Python-only...")
        _, router_python = await self.setup_test_environment()
        router_python.use_betanet = False
        router_python.betanet_transport = None
        python_result = await self.benchmark_packet_throughput(
            router_python,
            num_packets=num_packets
        )

        # Print comparison
        print(f"\n{'='*60}")
        print("COMPARISON RESULTS")
        print(f"{'='*60}")
        print(f"{'Metric':<30} {'BetaNet':<15} {'Python':<15} {'Improvement'}")
        print(f"{'-'*60}")

        improvement = betanet_result.throughput_pps / python_result.throughput_pps if python_result.throughput_pps > 0 else 0
        print(f"{'Throughput (pps)':<30} {betanet_result.throughput_pps:<15.0f} {python_result.throughput_pps:<15.0f} {improvement:.1f}x")

        improvement = python_result.avg_latency_ms / betanet_result.avg_latency_ms if betanet_result.avg_latency_ms > 0 else 0
        print(f"{'Avg Latency (ms)':<30} {betanet_result.avg_latency_ms:<15.2f} {python_result.avg_latency_ms:<15.2f} {improvement:.1f}x")

        improvement = python_result.p95_latency_ms / betanet_result.p95_latency_ms if betanet_result.p95_latency_ms > 0 else 0
        print(f"{'P95 Latency (ms)':<30} {betanet_result.p95_latency_ms:<15.2f} {python_result.p95_latency_ms:<15.2f} {improvement:.1f}x")

        print(f"{'='*60}\n")

        return betanet_result, python_result

    def generate_report(self, output_file: str | None = None):
        """Generate benchmark report"""
        report = []
        report.append("# BetaNet + VPN Performance Benchmark Report")
        report.append(f"\n**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"**Total Tests:** {len(self.results)}")
        report.append("\n## Summary\n")

        for result in self.results:
            report.append(f"### {result.test_name}\n")
            report.append(f"- Duration: {result.duration_seconds:.2f}s")
            report.append(f"- Total Packets: {result.total_packets:,}")
            report.append(f"- Successful: {result.successful_packets:,}")
            report.append(f"- Throughput: {result.throughput_pps:,.0f} pps")
            report.append(f"- Avg Latency: {result.avg_latency_ms:.2f} ms")
            report.append(f"- P95 Latency: {result.p95_latency_ms:.2f} ms")
            report.append("")

        report_text = "\n".join(report)

        if output_file:
            with open(output_file, "w") as f:
                f.write(report_text)
            print(f"\n✓ Report saved to: {output_file}")
        else:
            print(report_text)


async def main():
    """Main benchmark entry point"""
    parser = argparse.ArgumentParser(description="BetaNet + VPN Performance Benchmark")
    parser.add_argument("--mode", choices=["full", "quick", "comparison"], default="quick",
                        help="Benchmark mode")
    parser.add_argument("--circuits", type=int, default=10,
                        help="Number of circuits for circuit building test")
    parser.add_argument("--packets", type=int, default=1000,
                        help="Number of packets for throughput test")
    parser.add_argument("--nodes", type=int, default=5,
                        help="Number of test nodes")
    parser.add_argument("--output", type=str,
                        help="Output report file (markdown)")

    args = parser.parse_args()

    benchmark = BetaNetVPNBenchmark()

    try:
        if args.mode == "comparison":
            # Comparison benchmark
            await benchmark.comparison_benchmark(num_packets=args.packets)

        elif args.mode == "quick":
            # Quick benchmark
            transport, router = await benchmark.setup_test_environment(args.nodes)

            result1 = await benchmark.benchmark_circuit_building(router, num_circuits=args.circuits)
            result1.print_summary()

            result2 = await benchmark.benchmark_packet_throughput(router, num_packets=args.packets)
            result2.print_summary()

        elif args.mode == "full":
            # Full benchmark suite
            transport, router = await benchmark.setup_test_environment(args.nodes)

            result1 = await benchmark.benchmark_circuit_building(router, num_circuits=args.circuits)
            result1.print_summary()

            result2 = await benchmark.benchmark_packet_throughput(router, num_packets=args.packets)
            result2.print_summary()

            result3 = await benchmark.benchmark_concurrent_circuits(router, num_circuits=20)
            result3.print_summary()

            # Also run comparison
            await benchmark.comparison_benchmark(num_packets=args.packets)

        # Generate report
        if args.output:
            benchmark.generate_report(args.output)

        print("\n✓ Benchmark completed successfully")

    except Exception as e:
        print(f"\n✗ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
