"""
Integration tests for Memory Profiler + Prometheus monitoring pipeline
Tests the complete flow: Profiler -> Exporter -> Prometheus metrics
"""

import asyncio
import pytest
import time
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, "../backend/server")
sys.path.insert(0, "../monitoring/exporters")

from services.memory_profiler import get_memory_profiler, MemoryProfiler
from memory_exporter import get_memory_exporter, MemoryMetricsExporter


@pytest.fixture
async def profiler_and_exporter():
    """Create profiler and exporter instances for integration testing"""
    profiler = MemoryProfiler(
        snapshot_interval=0.2,
        enable_tracemalloc=False,
        top_objects_count=5,
    )
    exporter = MemoryMetricsExporter(port=19202)  # Test port

    # Link them
    exporter.set_memory_profiler(profiler)

    # Start profiler only (exporter HTTP server not started in tests)
    await profiler.start_memory_profiler()

    yield profiler, exporter

    # Cleanup
    await exporter.stop()
    await profiler.stop_memory_profiler()


class TestMemoryMonitoringIntegration:
    """Integration tests for complete monitoring pipeline"""

    @pytest.mark.asyncio
    async def test_profiler_exporter_linkage(self, profiler_and_exporter):
        """Test profiler and exporter are properly linked"""
        profiler, exporter = profiler_and_exporter

        assert exporter._memory_profiler is not None
        assert exporter._memory_profiler == profiler

    @pytest.mark.asyncio
    async def test_metrics_collection_flow(self, profiler_and_exporter):
        """Test metrics flow from profiler to exporter"""
        profiler, exporter = profiler_and_exporter

        # Wait for snapshots to accumulate
        await asyncio.sleep(0.5)

        # Verify profiler collected snapshots
        assert len(profiler._snapshots) >= 2

        # Get metrics from profiler
        metrics = await profiler.get_memory_metrics()
        assert metrics.total_objects > 0
        assert metrics.heap_used_mb >= 0

        # Update exporter metrics
        await exporter._update_metrics()

        # Verify exporter updated Prometheus gauges
        assert exporter.heap_used_mb._value.get() >= 0
        assert exporter.total_objects._value.get() > 0

    @pytest.mark.asyncio
    async def test_baseline_drift_metrics(self, profiler_and_exporter):
        """Test baseline drift metrics are exported"""
        profiler, exporter = profiler_and_exporter

        # Wait for baseline to be established
        await asyncio.sleep(0.5)

        # Verify baseline exists
        assert profiler._baseline_snapshot is not None

        # Update exporter metrics
        await exporter._update_metrics()

        # Check drift metrics are set (may be 0 for short-running tests)
        assert hasattr(exporter, "baseline_drift_percent")
        assert hasattr(exporter, "baseline_drift_mb")

    @pytest.mark.asyncio
    async def test_leak_detection_to_metrics(self, profiler_and_exporter):
        """Test detected leaks appear in metrics"""
        profiler, exporter = profiler_and_exporter

        # Manually add a detected leak
        from services.memory_profiler import Leak

        leak = Leak(
            object_type="dict",
            initial_count=100,
            current_count=300,
            growth_count=200,
            growth_percent=200.0,
            severity="high",
        )
        profiler._detected_leaks.append(leak)

        # Update exporter metrics
        await exporter._update_metrics()

        # Verify leak count in metrics
        assert exporter.active_leaks._value.get() == 1

    @pytest.mark.asyncio
    async def test_gc_metrics_export(self, profiler_and_exporter):
        """Test GC metrics are properly exported"""
        profiler, exporter = profiler_and_exporter

        # Wait for snapshots
        await asyncio.sleep(0.5)

        # Get metrics
        metrics = await profiler.get_memory_metrics()

        # Update exporter
        await exporter._update_metrics()

        # Verify GC metrics
        assert exporter.gc_collections_gen0._value.get() >= 0
        assert exporter.gc_collections_gen1._value.get() >= 0
        assert exporter.gc_collections_gen2._value.get() >= 0

    @pytest.mark.asyncio
    async def test_object_type_metrics(self, profiler_and_exporter):
        """Test top object types are exported"""
        profiler, exporter = profiler_and_exporter

        # Wait for snapshots
        await asyncio.sleep(0.5)

        # Update exporter
        await exporter._update_metrics()

        # Verify object type metrics exist
        snapshots = profiler.get_snapshots(count=1)
        if snapshots:
            top_objects = snapshots[0].get("objects", {}).get("top_types", {})
            # Should have exported top 5
            assert len(top_objects) >= 1

    @pytest.mark.asyncio
    async def test_alert_integration(self, profiler_and_exporter):
        """Test alerts from profiler trigger callbacks"""
        profiler, exporter = profiler_and_exporter

        alert_received = False
        received_alert = None

        def alert_callback(alert):
            nonlocal alert_received, received_alert
            alert_received = True
            received_alert = alert

        profiler.register_alert_callback(alert_callback)

        # Manually trigger threshold check with high values
        from services.memory_profiler import MemorySnapshot

        high_memory_snapshot = MemorySnapshot(heap_percent=92.0)
        await profiler._check_thresholds(high_memory_snapshot)

        # Verify alert was triggered
        assert alert_received is True
        assert received_alert is not None
        assert received_alert["type"] == "memory_critical"

    @pytest.mark.asyncio
    async def test_continuous_monitoring_cycle(self, profiler_and_exporter):
        """Test continuous monitoring over time"""
        profiler, exporter = profiler_and_exporter

        # Collect data over multiple cycles
        await asyncio.sleep(1.0)

        # Verify continuous collection
        assert len(profiler._snapshots) >= 4

        # Get snapshots and verify timestamps are sequential
        snapshots = profiler.get_snapshots()
        timestamps = [s["timestamp"] for s in snapshots]

        for i in range(len(timestamps) - 1):
            assert timestamps[i] < timestamps[i + 1], "Timestamps should be sequential"

    @pytest.mark.asyncio
    async def test_metrics_accuracy(self, profiler_and_exporter):
        """Test metrics are accurate and within expected ranges"""
        profiler, exporter = profiler_and_exporter

        await asyncio.sleep(0.5)

        metrics = await profiler.get_memory_metrics()

        # Verify metrics are within reasonable ranges
        assert 0 <= metrics.heap_percent <= 100, "Heap percent should be 0-100"
        assert metrics.heap_used_mb >= 0, "Heap used should be non-negative"
        assert metrics.total_objects > 0, "Should have some objects"
        assert metrics.gc_collections_gen0 >= 0, "GC count should be non-negative"

    @pytest.mark.asyncio
    async def test_baseline_comparison_integration(self, profiler_and_exporter):
        """Test baseline comparison over monitoring period"""
        profiler, exporter = profiler_and_exporter

        # Wait for baseline and additional snapshots
        await asyncio.sleep(0.8)

        # Get drift report
        drift = await profiler.compare_to_baseline()

        # Verify drift report structure
        assert drift.heap_drift_mb is not None
        assert drift.heap_drift_percent is not None
        assert drift.object_drift is not None
        assert isinstance(drift.significant_drifts, list)

    @pytest.mark.asyncio
    async def test_memory_growth_detection(self, profiler_and_exporter):
        """Test memory growth detection over time"""
        profiler, exporter = profiler_and_exporter

        # Record initial state
        initial_snapshot = await profiler.take_snapshot()
        initial_memory = initial_snapshot.heap_used_mb

        # Wait and take another snapshot
        await asyncio.sleep(0.5)
        final_snapshot = await profiler.take_snapshot()
        final_memory = final_snapshot.heap_used_mb

        # Verify we can measure memory changes
        # (May be small or zero for short test duration)
        assert final_memory >= 0
        assert initial_memory >= 0

    @pytest.mark.asyncio
    async def test_exporter_stats(self, profiler_and_exporter):
        """Test exporter statistics"""
        profiler, exporter = profiler_and_exporter

        stats = exporter.get_stats()

        assert "running" in stats
        assert "port" in stats
        assert "profiler_registered" in stats

        assert stats["profiler_registered"] is True
        assert stats["port"] == 19202

    @pytest.mark.asyncio
    async def test_profiler_restart(self, profiler_and_exporter):
        """Test profiler can be stopped and restarted"""
        profiler, exporter = profiler_and_exporter

        # Already started in fixture
        assert profiler._running is True

        # Stop
        await profiler.stop_memory_profiler()
        assert profiler._running is False

        # Restart
        await profiler.start_memory_profiler()
        assert profiler._running is True

        # Verify still works
        await asyncio.sleep(0.3)
        assert len(profiler._snapshots) >= 1


class TestMonitoringEdgeCases:
    """Test edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_exporter_without_profiler(self):
        """Test exporter fails gracefully without profiler"""
        exporter = MemoryMetricsExporter(port=19203)

        # Should raise error when starting without profiler
        with pytest.raises(RuntimeError, match="Memory profiler not set"):
            await exporter.start()

    @pytest.mark.asyncio
    async def test_multiple_start_calls(self):
        """Test multiple start calls don't cause issues"""
        profiler = MemoryProfiler(snapshot_interval=0.2, enable_tracemalloc=False)

        await profiler.start_memory_profiler()
        assert profiler._running is True

        # Second start should warn but not crash
        await profiler.start_memory_profiler()
        assert profiler._running is True

        await profiler.stop_memory_profiler()

    @pytest.mark.asyncio
    async def test_stop_without_start(self):
        """Test stopping profiler that wasn't started"""
        profiler = MemoryProfiler(snapshot_interval=0.2, enable_tracemalloc=False)

        # Should not raise error
        await profiler.stop_memory_profiler()
        assert profiler._running is False

    @pytest.mark.asyncio
    async def test_metrics_with_no_snapshots(self):
        """Test getting metrics when no snapshots collected"""
        profiler = MemoryProfiler(snapshot_interval=0.2, enable_tracemalloc=False)

        # Get metrics without starting
        metrics = await profiler.get_memory_metrics()

        # Should still return valid metrics
        assert metrics.total_objects >= 0
        assert metrics.heap_used_mb >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
