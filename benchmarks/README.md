# Fog-Compute Performance Benchmark Suite

Comprehensive performance testing for Betanet, BitChat, and Control Panel with automated CI/CD integration and regression detection.

## 📊 Benchmark Components

### 1. Betanet Throughput Benchmark (`betanet_throughput.rs`)
**Target Metrics:**
- Throughput: ≥25,000 packets per second (pps)
- Single stream performance
- Concurrent stream scaling

**What it measures:**
- Packet transmission rate
- Network latency distribution (P50, P95, P99)
- Multi-stream concurrency
- Throughput sustainability

**Run:**
```bash
cargo run --release --bin betanet_throughput
```

### 2. BitChat P2P Latency Benchmark (`bitchat_latency.ts`)
**Target Metrics:**
- Local P2P: <50ms (P99)
- Global P2P: <200ms (P99)
- Message broadcasting efficiency

**What it measures:**
- Peer-to-peer messaging latency
- Local vs global performance
- Broadcast distribution speed
- Direct message routing

**Run:**
```bash
ts-node bitchat_latency.ts
```

### 3. Control Panel Rendering Benchmark (`control_panel_render.ts`)
**Target Metrics:**
- Frame rate: 60 fps (16.67ms frame budget)
- User interactions: <100ms (P99)
- Smooth UI responsiveness

**What it measures:**
- Render loop performance
- Component mount time
- User interaction latency
- State update efficiency
- Large list rendering (virtual scrolling)

**Run:**
```bash
ts-node control_panel_render.ts
```

### 4. System Integration Benchmark (`system_integration.py`)
**Target Metrics:**
- End-to-end flow: >100 ops/sec
- Concurrent operations: >1000 ops/sec
- System reliability: >99% success rate

**What it measures:**
- Complete system flow performance
- Component integration overhead
- Concurrent operation handling
- Stress test resilience
- Fault tolerance and recovery

**Run:**
```bash
python system_integration.py
```

## 🚀 Quick Start

### Run All Benchmarks
```bash
chmod +x run_all_benchmarks.sh
./run_all_benchmarks.sh
```

This executes:
1. Betanet throughput test
2. BitChat latency measurement
3. Control Panel rendering benchmark
4. System integration tests
5. Generates consolidated report

## 📈 Performance Gates

Critical performance thresholds that must be met:

| Component | Metric | Target | Validation |
|-----------|--------|--------|------------|
| **Betanet** | Throughput | ≥25,000 pps | ✅ Pass if met |
| **Betanet** | P99 Latency | - | Monitor only |
| **BitChat Local** | P99 Latency | <50ms | ✅ Pass if met |
| **BitChat Global** | P99 Latency | <200ms | ✅ Pass if met |
| **Control Panel** | Frame Rate | ≥60 fps | ✅ Pass if met |
| **Control Panel** | Interaction P99 | <100ms | ✅ Pass if met |
| **Integration** | Throughput | ≥100 ops/sec | ✅ Pass if met |
| **Integration** | Success Rate | ≥99% | ✅ Pass if met |

## 🔄 CI/CD Integration

### Automated Testing
GitHub Actions workflow runs:
- On every push to `main`/`develop`
- On all pull requests
- Daily scheduled runs (2 AM UTC)

### Performance Validation
CI pipeline:
1. ✅ Builds all components
2. ✅ Runs benchmark suite
3. ✅ Validates against targets
4. ✅ Generates performance report
5. ✅ Comments on PR with results
6. ⚠️ Fails if any gate fails

### Regression Detection
Compares current run against baseline:
- Throughput decrease >10% → Fail
- Latency increase >20% → Warning
- Success rate drop >5% → Fail

## 📊 Reports & Artifacts

### JSON Reports
Each benchmark produces:
- `betanet_throughput_report.json`
- `bitchat_latency_report.json`
- `control_panel_render_report.json`
- `system_integration_report.json`
- `consolidated_benchmark_report.json`

### Report Schema
```json
{
  "benchmark": "betanet_throughput",
  "timestamp": 1234567890,
  "single_stream": {
    "packets_sent": 250000,
    "throughput_pps": 25847.5,
    "p50_latency_us": 12,
    "p95_latency_us": 35,
    "p99_latency_us": 58,
    "target_met": true
  },
  "performance_gate": {
    "target_pps": 25000,
    "actual_pps": 25847.5,
    "pass": true
  }
}
```

## 🔧 Configuration

### Betanet Configuration
```rust
// In betanet_throughput.rs
const TARGET_PPS: u64 = 25000;
const DURATION_SECS: u64 = 10;
const NUM_CONCURRENT_STREAMS: usize = 10;
```

### BitChat Configuration
```typescript
// In bitchat_latency.ts
const LOCAL_TARGET_MS = 50;
const GLOBAL_TARGET_MS = 200;
const MESSAGE_COUNT = 1000;
```

### Control Panel Configuration
```typescript
// In control_panel_render.ts
const TARGET_FPS = 60;
const FRAME_BUDGET_MS = 16.67;
const INTERACTION_BUDGET_MS = 100;
```

## 📈 Performance Optimization

### Betanet Tuning
- Packet batching for throughput
- Zero-copy networking
- Async I/O optimization
- Buffer pool management

### BitChat Tuning
- Connection pooling
- Message queue optimization
- Peer discovery caching
- Route table optimization

### Control Panel Tuning
- Virtual scrolling for lists
- React.memo for components
- Debounced state updates
- Web Worker offloading

## 🐛 Debugging Performance Issues

### Low Throughput
1. Check network bandwidth limits
2. Review packet size configuration
3. Verify async task scheduling
4. Profile CPU bottlenecks

### High Latency
1. Identify slow components
2. Check for blocking operations
3. Review message routing paths
4. Analyze network round-trips

### Render Performance
1. Use browser DevTools profiler
2. Check for unnecessary re-renders
3. Analyze main thread blocking
4. Review component lifecycle

## 📊 Baseline Establishment

### Initial Baseline
Run benchmarks 5x on clean system:
```bash
for i in {1..5}; do
  ./run_all_benchmarks.sh
  mv benchmarks/consolidated_benchmark_report.json \
     benchmarks/baseline_run_$i.json
done
```

### Calculate Baseline
```python
import json
import statistics

runs = [json.load(open(f'baseline_run_{i}.json')) for i in range(1, 6)]

# Calculate median values for each metric
baseline = {
    'betanet_throughput': statistics.median([r['betanet']['throughput_pps'] for r in runs]),
    'bitchat_local_p99': statistics.median([r['bitchat']['local_p99_ms'] for r in runs]),
    # ... more metrics
}
```

## 🔗 Dependencies

### Rust (Betanet)
- `tokio` - Async runtime
- `serde_json` - JSON serialization

### TypeScript (BitChat, Control Panel)
- `ts-node` - TypeScript execution
- `@types/node` - Node.js types

### Python (Integration)
- `asyncio` - Async support
- `json` - Report generation

## 📚 Best Practices

1. **Consistent Environment**: Always benchmark on same hardware
2. **Warm-up Runs**: Discard first 2-3 runs to warm caches
3. **Multiple Samples**: Run 5+ times, use median
4. **Isolated Testing**: Close other applications
5. **Realistic Workloads**: Use production-like data patterns

## 🎯 Performance Targets Rationale

### Betanet: 25k pps
- Supports 100 simultaneous peers
- Each peer sends ~250 packets/sec
- Leaves 10% headroom for bursts

### BitChat: <50ms local, <200ms global
- Local: LAN latency expectations
- Global: Typical WAN round-trip time
- Interactive messaging experience

### Control Panel: 60fps
- Standard for smooth UI
- Matches display refresh rate
- Responsive user experience

## 📞 Support

For performance issues:
1. Review benchmark reports
2. Check CI/CD logs
3. Compare against baseline
4. Open issue with artifacts

## 🔗 Related Documentation

- [Betanet Architecture](../docs/betanet.md)
- [BitChat Protocol](../docs/bitchat.md)
- [Control Panel Design](../docs/control-panel.md)
- [CI/CD Pipeline](../.github/workflows/README.md)