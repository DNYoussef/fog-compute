# Fog Compute v2: Post-Integration Architecture

**Date**: 2026-02-08
**Status**: Architecture Vision (Pre-Implementation)
**Premise**: All 9 open-source integrations executed. GPL-3.0 adopted.

---

## BEFORE vs AFTER: The Numbers

| Metric | v1 (Current) | v2 (Post-Integration) | Delta |
|--------|-------------|----------------------|-------|
| Architectural layers | 8 | 12 | +4 new layers |
| Source files (Rust) | 36 | ~70 | +34 (integrations + new modules) |
| Source files (Python) | 49 | ~55 | +6 (orchestration wrappers) |
| Source files (TypeScript) | ~15 | ~20 | +5 (group chat, WASM bridge) |
| Source files (Solidity) | 0 | ~8 | +8 (staking contracts) |
| Estimated LOC | 6,882 | ~18,000-22,000 | +160-220% |
| Test count | 148 | ~400+ | +170% |
| Gaps closed | 0/12 critical | 9/12 critical | 75% gap closure |
| Production readiness | 87/100 | 94/100 (projected) | +7 points |
| Competitor parity features | 3/10 | 8/10 | From lagging to leading |

---

## THE 12-LAYER ARCHITECTURE

```
+==============================================================================+
|                         FOG COMPUTE v2 - FULL STACK                          |
+==============================================================================+
|                                                                              |
|  LAYER 12: BENCHMARKING & OBSERVABILITY          src/fog/                    |
|  [existing] 4-category benchmark suite + Prometheus/Grafana                  |
|  [upgraded] + regression tracking, external baseline comparison              |
|                                                                              |
|  LAYER 11: STAKING & SYBIL RESISTANCE (NEW)      contracts/staking/         |
|  [from HOPR SafeStaking] Smart contract custody, slashing, node admission   |
|  Solidity on EVM chain, 30k token min stake, SafeStaking vault pattern      |
|                                                                              |
|  LAYER 10: TASK MARKETPLACE (UPGRADED)            src/market/               |
|  [from Golem Yagna Market] Offer/demand matching, negotiation protocol      |
|  Agreement lifecycle, payment channels, reputation-weighted scoring          |
|  Replaces: src/tokenomics/ (55% maturity -> 85%+)                          |
|                                                                              |
|  LAYER 9: COMPUTE ATTESTATION (NEW)              src/attestation/           |
|  [inspired by iExec SMS] TEE remote attestation (SGX/TDX)                  |
|  ZK proof of correct execution, result verification                         |
|  Reimplemented in Rust from iExec's Java design patterns                    |
|                                                                              |
|  LAYER 8: TASK EXECUTION RUNTIME (UPGRADED)       src/runtime/              |
|  [from Golem Yagna ExeUnit] VM/WASM/Docker execution backends              |
|  Resource metering, sandboxed execution, output capture                     |
|  Replaces: src/batch/ stubs + src/scheduler/ stubs                          |
|                                                                              |
|  LAYER 7: CONTAINER ORCHESTRATION (NEW)           src/orchestrator/         |
|  [inspired by Akash Provider] K8s pod lifecycle, manifest management        |
|  Dynamic scaling, health checks, resource allocation                        |
|  Reimplemented in Rust (not Go import), gRPC interface to Python scheduler  |
|                                                                              |
|  LAYER 6: BATCH SCHEDULER (EXISTING, ENHANCED)    src/batch/               |
|  [existing] NSGA-II multi-objective optimization                            |
|  [enhanced] Now dispatches to real ExeUnit runtime (Layer 8)                |
|  [enhanced] Feeds attestation results back to reputation (Layer 10)         |
|                                                                              |
|  LAYER 5: IDLE COMPUTE HARVESTING (EXISTING)      src/idle/                |
|  [existing] Battery/thermal-aware mobile compute collection                 |
|  [enhanced] Reports to ExeUnit runtime for actual job execution             |
|                                                                              |
|  LAYER 4: VPN/ONION ROUTING (EXISTING)            src/vpn/                 |
|  [existing] Circuit management, privacy-preserving task routing             |
|  [enhanced] Tasks routed through PQ-hardened BetaNet (Layer 1)              |
|                                                                              |
|  LAYER 3: P2P UNIFIED (EXISTING, ENHANCED)        src/p2p/                 |
|  [existing] Cross-protocol bridge (BLE + HTX + Mesh)                        |
|  [enhanced] + store-and-forward spool for offline peers                     |
|  [from Katzenpost Spool design] Reimplemented in Rust                       |
|                                                                              |
|  LAYER 2: BITCHAT MESSAGING (UPGRADED)            src/bitchat/             |
|  [existing] WebRTC mesh + BLE, ChaCha20-Poly1305 E2E                       |
|  [upgraded] + OpenMLS group encryption (Rust->WASM->TypeScript)             |
|  [upgraded] + store-and-forward for offline delivery                        |
|  Closes: group messaging gap, offline message gap                           |
|                                                                              |
|  LAYER 1: BETANET PRIVACY MIXNET (UPGRADED)       src/betanet/             |
|  [existing] Sphinx onion routing, VRF delays, 25k pkt/s pipeline           |
|  [upgraded] + HOPR Proof-of-Relay (verifiable packet forwarding)            |
|  [upgraded] + Katzenpost HPQC post-quantum KEM (hybrid classical+PQ)       |
|  [upgraded] + HOPR-style economic incentives per relay hop                  |
|  Closes: relay verification gap, PQ gap, incentive gap                      |
|                                                                              |
+==============================================================================+
```

---

## LAYER-BY-LAYER: WHAT CHANGES

### LAYER 1: BetaNet v2 (Privacy Mixnet - MAJOR UPGRADE)

**Before (v1)**:
```
src/betanet/
  core/       mixnode, routing, reputation, relay_lottery, config
  crypto/     sphinx, crypto (ChaCha20, X25519, Ed25519)
  vrf/        vrf_delay, vrf_neighbor, poisson_delay
  utils/      rate, delay, packet, timing_defense
  pipeline.rs
  cover.rs
  lib.rs
```

**After (v2)**:
```
src/betanet/
  core/            mixnode, routing, reputation, relay_lottery, config
  crypto/
    sphinx.rs      [existing] Sphinx onion routing
    crypto.rs      [existing] ChaCha20, X25519, Ed25519, BLAKE3
    pq_kem.rs      [NEW: from Katzenpost HPQC] Hybrid PQ KEM (MLKEM-768 + X25519)
    pq_sphinx.rs   [NEW] PQ-hardened Sphinx headers (hybrid ephemeral keys)
  vrf/             vrf_delay, vrf_neighbor, poisson_delay
  relay/
    proof.rs       [NEW: from HOPR] Proof-of-Relay cryptographic verification
    incentive.rs   [NEW: from HOPR] Per-hop payment channels for relay rewards
    verifier.rs    [NEW] Validates relay proofs from downstream nodes
  utils/           rate, delay, packet, timing_defense
  pipeline.rs      [enhanced] Pipeline now validates relay proofs inline
  cover.rs
  lib.rs
```

**What changes functionally**:

| Feature | v1 | v2 |
|---------|----|----|
| Packet format | Sphinx (classical X25519) | Hybrid Sphinx (MLKEM-768 + X25519) |
| Header size | 176 bytes | ~256 bytes (PQ key adds ~80 bytes) |
| Relay trust | None (hope nodes forward honestly) | Proof-of-Relay (cryptographic proof of forwarding) |
| Relay incentives | None | Per-hop micro-payments via payment channels |
| Quantum resistance | None | Hybrid PQ/classical (safe against quantum + classical) |
| Pipeline throughput | 25k pkt/s | ~20-22k pkt/s (PQ overhead ~10-15%) |

**Performance impact**: PQ KEM adds ~10-15% overhead to Sphinx processing. Pipeline throughput drops from 25k to ~20-22k pkt/s. Still 2x faster than Nym. Proof-of-Relay adds <1% overhead (one hash verification per hop).

**Security upgrade**: The system goes from "trust nodes to forward packets" to "mathematically verify they did." This is a fundamental trust model upgrade.

---

### LAYER 2: BitChat v2 (Messaging - SIGNIFICANT UPGRADE)

**Before (v1)**:
```
src/bitchat/
  types/          index.ts (interfaces)
  protocol/       webrtc.ts, bluetooth.ts
  encryption/     chacha20.ts
  hooks/          useBitChatService.ts
  ui/             BitChatInterface, PeerList, ConversationView, NetworkStatus
```

**After (v2)**:
```
src/bitchat/
  types/          index.ts [enhanced: group types, offline types]
  protocol/
    webrtc.ts     [existing]
    bluetooth.ts  [existing]
    spool.ts      [NEW] Store-and-forward client (queues msgs for offline peers)
  encryption/
    chacha20.ts   [existing] 1:1 E2E encryption
    mls.ts        [NEW: from OpenMLS via WASM] Group encryption (MLS protocol)
    mls_wasm.wasm [NEW] Compiled OpenMLS Rust -> WASM
  hooks/
    useBitChatService.ts    [enhanced: group state, offline queue]
    useGroupChat.ts         [NEW] Group creation, membership, key management
  ui/
    BitChatInterface.tsx    [enhanced]
    PeerList.tsx            [existing]
    ConversationView.tsx    [enhanced: group threads]
    NetworkStatus.tsx       [existing]
    GroupChatView.tsx       [NEW] Multi-party conversation UI
    OfflineIndicator.tsx    [NEW] Shows queued message status
```

**What changes functionally**:

| Feature | v1 | v2 |
|---------|----|----|
| Encryption model | 1:1 ChaCha20-Poly1305 | 1:1 ChaCha20 + Group MLS (Messaging Layer Security) |
| Max participants | 2 (1:1 only) | Unlimited (MLS tree-based key management) |
| Offline delivery | Message lost if peer offline | Store-and-forward spool queues until peer reconnects |
| Key management | Per-peer static keys + rotation | MLS ratchet tree (forward secrecy per message) |
| Group operations | N/A | Create, invite, remove, leave, key update |

**MLS Protocol Integration** (from OpenMLS, MIT license):
- Compiled Rust -> WASM for browser compatibility
- TreeKEM for efficient group key management
- Forward secrecy and post-compromise security
- Scales to 1000+ members per group
- ~50KB WASM bundle added to frontend

---

### LAYER 3: P2P Unified v2 (Enhanced)

**New addition**: Store-and-forward spool service

```
src/p2p/
  [existing files]
  spool/
    spool_service.rs   [NEW: inspired by Katzenpost] Message queue daemon
    spool_client.py    [NEW] Python client for spool service
    retention.rs       [NEW] TTL-based message expiry (7 days default)
```

**How it works**: When a message targets an offline peer, the P2P layer writes it to the spool. When the peer reconnects (via WebRTC or BLE), the spool drains queued messages to them. Messages expire after 7 days. Spool is encrypted at rest (per-recipient key).

---

### LAYERS 7-8-9: The Compute Stack (NEW + MAJOR UPGRADE)

This is where the biggest transformation happens. Three layers replace what was mostly stubs.

**Before (v1)**:
```
src/batch/           Python stubs (placement.py, sla_classes.py, marketplace.py)
src/scheduler/       Python stubs (intelligent_scheduler.py, resource_pool.py)
                     No actual container execution. Docker stubs flagged in MECE.
```

**After (v2)**:
```
src/runtime/                    [NEW: from Golem Yagna ExeUnit]
  exe_unit/
    mod.rs                      ExeUnit manager (Rust)
    vm_runtime.rs               VM-based execution backend
    wasm_runtime.rs             WASM-based execution (wasmtime)
    docker_runtime.rs           Docker container execution
    resource_meter.rs           CPU/memory/disk metering per task
    sandbox.rs                  Seccomp + namespace isolation
    output_capture.rs           stdout/stderr/artifact collection
  task_api.rs                   gRPC API for Python scheduler to submit tasks
  health.rs                     Liveness + readiness probes

src/orchestrator/               [NEW: inspired by Akash Provider]
  mod.rs                        Orchestrator main loop
  k8s_client.rs                 Kubernetes API client (kube-rs crate)
  manifest.rs                   Deployment manifest parsing
  scaling.rs                    Dynamic replica scaling (up/down)
  health_checks.rs              Pod health monitoring
  resource_allocator.rs         CPU/GPU/memory allocation from pool
  lifecycle.rs                  Pod create -> running -> cleanup lifecycle

src/attestation/                [NEW: inspired by iExec SMS]
  mod.rs                        Attestation coordinator
  tee_detect.rs                 Runtime TEE detection (SGX vs TDX vs none)
  sgx_attestation.rs            Intel SGX remote attestation flow
  tdx_attestation.rs            Intel TDX attestation flow
  zk_proof.rs                   ZK proof of correct execution (for non-TEE nodes)
  result_verifier.rs            Verify task output matches attestation claim
  quote_parser.rs               Parse SGX/TDX quotes

src/batch/                      [EXISTING, ENHANCED]
  placement.py                  [enhanced] Dispatches to ExeUnit via gRPC
  sla_classes.py                [existing]
  enhanced_sla_tiers.py         [existing]
  marketplace.py                [enhanced] Bridges to Yagna Market protocol
```

**What this means in practice**:

| Capability | v1 | v2 |
|------------|----|----|
| Can execute real compute tasks | No (stubs) | Yes (VM, WASM, Docker) |
| Resource metering | No | Per-task CPU/memory/disk tracking |
| Sandboxing | No | Seccomp + Linux namespaces |
| Container orchestration | Docker stubs | Full K8s lifecycle via kube-rs |
| Scaling | No | Dynamic replica scaling |
| Task verification | No | TEE attestation OR ZK proof |
| TEE support | No | SGX + TDX (4-8% overhead) |

---

### LAYER 10: Task Marketplace v2 (MAJOR UPGRADE)

**Before (v1)**:
```
src/tokenomics/
  __init__.py                    ~400 LOC, 55% maturity
  fog_tokenomics_service.py      Basic stubs
  tokenomics_integration.py      Basic stubs
  unified_dao_tokenomics_system.py  Basic stubs
```

**After (v2)**:
```
src/market/                     [NEW: from Golem Yagna Market protocol]
  protocol/
    offer.rs                    Provider capability advertisements
    demand.rs                   Requestor task requirements
    negotiation.rs              Multi-round offer/demand matching
    agreement.rs                Binding agreement with SLA terms
    payment.rs                  Payment channel management (escrow + release)
  matching/
    engine.rs                   Automated offer<->demand matching
    scoring.rs                  Reputation-weighted scoring algorithm
    filters.rs                  SLA tier filters, geo filters, TEE requirement filters
  governance/
    dao.rs                      On-chain voting (proposal + execution)
    treasury.rs                 Fee collection + distribution
    parameter_updates.rs        Governance-controlled system parameters

src/tokenomics/                 [EXISTING, SIMPLIFIED]
  token.rs                      ERC-20 token interface (Rust + Solidity bridge)
  pricing.rs                    Dynamic pricing engine (supply/demand curves)
  rewards.rs                    Compute/relay reward calculation
```

**What this means**:

| Capability | v1 | v2 |
|------------|----|----|
| Marketplace protocol | None (stubs) | Full offer/demand/negotiate/agree lifecycle |
| Payment | None | Escrow-based payment channels |
| Matching | None | Automated matching with reputation weighting |
| Governance | Stub DAO | On-chain DAO with treasury management |
| Dynamic pricing | Concept only | Supply/demand curve pricing engine |

---

### LAYER 11: Staking & Sybil Resistance (ENTIRELY NEW)

```
contracts/staking/              [NEW: from HOPR SafeStaking]
  FogSafe.sol                   SafeStaking vault (multi-sig + time-lock)
  FogStaking.sol                Staking registry (min stake, epoch management)
  FogSlashing.sol               Slashing conditions (failed relay proofs, bad attestations)
  NodeRegistry.sol              On-chain node registration + metadata
  RewardDistributor.sol         Epoch-based reward distribution
  GovernanceToken.sol           ERC-20 governance token
  test/
    FogStaking.t.sol            Foundry test suite
    FogSlashing.t.sol
```

**What this means**:

| Capability | v1 | v2 |
|------------|----|----|
| Sybil resistance | None | Minimum stake required to operate node |
| Slashing | None | Bad behavior (failed proofs, bad attestations) = stake loss |
| Node admission | Open (anyone can pretend to be a node) | Staking gate + on-chain registration |
| Fund safety | N/A | SafeStaking vault (funds safe even if node compromised) |
| Reward distribution | None | Automated epoch-based rewards for relay + compute |

---

## UPGRADED COMPETITIVE POSITION

### Before (v1) vs After (v2) Feature Comparison

| Feature | v1 | v2 | Closest Competitor | v2 vs Competitor |
|---------|----|----|-------------------|-----------------|
| Mixnet routing | Yes | Yes + PQ + PoR | Nym | **Ahead** (PQ + PoR, Nym has neither) |
| Mixnet throughput | 25k pkt/s | ~20-22k pkt/s | Nym (~10k est.) | **Still 2x ahead** |
| P2P messaging | 1:1 only | 1:1 + Groups + Offline | Briar | **Parity** (Briar still has more transports) |
| Container execution | Stubs | VM/WASM/Docker | Akash (K8s) | **Near parity** (Akash has more GPU) |
| Task marketplace | Stubs | Full protocol | Golem (Yagna) | **Parity** (using their protocol) |
| Staking | None | SafeStaking + slashing | HOPR | **Parity** (using their design) |
| Compute attestation | None | SGX/TDX + ZK fallback | iExec | **Near parity** (iExec has more TEE experience) |
| Post-quantum crypto | None | Hybrid MLKEM-768 + X25519 | Katzenpost | **Parity** (using their crypto lib) |
| Idle harvesting | Yes | Yes (now executes real tasks) | Nobody | **Unique** |
| Self-benchmarking | Yes | Yes (enhanced) | Nobody | **Unique** |
| Privacy-routed compute | Concept | Working (tasks through mixnet) | Nobody | **Unique** |

### Competitive Positioning Shift

```
                        HIGH PRIVACY
                            |
                  Nym       |    FOG COMPUTE v2
                  HOPR      |    *** DOMINANT POSITION ***
                  Katzenpost|    (privacy + compute + messaging +
                            |     attestation + marketplace + staking)
                            |
    NO COMPUTE -------------+------------- FULL COMPUTE
                            |
                  Briar     |    Akash, Golem, iExec
                  Session   |    io.net, Render
                  Mysterium |
                            |
                        LOW PRIVACY
```

**v1 was in the upper-right but couldn't prove it** (stubs, no staking, no attestation).
**v2 occupies and defends the upper-right** with real execution, verified relay, and economic incentives.

---

## WHAT REMAINS AFTER v2

### Gaps Still Open (3 of 12)

| Gap | Why Still Open | Path Forward |
|-----|---------------|--------------|
| **Live network** | Can't import this - need to deploy nodes | Testnet with 50+ nodes, then incentivized mainnet |
| **GPU support** | None of the Rust integrations bring GPU scheduling | Add CUDA/ROCm detection to ExeUnit, or integrate with io.net API |
| **Mobile SDK** | No open-source mobile fog SDK exists to integrate | Build React Native wrapper around idle compute + BitChat |

### New Capabilities Unlocked

| Capability | What It Enables |
|------------|----------------|
| Privacy-routed confidential compute | Run AI inference through mixnet with TEE attestation. Nobody else can do this. |
| Verifiable idle harvesting | Prove that a phone actually ran your computation correctly (attestation + PoR) |
| Censorship-resistant group messaging | MLS-encrypted groups routed through mixnet with offline delivery |
| Trustless marketplace | Stake-backed nodes, escrowed payments, slashing for misbehavior |
| Quantum-safe anonymity | Hybrid PQ Sphinx survives quantum computers. Only Katzenpost shares this. |

---

## IMPLEMENTATION ROADMAP

### Phase 1: Foundation (Weeks 1-3)
- Adopt GPL-3.0 license
- Import HOPR Proof-of-Relay module into BetaNet
- Import Golem Yagna ExeUnit crate (VM + WASM backends)
- Write integration tests for relay proof verification
- **Deliverable**: BetaNet verifies relays, ExeUnit runs real WASM tasks

### Phase 2: Marketplace (Weeks 4-6)
- Import Golem Yagna Market protocol
- Bridge Python scheduler to Rust market via gRPC
- Implement offer/demand matching with reputation scoring
- **Deliverable**: End-to-end task submission -> matching -> execution -> payment

### Phase 3: Security Hardening (Weeks 7-9)
- Deploy HOPR SafeStaking contracts (Foundry + EVM testnet)
- Integrate Katzenpost HPQC into Sphinx layer
- Build attestation module (SGX detection + quote verification)
- **Deliverable**: Staked nodes, PQ-hardened packets, TEE attestation

### Phase 4: Messaging Upgrade (Weeks 10-11)
- Compile OpenMLS to WASM, integrate into BitChat
- Build store-and-forward spool service (Rust)
- Add group chat UI components
- **Deliverable**: Group E2E messaging with offline delivery

### Phase 5: Container & Orchestration (Weeks 12-14)
- Build K8s orchestrator using kube-rs
- Add Docker execution backend to ExeUnit
- Implement ZK proof fallback for non-TEE nodes
- **Deliverable**: Full container lifecycle management

### Phase 6: Testnet (Weeks 15-18)
- Deploy 50-node testnet
- Run benchmark suite against live network
- Stress test marketplace + staking + attestation
- **Deliverable**: Live testnet with verified performance metrics

**Total estimated effort**: 18 weeks (4.5 months) for a single experienced Rust developer, or 9 weeks with 2 developers working in parallel on compute stack vs privacy stack.

---

## FILE TREE: COMPLETE v2 STRUCTURE

```
fog-compute/
  LICENSE                          GPL-3.0 (NEW)
  Cargo.toml                       Workspace root
  contracts/                       (NEW)
    staking/
      FogSafe.sol
      FogStaking.sol
      FogSlashing.sol
      NodeRegistry.sol
      RewardDistributor.sol
      GovernanceToken.sol
      test/
        FogStaking.t.sol
        FogSlashing.t.sol
      foundry.toml
  src/
    betanet/                       (UPGRADED)
      core/
        mixnode.rs
        routing.rs
        reputation.rs              [enhanced: relay proof scores]
        relay_lottery.rs
        config.rs
        protocol_version.rs
        versions.rs
        compatibility.rs
        mod.rs
      crypto/
        sphinx.rs                  [enhanced: PQ header support]
        crypto.rs
        pq_kem.rs                  [NEW: from Katzenpost HPQC]
        pq_sphinx.rs               [NEW: hybrid Sphinx headers]
        mod.rs
      relay/                       [NEW: from HOPR]
        proof.rs                   [Proof-of-Relay]
        incentive.rs               [Per-hop payments]
        verifier.rs                [Proof validation]
        mod.rs
      vrf/
        vrf_delay.rs
        vrf_neighbor.rs
        poisson_delay.rs
        mod.rs
      utils/
        rate.rs
        delay.rs
        packet.rs
        timing_defense.rs
        mod.rs
      server/
        tcp.rs
        http.rs
        mod.rs
      pipeline.rs                  [enhanced: relay proof inline check]
      cover.rs
      lib.rs
      Cargo.toml
    bitchat/                       (UPGRADED)
      types/
        index.ts                   [enhanced: group + offline types]
      protocol/
        webrtc.ts
        bluetooth.ts
        spool.ts                   [NEW: store-and-forward client]
      encryption/
        chacha20.ts
        mls.ts                     [NEW: OpenMLS WASM bridge]
        mls_wasm.wasm              [NEW: compiled from OpenMLS Rust]
      hooks/
        useBitChatService.ts       [enhanced]
        useGroupChat.ts            [NEW]
      ui/
        BitChatInterface.tsx
        PeerList.tsx
        ConversationView.tsx       [enhanced: group threads]
        NetworkStatus.tsx
        GroupChatView.tsx           [NEW]
        OfflineIndicator.tsx        [NEW]
      index.ts
    runtime/                       [NEW: from Golem Yagna ExeUnit]
      exe_unit/
        mod.rs
        vm_runtime.rs
        wasm_runtime.rs
        docker_runtime.rs
        resource_meter.rs
        sandbox.rs
        output_capture.rs
      task_api.rs
      health.rs
      Cargo.toml
    orchestrator/                  [NEW: inspired by Akash]
      mod.rs
      k8s_client.rs
      manifest.rs
      scaling.rs
      health_checks.rs
      resource_allocator.rs
      lifecycle.rs
      Cargo.toml
    attestation/                   [NEW: inspired by iExec]
      mod.rs
      tee_detect.rs
      sgx_attestation.rs
      tdx_attestation.rs
      zk_proof.rs
      result_verifier.rs
      quote_parser.rs
      Cargo.toml
    market/                        [NEW: from Golem Yagna Market]
      protocol/
        offer.rs
        demand.rs
        negotiation.rs
        agreement.rs
        payment.rs
      matching/
        engine.rs
        scoring.rs
        filters.rs
      governance/
        dao.rs
        treasury.rs
        parameter_updates.rs
      Cargo.toml
    p2p/                           (ENHANCED)
      spool/
        spool_service.rs           [NEW: inspired by Katzenpost]
        spool_client.py            [NEW]
        retention.rs               [NEW]
      [existing files]
    batch/                         (ENHANCED)
      [existing files, dispatch to ExeUnit]
    idle/                          (ENHANCED)
      [existing files, report to ExeUnit]
    vpn/                           (ENHANCED)
      [existing files, route through PQ BetaNet]
    tokenomics/                    (SIMPLIFIED)
      token.rs
      pricing.rs
      rewards.rs
    fog/                           (EXISTING)
      [existing benchmark suite]
    scheduler/                     (EXISTING)
      [existing files]
    config/                        (EXISTING)
      [existing files]
  backend/                         (EXISTING)
    [existing backend server]
  control-panel/                   (EXISTING)
    [existing Next.js control panel]
  docs/
    FOG-COMPUTE-COMPETITIVE-ANALYSIS.md
    FOG-COMPUTE-V2-ARCHITECTURE.md  (THIS FILE)
    [existing docs]
```

---

## DEPENDENCY ADDITIONS (Cargo.toml)

```toml
# NEW dependencies for v2 integrations

# Post-quantum crypto (from Katzenpost)
ml-kem = "0.2"                    # MLKEM-768 KEM
hybrid-array = "0.2"              # Hybrid key encapsulation

# Proof-of-relay (from HOPR patterns)
# (Custom implementation using existing crypto crates)

# Task execution (from Golem Yagna ExeUnit)
wasmtime = "18.0"                 # WASM runtime
bollard = "0.16"                  # Docker API client
nix = "0.28"                      # Linux namespace/seccomp

# Container orchestration (Akash-inspired)
kube = "0.88"                     # Kubernetes client
k8s-openapi = "0.21"              # K8s API types

# TEE attestation (iExec-inspired)
sgx-isa = "0.4"                   # SGX instruction set abstractions
# dcap-ql (Intel DCAP for remote attestation)

# Marketplace (from Golem Yagna Market)
# gRPC for Python<->Rust bridge
tonic = "0.11"                    # gRPC server/client
prost = "0.12"                    # Protocol buffers

# ZK proofs (for non-TEE attestation fallback)
ark-snark = "0.4"                 # arkworks ZK-SNARK library
```

---

## SUMMARY: What Fog Compute v2 Becomes

**v1**: A promising architecture with real privacy networking but mostly stubs for compute, no marketplace, no staking, no attestation, and 1:1-only messaging.

**v2**: **The only platform in existence that combines**:
1. Post-quantum-hardened mixnet routing (25k pkt/s)
2. Cryptographically verified relay forwarding
3. Group-encrypted P2P messaging with offline delivery
4. Real task execution (VM/WASM/Docker) with TEE attestation
5. Full marketplace protocol with reputation-weighted matching
6. Stake-backed Sybil resistance with slashing
7. Battery-aware idle device harvesting
8. Self-validating benchmark suite

No single competitor has more than 3 of these 8. Fog Compute v2 has all 8.

**The pitch becomes**: "Privacy-preserving distributed compute with verifiable execution, quantum-safe anonymity, and a trustless marketplace -- built entirely on battle-tested open-source components from Nym, HOPR, Golem, Katzenpost, OpenMLS, and iExec."
