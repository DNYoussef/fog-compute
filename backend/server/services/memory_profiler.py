"""
Memory Profiler Service - PERF-01
Tracks memory usage, detects leaks, and provides profiling insights

Features:
- Heap allocation tracking
- Object count monitoring
- GC frequency analysis
- Leak detection algorithm
- Baseline measurements
- Prometheus metrics integration
- Alert generation
"""

import asyncio
import gc
import logging
import sys
import time
import tracemalloc
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class MemorySnapshot:
    """Single point-in-time memory snapshot"""
    timestamp: datetime = field(default_factory=datetime.now)

    # Heap metrics
    heap_size_mb: float = 0.0
    heap_used_mb: float = 0.0
    heap_free_mb: float = 0.0
    heap_percent: float = 0.0

    # Object counts
    total_objects: int = 0
    top_objects: Dict[str, int] = field(default_factory=dict)

    # GC metrics
    gc_count: Tuple[int, int, int] = (0, 0, 0)
    gc_threshold: Tuple[int, int, int] = (0, 0, 0)

    # Tracemalloc metrics (if enabled)
    tracemalloc_current_mb: float = 0.0
    tracemalloc_peak_mb: float = 0.0
    tracemalloc_top_allocations: List[Dict[str, Any]] = field(default_factory=list)

    # Process metrics
    rss_mb: float = 0.0  # Resident Set Size
    vms_mb: float = 0.0  # Virtual Memory Size

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "heap": {
                "size_mb": round(self.heap_size_mb, 2),
                "used_mb": round(self.heap_used_mb, 2),
                "free_mb": round(self.heap_free_mb, 2),
                "percent": round(self.heap_percent, 2),
            },
            "objects": {
                "total": self.total_objects,
                "top_types": self.top_objects,
            },
            "gc": {
                "count": list(self.gc_count),
                "threshold": list(self.gc_threshold),
            },
            "tracemalloc": {
                "current_mb": round(self.tracemalloc_current_mb, 2),
                "peak_mb": round(self.tracemalloc_peak_mb, 2),
                "top_allocations": self.tracemalloc_top_allocations,
            },
            "process": {
                "rss_mb": round(self.rss_mb, 2),
                "vms_mb": round(self.vms_mb, 2),
            },
        }


@dataclass
class Leak:
    """Detected memory leak"""
    object_type: str
    initial_count: int
    current_count: int
    growth_count: int
    growth_percent: float
    detection_time: datetime = field(default_factory=datetime.now)
    severity: str = "medium"  # low, medium, high, critical

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "object_type": self.object_type,
            "initial_count": self.initial_count,
            "current_count": self.current_count,
            "growth_count": self.growth_count,
            "growth_percent": round(self.growth_percent, 2),
            "detection_time": self.detection_time.isoformat(),
            "severity": self.severity,
        }


@dataclass
class DriftReport:
    """Comparison between current snapshot and baseline"""
    baseline_timestamp: datetime
    current_timestamp: datetime

    heap_drift_mb: float
    heap_drift_percent: float

    object_drift: int
    object_drift_percent: float

    gc_frequency_change: float

    significant_drifts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "baseline_timestamp": self.baseline_timestamp.isoformat(),
            "current_timestamp": self.current_timestamp.isoformat(),
            "heap_drift_mb": round(self.heap_drift_mb, 2),
            "heap_drift_percent": round(self.heap_drift_percent, 2),
            "object_drift": self.object_drift,
            "object_drift_percent": round(self.object_drift_percent, 2),
            "gc_frequency_change": round(self.gc_frequency_change, 2),
            "significant_drifts": self.significant_drifts,
        }


@dataclass
class MemoryMetrics:
    """Current memory metrics for Prometheus export"""
    heap_size_mb: float
    heap_used_mb: float
    heap_percent: float
    total_objects: int
    gc_collections_gen0: int
    gc_collections_gen1: int
    gc_collections_gen2: int
    tracemalloc_current_mb: float
    tracemalloc_peak_mb: float
    rss_mb: float
    vms_mb: float
    active_leaks: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "heap_size_mb": self.heap_size_mb,
            "heap_used_mb": self.heap_used_mb,
            "heap_percent": self.heap_percent,
            "total_objects": self.total_objects,
            "gc_collections_gen0": self.gc_collections_gen0,
            "gc_collections_gen1": self.gc_collections_gen1,
            "gc_collections_gen2": self.gc_collections_gen2,
            "tracemalloc_current_mb": self.tracemalloc_current_mb,
            "tracemalloc_peak_mb": self.tracemalloc_peak_mb,
            "rss_mb": self.rss_mb,
            "vms_mb": self.vms_mb,
            "active_leaks": self.active_leaks,
        }


class MemoryProfiler:
    """
    Memory profiling service with leak detection and baseline tracking

    Tracks:
    - Heap allocations and usage
    - Object counts by type
    - GC frequency and collections
    - Memory growth trends
    - Leak detection
    """

    def __init__(
        self,
        snapshot_interval: float = 60.0,
        enable_tracemalloc: bool = True,
        top_objects_count: int = 20,
    ):
        self.snapshot_interval = snapshot_interval
        self.enable_tracemalloc = enable_tracemalloc
        self.top_objects_count = top_objects_count

        # State
        self._running = False
        self._profiler_task: Optional[asyncio.Task] = None

        # Snapshots
        self._snapshots: Deque[MemorySnapshot] = deque(maxlen=1000)
        self._baseline_snapshot: Optional[MemorySnapshot] = None

        # Leak detection
        self._detected_leaks: List[Leak] = []
        self._leak_callbacks: List[Callable[[Leak], None]] = []

        # Alert callbacks
        self._alert_callbacks: List[Callable[[Dict[str, Any]], None]] = []

        # Thresholds
        self.heap_warning_percent = 80.0
        self.heap_critical_percent = 90.0
        self.growth_rate_warning = 10.0  # % per hour
        self.gc_spike_threshold = 2.0  # multiplier

        # Metrics
        self._last_gc_count = (0, 0, 0)

        logger.info(
            f"MemoryProfiler initialized (interval={snapshot_interval}s, "
            f"tracemalloc={enable_tracemalloc})"
        )

    async def start_memory_profiler(self) -> None:
        """Start memory profiling"""
        if self._running:
            logger.warning("MemoryProfiler already running")
            return

        # Enable tracemalloc if requested
        if self.enable_tracemalloc and not tracemalloc.is_tracing():
            tracemalloc.start()
            logger.info("tracemalloc enabled")

        # Take initial baseline
        self._baseline_snapshot = await self.take_snapshot()
        logger.info("Baseline snapshot captured")

        # Start profiling loop
        self._running = True
        self._profiler_task = asyncio.create_task(self._profiling_loop())
        logger.info("Memory profiling started")

    async def stop_memory_profiler(self) -> None:
        """Stop memory profiling"""
        if not self._running:
            return

        self._running = False

        if self._profiler_task:
            self._profiler_task.cancel()
            try:
                await self._profiler_task
            except asyncio.CancelledError:
                pass
            self._profiler_task = None

        if self.enable_tracemalloc and tracemalloc.is_tracing():
            tracemalloc.stop()
            logger.info("tracemalloc disabled")

        logger.info("Memory profiling stopped")

    async def _profiling_loop(self) -> None:
        """Main profiling loop"""
        while self._running:
            try:
                # Take snapshot
                snapshot = await self.take_snapshot()
                self._snapshots.append(snapshot)

                # Check for leaks
                if len(self._snapshots) >= 5:
                    leaks = await self.detect_leaks(list(self._snapshots)[-10:])
                    for leak in leaks:
                        if leak not in self._detected_leaks:
                            self._detected_leaks.append(leak)
                            for callback in self._leak_callbacks:
                                try:
                                    callback(leak)
                                except Exception as e:
                                    logger.error(f"Error in leak callback: {e}")

                # Check thresholds
                await self._check_thresholds(snapshot)

                # Sleep
                await asyncio.sleep(self.snapshot_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in profiling loop: {e}")
                await asyncio.sleep(self.snapshot_interval)

    async def take_snapshot(self) -> MemorySnapshot:
        """Take a memory snapshot"""
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
        except ImportError:
            memory_info = None

        # Collect garbage to get accurate counts
        gc.collect()

        # Get all objects
        all_objects = gc.get_objects()
        total_objects = len(all_objects)

        # Count by type
        type_counts = defaultdict(int)
        for obj in all_objects:
            type_name = type(obj).__name__
            type_counts[type_name] += 1

        # Get top N types
        top_objects = dict(
            sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[
                : self.top_objects_count
            ]
        )

        # GC stats
        gc_count = gc.get_count()
        gc_threshold = gc.get_threshold()

        # Tracemalloc stats
        tracemalloc_current_mb = 0.0
        tracemalloc_peak_mb = 0.0
        tracemalloc_top_allocations = []

        if self.enable_tracemalloc and tracemalloc.is_tracing():
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc_current_mb = current / (1024 * 1024)
            tracemalloc_peak_mb = peak / (1024 * 1024)

            # Get top allocations
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')[:10]

            tracemalloc_top_allocations = [
                {
                    "file": stat.traceback.format()[0] if stat.traceback else "unknown",
                    "size_mb": round(stat.size / (1024 * 1024), 3),
                    "count": stat.count,
                }
                for stat in top_stats
            ]

        # Memory stats (rough approximation)
        heap_size_mb = sys.getsizeof(all_objects) / (1024 * 1024)

        # Process memory
        rss_mb = memory_info.rss / (1024 * 1024) if memory_info else 0.0
        vms_mb = memory_info.vms / (1024 * 1024) if memory_info else 0.0

        # Calculate heap percent (using RSS as reference)
        heap_percent = (rss_mb / 1024) * 100 if rss_mb > 0 else 0.0

        snapshot = MemorySnapshot(
            heap_size_mb=heap_size_mb,
            heap_used_mb=rss_mb,
            heap_free_mb=vms_mb - rss_mb if vms_mb > rss_mb else 0.0,
            heap_percent=min(heap_percent, 100.0),
            total_objects=total_objects,
            top_objects=top_objects,
            gc_count=gc_count,
            gc_threshold=gc_threshold,
            tracemalloc_current_mb=tracemalloc_current_mb,
            tracemalloc_peak_mb=tracemalloc_peak_mb,
            tracemalloc_top_allocations=tracemalloc_top_allocations,
            rss_mb=rss_mb,
            vms_mb=vms_mb,
        )

        return snapshot

    async def detect_leaks(
        self, snapshots: List[MemorySnapshot]
    ) -> List[Leak]:
        """
        Detect memory leaks from snapshot history

        Leak detection algorithm:
        1. Track object counts by type over time
        2. Identify types with consistent growth
        3. Calculate growth rate and severity
        4. Filter out expected growth patterns
        """
        if len(snapshots) < 3:
            return []

        leaks = []

        # Get initial and current snapshots
        initial = snapshots[0]
        current = snapshots[-1]

        # Track growth for each object type
        for obj_type, current_count in current.top_objects.items():
            initial_count = initial.top_objects.get(obj_type, 0)

            if initial_count == 0:
                continue

            growth_count = current_count - initial_count
            growth_percent = (growth_count / initial_count) * 100

            # Leak criteria:
            # - Growth > 50% over monitoring period
            # - Absolute growth > 100 objects
            # - Consistent growth trend (check intermediate snapshots)
            if growth_percent > 50 and growth_count > 100:
                # Check for consistent growth
                is_consistent = True
                prev_count = initial_count

                for snapshot in snapshots[1:]:
                    snap_count = snapshot.top_objects.get(obj_type, 0)
                    if snap_count < prev_count:
                        is_consistent = False
                        break
                    prev_count = snap_count

                if is_consistent:
                    # Determine severity
                    if growth_percent > 200:
                        severity = "critical"
                    elif growth_percent > 150:
                        severity = "high"
                    elif growth_percent > 100:
                        severity = "medium"
                    else:
                        severity = "low"

                    leak = Leak(
                        object_type=obj_type,
                        initial_count=initial_count,
                        current_count=current_count,
                        growth_count=growth_count,
                        growth_percent=growth_percent,
                        severity=severity,
                    )
                    leaks.append(leak)

        return leaks

    async def get_memory_metrics(self) -> MemoryMetrics:
        """Get current memory metrics for Prometheus export"""
        snapshot = await self.take_snapshot()

        return MemoryMetrics(
            heap_size_mb=snapshot.heap_size_mb,
            heap_used_mb=snapshot.heap_used_mb,
            heap_percent=snapshot.heap_percent,
            total_objects=snapshot.total_objects,
            gc_collections_gen0=snapshot.gc_count[0],
            gc_collections_gen1=snapshot.gc_count[1],
            gc_collections_gen2=snapshot.gc_count[2],
            tracemalloc_current_mb=snapshot.tracemalloc_current_mb,
            tracemalloc_peak_mb=snapshot.tracemalloc_peak_mb,
            rss_mb=snapshot.rss_mb,
            vms_mb=snapshot.vms_mb,
            active_leaks=len(self._detected_leaks),
        )

    async def compare_to_baseline(
        self, current: Optional[MemorySnapshot] = None
    ) -> DriftReport:
        """Compare current snapshot to baseline"""
        if not self._baseline_snapshot:
            raise ValueError("No baseline snapshot available")

        if current is None:
            current = await self.take_snapshot()

        baseline = self._baseline_snapshot

        # Calculate drifts
        heap_drift_mb = current.heap_used_mb - baseline.heap_used_mb
        heap_drift_percent = (
            (heap_drift_mb / baseline.heap_used_mb) * 100
            if baseline.heap_used_mb > 0
            else 0.0
        )

        object_drift = current.total_objects - baseline.total_objects
        object_drift_percent = (
            (object_drift / baseline.total_objects) * 100
            if baseline.total_objects > 0
            else 0.0
        )

        # GC frequency change
        time_delta = (current.timestamp - baseline.timestamp).total_seconds() / 3600
        gc_baseline = sum(baseline.gc_count)
        gc_current = sum(current.gc_count)
        gc_frequency_change = (
            ((gc_current - gc_baseline) / time_delta)
            if time_delta > 0
            else 0.0
        )

        # Identify significant drifts
        significant_drifts = []

        if heap_drift_percent > 20:
            significant_drifts.append(
                f"Heap usage increased by {heap_drift_percent:.1f}% ({heap_drift_mb:.1f} MB)"
            )

        if object_drift_percent > 30:
            significant_drifts.append(
                f"Object count increased by {object_drift_percent:.1f}% ({object_drift} objects)"
            )

        if gc_frequency_change > 10:
            significant_drifts.append(
                f"GC frequency increased by {gc_frequency_change:.1f} collections/hour"
            )

        return DriftReport(
            baseline_timestamp=baseline.timestamp,
            current_timestamp=current.timestamp,
            heap_drift_mb=heap_drift_mb,
            heap_drift_percent=heap_drift_percent,
            object_drift=object_drift,
            object_drift_percent=object_drift_percent,
            gc_frequency_change=gc_frequency_change,
            significant_drifts=significant_drifts,
        )

    async def _check_thresholds(self, snapshot: MemorySnapshot) -> None:
        """Check memory thresholds and trigger alerts"""
        alerts = []

        # Heap usage alerts
        if snapshot.heap_percent >= self.heap_critical_percent:
            alerts.append({
                "type": "memory_critical",
                "severity": "critical",
                "message": f"Heap usage critical: {snapshot.heap_percent:.1f}%",
                "value": snapshot.heap_percent,
                "threshold": self.heap_critical_percent,
                "timestamp": datetime.now().isoformat(),
            })
        elif snapshot.heap_percent >= self.heap_warning_percent:
            alerts.append({
                "type": "memory_warning",
                "severity": "warning",
                "message": f"Heap usage high: {snapshot.heap_percent:.1f}%",
                "value": snapshot.heap_percent,
                "threshold": self.heap_warning_percent,
                "timestamp": datetime.now().isoformat(),
            })

        # GC frequency spike
        current_gc = sum(snapshot.gc_count)
        prev_gc = sum(self._last_gc_count)

        if prev_gc > 0 and current_gc > prev_gc * self.gc_spike_threshold:
            alerts.append({
                "type": "gc_spike",
                "severity": "warning",
                "message": f"GC frequency spike detected: {current_gc - prev_gc} collections",
                "value": current_gc - prev_gc,
                "threshold": prev_gc * self.gc_spike_threshold,
                "timestamp": datetime.now().isoformat(),
            })

        self._last_gc_count = snapshot.gc_count

        # Growth rate check (if we have enough history)
        if len(self._snapshots) >= 2:
            hour_ago = datetime.now() - timedelta(hours=1)
            recent_snapshots = [
                s for s in self._snapshots if s.timestamp >= hour_ago
            ]

            if len(recent_snapshots) >= 2:
                first = recent_snapshots[0]
                last = recent_snapshots[-1]

                if first.heap_used_mb > 0:
                    growth_percent = (
                        (last.heap_used_mb - first.heap_used_mb) / first.heap_used_mb
                    ) * 100

                    if growth_percent > self.growth_rate_warning:
                        alerts.append({
                            "type": "memory_growth",
                            "severity": "warning",
                            "message": f"High memory growth rate: {growth_percent:.1f}% per hour",
                            "value": growth_percent,
                            "threshold": self.growth_rate_warning,
                            "timestamp": datetime.now().isoformat(),
                        })

        # Trigger alert callbacks
        for alert in alerts:
            for callback in self._alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    logger.error(f"Error in alert callback: {e}")

    def register_leak_callback(self, callback: Callable[[Leak], None]) -> None:
        """Register callback for leak detection"""
        self._leak_callbacks.append(callback)

    def register_alert_callback(
        self, callback: Callable[[Dict[str, Any]], None]
    ) -> None:
        """Register callback for alerts"""
        self._alert_callbacks.append(callback)

    def get_snapshots(
        self, count: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get recent snapshots"""
        snapshots = list(self._snapshots)
        if count:
            snapshots = snapshots[-count:]
        return [s.to_dict() for s in snapshots]

    def get_baseline_snapshot(self) -> Optional[Dict[str, Any]]:
        """Get baseline snapshot"""
        if self._baseline_snapshot:
            return self._baseline_snapshot.to_dict()
        return None

    def get_detected_leaks(self) -> List[Dict[str, Any]]:
        """Get all detected leaks"""
        return [leak.to_dict() for leak in self._detected_leaks]

    def reset_baseline(self) -> None:
        """Reset baseline to current snapshot"""
        if self._snapshots:
            self._baseline_snapshot = self._snapshots[-1]
            logger.info("Baseline reset to current snapshot")

    def clear_detected_leaks(self) -> None:
        """Clear detected leaks list"""
        self._detected_leaks.clear()
        logger.info("Detected leaks cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get profiler statistics"""
        return {
            "running": self._running,
            "snapshot_interval": self.snapshot_interval,
            "tracemalloc_enabled": self.enable_tracemalloc and tracemalloc.is_tracing(),
            "total_snapshots": len(self._snapshots),
            "baseline_set": self._baseline_snapshot is not None,
            "detected_leaks": len(self._detected_leaks),
            "thresholds": {
                "heap_warning_percent": self.heap_warning_percent,
                "heap_critical_percent": self.heap_critical_percent,
                "growth_rate_warning": self.growth_rate_warning,
                "gc_spike_threshold": self.gc_spike_threshold,
            },
        }


# Singleton instance
_profiler = MemoryProfiler()


def get_memory_profiler() -> MemoryProfiler:
    """Get the singleton MemoryProfiler instance"""
    return _profiler
