# Metric Collection System - FUNC-07

## Overview

The metric collection system provides comprehensive time-series metric storage, aggregation, and export capabilities for the fog-compute platform. It collects metrics from multiple sources (nodes, deployments, Betanet) and provides statistical analysis with configurable aggregation windows.

## Architecture

### Components

1. **MetricCollector** (`metric_collector.rs`)
   - Time-series storage with ring buffer (24 hours at 15s intervals = 5760 data points)
   - Custom metric registration
   - Multi-source metric collection
   - Label-based filtering

2. **MetricAggregator** (`aggregator.rs`)
   - Statistical functions: avg, min, max, sum, p50, p95, p99
   - Rolling window aggregation
   - Label-based grouping
   - Rate calculation for counters
   - Prometheus format export

3. **MetricSources**
   - NodeMetricSource: CPU, memory, disk, network I/O
   - DeploymentMetricSource: Replicas, request rate, error rate, latency
   - BetanetClient: Packets, latency, connections (FUNC-06)

## Metrics Collected

### Node Metrics
- `node_cpu_usage` - CPU usage percentage (with `node_id` label)
- `node_memory_usage` - Memory usage percentage (with `node_id` label)
- `node_disk_usage` - Disk usage percentage (with `node_id` label)
- `node_network_io` - Network I/O bytes per second (with `node_id` label)

### Deployment Metrics
- `deployment_replica_count` - Number of replicas (with `deployment_id` label)
- `deployment_request_rate` - Request rate (with `deployment_id` label)
- `deployment_error_rate` - Error rate (with `deployment_id` label)
- `deployment_latency` - Request latency histogram (with `deployment_id` label)

### Betanet Metrics
- `betanet_packets_processed` - Total packets processed
- `betanet_packets_dropped` - Total packets dropped
- `betanet_latency` - Network latency histogram
- `betanet_connections` - Active connections

### System Metrics
- `system_uptime` - System uptime in seconds
- `system_total_nodes` - Total nodes in cluster
- `system_active_deployments` - Number of active deployments

## API Endpoints

### 1. `/metrics` - Prometheus Format
Returns real-time metrics in Prometheus exposition format.

```bash
curl http://localhost:9200/metrics
```

**Example Output:**
```
betanet_connected_peers 5
betanet_messages_total 12345
betanet_packets_dropped_total 10
```

### 2. `/metrics/aggregated` - Aggregated Metrics
Returns aggregated statistics (last 5 minutes) in Prometheus format.

```bash
curl http://localhost:9200/metrics/aggregated
```

**Example Output:**
```
node_cpu_usage{node_id="node-1",stat="avg"} 45.5
node_cpu_usage{node_id="node-1",stat="min"} 30.2
node_cpu_usage{node_id="node-1",stat="max"} 68.9
node_cpu_usage{node_id="node-1",stat="p50"} 44.1
node_cpu_usage{node_id="node-1",stat="p95"} 65.2
node_cpu_usage{node_id="node-1",stat="p99"} 68.1
```

### 3. `/stats` - Buffer Statistics
Returns JSON with buffer fill levels and registered metrics.

```bash
curl http://localhost:9200/stats
```

**Example Output:**
```json
{
  "buffer_stats": {
    "node_cpu_usage": 240,
    "node_memory_usage": 240,
    "deployment_latency": 240
  },
  "registered_metrics": [
    "node_cpu_usage",
    "node_memory_usage",
    "deployment_latency"
  ],
  "total_metrics": 15
}
```

### 4. `/health` - Health Check
Returns service health status.

```bash
curl http://localhost:9200/health
```

**Example Output:**
```json
{
  "status": "healthy"
}
```

## Configuration

### Buffer Size
Default: 5760 data points (24 hours at 15s intervals)

To change:
```rust
let collector = Arc::new(MetricCollector::new(
    5760,  // buffer_size: number of data points
    15     // collection_interval_secs: seconds between collections
));
```

### Collection Interval
Default: 15 seconds

Modify in `betanet_exporter.rs`:
```rust
let mut interval = time::interval(Duration::from_secs(15));
```

### Aggregation Windows
Pre-defined windows in `AggregationWindows`:
- `LAST_5_MINUTES` = 300 seconds
- `LAST_15_MINUTES` = 900 seconds
- `LAST_HOUR` = 3600 seconds
- `LAST_6_HOURS` = 21600 seconds
- `LAST_24_HOURS` = 86400 seconds

## Custom Metric Registration

### Step 1: Register the Metric
```rust
collector.register_metric(
    "custom_metric_name".to_string(),
    "Description of metric".to_string(),
    MetricType::Gauge,  // or Counter, Histogram
    Some("units".to_string()),
);
```

### Step 2: Record Values
```rust
let mut labels = HashMap::new();
labels.insert("label_key".to_string(), "label_value".to_string());

collector.record_metric("custom_metric_name", 42.0, labels);
```

### Step 3: Create a Custom Metric Source
```rust
pub struct CustomMetricSource {
    id: String,
}

#[async_trait::async_trait]
impl MetricSource for CustomMetricSource {
    fn name(&self) -> &str {
        "custom_source"
    }

    async fn fetch_metrics(&self) -> Result<Vec<(String, f64, HashMap<String, String>)>, String> {
        let mut labels = HashMap::new();
        labels.insert("source_id".to_string(), self.id.clone());

        Ok(vec![
            ("custom_metric_name".to_string(), 42.0, labels),
        ])
    }
}
```

## Building and Running

### Build
```bash
cd monitoring/exporters
cargo build --release
```

### Run
```bash
cargo run --bin betanet_exporter
```

### Run with Logging
```bash
RUST_LOG=info cargo run --bin betanet_exporter
```

### Run Tests
```bash
cargo test
```

## Integration with Prometheus

### prometheus.yml Configuration
```yaml
scrape_configs:
  - job_name: 'betanet_exporter'
    static_configs:
      - targets: ['localhost:9200']
    scrape_interval: 15s

  - job_name: 'betanet_aggregated'
    static_configs:
      - targets: ['localhost:9200']
    metrics_path: '/metrics/aggregated'
    scrape_interval: 60s
```

### Example Prometheus Queries

**Average CPU usage by node (last 5 minutes):**
```promql
node_cpu_usage{stat="avg"}
```

**95th percentile latency for deployments:**
```promql
deployment_latency{stat="p95"}
```

**Maximum memory usage across all nodes:**
```promql
max(node_memory_usage{stat="max"})
```

## Performance Considerations

### Memory Usage
- Ring buffer: 5760 data points per metric
- Each data point: ~100 bytes (timestamp + value + labels)
- 15 metrics * 5760 points * 100 bytes = ~8.6 MB

### CPU Usage
- Collection interval: 15 seconds
- Aggregation: On-demand (HTTP request)
- Minimal overhead: <5% CPU on typical workloads

### Disk I/O
- All data stored in memory (no disk writes)
- Data persists only while service is running
- For persistent storage, use Prometheus or time-series database

## Troubleshooting

### No Data in Aggregated Metrics
- Check buffer fill level: `curl http://localhost:9200/stats`
- Ensure collection interval has passed (wait 15-30 seconds)
- Verify metric sources are responding

### High Memory Usage
- Reduce buffer size: `MetricCollector::new(1440, 15)` for 6 hours
- Reduce number of registered metrics
- Check for label cardinality explosion

### Circuit Breaker Open
- Betanet client has failed too many times
- Check Betanet service availability: `curl http://localhost:9000/api/v1/metrics`
- Wait 30 seconds for automatic recovery

## Testing

### Unit Tests
```bash
# Run all tests
cargo test

# Run specific module tests
cargo test metric_collector
cargo test aggregator
```

### Integration Test
```bash
# Start the exporter
cargo run --bin betanet_exporter &

# Wait for startup
sleep 2

# Test endpoints
curl http://localhost:9200/health
curl http://localhost:9200/stats
curl http://localhost:9200/metrics | head -20

# Wait for data collection
sleep 20

# Test aggregated metrics
curl http://localhost:9200/metrics/aggregated
```

## Future Enhancements

1. **Persistent Storage**
   - Add optional PostgreSQL/TimescaleDB backend
   - Support for long-term metric retention

2. **Advanced Aggregations**
   - Moving averages
   - Anomaly detection
   - Forecasting

3. **Multi-Region Support**
   - Cross-region metric aggregation
   - Geo-distributed collection

4. **Alert Rules**
   - Threshold-based alerting
   - Rate-of-change detection
   - Integration with alerting systems

## References

- FUNC-06: Betanet Metrics Fetch (prerequisite)
- Prometheus Exposition Format: https://prometheus.io/docs/instrumenting/exposition_formats/
- Time-Series Best Practices: https://prometheus.io/docs/practices/naming/
