# I2P vs Fog-Compute Betanet: MECE Comparison Chart

**Date**: 2026-01-04
**Analyst**: Reconnaissance Skill (delivery-workflows-research)
**Confidence**: 0.85 (ceiling: research 0.85)

---

## Executive Summary

| Dimension | I2P/I2Pd | Fog-Compute Betanet | Winner |
|-----------|----------|---------------------|--------|
| **Maturity** | 22+ years (2003) | ~2 years (alpha) | I2P |
| **Network Size** | 72,653 nodes (2025) | Single deployment | I2P |
| **Performance** | ~200KB/s typical | 25,000 pkt/s | Betanet |
| **Purpose** | General anonymity | Edge compute + privacy | Different |
| **Crypto Modern** | X25519/ChaCha20 (2024+) | X25519/ChaCha20 (native) | Tie |

---

## MECE Category 1: NETWORK ARCHITECTURE

| Aspect | I2P | Fog-Compute Betanet |
|--------|-----|---------------------|
| **Topology** | Fully decentralized DHT (Kademlia) | Mixnode mesh network |
| **Discovery** | Distributed hash table, floodfill nodes | Centralized coordinator (planned P2P) |
| **Tunnels** | Unidirectional (inbound/outbound separate) | Bidirectional pipelines |
| **Tunnel Refresh** | Every 10 minutes | Configurable (default continuous) |
| **Participation** | All users are nodes by default | Explicit node registration |
| **Transport** | NTCP2 (TCP) + SSU2 (UDP) | TCP primary, HTTP fallback |
| **Max Hops** | Variable (typically 3-7) | 5 hops (MAX_HOPS constant) |

### Verdict: I2P has mature decentralization; Betanet optimized for throughput

---

## MECE Category 2: CRYPTOGRAPHIC PRIMITIVES

| Primitive | I2P (Modern) | Fog-Compute Betanet |
|-----------|--------------|---------------------|
| **Key Exchange** | X25519 | X25519 (x25519_dalek) |
| **Symmetric Cipher** | ChaCha20/Poly1305, AES-256 | ChaCha20/Poly1305 |
| **Signatures** | EdDSA (Ed25519) | Ed25519 (ed25519_dalek) |
| **Hashing** | SHA-256 | SHA-256 (sha2) |
| **KDF** | Custom (ElGamal legacy) | HKDF-SHA256 |
| **Legacy Support** | ElGamal, ECDSA, DSA-SHA1 | None (modern only) |

### Verdict: TIE - Both use modern cryptography; I2P has legacy baggage

---

## MECE Category 3: ROUTING PROTOCOL

| Feature | I2P (Garlic Routing) | Fog-Compute (Sphinx) |
|---------|----------------------|----------------------|
| **Core Protocol** | Garlic routing (bundled cloves) | Sphinx onion routing |
| **Message Bundling** | Multiple messages per garlic | Single message per packet |
| **Layer Encryption** | 4 layers E2E | 5 layers (MAX_HOPS) |
| **Header Size** | Variable | 176 bytes fixed |
| **Payload Size** | 4KB default (streaming) | 1024 bytes fixed |
| **Replay Protection** | Session tags (8-byte) | Bloom filter (1MB) |
| **Traffic Analysis Resistance** | Clove bundling, timing variance | Cover traffic, VRF delays |

### Verdict: Different approaches - I2P bundles; Betanet optimizes per-packet

---

## MECE Category 4: PERFORMANCE CHARACTERISTICS

| Metric | I2P/I2Pd | Fog-Compute Betanet |
|--------|----------|---------------------|
| **Throughput** | ~200KB/s typical | 25,000 pkt/s verified |
| **Latency** | High (multi-hop + delays) | Low (optimized pipeline) |
| **Memory (Daemon)** | 50-200MB | ~100MB (Rust native) |
| **Batch Processing** | Per-message | 128 packets/batch |
| **Memory Pool** | None | 1024-buffer pool |
| **Backpressure** | Queue-based | Semaphore (10K depth) |

### Verdict: BETANET - Purpose-built for high throughput

---

## MECE Category 5: APPLICATION LAYER

| Feature | I2P | Fog-Compute |
|---------|-----|-------------|
| **Primary Use** | Anonymous web browsing | Edge compute orchestration |
| **Messaging** | Built-in (I2P-Bote, Susimail) | BitChat (P2P encrypted) |
| **Hidden Services** | Eepsites (.i2p domains) | None (not a goal) |
| **Monero Integration** | Native support | Not applicable |
| **API** | I2CP (Java), SAM | REST + WebSocket |
| **Control Panel** | Built-in web console | Next.js 3D dashboard |

### Verdict: Different purposes - I2P is anonymity network; Betanet is compute layer

---

## MECE Category 6: SECURITY FEATURES

| Security Aspect | I2P | Fog-Compute Betanet |
|-----------------|-----|---------------------|
| **Threat Model** | Global passive adversary | Traffic analysis resistance |
| **Timing Attacks** | Tunnel refresh, delays | VRF Poisson delays |
| **Sybil Resistance** | Reputation + bandwidth | Relay lottery (VRF-based) |
| **Replay Attacks** | Session tags (32-byte) | Bloom filter + HashMap |
| **Forward Secrecy** | ECIES ratchet | Per-session keys (HKDF) |
| **Cover Traffic** | Optional | Built-in (feature flag) |

### Verdict: TIE - Both have comprehensive defenses

---

## MECE Category 7: ECOSYSTEM & TOOLING

| Aspect | I2P | Fog-Compute |
|--------|-----|-------------|
| **Language** | Java (original), C++ (i2pd) | Rust + TypeScript + Python |
| **Implementations** | 2 major (Java I2P, i2pd) | 1 (monorepo) |
| **Package Managers** | apt, snap, docker | Docker Compose only |
| **Monitoring** | Basic web console | Prometheus/Grafana/Loki |
| **CI/CD** | Community builds | GitHub Actions |
| **Documentation** | Extensive (20+ years) | In-progress |

### Verdict: I2P has ecosystem maturity; Betanet has modern DevOps

---

## MECE Category 8: UNIQUE DIFFERENTIATORS

### I2P Unique Features
- 72,653+ active nodes globally
- 22 years of battle-testing
- Hidden services (.i2p domains)
- Monero blockchain integration
- Bidirectional anonymity (sender + receiver)
- NTCP2/SSU2 transport protocols

### Fog-Compute Betanet Unique Features
- 25,000 pkt/s throughput (125x I2P typical)
- NSGA-II multi-objective optimization
- Tokenomics/DAO governance (Phase 2)
- Federated learning integration (Phase 3)
- VRF-based relay lottery
- 3D visualization dashboard
- Edge compute orchestration

---

## Strategic Recommendation

| Scenario | Recommended System |
|----------|-------------------|
| Anonymous browsing | I2P |
| Hidden services | I2P |
| High-throughput privacy | Fog-Compute Betanet |
| Edge AI/ML workloads | Fog-Compute Betanet |
| Cryptocurrency privacy | I2P |
| Enterprise deployment | Fog-Compute Betanet |

### Integration Opportunity

Consider I2P as a **transport layer option** for Fog-Compute Phase 2 VPN/Onion integration:
- Use I2P tunnels for inter-node communication
- Leverage I2P's 72K node network for relay discovery
- Maintain Betanet's high-throughput pipeline internally

**Effort Estimate**: 40-60 hours for I2P transport adapter

---

## Confidence Statement

Confidence: 0.85 (ceiling: research 0.85)

Sources:
- I2P official documentation (geti2p.net)
- i2pd GitHub repository (PurpleI2P/i2pd)
- Fog-compute source code analysis
- 2025 academic research (Wiley Internet Technology Letters)
