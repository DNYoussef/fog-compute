# FUNC-07 Quick Start Guide

## Build and Run

```bash
cd monitoring/exporters

# Build
cargo build --release

# Run with logging
RUST_LOG=info cargo run --bin betanet_exporter

# Run tests
cargo test
```

## Endpoints

```bash
# Health check
curl http://localhost:9200/health

# Prometheus metrics (real-time)
curl http://localhost:9200/metrics

# Aggregated statistics (last 5 minutes)
curl http://localhost:9200/metrics/aggregated

# Buffer statistics
curl http://localhost:9200/stats | jq .
```

## Key Features

1. **Time-Series Storage**
   - 24 hours of data at 15-second intervals
   - Ring buffer (oldest data auto-removed)
   - 15 metrics registered by default

2. **Aggregation Functions**
   - avg, min, max, sum
   - p50 (median), p95, p99
   - Rolling windows: 5min, 15min, 1h, 6h, 24h

3. **Metric Sources**
   - Node: CPU, memory, disk, network I/O
   - Deployment: replicas, requests, errors, latency
   - Betanet: packets, latency, connections

4. **Labels**
   - `node_id`: Identify specific nodes
   - `deployment_id`: Identify deployments
   - Custom labels supported

## Add Custom Metric

```rust
// 1. Register metric
collector.register_metric(
    "my_custom_metric".to_string(),
    "Description".to_string(),
    MetricType::Gauge,
    Some("units".to_string()),
);

// 2. Record values
let mut labels = HashMap::new();
labels.insert("key".to_string(), "value".to_string());
collector.record_metric("my_custom_metric", 42.0, labels);

// 3. Query aggregated data
let agg = aggregator.rolling_window("my_custom_metric", 300);
```

## Prometheus Integration

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'fog-compute'
    static_configs:
      - targets: ['localhost:9200']
    scrape_interval: 15s
```

## Grafana Queries

```promql
# Average CPU by node
node_cpu_usage{stat="avg"}

# 95th percentile latency
deployment_latency{stat="p95"}

# Max memory usage
max(node_memory_usage{stat="max"})
```

## Troubleshooting

**No aggregated metrics?**
- Wait 20-30 seconds for data collection
- Check: `curl http://localhost:9200/stats`

**High memory?**
- Reduce buffer size in code
- Check label cardinality

**Betanet metrics missing?**
- Verify: `curl http://localhost:9000/api/v1/metrics`
- Check circuit breaker status in logs

## Files

- `metric_collector.rs` - Time-series storage
- `aggregator.rs` - Statistical functions
- `betanet_exporter.rs` - Main service
- `METRIC_COLLECTOR_README.md` - Full docs
- `test-metric-collector.sh` - Integration test

## Testing

```bash
# Unit tests
cargo test

# Integration test
./test-metric-collector.sh

# Manual test
curl http://localhost:9200/metrics/aggregated | grep "stat=\"p95\""
```

## Performance

- Memory: ~8.6 MB for 15 metrics (24h data)
- CPU: <5% during collection/aggregation
- Latency: <50ms per aggregation request

## Next Steps

1. Run the exporter: `cargo run --bin betanet_exporter`
2. Wait 30 seconds for data collection
3. Test endpoints: `curl http://localhost:9200/metrics/aggregated`
4. Configure Prometheus to scrape
5. Build Grafana dashboards

For full documentation, see `METRIC_COLLECTOR_README.md`
