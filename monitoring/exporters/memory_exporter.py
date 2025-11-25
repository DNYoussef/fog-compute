"""
Memory Profiler Prometheus Exporter
Exposes memory profiling metrics in Prometheus format
"""

import asyncio
import logging
import time
from typing import Optional

from prometheus_client import Counter, Gauge, Histogram, Info, start_http_server

logger = logging.getLogger(__name__)


class MemoryMetricsExporter:
    """Prometheus exporter for memory profiler metrics"""

    def __init__(self, port: int = 9202):
        self.port = port

        # Gauge metrics
        self.heap_size_mb = Gauge(
            "fogcompute_memory_heap_size_mb",
            "Total heap size in megabytes",
        )
        self.heap_used_mb = Gauge(
            "fogcompute_memory_heap_used_mb",
            "Used heap memory in megabytes",
        )
        self.heap_percent = Gauge(
            "fogcompute_memory_heap_percent",
            "Heap usage percentage",
        )
        self.total_objects = Gauge(
            "fogcompute_memory_total_objects",
            "Total number of objects in memory",
        )

        # GC metrics
        self.gc_collections = Counter(
            "fogcompute_memory_gc_collections_total",
            "Total garbage collections",
            ["generation"],
        )
        self.gc_collections_gen0 = Gauge(
            "fogcompute_memory_gc_collections_gen0",
            "Generation 0 garbage collections",
        )
        self.gc_collections_gen1 = Gauge(
            "fogcompute_memory_gc_collections_gen1",
            "Generation 1 garbage collections",
        )
        self.gc_collections_gen2 = Gauge(
            "fogcompute_memory_gc_collections_gen2",
            "Generation 2 garbage collections",
        )

        # Tracemalloc metrics
        self.tracemalloc_current_mb = Gauge(
            "fogcompute_memory_tracemalloc_current_mb",
            "Current traced memory in megabytes",
        )
        self.tracemalloc_peak_mb = Gauge(
            "fogcompute_memory_tracemalloc_peak_mb",
            "Peak traced memory in megabytes",
        )

        # Process metrics
        self.rss_mb = Gauge(
            "fogcompute_memory_rss_mb",
            "Resident Set Size in megabytes",
        )
        self.vms_mb = Gauge(
            "fogcompute_memory_vms_mb",
            "Virtual Memory Size in megabytes",
        )

        # Leak metrics
        self.active_leaks = Gauge(
            "fogcompute_memory_active_leaks",
            "Number of active memory leaks detected",
        )
        self.leak_detections = Counter(
            "fogcompute_memory_leak_detections_total",
            "Total number of leak detections",
            ["severity"],
        )

        # Baseline drift metrics
        self.baseline_drift_percent = Gauge(
            "fogcompute_memory_baseline_drift_percent",
            "Memory drift from baseline in percent",
        )
        self.baseline_drift_mb = Gauge(
            "fogcompute_memory_baseline_drift_mb",
            "Memory drift from baseline in megabytes",
        )

        # Object type metrics (top 5)
        self.object_counts = Gauge(
            "fogcompute_memory_object_count",
            "Count of objects by type",
            ["object_type"],
        )

        # Exporter info
        self.exporter_info = Info(
            "fogcompute_memory_exporter",
            "Memory profiler exporter information",
        )

        # State
        self._memory_profiler: Optional[object] = None
        self._running = False
        self._update_task: Optional[asyncio.Task] = None

        logger.info(f"MemoryMetricsExporter initialized (port={port})")

    def set_memory_profiler(self, profiler) -> None:
        """Set the memory profiler instance"""
        self._memory_profiler = profiler
        logger.info("Memory profiler instance registered")

    async def start(self) -> None:
        """Start the Prometheus exporter"""
        if self._running:
            logger.warning("Exporter already running")
            return

        if not self._memory_profiler:
            raise RuntimeError("Memory profiler not set. Call set_memory_profiler() first")

        # Start Prometheus HTTP server
        start_http_server(self.port)
        logger.info(f"Prometheus metrics server started on port {self.port}")

        # Set exporter info
        self.exporter_info.info({
            "version": "1.0.0",
            "service": "fog-compute",
            "component": "memory-profiler",
        })

        # Start update loop
        self._running = True
        self._update_task = asyncio.create_task(self._update_loop())
        logger.info("Memory metrics exporter started")

    async def stop(self) -> None:
        """Stop the exporter"""
        if not self._running:
            return

        self._running = False

        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
            self._update_task = None

        logger.info("Memory metrics exporter stopped")

    async def _update_loop(self) -> None:
        """Update metrics periodically"""
        while self._running:
            try:
                await self._update_metrics()
                await asyncio.sleep(15)  # Update every 15 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error updating metrics: {e}")
                await asyncio.sleep(15)

    async def _update_metrics(self) -> None:
        """Update all Prometheus metrics from memory profiler"""
        if not self._memory_profiler:
            return

        try:
            # Get current metrics
            metrics = await self._memory_profiler.get_memory_metrics()
            metrics_dict = metrics.to_dict()

            # Update gauges
            self.heap_size_mb.set(metrics_dict["heap_size_mb"])
            self.heap_used_mb.set(metrics_dict["heap_used_mb"])
            self.heap_percent.set(metrics_dict["heap_percent"])
            self.total_objects.set(metrics_dict["total_objects"])

            # GC metrics
            self.gc_collections_gen0.set(metrics_dict["gc_collections_gen0"])
            self.gc_collections_gen1.set(metrics_dict["gc_collections_gen1"])
            self.gc_collections_gen2.set(metrics_dict["gc_collections_gen2"])

            # Tracemalloc metrics
            self.tracemalloc_current_mb.set(metrics_dict["tracemalloc_current_mb"])
            self.tracemalloc_peak_mb.set(metrics_dict["tracemalloc_peak_mb"])

            # Process metrics
            self.rss_mb.set(metrics_dict["rss_mb"])
            self.vms_mb.set(metrics_dict["vms_mb"])

            # Leak metrics
            self.active_leaks.set(metrics_dict["active_leaks"])

            # Get detected leaks for severity breakdown
            leaks = self._memory_profiler.get_detected_leaks()
            for leak in leaks:
                self.leak_detections.labels(severity=leak["severity"]).inc(0)

            # Baseline drift (if available)
            try:
                if self._memory_profiler._baseline_snapshot:
                    drift_report = await self._memory_profiler.compare_to_baseline()
                    drift_dict = drift_report.to_dict()

                    self.baseline_drift_percent.set(drift_dict["heap_drift_percent"])
                    self.baseline_drift_mb.set(drift_dict["heap_drift_mb"])
            except Exception as e:
                logger.debug(f"Could not calculate baseline drift: {e}")

            # Top object types (get latest snapshot)
            snapshots = self._memory_profiler.get_snapshots(count=1)
            if snapshots:
                latest = snapshots[0]
                top_objects = latest.get("objects", {}).get("top_types", {})

                # Clear previous object type metrics
                self.object_counts._metrics.clear()

                # Update top 5 object types
                for obj_type, count in list(top_objects.items())[:5]:
                    self.object_counts.labels(object_type=obj_type).set(count)

        except Exception as e:
            logger.error(f"Error in _update_metrics: {e}")

    def get_stats(self) -> dict:
        """Get exporter statistics"""
        return {
            "running": self._running,
            "port": self.port,
            "profiler_registered": self._memory_profiler is not None,
        }


# Singleton instance
_exporter = MemoryMetricsExporter()


def get_memory_exporter() -> MemoryMetricsExporter:
    """Get the singleton MemoryMetricsExporter instance"""
    return _exporter


# Standalone server for testing
async def main():
    """Run standalone memory exporter server"""
    import sys
    sys.path.insert(0, "../../backend/server")

    from services.memory_profiler import get_memory_profiler

    # Initialize profiler and exporter
    profiler = get_memory_profiler()
    exporter = get_memory_exporter()

    # Link them
    exporter.set_memory_profiler(profiler)

    # Start both
    await profiler.start_memory_profiler()
    await exporter.start()

    logger.info("Memory profiler and exporter running. Press Ctrl+C to stop.")

    try:
        # Run indefinitely
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await exporter.stop()
        await profiler.stop_memory_profiler()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(main())
