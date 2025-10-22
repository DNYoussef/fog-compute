# BetaNet Network I/O Implementation

## Overview

This document details the implementation of TCP networking for BetaNet mixnode, transforming it from in-memory simulation to a production-ready network service.

## Architecture

### Network Topology

```
┌─────────────────────────────────────────────────────────────┐
│                  BetaNet 3-Node Mixnet                       │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│   Client                Node 1              Node 2           │
│     │                   (Entry)            (Middle)          │
│     │                      │                  │              │
│     │ ──── TCP ──────────► │                  │              │
│     │   (Port 9001)        │ ──── TCP ───────► │            │
│     │                      │   (Port 9002)     │            │
│     │                      │                   │            │
│     │ ◄─── Response ────── │ ◄─── Response ─── │            │
│                                                              │
│                                            Node 3            │
│                                            (Exit)            │
│                                               │              │
│                           ──── TCP ──────────► │            │
│                              (Port 9003)       │            │
│                                                │            │
│                           ◄─── Response ────── │            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Components Implemented

### 1. TCP Server (`src/betanet/server/tcp.rs`)

**Key Features:**
- Async TCP listener on configurable port (default: 9001)
- Length-prefix protocol for packet framing (4-byte big-endian)
- Integration with `PacketPipeline` for batch processing
- Automatic backpressure via semaphores
- Connection-per-peer model with concurrent handling

**Protocol:**
```
┌─────────────┬────────────────────┐
│ 4 bytes     │ N bytes            │
│ Length (u32)│ Packet Data        │
└─────────────┴────────────────────┘
```

**Performance:**
- Supports 8+ worker threads
- Batch size: 256 packets
- Memory pool: 1024 buffers
- Queue depth: 10,000 packets

### 2. TCP Client (`src/betanet/server/tcp.rs`)

**Purpose:** Connect to downstream mixnodes

**Features:**
- Async connection with timeout
- Length-prefix send/receive
- Automatic retry logic
- Circuit support for multi-hop routing

### 3. Python Integration (`backend/server/services/betanet_client.py`)

**`BetanetTcpClient`:**
- Async TCP client using asyncio
- Length-prefix protocol matching Rust implementation
- Retry logic with exponential backoff
- Context manager support

**`BetanetCircuitClient`:**
- Multi-hop circuit orchestration
- Sequential packet forwarding through mixnodes
- Automatic connection management

### 4. Integration Tests (`src/betanet/tests/test_networking.rs`)

**Test Suite:**

1. **test_tcp_send_receive()**
   - Basic TCP connectivity
   - Single packet send/receive
   - Protocol validation

2. **test_three_node_circuit()**
   - 3-hop mixnet topology
   - Sequential packet forwarding
   - Multi-node coordination

3. **test_throughput_benchmark()**
   - **Target:** 25,000 packets/second
   - 4 concurrent clients
   - 6,250 packets per client
   - Measures: throughput, latency, success rate

4. **test_concurrent_connections()**
   - 10 simultaneous connections
   - Validates server concurrency
   - Ensures no connection dropping

### 5. E2E Tests (`backend/tests/test_betanet_e2e.py`)

**Python → Rust Integration:**

- `test_betanet_connection()` - Basic connectivity
- `test_betanet_send_receive()` - Single packet flow
- `test_betanet_full_circuit()` - 3-node circuit validation
- `test_betanet_throughput_benchmark()` - Client-side performance
- `test_betanet_concurrent_connections()` - Stress testing

### 6. Docker Compose (`docker-compose.betanet.yml`)

**Services:**
- `betanet-mixnode-1` (entry) - Port 9001
- `betanet-mixnode-2` (middle) - Port 9002
- `betanet-mixnode-3` (exit) - Port 9003
- `postgres` - Database for metrics (Port 5433)
- `prometheus` - Metrics collection (Port 9090)
- `grafana` - Visualization (Port 3000)

**Multi-Network Attachment:**
- `betanet` network (172.30.0.0/16)
- `fog-network` (shared with main application)

## Implementation Details

### Packet Pipeline Integration

```rust
// TCP server receives packet
let packet_data = read_length_prefixed(stream).await?;

// Submit to pipeline
let pipeline_packet = PipelinePacket::new(packet_data);
pipeline.submit_packet(pipeline_packet).await?;

// Pipeline processes in batches (256 packets)
// - Sphinx decryption (if enabled)
// - VRF delay calculation
// - Rate limiting
// - Memory pool optimization

// Retrieve processed packets
let processed = pipeline.get_processed_packets(10);

// Send back to client
write_length_prefixed(stream, processed).await?;
```

### Length-Prefix Protocol

**Why length-prefix?**
- Frame delimitation in TCP stream
- No packet fragmentation issues
- Efficient buffer management
- Cross-language compatibility

**Implementation:**

Rust:
```rust
// Write: 4-byte length + data
let length = data.len() as u32;
stream.write_all(&length.to_be_bytes()).await?;
stream.write_all(&data).await?;

// Read: 4-byte length + data
let mut length_buf = [0u8; 4];
stream.read_exact(&mut length_buf).await?;
let length = u32::from_be_bytes(length_buf) as usize;
let mut data = vec![0u8; length];
stream.read_exact(&mut data).await?;
```

Python:
```python
# Write: 4-byte length + data
length = struct.pack(">I", len(data))  # Big-endian u32
writer.write(length + data)

# Read: 4-byte length + data
length_bytes = await reader.readexactly(4)
length = struct.unpack(">I", length_bytes)[0]
data = await reader.readexactly(length)
```

## Performance Benchmarks

### Target Metrics

| Metric | Target | Achieved |
|--------|--------|----------|
| Throughput | 25,000 pkt/s | TBD* |
| Latency (avg) | < 1ms | TBD* |
| Memory pool hit rate | > 85% | TBD* |
| Packet drop rate | < 0.1% | TBD* |

*Run `cargo test --release test_throughput_benchmark` for actual numbers

### Benchmark Execution

```bash
# Rust-side throughput test
cargo test --manifest-path src/betanet/Cargo.toml \
    --release test_throughput_benchmark -- --nocapture

# Python-side E2E test
pytest backend/tests/test_betanet_e2e.py::test_betanet_throughput_benchmark -v
```

## Docker Deployment

### Single Node

```bash
# Build and run
docker-compose -f docker-compose.betanet.yml up betanet-mixnode-1
```

### 3-Node Circuit

```bash
# Start all nodes
docker-compose -f docker-compose.betanet.yml up

# Check health
curl http://localhost:9001/health
curl http://localhost:9002/health
curl http://localhost:9003/health

# View metrics
curl http://localhost:9001/metrics
```

### Environment Variables

```bash
NODE_PORT=9001               # TCP listen port
RUST_LOG=info                # Logging level
PIPELINE_WORKERS=4           # Processing threads
BATCH_SIZE=128               # Packets per batch
POOL_SIZE=1024               # Memory pool size
MAX_QUEUE_DEPTH=10000        # Maximum queue depth
TARGET_THROUGHPUT=25000      # Target pkt/s
```

## Testing Guide

### 1. Unit Tests

```bash
# All library tests
cargo test --manifest-path src/betanet/Cargo.toml --lib

# Specific test
cargo test --manifest-path src/betanet/Cargo.toml \
    --lib test_tcp_server_creation
```

### 2. Integration Tests

```bash
# All networking tests
cargo test --manifest-path src/betanet/Cargo.toml \
    --test test_networking

# Specific integration test
cargo test --manifest-path src/betanet/Cargo.toml \
    --test test_networking test_three_node_circuit -- --nocapture
```

### 3. E2E Tests (Python)

```bash
# All E2E tests
pytest backend/tests/test_betanet_e2e.py -v

# Specific test
pytest backend/tests/test_betanet_e2e.py::test_betanet_full_circuit -v
```

### 4. Manual Testing

```bash
# Terminal 1: Start mixnode
cargo run --manifest-path src/betanet/Cargo.toml --bin http_server

# Terminal 2: Python client
python -c "
import asyncio
from backend.server.services.betanet_client import BetanetTcpClient, BetanetConfig

async def test():
    config = BetanetConfig(host='127.0.0.1', port=9001)
    async with BetanetTcpClient(config) as client:
        response = await client.send_packet(b'Hello BetaNet!')
        print(f'Response: {len(response)} bytes')

asyncio.run(test())
"
```

## Known Limitations

1. **Sphinx Processing**: Currently simplified - full Sphinx onion routing requires circuit establishment
2. **VRF Delays**: Optional feature - enable with `--features vrf`
3. **Cover Traffic**: Optional feature - enable with `--features cover-traffic`
4. **Persistent State**: Mixnodes are stateless - routing tables reset on restart

## Future Enhancements

1. **QUIC Transport**: Replace TCP with QUIC for better performance
2. **TLS Encryption**: Add TLS 1.3 for transport security
3. **Connection Pooling**: Reuse connections between mixnodes
4. **Load Balancing**: Distribute traffic across multiple entry nodes
5. **Metrics Persistence**: Store metrics in PostgreSQL
6. **Health Checks**: Implement proper health check endpoints

## Troubleshooting

### Connection Refused

```bash
# Check if port is in use
netstat -an | grep 9001

# Check firewall
# Windows: netsh advfirewall show allprofiles
# Linux: sudo ufw status
```

### Low Throughput

```bash
# Increase worker threads
export PIPELINE_WORKERS=8

# Increase batch size
export BATCH_SIZE=256

# Check system limits
ulimit -n  # File descriptors
```

### Memory Issues

```bash
# Increase pool size
export POOL_SIZE=2048

# Monitor memory
docker stats betanet-mixnode-1
```

## References

- [Sphinx Packet Format](https://www.cypherpunks.ca/~iang/pubs/Sphinx_Oakland09.pdf)
- [Mixnet Design](https://katzenpost.mixnetworks.org/)
- [Tokio Runtime](https://tokio.rs/)
- [AsyncIO Python](https://docs.python.org/3/library/asyncio.html)

## Coordination Hooks

```bash
# Pre-task hook
npx claude-flow@alpha hooks pre-task \
    --description "Implement BetaNet network I/O"

# Post-edit hook
npx claude-flow@alpha hooks post-edit \
    --file "src/betanet/server/tcp.rs" \
    --memory-key "swarm/betanet/tcp-networking"

# Post-task hook
npx claude-flow@alpha hooks post-task \
    --task-id "betanet-networking"
```

---

**Status**: ✅ Implementation Complete
**Last Updated**: 2025-10-22
**Implemented By**: Backend API Developer Agent
