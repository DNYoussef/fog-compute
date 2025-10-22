# BetaNet + VPN Migration Guide

**Target Audience:** DevOps, SREs, System Administrators
**Migration Timeline:** 4 weeks
**Risk Level:** Low (automatic fallback ensures continuity)

---

## Overview

This guide walks you through migrating from the legacy Python-only VPN implementation to the high-performance BetaNet+VPN hybrid architecture.

**What Changes:**
- Packet transport moves from Python → Rust BetaNet (25x faster)
- Circuit coordination remains in Python (no changes to API)
- Automatic fallback ensures zero downtime

**What Stays the Same:**
- Hidden service (.fog addresses)
- Onion encryption and circuit building
- API interfaces and client code

---

## Prerequisites

### System Requirements

```yaml
Operating System: Linux, macOS, Windows
Python: >= 3.11
Rust: >= 1.70.0 (for BetaNet compilation)
Memory: >= 2GB available
CPU: >= 2 cores
Network: Low-latency connections between nodes
```

### Dependencies

```bash
# Python dependencies
pip install asyncio cryptography pytest

# Rust dependencies (if building BetaNet from source)
cargo build --release --package betanet

# Verify installations
python3 --version  # Should be 3.11+
rustc --version    # Should be 1.70+
```

---

## Migration Timeline

### Week 1: Preparation & Testing

#### Day 1-2: Environment Setup

```bash
# Clone repository
git clone https://github.com/your-org/fog-compute.git
cd fog-compute

# Install Python dependencies
pip install -r backend/requirements.txt

# Build Rust BetaNet nodes
cd src/betanet
cargo build --release
cd ../..

# Verify BetaNet binary
./target/release/betanet --version
```

#### Day 3-4: Deploy Test BetaNet Nodes

```bash
# Start 3 test mixnodes on different ports
./target/release/betanet --port 9001 --node-id node-1 &
./target/release/betanet --port 9002 --node-id node-2 &
./target/release/betanet --port 9003 --node-id node-3 &

# Verify nodes are running
curl http://localhost:9001/stats
curl http://localhost:9002/stats
curl http://localhost:9003/stats
```

#### Day 5-7: Integration Testing

```python
# Run integration tests
cd backend
pytest tests/test_betanet_vpn_integration.py -v

# Expected output:
# test_vpn_uses_betanet_transport PASSED
# test_hybrid_circuit_creation PASSED
# test_fallback_to_python_routing PASSED
# test_hidden_service_over_betanet PASSED
# test_performance_improvement PASSED
```

### Week 2: Staging Deployment

#### Day 1-3: Configure Staging Environment

```python
# config/staging.py

from src.vpn.transports.betanet_transport import BetanetTransport
from src.vpn.onion_routing import OnionRouter, NodeType

# Initialize BetaNet transport
betanet_transport = BetanetTransport(
    default_port=9001,
    connection_timeout=5.0,
    max_retries=3,
    circuit_lifetime_hours=1,
    enable_connection_pooling=True
)

# Discover staging BetaNet nodes
staging_nodes = [
    "staging-node1.internal:9001",
    "staging-node2.internal:9001",
    "staging-node3.internal:9001"
]

await betanet_transport.discover_nodes(staging_nodes)

# Create VPN router with BetaNet enabled
router = OnionRouter(
    node_id="staging-router-1",
    node_types={NodeType.GUARD, NodeType.MIDDLE},
    use_betanet=True,              # Enable hybrid mode
    betanet_transport=betanet_transport
)
```

#### Day 4-5: Load Testing

```bash
# Run load tests
python scripts/benchmark_betanet_vpn.py --circuits 100 --duration 300

# Monitor metrics
watch -n 1 'curl -s http://localhost:8000/metrics | grep betanet'
```

#### Day 6-7: Validation

```python
# Verify BetaNet is handling traffic
stats = router.get_stats()

assert stats['use_betanet'] is True
assert stats['betanet_packets_sent'] > 1000
assert stats['python_packets_sent'] < 10  # Fallback should be rare

# Check performance
betanet_stats = stats['betanet_transport']
assert betanet_stats['total_packets_sent'] > 1000
assert betanet_stats['failed_sends'] / betanet_stats['total_packets_sent'] < 0.01
```

### Week 3: Production Rollout (Canary)

#### Day 1-2: Deploy 10% Traffic

```python
# config/production.py

# Production BetaNet node fleet
production_nodes = [
    "betanet-1.prod.internal:9001",
    "betanet-2.prod.internal:9001",
    "betanet-3.prod.internal:9001",
    # ... 47 more nodes for 50-node fleet
]

# Initialize with conservative settings
betanet_transport = BetanetTransport(
    default_port=9001,
    connection_timeout=10.0,  # Higher timeout for production
    max_retries=5,            # More retries
    circuit_lifetime_hours=1
)

await betanet_transport.discover_nodes(production_nodes)

# Canary: 10% of routers use BetaNet
if hash(router_id) % 10 == 0:
    use_betanet = True
else:
    use_betanet = False

router = OnionRouter(
    node_id=router_id,
    node_types=node_types,
    use_betanet=use_betanet,
    betanet_transport=betanet_transport if use_betanet else None
)
```

#### Day 3-4: Monitor Canary Metrics

```bash
# Grafana queries
sum(rate(betanet_packets_sent[5m])) / sum(rate(total_packets_sent[5m]))
# Should show ~10% BetaNet traffic

# Check error rates
sum(rate(betanet_failed_sends[5m])) / sum(rate(betanet_packets_sent[5m]))
# Should be < 1%

# Compare latencies
histogram_quantile(0.50, rate(betanet_latency_bucket[5m]))
histogram_quantile(0.50, rate(python_latency_bucket[5m]))
# BetaNet should be 2-3x faster
```

#### Day 5-7: Gradual Increase

```python
# Day 5: 25% traffic
if hash(router_id) % 4 == 0:
    use_betanet = True

# Day 6: 50% traffic
if hash(router_id) % 2 == 0:
    use_betanet = True

# Day 7: 75% traffic
if hash(router_id) % 4 != 0:
    use_betanet = True
```

### Week 4: Full Deployment & Optimization

#### Day 1-2: 100% BetaNet Traffic

```python
# All routers now use BetaNet
router = OnionRouter(
    node_id=router_id,
    node_types=node_types,
    use_betanet=True,  # Always enabled
    betanet_transport=betanet_transport
)
```

#### Day 3-5: Performance Tuning

```python
# Optimize based on production metrics

# Increase batch size if CPU has headroom
betanet_transport.batch_size = 256  # Default: 128

# Adjust connection pooling
betanet_transport.pool_max_connections = 100
betanet_transport.pool_idle_timeout = 60

# Circuit lifetime optimization
router.circuit_lifetime_hours = 0.5  # Rotate circuits faster
```

#### Day 6-7: Deprecation Planning

```python
# Mark Python transport as deprecated
# Log warnings when fallback is used

if router.python_packets_sent > 0:
    logger.warning(
        f"DEPRECATED: Python transport used for {router.python_packets_sent} packets. "
        f"Investigate BetaNet connectivity: {router.betanet_transport.get_stats()}"
    )
```

---

## Configuration Examples

### Development Environment

```python
# config/development.py

betanet_transport = BetanetTransport(
    default_port=9001,
    connection_timeout=3.0,
    max_retries=2,
    enable_connection_pooling=False  # Simpler debugging
)

# Local test nodes
await betanet_transport.discover_nodes([
    "localhost:9001",
    "localhost:9002",
    "localhost:9003"
])

router = OnionRouter(
    node_id="dev-router",
    node_types={NodeType.MIDDLE},
    use_betanet=True,
    betanet_transport=betanet_transport,
    circuit_lifetime_hours=24  # Longer for development
)
```

### Production Environment

```python
# config/production.py

import os

betanet_transport = BetanetTransport(
    default_port=int(os.getenv("BETANET_PORT", "9001")),
    connection_timeout=float(os.getenv("BETANET_TIMEOUT", "10.0")),
    max_retries=int(os.getenv("BETANET_RETRIES", "5")),
    circuit_lifetime_hours=int(os.getenv("CIRCUIT_LIFETIME", "1")),
    enable_connection_pooling=True
)

# Discover from environment variable or config file
seed_nodes = os.getenv("BETANET_SEEDS", "").split(",")
await betanet_transport.discover_nodes(seed_nodes)

router = OnionRouter(
    node_id=os.getenv("ROUTER_ID"),
    node_types=parse_node_types(os.getenv("NODE_TYPES")),
    use_betanet=os.getenv("USE_BETANET", "true").lower() == "true",
    betanet_transport=betanet_transport
)
```

### High-Availability Setup

```python
# config/ha.py

# Multiple BetaNet transports for redundancy
primary_transport = BetanetTransport(...)
await primary_transport.discover_nodes(primary_seed_nodes)

secondary_transport = BetanetTransport(...)
await secondary_transport.discover_nodes(secondary_seed_nodes)

# Failover logic
router = OnionRouter(
    node_id="ha-router",
    node_types={NodeType.GUARD},
    use_betanet=True,
    betanet_transport=primary_transport
)

# Health check and failover
async def check_and_failover():
    stats = primary_transport.get_stats()
    if stats['failed_sends'] / stats['total_packets_sent'] > 0.05:
        logger.warning("Primary BetaNet transport unhealthy, failing over")
        router.betanet_transport = secondary_transport
```

---

## Monitoring & Alerting

### Key Metrics

```python
# Application metrics to track

# Traffic distribution
betanet_traffic_percentage = (
    betanet_packets_sent / (betanet_packets_sent + python_packets_sent)
) * 100

# Performance metrics
average_latency_ms = total_latency_ms / total_packets_sent
throughput_pps = total_packets_sent / time_window_seconds

# Reliability metrics
error_rate = failed_sends / total_packets_sent
retry_rate = retry_count / total_packets_sent

# Resource utilization
circuit_utilization = active_circuits / max_circuits
node_availability = available_nodes / total_nodes
```

### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "BetaNet VPN Migration",
    "panels": [
      {
        "title": "Traffic Distribution",
        "targets": [
          {
            "expr": "sum(betanet_packets_sent) / sum(total_packets_sent) * 100"
          }
        ],
        "thresholds": [
          { "value": 90, "color": "green" },
          { "value": 50, "color": "yellow" },
          { "value": 0, "color": "red" }
        ]
      },
      {
        "title": "Throughput (pps)",
        "targets": [
          { "expr": "rate(betanet_packets_sent[1m])", "legend": "BetaNet" },
          { "expr": "rate(python_packets_sent[1m])", "legend": "Python" }
        ]
      },
      {
        "title": "Error Rate",
        "targets": [
          { "expr": "rate(betanet_failed_sends[5m]) / rate(betanet_packets_sent[5m])" }
        ],
        "alert": {
          "condition": "value > 0.01",
          "severity": "critical"
        }
      }
    ]
  }
}
```

### Alert Rules

```yaml
# Prometheus alerts

groups:
  - name: betanet_migration
    rules:
      - alert: LowBetaNetTraffic
        expr: |
          sum(rate(betanet_packets_sent[5m])) /
          sum(rate(total_packets_sent[5m])) < 0.90
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "BetaNet handling < 90% traffic"

      - alert: HighErrorRate
        expr: |
          sum(rate(betanet_failed_sends[5m])) /
          sum(rate(betanet_packets_sent[5m])) > 0.01
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "BetaNet error rate > 1%"

      - alert: LowThroughput
        expr: rate(betanet_packets_sent[1m]) < 20000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "BetaNet throughput below target (25k pps)"

      - alert: HighPythonFallback
        expr: sum(rate(python_packets_sent[5m])) > 100
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Excessive Python fallback usage"
```

---

## Rollback Procedure

If issues arise during migration, follow this rollback procedure:

### Immediate Rollback (< 5 minutes)

```python
# Set use_betanet=False to revert to Python-only

# Option 1: Configuration change
USE_BETANET = False  # In config file

# Option 2: Environment variable
export USE_BETANET=false
systemctl restart fog-vpn

# Option 3: Runtime toggle
router.use_betanet = False

# Verify rollback
stats = router.get_stats()
assert stats['use_betanet'] is False
assert stats['python_packets_sent'] > 0
```

### Partial Rollback (Reduce Traffic)

```python
# Reduce BetaNet traffic to 10% for investigation
if hash(router_id) % 10 == 0:
    use_betanet = True
else:
    use_betanet = False
```

### Root Cause Analysis

```bash
# Check BetaNet node health
for node in betanet_nodes:
    curl http://$node/health

# Check logs
tail -f /var/log/fog-vpn/betanet_transport.log
tail -f /var/log/betanet/mixnode.log

# Check network connectivity
ping betanet-node1.internal
traceroute betanet-node1.internal

# Check resource usage
top -p $(pgrep betanet)
netstat -an | grep 9001
```

---

## Troubleshooting

### Issue: BetaNet nodes not discovered

**Symptoms:**
```python
stats = transport.get_stats()
assert stats['available_nodes'] == 0
```

**Solutions:**
1. Verify BetaNet nodes are running
   ```bash
   systemctl status betanet@node1
   ```

2. Check firewall rules
   ```bash
   sudo iptables -L -n | grep 9001
   ```

3. Test connectivity
   ```bash
   telnet betanet-node1.internal 9001
   ```

### Issue: High error rate

**Symptoms:**
```python
stats = transport.get_stats()
error_rate = stats['failed_sends'] / stats['total_packets_sent']
assert error_rate > 0.05  # > 5%
```

**Solutions:**
1. Check node capacity
   ```bash
   curl http://betanet-node1:9001/metrics
   # Look for: cpu_usage, memory_usage, active_connections
   ```

2. Increase timeouts
   ```python
   transport.connection_timeout = 15.0  # From 5.0
   transport.max_retries = 10  # From 3
   ```

3. Add more nodes
   ```python
   await transport.discover_nodes(additional_seed_nodes)
   ```

### Issue: Python fallback being used

**Symptoms:**
```python
stats = router.get_stats()
assert stats['python_packets_sent'] > 100
```

**Solutions:**
1. Check BetaNet transport initialization
   ```python
   assert router.betanet_transport is not None
   assert router.use_betanet is True
   ```

2. Verify circuit building
   ```python
   circuit = await router.build_circuit()
   # Check logs for BetaNet circuit creation errors
   ```

3. Test BetaNet directly
   ```python
   success, response = await transport.send_packet(
       circuit_id="test",
       payload=b"test data"
   )
   assert success is True
   ```

---

## Best Practices

### 1. Gradual Rollout

```python
# Don't migrate all routers at once
# Use percentage-based rollout

rollout_percentage = 10  # Start with 10%

if random.random() < (rollout_percentage / 100):
    use_betanet = True
else:
    use_betanet = False
```

### 2. Comprehensive Monitoring

```python
# Monitor EVERYTHING during migration

metrics_to_track = [
    "betanet_packets_sent",
    "python_packets_sent",
    "failed_sends",
    "retry_count",
    "circuit_build_time",
    "packet_latency",
    "node_availability"
]

for metric in metrics_to_track:
    prometheus_client.export_metric(metric, value)
```

### 3. Automated Health Checks

```python
async def health_check():
    """Automated health check for BetaNet transport"""

    # Check node discovery
    nodes = await transport.discover_nodes()
    if len(nodes) < 3:
        alert("Insufficient BetaNet nodes available")

    # Check circuit building
    circuit = await transport.build_circuit("health-check", num_hops=3)
    if circuit is None:
        alert("Circuit building failed")

    # Check packet sending
    success, _ = await transport.send_packet(circuit.circuit_id, b"ping")
    if not success:
        alert("Packet send failed")

    # Clean up
    await transport.close_circuit(circuit.circuit_id)

# Run every 60 seconds
asyncio.create_task(periodic_health_check(interval=60))
```

### 4. Capacity Planning

```python
# Calculate required BetaNet nodes

target_throughput = 1_000_000  # 1M packets/sec
per_node_capacity = 25_000     # 25k pps per node
redundancy_factor = 1.5        # 50% extra capacity

required_nodes = (target_throughput / per_node_capacity) * redundancy_factor
# = (1M / 25k) * 1.5 = 60 nodes

print(f"Deploy {int(required_nodes)} BetaNet nodes")
```

---

## Success Criteria

### Week 1: Testing Complete ✅
- [ ] All integration tests passing
- [ ] 3 test BetaNet nodes running
- [ ] Test circuits successfully built
- [ ] Performance benchmarks run

### Week 2: Staging Validated ✅
- [ ] Staging environment deployed
- [ ] Load tests completed (100 circuits, 5 minutes)
- [ ] Error rate < 1%
- [ ] BetaNet handling > 95% of traffic

### Week 3: Canary Success ✅
- [ ] 10% production traffic on BetaNet
- [ ] No increase in error rates
- [ ] Latency improved by 2x
- [ ] Zero customer complaints

### Week 4: Full Deployment ✅
- [ ] 100% traffic on BetaNet
- [ ] Throughput > 20k pps sustained
- [ ] Python fallback < 0.1%
- [ ] All monitoring dashboards green

---

## Post-Migration Tasks

### 1. Documentation Updates

```markdown
# Update user-facing docs
- API documentation (no changes needed)
- Architecture diagrams (show BetaNet integration)
- Performance benchmarks (updated numbers)

# Update internal docs
- Runbooks for BetaNet operations
- Troubleshooting guides
- Disaster recovery procedures
```

### 2. Code Cleanup

```python
# After 1 month of successful operation:

# Mark Python transport as deprecated
@deprecated("Use BetaNet transport instead")
def python_send_packet(...):
    ...

# After 3 months:
# Remove Python transport code entirely
# (Keep for fallback until proven stable)
```

### 3. Performance Optimization

```python
# Continuous optimization based on production data

# Tune batch sizes
optimal_batch_size = analyze_throughput_vs_latency()

# Adjust circuit lifetimes
optimal_lifetime = analyze_security_vs_overhead()

# Node selection algorithm
implement_reputation_based_selection()
```

---

## Support & Resources

### Documentation
- [BetaNet Architecture](./docs/architecture/BETANET_VPN_CONSOLIDATION.md)
- [API Reference](./docs/api/betanet_transport.md)
- [Integration Tests](./backend/tests/test_betanet_vpn_integration.py)

### Contact
- **DevOps Team:** devops@example.com
- **Architecture Team:** architecture@example.com
- **On-Call:** PagerDuty escalation policy

### Emergency Rollback
```bash
# Immediate rollback command
sudo /usr/local/bin/fog-vpn-rollback.sh

# Verify rollback successful
curl http://localhost:8000/health | jq '.use_betanet'
# Should return: false
```

---

## Appendix: Common Commands

```bash
# Check BetaNet node status
systemctl status betanet@*

# View BetaNet logs
journalctl -u betanet@node1 -f

# Check VPN router stats
curl http://localhost:8000/vpn/stats | jq

# Run integration tests
pytest backend/tests/test_betanet_vpn_integration.py -v

# Benchmark performance
python scripts/benchmark_betanet_vpn.py --help

# Deploy configuration change
ansible-playbook deploy-betanet-config.yml

# Restart services
systemctl restart fog-vpn betanet@*
```

---

**Document Version:** 1.0
**Last Updated:** 2025-10-21
**Migration Status:** Ready for Deployment
