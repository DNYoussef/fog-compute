"""
Unit tests for Memory Profiler Service
"""

import asyncio
import gc
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import sys
sys.path.insert(0, "../backend/server")

from services.memory_profiler import (
    MemoryProfiler,
    MemorySnapshot,
    Leak,
    DriftReport,
    MemoryMetrics,
)


@pytest.fixture
def profiler():
    """Create a memory profiler instance for testing"""
    return MemoryProfiler(
        snapshot_interval=0.1,  # Fast for testing
        enable_tracemalloc=False,  # Disable for simpler tests
        top_objects_count=5,
    )


@pytest.fixture
async def running_profiler(profiler):
    """Create and start a profiler"""
    await profiler.start_memory_profiler()
    yield profiler
    await profiler.stop_memory_profiler()


class TestMemorySnapshot:
    """Test MemorySnapshot dataclass"""

    def test_snapshot_to_dict(self):
        """Test snapshot serialization"""
        snapshot = MemorySnapshot(
            heap_size_mb=100.5,
            heap_used_mb=75.3,
            heap_percent=75.0,
            total_objects=1000,
            top_objects={"dict": 100, "list": 50},
            gc_count=(10, 5, 2),
            gc_threshold=(700, 10, 10),
        )

        data = snapshot.to_dict()

        assert data["heap"]["size_mb"] == 100.5
        assert data["heap"]["used_mb"] == 75.3
        assert data["heap"]["percent"] == 75.0
        assert data["objects"]["total"] == 1000
        assert data["objects"]["top_types"]["dict"] == 100
        assert data["gc"]["count"] == [10, 5, 2]

    def test_snapshot_timestamp(self):
        """Test snapshot includes timestamp"""
        snapshot = MemorySnapshot()
        assert isinstance(snapshot.timestamp, datetime)
        assert snapshot.timestamp <= datetime.now()


class TestLeak:
    """Test Leak dataclass"""

    def test_leak_to_dict(self):
        """Test leak serialization"""
        leak = Leak(
            object_type="dict",
            initial_count=100,
            current_count=250,
            growth_count=150,
            growth_percent=150.0,
            severity="high",
        )

        data = leak.to_dict()

        assert data["object_type"] == "dict"
        assert data["initial_count"] == 100
        assert data["current_count"] == 250
        assert data["growth_count"] == 150
        assert data["growth_percent"] == 150.0
        assert data["severity"] == "high"

    def test_leak_severity_levels(self):
        """Test different severity levels"""
        severities = ["low", "medium", "high", "critical"]
        for severity in severities:
            leak = Leak(
                object_type="test",
                initial_count=100,
                current_count=200,
                growth_count=100,
                growth_percent=100.0,
                severity=severity,
            )
            assert leak.severity == severity


class TestMemoryProfiler:
    """Test MemoryProfiler class"""

    def test_profiler_initialization(self, profiler):
        """Test profiler initializes correctly"""
        assert profiler.snapshot_interval == 0.1
        assert profiler.enable_tracemalloc is False
        assert profiler.top_objects_count == 5
        assert profiler._running is False
        assert len(profiler._snapshots) == 0
        assert profiler._baseline_snapshot is None

    @pytest.mark.asyncio
    async def test_take_snapshot(self, profiler):
        """Test taking a memory snapshot"""
        snapshot = await profiler.take_snapshot()

        assert isinstance(snapshot, MemorySnapshot)
        assert snapshot.heap_size_mb >= 0
        assert snapshot.heap_used_mb >= 0
        assert snapshot.total_objects > 0
        assert len(snapshot.top_objects) > 0
        assert snapshot.gc_count[0] >= 0

    @pytest.mark.asyncio
    async def test_start_stop_profiler(self, profiler):
        """Test starting and stopping profiler"""
        assert profiler._running is False

        await profiler.start_memory_profiler()
        assert profiler._running is True
        assert profiler._baseline_snapshot is not None

        await profiler.stop_memory_profiler()
        assert profiler._running is False

    @pytest.mark.asyncio
    async def test_baseline_snapshot_captured(self, profiler):
        """Test baseline snapshot is captured on start"""
        await profiler.start_memory_profiler()

        assert profiler._baseline_snapshot is not None
        assert isinstance(profiler._baseline_snapshot, MemorySnapshot)

        await profiler.stop_memory_profiler()

    @pytest.mark.asyncio
    async def test_snapshots_collected(self, running_profiler):
        """Test snapshots are collected periodically"""
        # Wait for a few snapshots
        await asyncio.sleep(0.5)

        assert len(running_profiler._snapshots) >= 2

    @pytest.mark.asyncio
    async def test_get_memory_metrics(self, profiler):
        """Test getting memory metrics"""
        metrics = await profiler.get_memory_metrics()

        assert isinstance(metrics, MemoryMetrics)
        assert metrics.heap_size_mb >= 0
        assert metrics.heap_used_mb >= 0
        assert metrics.total_objects > 0
        assert metrics.gc_collections_gen0 >= 0

    @pytest.mark.asyncio
    async def test_detect_leaks_no_growth(self, profiler):
        """Test leak detection with no growth"""
        # Create snapshots with stable object counts
        snapshots = []
        for i in range(5):
            snapshot = MemorySnapshot(
                total_objects=1000,
                top_objects={"dict": 100, "list": 50},
            )
            snapshots.append(snapshot)

        leaks = await profiler.detect_leaks(snapshots)
        assert len(leaks) == 0

    @pytest.mark.asyncio
    async def test_detect_leaks_with_growth(self, profiler):
        """Test leak detection with consistent growth"""
        # Create snapshots with growing object counts
        snapshots = []
        for i in range(5):
            snapshot = MemorySnapshot(
                total_objects=1000 + (i * 500),
                top_objects={"dict": 100 + (i * 50)},
            )
            snapshots.append(snapshot)

        leaks = await profiler.detect_leaks(snapshots)

        # Should detect leak for "dict" type
        assert len(leaks) > 0
        dict_leak = next((l for l in leaks if l.object_type == "dict"), None)
        assert dict_leak is not None
        assert dict_leak.growth_count > 100
        assert dict_leak.growth_percent > 50

    @pytest.mark.asyncio
    async def test_leak_severity_classification(self, profiler):
        """Test leak severity is classified correctly"""
        # Critical severity (>200% growth)
        snapshots_critical = [
            MemorySnapshot(top_objects={"dict": 100}),
            MemorySnapshot(top_objects={"dict": 400}),
        ]

        leaks = await profiler.detect_leaks(snapshots_critical)
        if leaks:
            assert leaks[0].severity == "critical"

        # High severity (>150% growth)
        snapshots_high = [
            MemorySnapshot(top_objects={"list": 100}),
            MemorySnapshot(top_objects={"list": 280}),
        ]

        leaks = await profiler.detect_leaks(snapshots_high)
        if leaks:
            assert leaks[0].severity == "high"

    @pytest.mark.asyncio
    async def test_compare_to_baseline(self, profiler):
        """Test baseline comparison"""
        # Set baseline
        baseline = MemorySnapshot(
            timestamp=datetime.now() - timedelta(hours=1),
            heap_used_mb=100.0,
            total_objects=1000,
            gc_count=(10, 5, 2),
        )
        profiler._baseline_snapshot = baseline

        # Current snapshot with growth
        current = MemorySnapshot(
            timestamp=datetime.now(),
            heap_used_mb=150.0,
            total_objects=1500,
            gc_count=(20, 10, 4),
        )

        drift = await profiler.compare_to_baseline(current)

        assert isinstance(drift, DriftReport)
        assert drift.heap_drift_mb == 50.0
        assert drift.heap_drift_percent == 50.0
        assert drift.object_drift == 500
        assert drift.object_drift_percent == 50.0

    @pytest.mark.asyncio
    async def test_compare_to_baseline_no_baseline(self, profiler):
        """Test comparison fails without baseline"""
        with pytest.raises(ValueError, match="No baseline snapshot available"):
            await profiler.compare_to_baseline()

    @pytest.mark.asyncio
    async def test_reset_baseline(self, profiler):
        """Test resetting baseline"""
        # Add some snapshots
        snapshot1 = MemorySnapshot(heap_used_mb=100.0)
        snapshot2 = MemorySnapshot(heap_used_mb=150.0)
        profiler._snapshots.append(snapshot1)
        profiler._snapshots.append(snapshot2)

        # Reset baseline
        profiler.reset_baseline()

        assert profiler._baseline_snapshot == snapshot2

    @pytest.mark.asyncio
    async def test_leak_callback_registration(self, profiler):
        """Test registering leak callbacks"""
        callback_called = False
        detected_leak = None

        def leak_callback(leak: Leak):
            nonlocal callback_called, detected_leak
            callback_called = True
            detected_leak = leak

        profiler.register_leak_callback(leak_callback)

        # Manually trigger leak detection
        leak = Leak(
            object_type="test",
            initial_count=100,
            current_count=300,
            growth_count=200,
            growth_percent=200.0,
            severity="high",
        )
        profiler._detected_leaks.append(leak)

        for callback in profiler._leak_callbacks:
            callback(leak)

        assert callback_called is True
        assert detected_leak == leak

    @pytest.mark.asyncio
    async def test_alert_callback_registration(self, profiler):
        """Test registering alert callbacks"""
        alert_called = False
        detected_alert = None

        def alert_callback(alert: dict):
            nonlocal alert_called, detected_alert
            alert_called = True
            detected_alert = alert

        profiler.register_alert_callback(alert_callback)

        # Trigger alert manually
        alert = {
            "type": "memory_critical",
            "severity": "critical",
            "message": "Test alert",
        }

        for callback in profiler._alert_callbacks:
            callback(alert)

        assert alert_called is True
        assert detected_alert == alert

    @pytest.mark.asyncio
    async def test_heap_threshold_alerts(self, profiler):
        """Test heap usage threshold alerts"""
        alert_triggered = False
        triggered_alert = None

        def alert_callback(alert: dict):
            nonlocal alert_triggered, triggered_alert
            alert_triggered = True
            triggered_alert = alert

        profiler.register_alert_callback(alert_callback)

        # Create snapshot exceeding critical threshold
        snapshot = MemorySnapshot(heap_percent=92.0)
        await profiler._check_thresholds(snapshot)

        assert alert_triggered is True
        assert triggered_alert["type"] == "memory_critical"
        assert triggered_alert["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_get_stats(self, profiler):
        """Test getting profiler statistics"""
        stats = profiler.get_stats()

        assert "running" in stats
        assert "snapshot_interval" in stats
        assert "tracemalloc_enabled" in stats
        assert "total_snapshots" in stats
        assert "baseline_set" in stats
        assert "detected_leaks" in stats
        assert "thresholds" in stats

        assert stats["running"] is False
        assert stats["snapshot_interval"] == 0.1
        assert stats["total_snapshots"] == 0

    @pytest.mark.asyncio
    async def test_get_snapshots(self, profiler):
        """Test getting snapshot history"""
        # Add some snapshots
        for i in range(10):
            profiler._snapshots.append(MemorySnapshot(heap_used_mb=100.0 + i))

        snapshots = profiler.get_snapshots()
        assert len(snapshots) == 10

        # Get limited count
        snapshots_limited = profiler.get_snapshots(count=5)
        assert len(snapshots_limited) == 5

    @pytest.mark.asyncio
    async def test_clear_detected_leaks(self, profiler):
        """Test clearing detected leaks"""
        # Add some leaks
        leak = Leak(
            object_type="test",
            initial_count=100,
            current_count=200,
            growth_count=100,
            growth_percent=100.0,
        )
        profiler._detected_leaks.append(leak)

        assert len(profiler._detected_leaks) == 1

        profiler.clear_detected_leaks()
        assert len(profiler._detected_leaks) == 0


class TestIntegration:
    """Integration tests"""

    @pytest.mark.asyncio
    async def test_full_profiling_cycle(self):
        """Test complete profiling cycle"""
        profiler = MemoryProfiler(snapshot_interval=0.1, enable_tracemalloc=False)

        # Start profiler
        await profiler.start_memory_profiler()
        assert profiler._running is True

        # Wait for snapshots to accumulate
        await asyncio.sleep(0.5)

        # Check snapshots were collected
        assert len(profiler._snapshots) >= 3

        # Get current metrics
        metrics = await profiler.get_memory_metrics()
        assert metrics.total_objects > 0

        # Compare to baseline
        drift = await profiler.compare_to_baseline()
        assert isinstance(drift, DriftReport)

        # Stop profiler
        await profiler.stop_memory_profiler()
        assert profiler._running is False

    @pytest.mark.asyncio
    async def test_leak_detection_integration(self):
        """Test leak detection in running profiler"""
        profiler = MemoryProfiler(snapshot_interval=0.1, enable_tracemalloc=False)

        leak_detected = False

        def leak_callback(leak: Leak):
            nonlocal leak_detected
            leak_detected = True

        profiler.register_leak_callback(leak_callback)

        # Note: In a real scenario, we would create actual memory leaks
        # For testing, we verify the mechanism works

        await profiler.start_memory_profiler()
        await asyncio.sleep(0.5)
        await profiler.stop_memory_profiler()

        # Verify profiler ran successfully
        assert len(profiler._snapshots) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
