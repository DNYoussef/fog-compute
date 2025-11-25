# Memory Profiling API Documentation

## Overview

The Memory Profiling system (PERF-01) provides comprehensive memory monitoring, leak detection, and performance insights for the fog-compute backend.

**Features:**
- Real-time heap allocation tracking
- Object count monitoring by type
- Garbage collection frequency analysis
- Memory leak detection with severity classification
- Baseline measurements and drift detection
- Prometheus metrics integration
- Configurable alerting

## Architecture

```
+------------------+       +-------------------+       +------------------+
| Memory Profiler  | ----> | Metrics Exporter  | ----> | Prometheus       |
| (Python Service) |       | (HTTP Server)     |       | (Time Series DB) |
+------------------+       +-------------------+       +------------------+
        |                           |                           |
        v                           v                           v
  [Snapshots]              [Prometheus Metrics]           [Alert Rules]
  [Leak Detection]         [Gauges/Counters]              [AlertManager]
  [Baseline Tracking]      [Histograms]                   [Notifications]
```

## Components

### 1. Memory Profiler Service

**Location:** `backend/server/services/memory_profiler.py`

Core service that tracks memory usage and detects leaks.

#### Initialization

```python
from services.memory_profiler import get_memory_profiler

profiler = get_memory_profiler()

# Or create custom instance
from services.memory_profiler import MemoryProfiler

profiler = MemoryProfiler(
    snapshot_interval=60.0,      # Seconds between snapshots
    enable_tracemalloc=True,     # Enable detailed allocation tracking
    top_objects_count=20         # Number of top object types to track
)
```

#### Starting/Stopping

```python
# Start profiling
await profiler.start_memory_profiler()

# Stop profiling
await profiler.stop_memory_profiler()
```

#### Taking Snapshots

```python
# Take a manual snapshot
snapshot = await profiler.take_snapshot()

# Access snapshot data
print(f"Heap used: {snapshot.heap_used_mb} MB")
print(f"Total objects: {snapshot.total_objects}")
print(f"Top objects: {snapshot.top_objects}")
print(f"GC counts: {snapshot.gc_count}")
```

#### Leak Detection

```python
# Get recent snapshots
recent_snapshots = profiler.get_snapshots(count=10)

# Detect leaks
leaks = await profiler.detect_leaks(recent_snapshots)

# Process leaks
for leak in leaks:
    print(f"Leak detected: {leak.object_type}")
    print(f"Growth: {leak.growth_count} objects ({leak.growth_percent}%)")
    print(f"Severity: {leak.severity}")
```

#### Baseline Comparison

```python
# Compare current state to baseline
drift_report = await profiler.compare_to_baseline()

print(f"Heap drift: {drift_report.heap_drift_mb} MB ({drift_report.heap_drift_percent}%)")
print(f"Object drift: {drift_report.object_drift} objects")
print(f"Significant drifts: {drift_report.significant_drifts}")

# Reset baseline to current snapshot
profiler.reset_baseline()
```

#### Getting Metrics

```python
# Get metrics for Prometheus export
metrics = await profiler.get_memory_metrics()

print(f"Heap: {metrics.heap_used_mb} MB ({metrics.heap_percent}%)")
print(f"Objects: {metrics.total_objects}")
print(f"GC Gen0: {metrics.gc_collections_gen0}")
print(f"Active leaks: {metrics.active_leaks}")
```

#### Callbacks

```python
# Register leak detection callback
def on_leak_detected(leak):
    print(f"LEAK ALERT: {leak.object_type} - {leak.severity}")
    # Send notification, log to file, etc.

profiler.register_leak_callback(on_leak_detected)

# Register alert callback
def on_alert(alert):
    print(f"ALERT: {alert['type']} - {alert['severity']}")
    print(f"Message: {alert['message']}")

profiler.register_alert_callback(on_alert)
```

### 2. Metrics Exporter

**Location:** `monitoring/exporters/memory_exporter.py`

Exposes memory profiler metrics in Prometheus format.

#### Initialization

```python
from memory_exporter import get_memory_exporter

exporter = get_memory_exporter()

# Link to profiler
exporter.set_memory_profiler(profiler)

# Start HTTP server
await exporter.start()  # Runs on port 9202
```

#### Standalone Mode

Run as standalone service:

```bash
cd monitoring/exporters
python memory_exporter.py
```

Access metrics at `http://localhost:9202/metrics`

### 3. Alert Rules

**Location:** `monitoring/alerting/memory_alerts.yml`

Prometheus alert rules for memory anomalies.

#### Alert Categories

1. **Critical Alerts**
   - `MemoryHeapCritical`: Heap usage >90% for 5 minutes
   - `MemoryLeakDetected`: Active memory leaks detected
   - `MemoryRSSCritical`: Process RSS >8GB

2. **Growth Alerts**
   - `MemoryGrowthRateHigh`: Growing >100MB/hour
   - `MemoryGrowthRateCritical`: Growing >500MB/hour
   - `MemoryObjectGrowthUnreleased`: Object count growing without release

3. **GC Alerts**
   - `MemoryGCSpike`: High GC frequency
   - `MemoryGCGen2High`: Frequent full GC cycles

4. **Baseline Alerts**
   - `MemoryBaselineDriftHigh`: >50% above baseline
   - `MemoryBaselineDriftCritical`: >100% above baseline

5. **Capacity Alerts**
   - `MemoryCapacityWarning`: Predicted to reach 8GB in 24 hours
   - `MemoryExhaustionRisk`: Predicted to reach 95% in 1 hour

## API Reference

### MemorySnapshot

Represents a point-in-time memory snapshot.

**Attributes:**
- `timestamp` (datetime): Snapshot time
- `heap_size_mb` (float): Total heap size
- `heap_used_mb` (float): Used heap memory
- `heap_free_mb` (float): Free heap memory
- `heap_percent` (float): Heap usage percentage
- `total_objects` (int): Total object count
- `top_objects` (dict): Top N objects by type
- `gc_count` (tuple): GC counts per generation
- `gc_threshold` (tuple): GC thresholds
- `tracemalloc_current_mb` (float): Current traced memory
- `tracemalloc_peak_mb` (float): Peak traced memory
- `rss_mb` (float): Resident Set Size
- `vms_mb` (float): Virtual Memory Size

**Methods:**
- `to_dict()`: Convert to dictionary

### Leak

Represents a detected memory leak.

**Attributes:**
- `object_type` (str): Type of leaking objects
- `initial_count` (int): Count at start of monitoring
- `current_count` (int): Current count
- `growth_count` (int): Absolute growth
- `growth_percent` (float): Percentage growth
- `detection_time` (datetime): When detected
- `severity` (str): low, medium, high, critical

**Methods:**
- `to_dict()`: Convert to dictionary

### DriftReport

Comparison between current snapshot and baseline.

**Attributes:**
- `baseline_timestamp` (datetime): Baseline time
- `current_timestamp` (datetime): Current time
- `heap_drift_mb` (float): Heap drift in MB
- `heap_drift_percent` (float): Heap drift percentage
- `object_drift` (int): Object count drift
- `object_drift_percent` (float): Object drift percentage
- `gc_frequency_change` (float): GC frequency change
- `significant_drifts` (list): List of significant drifts

**Methods:**
- `to_dict()`: Convert to dictionary

### MemoryMetrics

Current metrics for Prometheus export.

**Attributes:**
- `heap_size_mb` (float)
- `heap_used_mb` (float)
- `heap_percent` (float)
- `total_objects` (int)
- `gc_collections_gen0` (int)
- `gc_collections_gen1` (int)
- `gc_collections_gen2` (int)
- `tracemalloc_current_mb` (float)
- `tracemalloc_peak_mb` (float)
- `rss_mb` (float)
- `vms_mb` (float)
- `active_leaks` (int)

**Methods:**
- `to_dict()`: Convert to dictionary

### MemoryProfiler

Main profiling service.

**Methods:**

#### `async start_memory_profiler() -> None`
Start memory profiling and take baseline snapshot.

#### `async stop_memory_profiler() -> None`
Stop memory profiling.

#### `async take_snapshot() -> MemorySnapshot`
Take a manual memory snapshot.

#### `async detect_leaks(snapshots: List[MemorySnapshot]) -> List[Leak]`
Detect memory leaks from snapshot history.

**Leak Detection Algorithm:**
1. Track object counts by type over time
2. Identify types with consistent growth (>50% and >100 objects)
3. Calculate growth rate and classify severity
4. Filter out expected growth patterns

#### `async get_memory_metrics() -> MemoryMetrics`
Get current memory metrics for Prometheus export.

#### `async compare_to_baseline(current: Optional[MemorySnapshot] = None) -> DriftReport`
Compare current snapshot to baseline.

#### `register_leak_callback(callback: Callable[[Leak], None]) -> None`
Register callback for leak detection.

#### `register_alert_callback(callback: Callable[[Dict[str, Any]], None]) -> None`
Register callback for alerts.

#### `get_snapshots(count: Optional[int] = None) -> List[Dict[str, Any]]`
Get recent snapshots.

#### `get_baseline_snapshot() -> Optional[Dict[str, Any]]`
Get baseline snapshot.

#### `get_detected_leaks() -> List[Dict[str, Any]]`
Get all detected leaks.

#### `reset_baseline() -> None`
Reset baseline to current snapshot.

#### `clear_detected_leaks() -> None`
Clear detected leaks list.

#### `get_stats() -> Dict[str, Any]`
Get profiler statistics.

## Configuration

### Profiler Configuration

```python
profiler = MemoryProfiler(
    snapshot_interval=60.0,       # Snapshot frequency (seconds)
    enable_tracemalloc=True,      # Enable detailed allocation tracking
    top_objects_count=20          # Number of top object types
)

# Adjust thresholds
profiler.heap_warning_percent = 80.0     # Warning threshold
profiler.heap_critical_percent = 90.0    # Critical threshold
profiler.growth_rate_warning = 10.0      # % per hour
profiler.gc_spike_threshold = 2.0        # GC frequency multiplier
```

### Prometheus Configuration

**File:** `monitoring/prometheus.yml`

```yaml
scrape_configs:
  - job_name: 'memory-profiler'
    static_configs:
      - targets: ['memory-exporter:9202']
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance
        replacement: 'fog-compute-backend'
```

### Alert Configuration

**File:** `monitoring/alerting/memory_alerts.yml`

Customize alert thresholds:

```yaml
- alert: MemoryHeapCritical
  expr: fogcompute_memory_heap_percent > 90
  for: 5m
  labels:
    severity: critical
```

## Prometheus Metrics

### Gauges

- `fogcompute_memory_heap_size_mb`: Total heap size
- `fogcompute_memory_heap_used_mb`: Used heap memory
- `fogcompute_memory_heap_percent`: Heap usage percentage
- `fogcompute_memory_total_objects`: Total object count
- `fogcompute_memory_gc_collections_gen0`: Gen 0 GC count
- `fogcompute_memory_gc_collections_gen1`: Gen 1 GC count
- `fogcompute_memory_gc_collections_gen2`: Gen 2 GC count
- `fogcompute_memory_tracemalloc_current_mb`: Current traced memory
- `fogcompute_memory_tracemalloc_peak_mb`: Peak traced memory
- `fogcompute_memory_rss_mb`: Resident Set Size
- `fogcompute_memory_vms_mb`: Virtual Memory Size
- `fogcompute_memory_active_leaks`: Active leak count
- `fogcompute_memory_baseline_drift_percent`: Drift from baseline
- `fogcompute_memory_object_count{object_type}`: Count by type

### Counters

- `fogcompute_memory_gc_collections_total{generation}`: Total GC collections
- `fogcompute_memory_leak_detections_total{severity}`: Total leak detections

## Usage Examples

### Basic Usage

```python
import asyncio
from services.memory_profiler import get_memory_profiler

async def main():
    profiler = get_memory_profiler()

    # Start profiling
    await profiler.start_memory_profiler()

    # Run application
    await asyncio.sleep(3600)  # 1 hour

    # Get metrics
    metrics = await profiler.get_memory_metrics()
    print(f"Memory usage: {metrics.heap_percent}%")

    # Check for leaks
    leaks = profiler.get_detected_leaks()
    if leaks:
        print(f"WARNING: {len(leaks)} leaks detected!")

    # Stop profiling
    await profiler.stop_memory_profiler()

asyncio.run(main())
```

### With Monitoring Integration

```python
from services.memory_profiler import get_memory_profiler
from memory_exporter import get_memory_exporter

async def main():
    # Initialize
    profiler = get_memory_profiler()
    exporter = get_memory_exporter()

    # Setup callbacks
    def on_leak(leak):
        print(f"LEAK: {leak.object_type} ({leak.severity})")

    def on_alert(alert):
        print(f"ALERT: {alert['type']} - {alert['message']}")

    profiler.register_leak_callback(on_leak)
    profiler.register_alert_callback(on_alert)

    # Link and start
    exporter.set_memory_profiler(profiler)
    await profiler.start_memory_profiler()
    await exporter.start()

    # Run indefinitely
    try:
        while True:
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        await exporter.stop()
        await profiler.stop_memory_profiler()

asyncio.run(main())
```

### Production Deployment

```python
# In your application startup
from services.memory_profiler import get_memory_profiler
from services.metrics_aggregator import metrics_aggregator

async def startup():
    profiler = get_memory_profiler()

    # Register with metrics aggregator
    async def report_to_aggregator(alert):
        await metrics_aggregator.record_metric(
            "memory_alerts",
            1,
            metadata=alert
        )

    profiler.register_alert_callback(report_to_aggregator)

    # Start profiling
    await profiler.start_memory_profiler()

# In your application shutdown
async def shutdown():
    profiler = get_memory_profiler()
    await profiler.stop_memory_profiler()
```

## Testing

Run tests:

```bash
# Unit tests
pytest tests/test_memory_profiler.py -v

# Integration tests
pytest tests/test_memory_monitoring_integration.py -v

# All memory profiling tests
pytest tests/test_memory*.py -v
```

## Troubleshooting

### High Memory Usage Alerts

1. Check for leaks: `profiler.get_detected_leaks()`
2. Compare to baseline: `await profiler.compare_to_baseline()`
3. Review top objects: Check snapshot `top_objects`
4. Enable tracemalloc for detailed allocation tracking

### No Metrics in Prometheus

1. Verify exporter is running: `curl http://localhost:9202/metrics`
2. Check Prometheus scrape config
3. Verify profiler is linked to exporter
4. Check logs for errors

### False Positive Leak Detection

Adjust leak detection criteria:

```python
# In memory_profiler.py, modify detect_leaks():
# Increase thresholds
if growth_percent > 100 and growth_count > 500:  # More conservative
    # Detect leak
```

## Performance Impact

- **Snapshot overhead**: <10ms per snapshot
- **Memory overhead**: ~5MB for 1000 snapshots
- **CPU impact**: <1% with 60s interval
- **Tracemalloc overhead**: +5-10% when enabled

## Best Practices

1. **Production Settings**
   - Use 60-120s snapshot interval
   - Enable tracemalloc only for debugging
   - Set conservative alert thresholds

2. **Leak Detection**
   - Monitor over extended periods (>1 hour)
   - Reset baseline after deployments
   - Investigate high-severity leaks immediately

3. **Alert Tuning**
   - Start with default thresholds
   - Adjust based on application behavior
   - Use Prometheus `for` clause to reduce noise

4. **Performance**
   - Disable tracemalloc in production if not needed
   - Limit `top_objects_count` to 10-20
   - Use longer snapshot intervals for low-overhead

## Future Enhancements

- [ ] Integration with OpenTelemetry
- [ ] Memory flame graphs
- [ ] Automatic leak remediation
- [ ] ML-based anomaly detection
- [ ] Multi-process profiling
- [ ] Memory allocation tracing

## Support

For issues or questions:
- GitHub Issues: fog-compute/issues
- Documentation: docs/MEMORY_PROFILING_API.md
- Runbooks: https://docs.example.com/runbooks/memory-profiling
