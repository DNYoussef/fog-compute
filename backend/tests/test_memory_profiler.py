"""
Tests for Memory Profiler Service - PERF-01
Tests memory profiling, leak detection, and baseline comparison
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from server.services.memory_profiler import (
    MemoryProfiler,
    MemorySnapshot,
    MemoryMetrics,
    Leak,
    DriftReport,
    get_memory_profiler,
)


class TestMemorySnapshot:
    """Tests for MemorySnapshot dataclass"""

    def test_snapshot_defaults(self):
        """Test MemorySnapshot has correct defaults"""
        snapshot = MemorySnapshot()

        assert snapshot.heap_size_mb == 0.0
        assert snapshot.heap_used_mb == 0.0
        assert snapshot.total_objects == 0
        assert snapshot.gc_count == (0, 0, 0)
        assert isinstance(snapshot.timestamp, datetime)
        assert snapshot.top_objects == {}

    def test_snapshot_to_dict(self):
        """Test MemorySnapshot serialization"""
        snapshot = MemorySnapshot(
            heap_size_mb=100.5,
            heap_used_mb=75.25,
            heap_free_mb=25.25,
            heap_percent=75.0,
            total_objects=10000,
            top_objects={"dict": 500, "list": 300},
            gc_count=(10, 5, 2),
            gc_threshold=(700, 10, 10),
            rss_mb=200.0,
            vms_mb=400.0,
        )

        data = snapshot.to_dict()

        assert data["heap"]["size_mb"] == 100.5
        assert data["heap"]["used_mb"] == 75.25
        assert data["heap"]["percent"] == 75.0
        assert data["objects"]["total"] == 10000
        assert data["objects"]["top_types"] == {"dict": 500, "list": 300}
        assert data["gc"]["count"] == [10, 5, 2]
        assert data["process"]["rss_mb"] == 200.0

    def test_snapshot_timestamp_serialization(self):
        """Test timestamp is properly serialized to ISO format"""
        snapshot = MemorySnapshot()
        data = snapshot.to_dict()

        # Should be valid ISO format
        parsed = datetime.fromisoformat(data["timestamp"])
        assert isinstance(parsed, datetime)


class TestLeak:
    """Tests for Leak dataclass"""

    def test_leak_creation(self):
        """Test Leak dataclass creation"""
        leak = Leak(
            object_type="dict",
            initial_count=100,
            current_count=200,
            growth_count=100,
            growth_percent=100.0,
            severity="high",
        )

        assert leak.object_type == "dict"
        assert leak.initial_count == 100
        assert leak.current_count == 200
        assert leak.growth_count == 100
        assert leak.growth_percent == 100.0
        assert leak.severity == "high"
        assert isinstance(leak.detection_time, datetime)

    def test_leak_to_dict(self):
        """Test Leak serialization"""
        leak = Leak(
            object_type="list",
            initial_count=50,
            current_count=150,
            growth_count=100,
            growth_percent=200.0,
            severity="critical",
        )

        data = leak.to_dict()

        assert data["object_type"] == "list"
        assert data["initial_count"] == 50
        assert data["current_count"] == 150
        assert data["growth_count"] == 100
        assert data["growth_percent"] == 200.0
        assert data["severity"] == "critical"
        assert "detection_time" in data


class TestDriftReport:
    """Tests for DriftReport dataclass"""

    def test_drift_report_creation(self):
        """Test DriftReport dataclass creation"""
        baseline_time = datetime.now() - timedelta(hours=1)
        current_time = datetime.now()

        report = DriftReport(
            baseline_timestamp=baseline_time,
            current_timestamp=current_time,
            heap_drift_mb=50.0,
            heap_drift_percent=25.0,
            object_drift=1000,
            object_drift_percent=10.0,
            gc_frequency_change=5.0,
            significant_drifts=["Heap usage increased"],
        )

        assert report.heap_drift_mb == 50.0
        assert report.heap_drift_percent == 25.0
        assert report.object_drift == 1000
        assert len(report.significant_drifts) == 1

    def test_drift_report_to_dict(self):
        """Test DriftReport serialization"""
        report = DriftReport(
            baseline_timestamp=datetime.now(),
            current_timestamp=datetime.now(),
            heap_drift_mb=25.5,
            heap_drift_percent=12.5,
            object_drift=500,
            object_drift_percent=5.0,
            gc_frequency_change=2.5,
        )

        data = report.to_dict()

        assert data["heap_drift_mb"] == 25.5
        assert data["heap_drift_percent"] == 12.5
        assert data["object_drift"] == 500
        assert "baseline_timestamp" in data
        assert "current_timestamp" in data


class TestMemoryProfiler:
    """Tests for MemoryProfiler service"""

    @pytest.fixture
    def profiler(self):
        """Fresh MemoryProfiler instance"""
        return MemoryProfiler(
            snapshot_interval=60.0,
            enable_tracemalloc=False,
            top_objects_count=10,
        )

    def test_profiler_initialization(self, profiler):
        """Test profiler initializes with correct defaults"""
        assert profiler.snapshot_interval == 60.0
        assert profiler.enable_tracemalloc is False
        assert profiler.top_objects_count == 10
        assert profiler._running is False
        assert profiler._baseline_snapshot is None

    def test_get_stats(self, profiler):
        """Test getting profiler statistics"""
        stats = profiler.get_stats()

        assert stats["running"] is False
        assert stats["snapshot_interval"] == 60.0
        assert stats["total_snapshots"] == 0
        assert stats["baseline_set"] is False
        assert stats["detected_leaks"] == 0
        assert "thresholds" in stats

    @pytest.mark.asyncio
    async def test_take_snapshot(self, profiler):
        """Test taking a memory snapshot"""
        # No mocking needed - psutil handles gracefully if not available
        snapshot = await profiler.take_snapshot()

        assert isinstance(snapshot, MemorySnapshot)
        assert snapshot.total_objects > 0
        # rss_mb will be 0 if psutil not available, > 0 if available
        assert snapshot.rss_mb >= 0
        assert len(snapshot.top_objects) <= 10

    @pytest.mark.asyncio
    async def test_get_memory_metrics(self, profiler):
        """Test getting memory metrics"""
        metrics = await profiler.get_memory_metrics()

        assert isinstance(metrics, MemoryMetrics)
        # rss_mb will be 0 if psutil not available, > 0 if available
        assert metrics.rss_mb >= 0
        assert metrics.active_leaks == 0

    def test_register_leak_callback(self, profiler):
        """Test registering leak callback"""
        callback = MagicMock()

        profiler.register_leak_callback(callback)

        assert callback in profiler._leak_callbacks

    def test_register_alert_callback(self, profiler):
        """Test registering alert callback"""
        callback = MagicMock()

        profiler.register_alert_callback(callback)

        assert callback in profiler._alert_callbacks

    def test_get_snapshots_empty(self, profiler):
        """Test getting snapshots when none exist"""
        snapshots = profiler.get_snapshots()

        assert snapshots == []

    def test_get_detected_leaks_empty(self, profiler):
        """Test getting detected leaks when none exist"""
        leaks = profiler.get_detected_leaks()

        assert leaks == []

    def test_clear_detected_leaks(self, profiler):
        """Test clearing detected leaks"""
        # Add a fake leak
        profiler._detected_leaks.append(
            Leak(
                object_type="test",
                initial_count=10,
                current_count=20,
                growth_count=10,
                growth_percent=100.0,
            )
        )

        assert len(profiler._detected_leaks) == 1

        profiler.clear_detected_leaks()

        assert len(profiler._detected_leaks) == 0


class TestLeakDetection:
    """Tests for memory leak detection"""

    @pytest.fixture
    def profiler(self):
        """Fresh MemoryProfiler instance"""
        return MemoryProfiler(enable_tracemalloc=False)

    @pytest.mark.asyncio
    async def test_detect_leaks_insufficient_snapshots(self, profiler):
        """Test leak detection with insufficient snapshots"""
        snapshots = [MemorySnapshot()]

        leaks = await profiler.detect_leaks(snapshots)

        assert leaks == []

    @pytest.mark.asyncio
    async def test_detect_leaks_no_growth(self, profiler):
        """Test leak detection with no object growth"""
        snapshots = [
            MemorySnapshot(top_objects={"dict": 100, "list": 50}),
            MemorySnapshot(top_objects={"dict": 100, "list": 50}),
            MemorySnapshot(top_objects={"dict": 100, "list": 50}),
        ]

        leaks = await profiler.detect_leaks(snapshots)

        assert leaks == []

    @pytest.mark.asyncio
    async def test_detect_leaks_with_growth(self, profiler):
        """Test leak detection with significant object growth"""
        # Create snapshots with consistent growth > 50% and > 100 objects
        snapshots = [
            MemorySnapshot(top_objects={"dict": 200, "list": 100}),
            MemorySnapshot(top_objects={"dict": 250, "list": 100}),
            MemorySnapshot(top_objects={"dict": 350, "list": 100}),
        ]

        leaks = await profiler.detect_leaks(snapshots)

        # Should detect dict as leaking (75% growth, 150 objects)
        assert len(leaks) >= 1
        dict_leak = next((l for l in leaks if l.object_type == "dict"), None)
        assert dict_leak is not None
        assert dict_leak.growth_percent > 50

    @pytest.mark.asyncio
    async def test_detect_leaks_inconsistent_growth(self, profiler):
        """Test leak detection ignores inconsistent growth patterns"""
        # Growth that goes down should not be detected as leak
        snapshots = [
            MemorySnapshot(top_objects={"dict": 200}),
            MemorySnapshot(top_objects={"dict": 150}),  # Goes down
            MemorySnapshot(top_objects={"dict": 400}),
        ]

        leaks = await profiler.detect_leaks(snapshots)

        # Should not detect as leak due to inconsistent pattern
        assert len([l for l in leaks if l.object_type == "dict"]) == 0


class TestBaselineComparison:
    """Tests for baseline drift comparison"""

    @pytest.fixture
    def profiler(self):
        """Fresh MemoryProfiler instance"""
        return MemoryProfiler(enable_tracemalloc=False)

    @pytest.mark.asyncio
    async def test_compare_to_baseline_no_baseline(self, profiler):
        """Test comparison fails without baseline"""
        with pytest.raises(ValueError, match="No baseline snapshot available"):
            await profiler.compare_to_baseline()

    @pytest.mark.asyncio
    async def test_compare_to_baseline_with_drift(self, profiler):
        """Test drift calculation between baseline and current"""
        # Set up baseline
        profiler._baseline_snapshot = MemorySnapshot(
            timestamp=datetime.now() - timedelta(hours=1),
            heap_used_mb=100.0,
            total_objects=10000,
            gc_count=(10, 5, 2),
        )

        # Current snapshot with drift
        current = MemorySnapshot(
            timestamp=datetime.now(),
            heap_used_mb=150.0,  # 50% increase
            total_objects=15000,  # 50% increase
            gc_count=(20, 10, 4),
        )

        report = await profiler.compare_to_baseline(current)

        assert isinstance(report, DriftReport)
        assert report.heap_drift_mb == 50.0
        assert report.heap_drift_percent == 50.0
        assert report.object_drift == 5000
        assert report.object_drift_percent == 50.0

    @pytest.mark.asyncio
    async def test_significant_drifts_detected(self, profiler):
        """Test significant drifts are reported"""
        profiler._baseline_snapshot = MemorySnapshot(
            timestamp=datetime.now() - timedelta(hours=1),
            heap_used_mb=100.0,
            total_objects=10000,
            gc_count=(10, 5, 2),
        )

        # Large drift current snapshot
        current = MemorySnapshot(
            timestamp=datetime.now(),
            heap_used_mb=300.0,  # 200% increase
            total_objects=30000,  # 200% increase
            gc_count=(100, 50, 20),
        )

        report = await profiler.compare_to_baseline(current)

        # Should have significant drifts flagged
        assert len(report.significant_drifts) > 0


class TestProfilerLifecycle:
    """Tests for profiler start/stop lifecycle"""

    @pytest.fixture
    def profiler(self):
        """Fresh MemoryProfiler instance"""
        return MemoryProfiler(
            snapshot_interval=0.1,  # Short interval for testing
            enable_tracemalloc=False,
        )

    @pytest.mark.asyncio
    async def test_start_profiler(self, profiler):
        """Test starting the profiler"""
        # No mocking needed - psutil handles gracefully if not available
        await profiler.start_memory_profiler()

        assert profiler._running is True
        assert profiler._baseline_snapshot is not None
        assert profiler._profiler_task is not None

        # Clean up
        await profiler.stop_memory_profiler()

    @pytest.mark.asyncio
    async def test_stop_profiler(self, profiler):
        """Test stopping the profiler"""
        await profiler.start_memory_profiler()
        await profiler.stop_memory_profiler()

        assert profiler._running is False
        assert profiler._profiler_task is None

    @pytest.mark.asyncio
    async def test_start_already_running(self, profiler):
        """Test starting when already running is safe"""
        await profiler.start_memory_profiler()
        await profiler.start_memory_profiler()  # Should not raise

        assert profiler._running is True

        await profiler.stop_memory_profiler()


class TestMemoryMetrics:
    """Tests for MemoryMetrics dataclass"""

    def test_metrics_to_dict(self):
        """Test MemoryMetrics serialization"""
        metrics = MemoryMetrics(
            heap_size_mb=100.0,
            heap_used_mb=75.0,
            heap_percent=75.0,
            total_objects=10000,
            gc_collections_gen0=100,
            gc_collections_gen1=50,
            gc_collections_gen2=10,
            tracemalloc_current_mb=50.0,
            tracemalloc_peak_mb=60.0,
            rss_mb=200.0,
            vms_mb=400.0,
            active_leaks=2,
        )

        data = metrics.to_dict()

        assert data["heap_size_mb"] == 100.0
        assert data["heap_used_mb"] == 75.0
        assert data["total_objects"] == 10000
        assert data["gc_collections_gen0"] == 100
        assert data["active_leaks"] == 2


class TestSingletonPattern:
    """Tests for singleton pattern"""

    def test_get_memory_profiler_returns_singleton(self):
        """Test get_memory_profiler returns singleton instance"""
        profiler1 = get_memory_profiler()
        profiler2 = get_memory_profiler()

        assert profiler1 is profiler2
        assert isinstance(profiler1, MemoryProfiler)
