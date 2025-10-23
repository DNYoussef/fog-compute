"""
Performance Profiler - Comprehensive profiling and bottleneck detection

Features:
- CPU profiling (cProfile integration)
- Memory profiling (tracemalloc)
- I/O profiling (disk, network)
- Bottleneck detection
- Performance reports (HTML output)
- Continuous profiling (production safe)
"""

import cProfile
import io
import logging
import pstats
import threading
import time
import tracemalloc
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import json

import psutil

logger = logging.getLogger(__name__)


class ProfilerMode(Enum):
    """Profiling modes"""
    CPU = "cpu"
    MEMORY = "memory"
    IO = "io"
    ALL = "all"


@dataclass
class ProfileEntry:
    """Single profiling entry"""
    timestamp: datetime
    mode: ProfilerMode
    duration_ms: float
    data: Dict[str, Any]


@dataclass
class Bottleneck:
    """Detected performance bottleneck"""
    category: str  # cpu, memory, disk, network
    severity: str  # low, medium, high, critical
    description: str
    metrics: Dict[str, Any]
    detected_at: datetime = field(default_factory=datetime.now)


class CPUProfiler:
    """CPU profiling using cProfile"""

    def __init__(self):
        self._profiler: Optional[cProfile.Profile] = None
        self._running = False
        self._stats: Optional[pstats.Stats] = None

    def start(self) -> None:
        """Start CPU profiling"""
        if not self._running:
            self._profiler = cProfile.Profile()
            self._profiler.enable()
            self._running = True
            logger.info("CPU profiling started")

    def stop(self) -> Dict[str, Any]:
        """Stop CPU profiling and return results"""
        if not self._running or not self._profiler:
            return {}

        self._profiler.disable()
        self._running = False

        # Get stats
        stream = io.StringIO()
        self._stats = pstats.Stats(self._profiler, stream=stream)
        self._stats.sort_stats('cumulative')

        # Extract top functions
        top_functions = []
        for func_info in list(self._stats.stats.items())[:10]:
            func, stats = func_info
            filename, line, func_name = func

            top_functions.append({
                "function": func_name,
                "file": filename,
                "line": line,
                "calls": stats[0],
                "total_time": stats[3],
                "cumulative_time": stats[3],
            })

        logger.info("CPU profiling stopped")

        return {
            "total_calls": self._stats.total_calls,
            "primitive_calls": self._stats.prim_calls,
            "top_functions": top_functions,
        }

    def get_report(self, top_n: int = 20) -> str:
        """Get formatted profiling report"""
        if not self._stats:
            return "No profiling data available"

        stream = io.StringIO()
        stats = pstats.Stats(self._profiler, stream=stream)
        stats.sort_stats('cumulative')
        stats.print_stats(top_n)

        return stream.getvalue()


class MemoryProfiler:
    """Memory profiling using tracemalloc"""

    def __init__(self):
        self._running = False
        self._snapshot_start: Optional[tracemalloc.Snapshot] = None
        self._snapshot_end: Optional[tracemalloc.Snapshot] = None

    def start(self) -> None:
        """Start memory profiling"""
        if not self._running:
            tracemalloc.start()
            self._snapshot_start = tracemalloc.take_snapshot()
            self._running = True
            logger.info("Memory profiling started")

    def stop(self) -> Dict[str, Any]:
        """Stop memory profiling and return results"""
        if not self._running:
            return {}

        self._snapshot_end = tracemalloc.take_snapshot()
        self._running = False

        # Compare snapshots
        if not self._snapshot_start or not self._snapshot_end:
            tracemalloc.stop()
            return {}

        top_stats = self._snapshot_end.compare_to(self._snapshot_start, 'lineno')

        # Extract top memory allocations
        top_allocations = []
        for stat in top_stats[:10]:
            top_allocations.append({
                "file": str(stat.traceback.format()[0]) if stat.traceback else "unknown",
                "size_kb": stat.size / 1024,
                "size_diff_kb": stat.size_diff / 1024,
                "count": stat.count,
                "count_diff": stat.count_diff,
            })

        tracemalloc.stop()
        logger.info("Memory profiling stopped")

        return {
            "top_allocations": top_allocations,
            "total_traced_memory_kb": tracemalloc.get_traced_memory()[0] / 1024 if self._running else 0,
        }


class IOProfiler:
    """I/O profiling for disk and network"""

    def __init__(self):
        self._running = False
        self._start_io: Optional[Dict[str, Any]] = None
        self._process = psutil.Process()

    def start(self) -> None:
        """Start I/O profiling"""
        if not self._running:
            self._start_io = {
                "disk": self._process.io_counters(),
                "net": psutil.net_io_counters(),
                "timestamp": time.time(),
            }
            self._running = True
            logger.info("I/O profiling started")

    def stop(self) -> Dict[str, Any]:
        """Stop I/O profiling and return results"""
        if not self._running or not self._start_io:
            return {}

        end_time = time.time()
        duration = end_time - self._start_io["timestamp"]

        try:
            end_disk = self._process.io_counters()
            end_net = psutil.net_io_counters()

            start_disk = self._start_io["disk"]
            start_net = self._start_io["net"]

            disk_read_mb = (end_disk.read_bytes - start_disk.read_bytes) / (1024 * 1024)
            disk_write_mb = (end_disk.write_bytes - start_disk.write_bytes) / (1024 * 1024)

            net_sent_mb = (end_net.bytes_sent - start_net.bytes_sent) / (1024 * 1024)
            net_recv_mb = (end_net.bytes_recv - start_net.bytes_recv) / (1024 * 1024)

            self._running = False
            logger.info("I/O profiling stopped")

            return {
                "duration_seconds": duration,
                "disk": {
                    "read_mb": round(disk_read_mb, 2),
                    "write_mb": round(disk_write_mb, 2),
                    "read_count": end_disk.read_count - start_disk.read_count,
                    "write_count": end_disk.write_count - start_disk.write_count,
                    "read_mbps": round(disk_read_mb / duration, 2) if duration > 0 else 0,
                    "write_mbps": round(disk_write_mb / duration, 2) if duration > 0 else 0,
                },
                "network": {
                    "sent_mb": round(net_sent_mb, 2),
                    "recv_mb": round(net_recv_mb, 2),
                    "packets_sent": end_net.packets_sent - start_net.packets_sent,
                    "packets_recv": end_net.packets_recv - start_net.packets_recv,
                    "sent_mbps": round(net_sent_mb / duration, 2) if duration > 0 else 0,
                    "recv_mbps": round(net_recv_mb / duration, 2) if duration > 0 else 0,
                },
            }

        except Exception as e:
            logger.error(f"Error in I/O profiling: {e}")
            self._running = False
            return {}


class BottleneckDetector:
    """Detect performance bottlenecks from profiling data"""

    @staticmethod
    def detect_cpu_bottlenecks(cpu_data: Dict[str, Any]) -> List[Bottleneck]:
        """Detect CPU bottlenecks"""
        bottlenecks = []

        # Check for hot functions
        if "top_functions" in cpu_data:
            for func in cpu_data["top_functions"][:3]:
                if func["cumulative_time"] > 1.0:  # More than 1 second
                    severity = "high" if func["cumulative_time"] > 5.0 else "medium"
                    bottlenecks.append(Bottleneck(
                        category="cpu",
                        severity=severity,
                        description=f"Hot function: {func['function']} consuming {func['cumulative_time']:.2f}s",
                        metrics=func,
                    ))

        return bottlenecks

    @staticmethod
    def detect_memory_bottlenecks(memory_data: Dict[str, Any]) -> List[Bottleneck]:
        """Detect memory bottlenecks"""
        bottlenecks = []

        # Check for large allocations
        if "top_allocations" in memory_data:
            for alloc in memory_data["top_allocations"][:3]:
                if alloc["size_diff_kb"] > 10 * 1024:  # More than 10 MB increase
                    severity = "high" if alloc["size_diff_kb"] > 50 * 1024 else "medium"
                    bottlenecks.append(Bottleneck(
                        category="memory",
                        severity=severity,
                        description=f"Large memory allocation: {alloc['size_diff_kb']:.2f} KB increase",
                        metrics=alloc,
                    ))

        return bottlenecks

    @staticmethod
    def detect_io_bottlenecks(io_data: Dict[str, Any]) -> List[Bottleneck]:
        """Detect I/O bottlenecks"""
        bottlenecks = []

        if "disk" in io_data:
            disk = io_data["disk"]

            # High disk I/O
            if disk["read_mbps"] > 100 or disk["write_mbps"] > 100:
                severity = "high" if max(disk["read_mbps"], disk["write_mbps"]) > 500 else "medium"
                bottlenecks.append(Bottleneck(
                    category="disk",
                    severity=severity,
                    description=f"High disk I/O: {disk['read_mbps']:.2f} MB/s read, {disk['write_mbps']:.2f} MB/s write",
                    metrics=disk,
                ))

        if "network" in io_data:
            net = io_data["network"]

            # High network I/O
            if net["sent_mbps"] > 50 or net["recv_mbps"] > 50:
                severity = "high" if max(net["sent_mbps"], net["recv_mbps"]) > 200 else "medium"
                bottlenecks.append(Bottleneck(
                    category="network",
                    severity=severity,
                    description=f"High network I/O: {net['sent_mbps']:.2f} MB/s sent, {net['recv_mbps']:.2f} MB/s received",
                    metrics=net,
                ))

        return bottlenecks


class PerformanceProfiler:
    """
    Comprehensive performance profiler

    Supports CPU, memory, and I/O profiling with bottleneck detection
    """

    def __init__(self, output_dir: str = "profiling_reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._cpu_profiler = CPUProfiler()
        self._memory_profiler = MemoryProfiler()
        self._io_profiler = IOProfiler()
        self._detector = BottleneckDetector()

        self._profile_history: List[ProfileEntry] = []
        self._active_modes: set = set()

        logger.info(f"PerformanceProfiler initialized (output: {self.output_dir})")

    def start(self, mode: ProfilerMode = ProfilerMode.ALL) -> None:
        """Start profiling"""
        if mode in (ProfilerMode.CPU, ProfilerMode.ALL):
            self._cpu_profiler.start()
            self._active_modes.add(ProfilerMode.CPU)

        if mode in (ProfilerMode.MEMORY, ProfilerMode.ALL):
            self._memory_profiler.start()
            self._active_modes.add(ProfilerMode.MEMORY)

        if mode in (ProfilerMode.IO, ProfilerMode.ALL):
            self._io_profiler.start()
            self._active_modes.add(ProfilerMode.IO)

        logger.info(f"Profiling started with mode: {mode.value}")

    def stop(self) -> Dict[str, Any]:
        """Stop profiling and return results"""
        start_time = time.time()
        results = {}

        if ProfilerMode.CPU in self._active_modes:
            results["cpu"] = self._cpu_profiler.stop()

        if ProfilerMode.MEMORY in self._active_modes:
            results["memory"] = self._memory_profiler.stop()

        if ProfilerMode.IO in self._active_modes:
            results["io"] = self._io_profiler.stop()

        duration_ms = (time.time() - start_time) * 1000

        # Detect bottlenecks
        bottlenecks = []
        if "cpu" in results:
            bottlenecks.extend(self._detector.detect_cpu_bottlenecks(results["cpu"]))
        if "memory" in results:
            bottlenecks.extend(self._detector.detect_memory_bottlenecks(results["memory"]))
        if "io" in results:
            bottlenecks.extend(self._detector.detect_io_bottlenecks(results["io"]))

        results["bottlenecks"] = [
            {
                "category": b.category,
                "severity": b.severity,
                "description": b.description,
                "metrics": b.metrics,
            }
            for b in bottlenecks
        ]

        # Record in history
        for mode in self._active_modes:
            self._profile_history.append(ProfileEntry(
                timestamp=datetime.now(),
                mode=mode,
                duration_ms=duration_ms,
                data=results,
            ))

        self._active_modes.clear()

        logger.info(f"Profiling stopped. Found {len(bottlenecks)} bottlenecks")

        return results

    def profile(self, func: Callable, mode: ProfilerMode = ProfilerMode.ALL) -> tuple[Any, Dict[str, Any]]:
        """Profile a function execution"""
        self.start(mode)
        result = func()
        profile_results = self.stop()

        return result, profile_results

    def generate_html_report(self, results: Dict[str, Any], filename: str = "profile_report.html") -> Path:
        """Generate HTML report from profiling results"""
        report_path = self.output_dir / filename

        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Performance Profile Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #333; }}
                h2 {{ color: #666; margin-top: 30px; }}
                .section {{ margin: 20px 0; padding: 15px; background: #f5f5f5; border-radius: 5px; }}
                table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
                th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #4CAF50; color: white; }}
                .severity-high {{ color: #f44336; font-weight: bold; }}
                .severity-medium {{ color: #ff9800; }}
                .severity-low {{ color: #2196F3; }}
                .metric {{ display: inline-block; margin: 10px; padding: 10px; background: white; border-radius: 3px; }}
            </style>
        </head>
        <body>
            <h1>Performance Profile Report</h1>
            <p>Generated: {timestamp}</p>
        """.format(timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        # Bottlenecks section
        if "bottlenecks" in results and results["bottlenecks"]:
            html += """
            <div class="section">
                <h2>🚨 Detected Bottlenecks</h2>
                <table>
                    <tr>
                        <th>Category</th>
                        <th>Severity</th>
                        <th>Description</th>
                    </tr>
            """
            for b in results["bottlenecks"]:
                severity_class = f"severity-{b['severity']}"
                html += f"""
                    <tr>
                        <td>{b['category'].upper()}</td>
                        <td class="{severity_class}">{b['severity'].upper()}</td>
                        <td>{b['description']}</td>
                    </tr>
                """
            html += """
                </table>
            </div>
            """

        # CPU section
        if "cpu" in results:
            cpu = results["cpu"]
            html += f"""
            <div class="section">
                <h2>💻 CPU Profile</h2>
                <div class="metric">Total Calls: {cpu.get('total_calls', 0)}</div>
                <div class="metric">Primitive Calls: {cpu.get('primitive_calls', 0)}</div>
            """

            if "top_functions" in cpu:
                html += """
                <h3>Top Functions by Time</h3>
                <table>
                    <tr>
                        <th>Function</th>
                        <th>File</th>
                        <th>Calls</th>
                        <th>Total Time (s)</th>
                    </tr>
                """
                for func in cpu["top_functions"][:10]:
                    html += f"""
                    <tr>
                        <td>{func['function']}</td>
                        <td>{func['file']}:{func['line']}</td>
                        <td>{func['calls']}</td>
                        <td>{func['total_time']:.4f}</td>
                    </tr>
                    """
                html += """
                </table>
                """

            html += "</div>"

        # Memory section
        if "memory" in results:
            memory = results["memory"]
            html += """
            <div class="section">
                <h2>🧠 Memory Profile</h2>
            """

            if "top_allocations" in memory:
                html += """
                <h3>Top Memory Allocations</h3>
                <table>
                    <tr>
                        <th>Location</th>
                        <th>Size (KB)</th>
                        <th>Size Diff (KB)</th>
                        <th>Count</th>
                    </tr>
                """
                for alloc in memory["top_allocations"][:10]:
                    html += f"""
                    <tr>
                        <td>{alloc['file']}</td>
                        <td>{alloc['size_kb']:.2f}</td>
                        <td>{alloc['size_diff_kb']:.2f}</td>
                        <td>{alloc['count']}</td>
                    </tr>
                    """
                html += """
                </table>
                """

            html += "</div>"

        # I/O section
        if "io" in results:
            io_data = results["io"]
            html += f"""
            <div class="section">
                <h2>📊 I/O Profile</h2>
                <p>Duration: {io_data.get('duration_seconds', 0):.2f} seconds</p>
            """

            if "disk" in io_data:
                disk = io_data["disk"]
                html += f"""
                <h3>Disk I/O</h3>
                <div class="metric">Read: {disk['read_mb']:.2f} MB ({disk['read_mbps']:.2f} MB/s)</div>
                <div class="metric">Write: {disk['write_mb']:.2f} MB ({disk['write_mbps']:.2f} MB/s)</div>
                <div class="metric">Read Ops: {disk['read_count']}</div>
                <div class="metric">Write Ops: {disk['write_count']}</div>
                """

            if "network" in io_data:
                net = io_data["network"]
                html += f"""
                <h3>Network I/O</h3>
                <div class="metric">Sent: {net['sent_mb']:.2f} MB ({net['sent_mbps']:.2f} MB/s)</div>
                <div class="metric">Received: {net['recv_mb']:.2f} MB ({net['recv_mbps']:.2f} MB/s)</div>
                <div class="metric">Packets Sent: {net['packets_sent']}</div>
                <div class="metric">Packets Received: {net['packets_recv']}</div>
                """

            html += "</div>"

        html += """
        </body>
        </html>
        """

        report_path.write_text(html, encoding="utf-8")
        logger.info(f"HTML report generated: {report_path}")

        return report_path

    def get_history(self, mode: Optional[ProfilerMode] = None) -> List[ProfileEntry]:
        """Get profiling history"""
        if mode is None:
            return self._profile_history

        return [e for e in self._profile_history if e.mode == mode]


# Singleton instance
_profiler = PerformanceProfiler()


def get_profiler() -> PerformanceProfiler:
    """Get the singleton PerformanceProfiler instance"""
    return _profiler
