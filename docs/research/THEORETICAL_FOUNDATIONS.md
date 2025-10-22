# Theoretical Foundations and Architecture Standards
## Fog-Compute Project Research Report

**Date:** 2025-10-21
**Researcher:** Research Specialist Agent
**Objective:** Establish theoretical foundations and best practices for each layer based on academic/industry standards

---

## 1. Betanet 1.2 - Privacy Mixnet

### Theoretical Foundation

**Core Concepts:**
- **Sphinx Packet Format**: Compact and provably secure mix format providing unlinkability for each leg of packet's journey
- **VRF-Based Routing**: Verifiable Random Functions ensure randomly chosen routes according to publicly known routing policy
- **Poisson Mixing**: Continuous-time mixing with Poisson-distributed delays for traffic analysis resistance
- **Cover Traffic**: Dummy packets to prevent flow correlation attacks

**Key Algorithms:**
1. **Sphinx Cryptographic Operations** (Danezis & Goldberg, 2009)
   - Layered encryption with header transformation
   - Replay detection via seen packet IDs
   - Path length hiding
   - Indistinguishable replies

2. **VRF-Based Node Selection** (Diaz, Halpin, Kiayias, 2024)
   - Verifiable randomness for relay lottery
   - Decentralized reliability estimation
   - Measurement packet lottery system
   - Prevents biased route selection

3. **Poisson Delay Scheduling**
   - Exponential distribution: f(x; λ) = λe^(-λx) for x ≥ 0
   - Memoryless property prevents timing correlation
   - Per-hop delay parameter tuning

**Performance Targets:**
- **Latency**: 3-10 seconds per hop (continuous-time mixing)
- **Throughput**: 10-100 KB/s per node (cover traffic dependent)
- **Anonymity Set**: Minimum 5-10 concurrent messages per mix
- **Packet Size**: 2KB (standard Sphinx), up to 32KB (extended)

### Industry Standards

**Established Protocols:**
- **Sphinx v1.0** (IEEE S&P 2009) - Original specification
- **Outfox** (2024) - Post-quantum Sphinx variant
- **Nym Mixnet** - Production implementation using Sphinx
- **Katzenpost** - Modern mixnet framework

**Reference Implementations:**
- `sphinxmixcrypto` (Python) - Applied Mixnetworks project
- Katzenpost Sphinx - Go implementation with full spec compliance
- Nym mixnet - Rust implementation with VRF extensions

**Best Practices:**
- Use 5-layer circuits minimum for strong anonymity
- Implement replay detection with time-windowed bloom filters
- Deploy cover traffic at 10-30% of actual traffic rate
- Rotate mix keys every 24-48 hours
- Monitor and publish mix node uptime/reliability

### Academic Research

**Seminal Papers:**
1. **Sphinx: A Compact and Provably Secure Mix Format** (Danezis & Goldberg, 2009, IEEE S&P)
   - Proved security in random oracle model
   - Introduced header transformation mechanism
   - O(log n) header size vs O(n) in previous designs

2. **Decentralized Reliability Estimation for Low Latency Mixnets** (Diaz, Halpin, Kiayias, 2024, arXiv)
   - VRF-based routing novel primitive
   - Public verifiability of measurement packets
   - No impact on client packet latency

3. **The Traffic Analysis of Continuous-Time Mixes** (Serjantov & Sewell, 2002)
   - Analyzed anonymity set size using differential entropy
   - Poisson arrival rate assumptions
   - Impact of pool mixing vs continuous-time

4. **LARMix++: Latency-Aware Routing in Mix Networks** (2024)
   - Free routes topology for reduced latency
   - Maintains security under timing attacks
   - Stratified architecture optimization

5. **MixMatch: Flow Matching for Mixnet Traffic** (PoPETs 2024.2)
   - Traffic analysis countermeasures
   - Adaptive cover traffic generation
   - Flow-level anonymity preservation

**Recent Advances (2022-2025):**
- Post-quantum Sphinx variants (Outfox, 2024)
- VRF integration for decentralized monitoring
- Machine learning for traffic pattern optimization
- Latency reduction techniques (LARMix series)

### Architecture Patterns

**Component Breakdown:**
```
Mixnet Layer Architecture:
├── Packet Processing
│   ├── Sphinx Header Unwrapping
│   ├── Payload Decryption (per-hop)
│   └── Replay Detection (bloom filter)
├── Delay Scheduling
│   ├── Poisson RNG (cryptographically secure)
│   ├── Queue Management (FIFO with delays)
│   └── Cover Traffic Generator
├── Routing
│   ├── VRF-Based Next Hop Selection
│   ├── Circuit Construction (client-side)
│   └── Path Verification
└── Reliability Monitoring
    ├── Measurement Packet Handling
    ├── Public Proof Verification
    └── Reputation Score Computation
```

**Integration Patterns:**
- **Directory Service Integration**: Fetch mix descriptors (keys, addresses, stats)
- **DHT Integration**: Decentralized mix discovery and reputation storage
- **Application Layer**: SOCKS5 proxy or custom protocol gateway
- **Network Layer**: Compatible with TCP, UDP, QUIC transports

### What SHOULD Be Implemented

**Minimum Viable Functionality:**
1. **Core Sphinx Operations**
   - Header unwrapping with EC-DH (Curve25519)
   - LIONESS-based payload encryption
   - Replay detection with rolling bloom filter (1M entry capacity)
   - SURB (Single Use Reply Block) support

2. **Delay Scheduling**
   - Poisson delay with configurable λ parameter
   - Queue-based packet buffering
   - Basic cover traffic (constant rate dummy packets)

3. **Routing Infrastructure**
   - Client-side circuit construction (5-hop default)
   - Mix descriptor fetching from directory
   - Path selection with diversity constraints

4. **Reliability Features**
   - Basic uptime monitoring
   - Failed node detection and rerouting
   - Mix descriptor validation

**Optional Advanced Features:**
- VRF-based routing with public verifiability
- Decentralized reliability estimation protocol
- Adaptive cover traffic (traffic-dependent rates)
- Post-quantum Sphinx (Outfox variant)
- Stratified topology with latency optimization
- Multi-path routing for high-availability

**Performance Expectations:**
- **Message Latency**: 15-50 seconds end-to-end (5 hops × 3-10s per hop)
- **Throughput**: 50-200 KB/s per mix node
- **Success Rate**: >95% packet delivery
- **Anonymity Set**: >10 concurrent users per mix
- **Resource Usage**: <100 MB RAM, <5% CPU per 1000 packets/hour

---

## 2. BitChat - Offline P2P Messaging

### Theoretical Foundation

**Core Concepts:**
- **Delay Tolerant Networking (DTN)**: Store-carry-forward paradigm for intermittent connectivity
- **Opportunistic Routing**: Message relay during brief contact windows
- **BLE Mesh Networking**: Multi-hop ad-hoc networking using Bluetooth Low Energy
- **Epidemic Routing**: Replication-based forwarding to maximize delivery probability

**Key Algorithms:**
1. **PRoPHET (Probabilistic Routing Protocol using History of Encounters and Transitivity)**
   - Delivery predictability: P(a,b) based on encounter history
   - Aging equation: P(a,b) = P(a,b)_old × γ^k (where γ ∈ [0,1], k = time units)
   - Transitivity: P(a,c) = P(a,b) × P(b,c) × β (where β is transitivity factor)
   - Forwards messages when P_sender > P_receiver

2. **Epidemic Routing**
   - Summary Vector Exchange: Nodes exchange message ID lists
   - Full replication: Forward all messages not in peer's summary
   - Resource-intensive but maximizes delivery probability

3. **Spray and Wait**
   - Spray phase: Create L copies, distribute to first L/2 nodes
   - Wait phase: Direct transmission only
   - Limits message flooding while maintaining delivery probability

**BLE Mesh Mechanisms:**
- **Managed Flooding**: Messages broadcast via advertising channels
- **Advertising Bearer**: Non-connectable advertisements for mesh PDUs
- **GATT Bearer**: Connection-based mesh for commissioning
- **TTL (Time-to-Live)**: Hop count limitation to prevent infinite loops

**Performance Targets:**
- **Message Latency**: Minutes to hours (opportunistic delivery)
- **Delivery Success**: 70-90% (depends on node density and mobility)
- **Throughput**: 1-10 KB/s (BLE 4.x), 20-50 KB/s (BLE 5.x)
- **Range**: 10-100m (BLE), extended via multi-hop
- **Network Size**: 100-1000 nodes (practical BLE mesh)

### Industry Standards

**Established Protocols:**
- **RFC 4838**: DTN Architecture (IRTF, 2007)
- **RFC 5050**: Bundle Protocol Specification (2007)
- **Bluetooth Mesh Profile v1.0** (2017) - Official Bluetooth SIG standard
- **PRoPHET** (RFC 6693, 2012) - Probabilistic routing for DTN

**Reference Implementations:**
- **Berty Protocol**: libp2p + BLE for offline messaging (open source)
- **Briar**: Tor + BLE mesh for secure P2P chat
- **FireChat**: Proprietary mesh messaging (iOS/Android)
- **BE-Mesh**: Open source Android BLE mesh library
- **CSRmesh**: Proprietary BLE mesh (pre-standard)

**Best Practices:**
- Message size limits: <1KB for efficient BLE transmission
- TTL configuration: 5-10 hops for urban deployments
- Battery management: Advertising intervals >1s for mobile devices
- Encryption: End-to-end encryption (Signal Protocol, Double Ratchet)
- Message expiry: 24-72 hours for storage management
- Deduplication: Message ID tracking to prevent storage bloat

### Academic Research

**Seminal Papers:**
1. **Delay-Tolerant Networking Architecture** (Fall, 2003, ACM SIGCOMM Workshop)
   - Introduced store-carry-forward paradigm
   - Bundle layer abstraction above transport
   - Custody transfer for reliability

2. **Epidemic Routing for Partially Connected Ad Hoc Networks** (Vahdat & Becker, 2000)
   - First replication-based DTN routing
   - Summary vector exchange protocol
   - Probabilistic forwarding analysis

3. **BLEmesh: A Wireless Mesh Network Protocol for Bluetooth Low Energy Devices** (2015, IEEE)
   - Broadcasting-based mesh without connections
   - GAP non-connectable advertisements
   - Evaluated throughput and latency characteristics

4. **Bluetooth Low Energy Mesh Networks: Survey of Communication and Security Protocols** (2020, Sensors)
   - Comprehensive taxonomy of BLE mesh protocols
   - Security analysis of flooding-based approaches
   - Comparison of official Bluetooth Mesh vs proprietary solutions

5. **Berty, Libp2p and Bluetooth Low Energy** (Berty Technologies, 2020)
   - Integration of libp2p transport over BLE
   - Peer-to-peer messaging without internet
   - Cross-platform driver implementation

**Recent Advances (2022-2025):**
- Machine learning for contact prediction in opportunistic networks
- Social-aware routing using community detection
- Energy-efficient BLE mesh with adaptive advertising intervals
- Integration of BLE mesh with LoRa for extended range

### Architecture Patterns

**Component Breakdown:**
```
Offline P2P Messaging Architecture:
├── Transport Layer
│   ├── BLE Advertiser/Scanner
│   ├── Connection Manager (GATT for large messages)
│   └── Protocol Multiplexer (identify peer types)
├── DTN Bundle Layer
│   ├── Bundle Creation/Parsing
│   ├── Custody Transfer (store-and-forward)
│   └── Fragment/Reassembly (for large messages)
├── Routing Engine
│   ├── PRoPHET Probability Calculator
│   ├── Encounter History Database
│   └── Forwarding Decision Logic
├── Message Storage
│   ├── Pending Messages Queue
│   ├── Delivered Messages Archive
│   └── Deduplication Index (message IDs)
├── Cryptography
│   ├── Double Ratchet Key Exchange
│   ├── End-to-End Encryption
│   └── Identity Verification
└── Contact Management
    ├── Peer Discovery (BLE scanning)
    ├── Trust Model (contact list, strangers)
    └── Delivery Receipts (when online)
```

**Integration Patterns:**
- **Hybrid Online/Offline**: Switch between internet and BLE mesh based on connectivity
- **Gateway Nodes**: Bridging BLE mesh to internet for syncing
- **Multi-Protocol**: Combine BLE, WiFi Direct, LoRa for different ranges
- **Federated Storage**: Distributed message storage across trusted peers

### What SHOULD Be Implemented

**Minimum Viable Functionality:**
1. **BLE Mesh Transport**
   - Advertising bearer (non-connectable ads for message broadcast)
   - GATT bearer (connection for >20 byte messages)
   - TTL-based hop limiting (default 7 hops)
   - Message deduplication (seen message ID cache)

2. **DTN Store-and-Forward**
   - Local message queue (persistent storage)
   - Bundle creation with source/destination IDs
   - Custody transfer mechanism
   - Message expiry (configurable TTL, default 48h)

3. **Basic Routing**
   - Epidemic routing for initial deployment
   - Summary vector exchange protocol
   - Optional: PRoPHET with delivery predictability

4. **Security Baseline**
   - End-to-end encryption (Signal Protocol recommended)
   - Message authentication codes
   - Forward secrecy (ratcheting keys)

5. **User Features**
   - Text messaging (<1KB per message)
   - Delivery status (sent, relayed, delivered)
   - Contact management (trusted peer list)

**Optional Advanced Features:**
- Social-aware routing (community-based forwarding)
- Adaptive replication (spray-and-wait with dynamic L)
- Network coding for reliability
- Image/file transfer (chunking + reassembly)
- Voice messages (compressed audio)
- Mesh topology visualization
- Reputation-based routing (trusted relays)

**Performance Expectations:**
- **Message Delivery**: 70-85% success in urban environments
- **Latency**: 5-30 minutes for messages within 500m radius
- **Battery Consumption**: <5% per hour with 10s advertising intervals
- **Storage**: 10-50 MB for message queue
- **Network Density**: Functional with >5 active nodes within 50m

---

## 3. P2P Unified Systems

### Theoretical Foundation

**Core Concepts:**
- **Distributed Hash Tables (DHT)**: Decentralized key-value storage with logarithmic lookup
- **Gossip Protocols**: Epidemic information dissemination for peer discovery and state sync
- **NAT Traversal**: Peer connectivity despite Network Address Translation
- **Hybrid P2P**: Combination of DHT, gossip, and optional super-peers

**Key Algorithms:**
1. **Kademlia DHT** (Maymounkov & Mazières, 2002)
   - XOR metric for distance: d(a,b) = a ⊕ b
   - k-buckets routing table (k=20 typical)
   - Parallel lookups: α concurrent RPCs (α=3)
   - Node lookup complexity: O(log N)
   - Key operations: FIND_NODE, FIND_VALUE, STORE

2. **Chord DHT** (Stoica et al., 2001)
   - Consistent hashing on circular identifier space
   - Finger table: m entries for 2^m address space
   - Lookup complexity: O(log N)
   - Stabilization protocol for maintaining correctness

3. **GossipSub** (libp2p pubsub)
   - Topic-based mesh overlay (DEGREE_LOW=6, DEGREE_HIGH=12)
   - Heartbeat protocol (1 second intervals)
   - IHAVE/IWANT metadata exchange
   - Peer scoring for flood protection

4. **ICE (Interactive Connectivity Establishment)** - RFC 8445
   - STUN for address discovery
   - TURN for relay fallback
   - Candidate gathering and connectivity checks
   - Priority-based selection

**Performance Targets:**
- **DHT Lookup Latency**: <500ms for 1M node network
- **Peer Discovery**: 10-30 seconds cold start
- **NAT Traversal Success**: >80% (STUN), >95% (STUN+TURN)
- **Gossip Propagation**: <5 seconds to 95% of mesh
- **Connection Count**: 10-30 peers (mesh degree)

### Industry Standards

**Established Protocols:**
- **libp2p** - IPFS modular P2P stack (production standard)
- **Kademlia** - Mainline DHT (BitTorrent), IPFS DHT
- **GossipSub v1.1** (libp2p pubsub specification)
- **RFC 8445** - Interactive Connectivity Establishment (ICE)
- **RFC 5389** - STUN (Session Traversal Utilities for NAT)
- **RFC 8656** - TURN (Traversal Using Relays around NAT)

**Reference Implementations:**
- **libp2p** (Go, Rust, JS, Python) - Production-grade modular stack
- **OpenDHT** (C++) - Kademlia with security extensions
- **kademlia** (Python asyncio) - Lightweight async implementation
- **WebRTC** - Browser P2P with built-in ICE/NAT traversal

**Best Practices:**
- Use Kademlia for global peer/content routing
- Use GossipSub for real-time messaging/pubsub
- Implement circuit relay (libp2p relay) for NAT traversal
- Bootstrap with 5-10 well-known nodes
- Peer exchange (PEX) for decentralized discovery
- Connection manager with peer limits (avoid resource exhaustion)
- DHT key expiry/republishing (every 24 hours)

### Academic Research

**Seminal Papers:**
1. **Kademlia: A Peer-to-Peer Information System Based on the XOR Metric** (Maymounkov & Mazières, 2002, IPTPS)
   - XOR metric enables symmetric routing table
   - Parallel lookups with exponential convergence
   - Resilient to node churn

2. **Chord: A Scalable Peer-to-peer Lookup Service for Internet Applications** (Stoica et al., 2001, ACM SIGCOMM)
   - Consistent hashing for load balancing
   - Finger table for O(log N) routing
   - Stabilization protocol for correctness

3. **Gossip-Based Peer Sampling** (Jelasity et al., 2007, ACM TOCS)
   - Random peer sampling service
   - View propagation with exponential spread
   - Resilience to failures and network partitions

4. **libp2p: A Modular Peer-to-Peer Networking Stack** (IPFS Technical Report, 2019)
   - Pluggable transport, crypto, and protocols
   - Multi-address format for heterogeneous networks
   - Protocol negotiation via multistream-select

5. **NAT Traversal Techniques in Peer-to-Peer Systems** (Ford et al., 2005, USENIX ATC)
   - Analyzed STUN success rates across NAT types
   - Hole punching reliability: 82% for UDP, 64% for TCP
   - Birthday paradox for simultaneous open

**Recent Advances (2022-2025):**
- QUIC transport for improved NAT traversal and performance
- DHT security: S/Kademlia extensions for Sybil resistance
- AutoNAT for automatic public/private address detection
- Hole punching optimizations (DCUtR - Direct Connection Upgrade through Relay)

### Architecture Patterns

**Component Breakdown:**
```
P2P Unified System Architecture:
├── Transport Layer
│   ├── TCP, QUIC, WebSocket, WebRTC
│   ├── Protocol Negotiation (multistream-select)
│   └── Connection Upgrading (security, multiplexing)
├── Discovery
│   ├── Bootstrap (hardcoded seed nodes)
│   ├── mDNS (local network discovery)
│   ├── DHT Peer Routing (Kademlia FIND_NODE)
│   └── Rendezvous Protocol (topic-based discovery)
├── Routing
│   ├── DHT (Kademlia - content/peer routing)
│   ├── PubSub (GossipSub - real-time messaging)
│   └── Circuit Relay (NAT traversal fallback)
├── NAT Traversal
│   ├── AutoNAT (detect public reachability)
│   ├── Hole Punching (DCUtR protocol)
│   ├── STUN Client (address discovery)
│   └── TURN Client (relay fallback)
├── Peer Management
│   ├── Connection Manager (resource limits)
│   ├── Peer Store (metadata, latency, reliability)
│   └── Reputation System (scoring, pruning)
└── Application Protocols
    ├── Custom RPC (request/response)
    ├── Streaming (bidirectional streams)
    └── Sync Protocols (state reconciliation)
```

**Integration Patterns:**
- **DHT + GossipSub**: DHT for discovery, GossipSub for data dissemination
- **Circuit Relay Chain**: Multi-hop relay for unreachable peers
- **Content Routing**: DHT provider records for content advertisement
- **Hybrid Super-Peer**: Some nodes with public IPs act as relays/rendezvous

### What SHOULD Be Implemented

**Minimum Viable Functionality:**
1. **Kademlia DHT**
   - k-bucket routing table (k=20, 256 buckets for 256-bit IDs)
   - FIND_NODE, FIND_VALUE, STORE RPCs
   - Iterative lookup with α=3 parallel requests
   - Bucket refresh every hour
   - Key republishing every 24 hours

2. **Peer Discovery**
   - Bootstrap list (5-10 seed nodes)
   - DHT random walk for continuous discovery
   - Optional: mDNS for local peers

3. **NAT Traversal**
   - AutoNAT for public IP detection
   - Hole punching (DCUtR or custom)
   - Circuit relay (libp2p relay protocol)
   - STUN integration (or use public STUN servers)

4. **Connection Management**
   - Connection limits (50-200 concurrent)
   - Peer pruning (keep low-latency, high-uptime peers)
   - Backoff for failed connections

5. **Protocol Layer**
   - Multistream-select for protocol negotiation
   - Basic RPC (request/response) framework
   - Optional: GossipSub for pubsub

**Optional Advanced Features:**
- S/Kademlia security (crypto puzzles, sibling checks)
- GossipSub with peer scoring (v1.1 spec)
- TURN server integration for high-NAT environments
- DHT-based rendezvous for topic-specific discovery
- Content-addressed storage with IPFS compatibility
- Multi-path routing for reliability
- Adaptive timeout and retry strategies

**Performance Expectations:**
- **DHT Lookup**: <1 second for 90th percentile
- **Peer Discovery**: Find 20+ peers in <30 seconds
- **NAT Traversal**: >70% hole punching success without TURN
- **Connection Establishment**: <2 seconds per peer
- **Message Propagation**: <5 seconds to 95% of subscribed peers (GossipSub)
- **Resource Usage**: <200 MB RAM for 200 connections

---

## 4. Fog Computing & Edge Orchestration

### Theoretical Foundation

**Core Concepts:**
- **Fog Computing**: Distributed computing paradigm bringing cloud resources to network edge
- **Heterogeneous Device Management**: Orchestration across mobile, IoT, desktop, and edge servers
- **Resource Virtualization**: Container/VM-based compute pooling
- **Task Placement**: Optimization problem minimizing latency, cost, energy

**Key Algorithms:**
1. **Task Placement Optimization**
   - Multi-objective: minimize latency, energy, cost
   - Constraints: SLA, resource capacity, network bandwidth
   - Approaches: ILP (small scale), genetic algorithms, DRL (large scale)

2. **Battery-Aware Scheduling**
   - Device eligibility: battery >50%, charging state, thermal limits
   - DVFS (Dynamic Voltage Frequency Scaling) for energy efficiency
   - Preemption for battery events (e.g., unplug charger → migrate task)

3. **Federated Learning at Edge**
   - Local training on edge devices
   - Model aggregation at edge servers (FedAvg, FedProx)
   - Resource-constrained split learning (EdgeSplit)
   - Privacy-preserving (differential privacy, secure aggregation)

**Performance Targets:**
- **Task Latency**: 10-500ms (vs 100-1000ms cloud)
- **Offloading Decision Time**: <100ms
- **Energy Efficiency**: 30-60% improvement vs local execution
- **Device Participation**: 20-50% of eligible devices (dynamic)
- **Network Bandwidth**: 10-100 Mbps per edge server

### Industry Standards

**Established Protocols:**
- **ETSI MEC (Multi-access Edge Computing)** - Industry standard architecture
- **OpenFog Reference Architecture** (IEEE 1934-2018)
- **LF Edge** (Linux Foundation) - EdgeX Foundry, Akraino
- **Kubernetes** + **KubeEdge** - Container orchestration at edge

**Reference Implementations:**
- **KubeEdge** - Kubernetes extension for edge
- **EdgeX Foundry** - IoT edge framework
- **Azure IoT Edge** - Commercial edge platform
- **AWS Greengrass** - Edge computing service
- **OpenNebula** - Open-source cloud/edge orchestration

**Best Practices:**
- Use containers (Docker, containerd) for portable workloads
- Kubernetes for orchestration (KubeEdge for edge extensions)
- Implement hierarchical architecture: Cloud → Edge Clusters → Fog Nodes → IoT Devices
- Resource monitoring: CPU, memory, network, battery, thermal
- SLA-based placement: latency-sensitive tasks to edge, batch to cloud
- Failure recovery: task migration, checkpointing
- Security: mutual TLS, attestation for edge nodes

### Academic Research

**Seminal Papers:**
1. **Fog Computing: A Platform for Internet of Things and Analytics** (Bonomi et al., 2014)
   - Introduced fog computing paradigm
   - Defined hierarchical cloud-fog-edge architecture
   - Identified use cases: smart grid, connected vehicles, smart cities

2. **Orchestration in Fog Computing: A Comprehensive Survey** (Souza et al., ACM Computing Surveys 2022)
   - Taxonomy of orchestration mechanisms
   - Service deployment, resource management, SLA monitoring
   - Challenges: heterogeneity, mobility, energy constraints

3. **Mobile Edge Computing: A Survey** (Mach & Becvar, 2017, IEEE IoT)
   - MEC architecture and standardization (ETSI)
   - Offloading decision frameworks
   - Resource allocation strategies

4. **Battery-Aware Task Scheduling for Mobile Edge Computing** (2024, Scientific Reports)
   - DVFS-integrated scheduling
   - Thermal-aware task allocation
   - Hybrid energy systems (grid + battery + harvesting)

5. **Federated Learning for Edge Computing: A Survey** (2024)
   - FL algorithms adapted for resource-constrained devices
   - EdgeSplit, HetFL, FedFSE for heterogeneous clients
   - Privacy, communication efficiency, and system heterogeneity

**Recent Advances (2022-2025):**
- Deep RL for dynamic task offloading (DQN, PPO, A3C)
- Digital twins for edge resource modeling
- Serverless computing at edge (FaaS)
- Energy harvesting integration (solar, kinetic)
- 5G integration with MEC (ultra-low latency)

### Architecture Patterns

**Component Breakdown:**
```
Fog Computing Architecture:
├── Cloud Layer
│   ├── Global Orchestrator
│   ├── Model Training (federated aggregation)
│   └── Long-term Storage
├── Edge Server Layer
│   ├── Edge Orchestrator (task placement)
│   ├── Container Runtime (Docker/containerd)
│   ├── Local Cache (content, models)
│   ├── Aggregation Service (FL, data preprocessing)
│   └── Gateway (protocol translation)
├── Fog Node Layer (Mobile, Desktop, IoT)
│   ├── Resource Monitor (CPU, battery, thermal)
│   ├── Task Executor (sandboxed containers)
│   ├── Local ML Inference
│   └── Data Collector (sensors, cameras)
├── Orchestration
│   ├── Service Discovery
│   ├── Task Scheduler (multi-objective optimization)
│   ├── Resource Allocator
│   ├── SLA Monitor
│   └── Migration Controller
└── Network
    ├── SDN Controller (traffic routing)
    ├── QoS Manager
    └── Bandwidth Allocation
```

**Integration Patterns:**
- **Hierarchical Offloading**: Try local → fog peer → edge server → cloud
- **Federated Data Processing**: Raw data at edge, aggregated insights to cloud
- **Content Caching**: CDN-like caching at edge for latency reduction
- **Hybrid Computation**: Split tasks across multiple tiers

### What SHOULD Be Implemented

**Minimum Viable Functionality:**
1. **Edge Server Orchestrator**
   - Container deployment (Docker API integration)
   - Task queue management
   - Resource allocation (CPU, memory quotas)
   - Basic scheduling (first-fit, round-robin)

2. **Fog Node Agent**
   - Resource monitoring (CPU, memory, battery %, thermal, network)
   - Task execution environment (sandboxed)
   - Heartbeat to edge server
   - Battery event handling (pause/migrate on low battery)

3. **Task Offloading API**
   - REST API for task submission
   - Task description: code/container, resource requirements, SLA
   - Response: task ID, assigned node, status endpoint

4. **Device Eligibility**
   - Battery >50% (configurable threshold)
   - Charging state (prefer plugged-in devices)
   - Thermal <70°C (avoid overheating)
   - Network connectivity (WiFi preferred over cellular)

5. **Basic Scheduler**
   - Greedy placement (first available node)
   - Optional: latency-aware (prefer closer nodes)

**Optional Advanced Features:**
- Multi-objective task placement (NSGA-II, DRL)
- Federated learning framework (FedAvg aggregation)
- Checkpointing and migration for long-running tasks
- Predictive resource availability (ML-based forecasting)
- Energy-aware scheduling (DVFS integration)
- SLA violation detection and remediation
- Load balancing with live migration
- Secure enclaves (TEE) for sensitive computations

**Performance Expectations:**
- **Offloading Latency**: <100ms decision + <500ms deployment
- **Task Completion**: 30-70% faster than local (latency-sensitive tasks)
- **Energy Savings**: 20-50% for mobile devices (offloading intensive tasks)
- **Device Uptime**: >80% of eligible devices available during peak hours
- **Success Rate**: >90% task completion (with migration fallback)

---

## 5. Onion Routing / Tor Protocol

### Theoretical Foundation

**Core Concepts:**
- **Circuit-Based Routing**: Pre-established encrypted paths through multiple relays
- **Layered Encryption**: Onion encryption with per-hop unwrapping
- **Hidden Services**: .onion addresses with rendezvous protocol
- **Directory Consensus**: Decentralized node discovery and verification

**Key Algorithms:**
1. **Circuit Construction**
   - 3-hop default circuit (Guard → Middle → Exit)
   - CREATE/CREATED cells with DH handshake (ntor protocol)
   - EXTEND/EXTENDED cells for multi-hop circuits
   - Key derivation: KDF_TOR (SHA256-based)

2. **Hidden Service Protocol (v3)**
   - Long-term identity: Ed25519 keypair
   - Introduction points: 3-5 relays advertising service
   - Rendezvous protocol: Client and service meet at rendezvous point
   - 6-hop total circuit (3 client + 3 service)

3. **Directory Consensus**
   - Hourly consensus documents signed by directory authorities (9 authorities)
   - Bandwidth weights for relay selection
   - Guard, middle, exit flags based on capabilities

**Performance Targets:**
- **Circuit Build Time**: 3-8 seconds (3 hops)
- **Latency**: 200-800ms overhead per request
- **Throughput**: 1-5 Mbps typical (relay bandwidth limited)
- **Hidden Service Connection**: 10-30 seconds (6-hop circuit + rendezvous)

### Industry Standards

**Established Protocols:**
- **Tor Protocol Specification** (torproject.org/docs/tor-spec.txt)
- **Tor Rendezvous Specification** (rend-spec-v3.txt for v3 onion services)
- **Tor Directory Protocol** (dir-spec.txt)
- **ntor Handshake** (Curve25519-based, faster than TAP)

**Reference Implementations:**
- **Tor** (C) - Official implementation
- **Arti** (Rust) - Modern Tor implementation by Tor Project
- **OnionCat** - IPv6 VPN over Tor
- **Tor Browser** - Firefox-based browser with Tor integration

**Best Practices:**
- Use ntor handshake (vs deprecated TAP)
- 3-hop circuits for regular traffic, 6-hop for hidden services
- Guard relay pinning (reduce fingerprinting)
- Rotate circuits every 10 minutes
- Path selection with bandwidth weighting
- Hidden service descriptor caching (reduce HSDirs load)
- Rate limiting per circuit (avoid congestion)

### Academic Research

**Seminal Papers:**
1. **Tor: The Second-Generation Onion Router** (Dingledine et al., 2004, USENIX Security)
   - Perfect forward secrecy with DH handshake
   - Directory authorities for trust
   - Exit policies for abuse mitigation
   - Analyzed traffic correlation attacks

2. **Improving Efficiency and Simplicity of Tor Circuit Establishment** (Goldberg et al., 2011)
   - ntor handshake design (Curve25519)
   - 3x faster than TAP, smaller cells
   - Forward secrecy maintained

3. **A Model of Onion Routing with Provable Anonymity** (Feigenbaum et al., 2007)
   - Formal anonymity analysis
   - Adversary models (local, global)
   - Unlinkability guarantees under assumptions

4. **Vuvuzela: Scalable Private Messaging Resistant to Traffic Analysis** (van den Hooff et al., 2015, SOSP)
   - Differential privacy for metadata protection
   - Dead drops for asynchronous messaging
   - Comparison to Tor's synchronous circuits

5. **The Loopix Anonymity System** (Piotrowska et al., 2017, USENIX Security)
   - Poisson mixing for Tor-like circuits
   - Continuous-time cover traffic
   - Stratified topology (provider → mix → mix → provider)

**Recent Advances (2022-2025):**
- Walking Onions: Scalable client-side path selection without full consensus
- Congestion control improvements (EWMA-based)
- Post-quantum handshakes (experimental)
- Proof-of-Work DoS mitigation for onion services

### Architecture Patterns

**Component Breakdown:**
```
Tor/Onion Routing Architecture:
├── Client
│   ├── Directory Client (fetch consensus, descriptors)
│   ├── Circuit Manager (build, maintain, rotate)
│   ├── Path Selection (bandwidth-weighted, flags)
│   ├── Stream Manager (map connections to circuits)
│   └── SOCKS Proxy (application interface)
├── Relay
│   ├── OR Protocol (onion routing)
│   ├── TLS Connection Manager
│   ├── Circuit Processing (decrypt, relay cells)
│   ├── Exit Policy (allow/deny by port, IP)
│   └── Bandwidth Accounting
├── Directory Authority
│   ├── Relay Measurement (bandwidth, uptime)
│   ├── Consensus Generation (hourly)
│   ├── Signature Verification
│   └── Descriptor Publishing
├── Hidden Service
│   ├── Introduction Point Manager (3-5 relays)
│   ├── Descriptor Publisher (to HSDirs)
│   ├── Rendezvous Protocol
│   └── Service-Side Circuit Builder
└── Cryptography
    ├── ntor Handshake (Curve25519)
    ├── AES128-CTR (relay encryption)
    ├── SHA256 (KDF, integrity)
    └── Ed25519 (identity, signing)
```

**Integration Patterns:**
- **SOCKS5 Proxy**: Applications connect via SOCKS to Tor
- **Transparent Proxy**: iptables redirect for entire system
- **OnionBalance**: Load balancing for hidden services
- **Tor over VPN**: VPN → Tor → Internet (hide Tor usage)

### What SHOULD Be Implemented

**Minimum Viable Functionality:**
1. **Client-Side Tor**
   - Directory fetching (consensus + relay descriptors)
   - Circuit construction (3-hop with ntor handshake)
   - Path selection (weighted by bandwidth, respect flags)
   - Stream multiplexing (multiple TCP streams per circuit)
   - SOCKS5 proxy interface

2. **Relay Operation**
   - OR protocol (process RELAY cells)
   - TLS connection handling
   - Circuit extend/relay logic
   - Exit policy enforcement
   - Bandwidth reporting to directories

3. **Hidden Service (Client-Side)**
   - Fetch hidden service descriptors from HSDirs
   - Introduction point connection
   - Rendezvous protocol (client-side)
   - 6-hop circuit construction

4. **Cryptography**
   - ntor handshake (Curve25519 + SHA256 KDF)
   - AES128-CTR for relay encryption
   - Ed25519 for identity verification
   - Cell integrity checks

**Optional Advanced Features:**
- Hidden service hosting (introduction points, descriptor publishing)
- OnionBalance for HS load balancing
- Pluggable transports (obfuscation for censorship resistance)
- Vanguards (guard discovery attack mitigation)
- Walking Onions (client-side path selection)
- Congestion control (circuit-level flow control)
- Post-quantum handshakes (future-proofing)

**Performance Expectations:**
- **Circuit Build**: <5 seconds (3-hop)
- **Latency Overhead**: 200-500ms for web requests
- **Throughput**: 2-10 Mbps (relay bandwidth dependent)
- **Hidden Service Connection**: <20 seconds
- **Circuit Rotation**: Every 10 minutes or after 10 streams
- **Resource Usage**: <100 MB RAM client, <500 MB relay

---

## 6. Tokenomics & DAO Governance

### Theoretical Foundation

**Core Concepts:**
- **Token Economics**: Incentive design for decentralized systems
- **Staking Mechanisms**: Lock tokens to provide service/security
- **Market-Based Pricing**: Supply/demand equilibrium for compute resources
- **DAO Governance**: Decentralized decision-making via token voting

**Key Algorithms:**
1. **Proof-of-Stake (PoS) Variants**
   - Bonded PoS: Slash stake for misbehavior
   - Delegated PoS (DPoS): Token holders elect validators
   - Liquid Staking: Stake while maintaining liquidity (e.g., stETH)

2. **Market Mechanisms**
   - Automated Market Maker (AMM): x * y = k for price discovery
   - Dutch Auction: Price decreases until buyer found
   - Combinatorial Auctions: Multi-attribute bidding (price, latency, security)

3. **Voting Systems**
   - Quadratic Voting: Cost = (votes)^2 (prevents plutocracy)
   - Liquid Democracy: Delegate votes to trusted parties
   - Conviction Voting: Longer vote lock → more weight (Polkadot governance)

4. **Token Distribution**
   - Vesting schedules: Linear, cliff, exponential decay
   - Airdrops: Community distribution (Sybil-resistant via proof-of-personhood)
   - Liquidity mining: Reward LPs for market depth

**Performance Targets:**
- **Transaction Finality**: <10 seconds (PoS consensus)
- **Governance Proposal Cycle**: 7-14 days (discussion + voting)
- **Staking APY**: 5-15% for compute providers
- **Slashing**: 1-10% of stake for provable misbehavior
- **Participation Rate**: >30% token holder voting

### Industry Standards

**Established Protocols:**
- **Ethereum PoS** (Gasper: Casper FFG + LMD GHOST) - Finality in 2 epochs (~12 min)
- **Polkadot NPoS** (Nominated Proof-of-Stake) - Phragmén election algorithm
- **Cosmos PoS** (Tendermint BFT) - Instant finality
- **Uniswap AMM** - x * y = k for token swaps
- **Snapshot** - Off-chain gasless voting (signature-based)

**Reference Implementations:**
- **OpenZeppelin Governor** (Solidity) - On-chain DAO governance
- **Aragon** - DAO framework with voting, treasury management
- **Snapshot** - Off-chain voting with on-chain execution
- **Gnosis Safe** - Multi-sig treasury for DAO funds

**Best Practices:**
- **Sybil Resistance**: Proof-of-stake, proof-of-personhood (Worldcoin, BrightID)
- **Token Utility**: Staking (security), governance (voting), payment (compute)
- **Treasury Management**: Multi-sig (3-of-5 or 5-of-9), vesting for team/investors
- **Inflation Control**: Capped supply or burn mechanisms (EIP-1559 style)
- **Slashing**: Automated for provable faults, DAO vote for subjective issues
- **Delegation**: Allow token holders to delegate governance to experts
- **Quorum**: Minimum participation (10-20%) to prevent low-turnout attacks

### Academic Research

**Seminal Papers:**
1. **SoK: Blockchain Governance** (Reijers et al., 2021, ACM Computing Surveys)
   - Taxonomy: On-chain vs off-chain governance
   - Case studies: Bitcoin, Ethereum, Tezos, Polkadot
   - Governance attacks: plutocracy, voter apathy, collusion

2. **Quadratic Payments: A Primer** (Buterin et al., 2019)
   - Cost = (votes)^2 prevents vote buying
   - Optimal for public goods funding
   - Sybil resistance remains challenge

3. **Tokenomics: Dynamic Adoption and Valuation** (Cong et al., 2021, Review of Financial Studies)
   - Token velocity problem (hold vs spend)
   - Staking as velocity sink
   - Network effects and adoption curves

4. **Stake-Driven Consensus** (Garay et al., 2020, CRYPTO)
   - Formal security of PoS under grinding attacks
   - Nothing-at-stake problem solutions
   - Long-range attack mitigations

5. **A Survey on Decentralized Autonomous Organizations** (Hassan & De Filippi, 2021)
   - Legal status of DAOs (Wyoming DAO LLC)
   - Governance models: token-weighted, reputation, futarchy
   - Case studies: MakerDAO, Uniswap, Compound

**Recent Advances (2022-2025):**
- Liquid staking protocols (Lido, Rocket Pool)
- Futarchy: Decision markets for governance
- Optimistic governance: Execute proposals, challenge period
- ZK voting: Privacy-preserving governance (MACI)
- Rage-quit mechanisms: Minority protection (Moloch DAO)

### Architecture Patterns

**Component Breakdown:**
```
Tokenomics & DAO Architecture:
├── Token Contract
│   ├── ERC20 (fungible token standard)
│   ├── Minting (controlled by DAO/protocol)
│   ├── Burning (deflationary mechanism)
│   └── Staking Module (lock tokens, earn rewards)
├── Governance
│   ├── Proposal Submission (min token threshold)
│   ├── Voting Module (quadratic, liquid democracy)
│   ├── Timelock (delay execution, allow exit)
│   └── Execution (on-chain parameter changes)
├── Treasury
│   ├── Multi-sig Wallet (Gnosis Safe)
│   ├── Vesting Contracts (team, investors)
│   └── Grant Distribution (community proposals)
├── Marketplace
│   ├── Compute Task Auction (buyers bid)
│   ├── Provider Pricing (dynamic based on supply/demand)
│   ├── Escrow (hold payment until task completion)
│   └── Reputation System (uptime, quality scores)
├── Staking & Slashing
│   ├── Staking Pool (aggregate small holders)
│   ├── Validator Set (staked providers)
│   ├── Slashing Conditions (offline, incorrect results)
│   └── Reward Distribution (pro-rata by stake)
└── Oracle
    ├── Price Feeds (token value, resource prices)
    ├── Task Verification (off-chain compute results)
    └── Reputation Aggregation
```

**Integration Patterns:**
- **L2 for Governance**: Use Optimistic Rollup/ZK Rollup for cheap voting
- **Off-Chain Voting + On-Chain Execution**: Snapshot + Gnosis Safe
- **Hybrid Pricing**: Base price (DAO set) + market multiplier
- **Staking for Multiple Purposes**: Security + governance + resource allocation

### What SHOULD Be Implemented

**Minimum Viable Functionality:**
1. **Token Contract**
   - ERC20 fungible token
   - Fixed or capped supply
   - Minting controlled by governance/protocol
   - Transfer, approve, transferFrom (standard)

2. **Staking Module**
   - Stake tokens to become compute provider
   - Minimum stake (e.g., 1000 tokens)
   - Unstaking period (7-14 days)
   - Reward distribution (pro-rata)

3. **Basic Governance**
   - Proposal submission (min 1% token threshold)
   - Token-weighted voting (1 token = 1 vote)
   - Quorum requirement (20% participation)
   - Timelock (2-7 days before execution)

4. **Marketplace**
   - Task posting by users
   - Provider bidding (price per compute unit)
   - Escrow payment (release on completion)
   - Basic reputation (task count, success rate)

5. **Slashing (Manual)**
   - Report mechanism for misbehavior
   - DAO vote to slash (initial version)
   - Slashed tokens go to treasury or burn

**Optional Advanced Features:**
- Quadratic voting or liquid democracy
- Automated slashing (provable faults via fraud proofs)
- AMM for token liquidity (Uniswap integration)
- Liquid staking (staked tokens as tradable derivative)
- Conviction voting (time-weighted proposals)
- Futarchy (decision markets)
- ZK voting (privacy-preserving)
- Dynamic inflation (reward compute providers)
- Burn mechanisms (token value accrual)

**Performance Expectations:**
- **Voting Period**: 7 days discussion + 7 days voting
- **Quorum**: 20-30% of circulating supply
- **Staking APY**: 8-12% (sustainable)
- **Slashing Events**: <1% annually (well-behaved network)
- **Marketplace Transaction Time**: <30 seconds (L2 or fast L1)
- **Governance Execution**: 3-7 day timelock post-vote

---

## 7. Batch Job Scheduling

### Theoretical Foundation

**Core Concepts:**
- **Multi-Objective Optimization**: Minimize latency, cost, energy simultaneously
- **SLA-Aware Placement**: Deadline constraints, quality-of-service guarantees
- **Resource Fragmentation**: Bin-packing to maximize utilization
- **Evolutionary Algorithms**: NSGA-II, genetic algorithms for NP-hard scheduling

**Key Algorithms:**
1. **NSGA-II (Non-dominated Sorting Genetic Algorithm II)**
   - Pareto front approximation for multi-objective problems
   - Fast non-dominated sorting: O(MN^2) for M objectives, N solutions
   - Crowding distance for diversity
   - Elitism: Best solutions carry over generations

2. **Bin-Packing Heuristics**
   - First-Fit: O(n) greedy allocation
   - Best-Fit: Minimize remaining capacity
   - First-Fit Decreasing (FFD): Sort by size, then first-fit (1.22 OPT approximation)

3. **Constraint Programming**
   - MiniZinc, OR-Tools for exact solutions (small scale)
   - Branch-and-bound for integer programming
   - Time complexity: Exponential (NP-complete)

4. **Deep Reinforcement Learning**
   - DQN, PPO for dynamic scheduling
   - State: cluster state, pending tasks
   - Action: task → node assignment
   - Reward: negative latency, energy, cost

**Performance Targets:**
- **Scheduling Latency**: <1 second for 1000 tasks (heuristics), <10s (NSGA-II)
- **SLA Violations**: <5% of tasks
- **Resource Utilization**: >70% CPU, >60% memory
- **Energy Efficiency**: 20-40% savings vs random placement
- **Deadline Success**: >95% of deadline-sensitive tasks

### Industry Standards

**Established Protocols:**
- **Kubernetes Scheduler** - Default, customizable (scheduler framework)
- **Apache Mesos** - Two-level scheduling (resource offers)
- **YARN** (Hadoop) - Capacity, Fair scheduling
- **Slurm** (HPC) - Batch job scheduling with priorities
- **HTCondor** - High-throughput computing

**Reference Implementations:**
- **Kubernetes** - Production scheduler with plugins (score, filter, bind)
- **NSGA-II Libraries**: pymoo (Python), jMetal (Java)
- **OR-Tools** (Google) - Constraint programming, vehicle routing
- **Ray** (Anyscale) - Distributed RL for scheduling

**Best Practices:**
- **Multi-tier Scheduling**: Fast heuristics + periodic optimization
- **Preemption**: Allow low-priority task eviction for SLA jobs
- **Gang Scheduling**: Co-schedule dependent tasks (ML distributed training)
- **Backfilling**: Fill gaps with small tasks while large task waits
- **Resource Reservations**: Pre-allocate for critical workloads
- **Monitoring**: Track SLA violations, re-schedule if needed

### Academic Research

**Seminal Papers:**
1. **A Fast and Elitist Multiobjective Genetic Algorithm: NSGA-II** (Deb et al., 2002, IEEE Trans. Evolutionary Computation)
   - Introduced fast non-dominated sorting
   - Crowding distance for diversity
   - O(MN^2) complexity, suitable for large populations

2. **Approximation Algorithms for Bin Packing: A Survey** (Coffman et al., 2013)
   - FFD achieves 11/9 OPT + 6/9
   - Online algorithms: Next-Fit, First-Fit (2 OPT)
   - Lower bounds for online bin packing

3. **Borg: The Next Generation** (Verma et al., 2015, EuroSys)
   - Google's cluster scheduler
   - Admission control, task preemption
   - Resource reclamation (utilization >70%)

4. **Resource Management with Deep Reinforcement Learning** (Mao et al., 2016, HotNets)
   - DRL for job scheduling (minimize slowdown)
   - Outperforms heuristics in heterogeneous clusters
   - Generalizes to unseen workloads

5. **Multi-Objective Optimization for Edge Computing Task Scheduling** (2024, Scientific Reports)
   - NSGA-II for latency, energy, cost
   - SLA-aware constraints
   - Comparison: NSGA-II > genetic > greedy

**Recent Advances (2022-2025):**
- Graph neural networks for DAG task scheduling
- Federated RL for multi-cluster scheduling
- Energy-aware scheduling with DVFS integration
- Serverless scheduling (cold start mitigation)

### Architecture Patterns

**Component Breakdown:**
```
Batch Job Scheduler Architecture:
├── Task Queue
│   ├── Priority Queue (SLA, deadline)
│   ├── Task Metadata (resource requirements, dependencies)
│   └── Pending Tasks Index
├── Scheduler
│   ├── Filtering (resource constraints, affinity)
│   ├── Scoring (NSGA-II, heuristics)
│   ├── Binding (assign task → node)
│   └── Preemption Logic (evict low-priority)
├── Resource Manager
│   ├── Cluster State (available CPU, memory, GPU)
│   ├── Node Heartbeat (liveness, capacity)
│   └── Resource Reservation
├── Execution
│   ├── Task Launcher (container runtime)
│   ├── Monitoring (progress, resource usage)
│   └── Checkpointing (for migration)
├── SLA Monitor
│   ├── Deadline Tracker
│   ├── Violation Logger
│   └── Re-scheduling Trigger
└── Optimization Loop
    ├── Periodic NSGA-II Run (every 5-10 min)
    ├── Task Migration Planner
    └── Load Balancing
```

**Integration Patterns:**
- **DAG Scheduler**: Dependency-aware (Apache Airflow, Kubeflow)
- **Hybrid**: Fast heuristics (real-time) + NSGA-II (periodic optimization)
- **Feedback Loop**: Monitor SLA violations → adjust scheduling weights
- **Multi-Cluster**: Federated scheduling across fog/edge/cloud

### What SHOULD Be Implemented

**Minimum Viable Functionality:**
1. **Task Queue**
   - Priority queue (deadline, user priority)
   - Task metadata: resource requirements (CPU, memory, GPU), estimated runtime, deadline
   - CRUD API for task submission/cancellation

2. **Basic Scheduler**
   - First-Fit Decreasing: Sort tasks by resource demand, assign to first available node
   - Filtering: Exclude nodes without sufficient resources
   - Affinity/anti-affinity rules (optional)

3. **Resource Manager**
   - Cluster state tracking (available resources per node)
   - Heartbeat from nodes (every 10-30s)
   - Resource reservation (prevent over-subscription)

4. **Execution**
   - Container launcher (Docker API)
   - Task monitoring (running, success, failed)
   - Log collection

5. **SLA Tracking**
   - Deadline field in task metadata
   - Track on-time completion rate
   - Alert on violations (for manual intervention)

**Optional Advanced Features:**
- NSGA-II optimizer (minimize latency, energy, cost)
- Preemption (low-priority task eviction)
- Gang scheduling (co-locate dependent tasks)
- Checkpointing (task migration without loss)
- DRL scheduler (PPO, DQN for dynamic workloads)
- DAG scheduling (Airflow-like dependencies)
- Spot instance integration (cloud bursting)
- Energy-aware placement (DVFS, node powering)

**Performance Expectations:**
- **Scheduling Latency**: <500ms for 100 tasks (heuristics)
- **SLA Compliance**: >95% on-time completion
- **Cluster Utilization**: >65% CPU, >55% memory
- **Throughput**: 100-1000 tasks/minute (cluster size dependent)
- **Optimization Cycle**: NSGA-II every 5 minutes (if implemented)

---

## 8. Idle Compute Harvesting

### Theoretical Foundation

**Core Concepts:**
- **Opportunistic Computing**: Use idle resources when available, pause when needed
- **Device Eligibility**: Battery, thermal, network constraints
- **Cross-Platform APIs**: Android JobScheduler, iOS BackgroundTasks, Windows Task Scheduler
- **Checkpoint/Restart**: Save progress for preemptible workloads

**Key Algorithms:**
1. **Eligibility Detection**
   - Battery >50% OR charging
   - Thermal <70°C (prevent overheating)
   - Network: WiFi preferred (avoid cellular costs)
   - Screen off (user idle detection)
   - Non-metered network (avoid user data charges)

2. **Power Modeling**
   - Linear model: Power = α + β * CPU_util
   - DVFS integration: Power ∝ V^2 * f (voltage, frequency)
   - Measured: Collect battery drain rate during tasks

3. **Workload Partitioning**
   - Embarrassingly parallel tasks (MapReduce, rendering)
   - Checkpointing: Save state every N minutes
   - Speculative execution: Redundant tasks for reliability

**Performance Targets:**
- **Battery Drain**: <5% per hour (when battery >50%)
- **Thermal**: CPU temp <60°C sustained
- **Availability**: 20-40% of enrolled devices active at any time
- **Task Completion**: 80% without preemption (charging devices)
- **Participation Rate**: 10-30% of app installs opt-in

### Industry Standards

**Established Protocols:**
- **Android WorkManager** - Unified API for background work (JobScheduler, Doze)
- **iOS BackgroundTasks** - BGProcessingTask for deferrable work
- **BOINC** (Berkeley Open Infrastructure for Network Computing) - Volunteer computing standard
- **Folding@home** - Distributed biology simulations

**Reference Implementations:**
- **BOINC** - Cross-platform (Windows, Mac, Linux, Android)
- **Android WorkManager** - Constraints: charging, battery not low, WiFi
- **iOS BackgroundTasks** - Up to 30 min per task, system-scheduled
- **Folding@home** - GPU-accelerated protein folding

**Best Practices:**
- **Explicit Opt-In**: User consent for compute harvesting
- **Transparent UI**: Show current task, estimated completion, energy impact
- **Graceful Pause**: Save state, resume when eligible again
- **User Override**: Manual pause/resume controls
- **Battery Thresholds**: Conservative defaults (>50% battery, charging preferred)
- **Thermal Limits**: Monitor CPU/GPU temp, throttle if >70°C
- **Network Awareness**: Pause on cellular unless user allows
- **Sandboxing**: Isolate tasks (containers, WASM) for security

### Academic Research

**Seminal Papers:**
1. **SETI@home: An Experiment in Public-Resource Computing** (Anderson et al., 2002, CACM)
   - First large-scale volunteer computing
   - Client-server architecture with result validation
   - Incentives: Screensavers, leaderboards

2. **Harvesting Idle Resources in Heterogeneous Environments** (Zhang et al., 2021)
   - Device diversity (mobile, desktop, IoT)
   - Eligibility prediction using ML
   - Energy models for Android devices

3. **Energy-Aware Scheduling for Edge Computing** (2024, Scientific Reports)
   - DVFS-integrated scheduling
   - Battery-aware task allocation
   - Thermal management via predictive models

4. **Mobile Crowd Computing: Challenges and Opportunities** (Guo et al., 2014, IEEE Network)
   - Incentive mechanisms (monetary, gamification)
   - Quality control (result verification)
   - Privacy-preserving task distribution

5. **Checkpoint/Restart for Preemptive Mobile Computing** (2019)
   - Incremental checkpointing (save diffs)
   - Resume overhead <5% for well-designed tasks
   - Storage vs computation tradeoff

**Recent Advances (2022-2025):**
- WebAssembly for cross-platform compute (browser, mobile, server)
- Federated learning on idle mobile devices
- Blockchain-based incentives (Golem, iExec)
- Edge inference (ML model serving on idle devices)

### Architecture Patterns

**Component Breakdown:**
```
Idle Compute Harvesting Architecture:
├── Client Agent (Mobile/Desktop)
│   ├── Eligibility Monitor
│   │   ├── Battery Level (>50%)
│   │   ├── Charging State
│   │   ├── Thermal (CPU/GPU temp)
│   │   ├── Network (WiFi vs cellular)
│   │   └── User Idle (screen off, no interaction)
│   ├── Task Executor
│   │   ├── Sandbox (container, WASM)
│   │   ├── Resource Limiter (CPU quota, memory)
│   │   └── Checkpoint Manager
│   ├── Scheduler Integration
│   │   ├── Android WorkManager
│   │   ├── iOS BGProcessingTask
│   │   └── Desktop Cron/SystemD
│   └── Result Reporter
├── Server Orchestrator
│   ├── Task Distributor
│   │   ├── Task Chunking (for checkpointing)
│   │   ├── Redundancy (speculative execution)
│   │   └── Device Matching (capability-based)
│   ├── Result Validator
│   │   ├── Majority Voting (3+ replicas)
│   │   ├── Trusted Quorum
│   │   └── Fraud Detection
│   ├── Device Registry
│   │   ├── Capabilities (CPU, GPU, RAM)
│   │   ├── Reputation (task success rate)
│   │   └── Availability History
│   └── Incentive Manager
│       ├── Token Rewards
│       ├── Leaderboard
│       └── Gamification
└── Platform-Specific APIs
    ├── Android: JobScheduler, Doze exemption (with care)
    ├── iOS: BGProcessingTask (up to 30 min)
    ├── Windows: Task Scheduler
    └── Linux: systemd timers, cron
```

**Integration Patterns:**
- **BOINC-Like**: Client pulls work units, computes, uploads results
- **Push-Based**: Server pushes tasks to online, eligible devices
- **Hybrid**: Client polls when eligible, server pushes high-priority tasks
- **Federated Learning**: Local training, upload gradients, aggregate server-side

### What SHOULD Be Implemented

**Minimum Viable Functionality:**
1. **Client Eligibility Detection**
   - Battery level check (>50%)
   - Charging state (prefer charging)
   - Network type (WiFi only initially)
   - User idle detection (screen off, no input >5 min)

2. **Platform Integration**
   - **Android**: WorkManager with constraints (battery not low, charging, WiFi)
   - **iOS**: BGProcessingTask (limited to 30 min, system decides timing)
   - **Desktop**: Simple daemon with eligibility checks

3. **Task Execution**
   - Download task package (code + data)
   - Run in sandbox (Docker on desktop, restricted process on mobile)
   - CPU/memory limits (50% CPU max to avoid overheating)
   - Periodic checkpointing (every 5-10 min)

4. **Result Upload**
   - Compress results
   - Upload when on WiFi
   - Retry with exponential backoff

5. **User Controls**
   - Opt-in/opt-out toggle
   - Battery threshold setting (default 50%)
   - Manual pause/resume
   - Stats: Tasks completed, tokens earned, energy contributed

**Optional Advanced Features:**
- ML-based eligibility prediction (forecast user idle periods)
- DVFS integration (reduce frequency for lower power)
- Thermal throttling (reduce workload if temp >65°C)
- Speculative execution (redundant tasks, fastest wins)
- WebAssembly runtime (cross-platform, sandboxed)
- Federated learning (local model training)
- GPU harvesting (mobile GPUs for inference, rendering)
- Cellular network option (user configurable, pay for data)
- Advanced checkpointing (incremental, compression)

**Performance Expectations:**
- **Battery Drain**: <3% per hour when battery >70%
- **Thermal**: Sustained CPU temp <60°C
- **Task Completion**: 70-85% without preemption
- **Participation**: 15-25% of enrolled devices active during peak hours
- **Energy Efficiency**: 2-5x more compute per watt vs cloud (idle resources)
- **Result Turnaround**: 1-24 hours depending on task size and device availability

---

## Summary: Implementation Priority Matrix

| Layer | Priority | Complexity | Impact | Recommended MVP |
|-------|----------|------------|--------|-----------------|
| **Betanet (Mixnet)** | High | High | High | Sphinx + Poisson + VRF-lite |
| **BitChat** | Medium | Medium | Medium | Epidemic routing + BLE mesh |
| **P2P Systems** | High | Medium | High | Kademlia DHT + NAT traversal |
| **Fog Orchestration** | High | High | High | Container orchestrator + battery-aware |
| **Tor/Onion** | Low | High | Medium | Use existing Tor lib (Arti) |
| **Tokenomics/DAO** | Medium | Medium | High | Staking + token-weighted voting |
| **Batch Scheduling** | Medium | Medium | Medium | FFD heuristic + NSGA-II (optional) |
| **Idle Harvesting** | High | Low | High | Eligibility detection + WorkManager |

---

## Key Takeaways

1. **Mixnet Foundation**: Sphinx is the industry standard; VRF-based routing is cutting-edge (2024 research)
2. **Offline Messaging**: PRoPHET + BLE mesh balances delivery probability and resource usage
3. **P2P Infrastructure**: libp2p provides battle-tested modular stack (Kademlia + GossipSub)
4. **Edge Orchestration**: Kubernetes + battery-awareness is practical; FL at edge is active research
5. **Onion Routing**: Leverage existing Tor implementations (Arti in Rust) rather than rebuild
6. **Token Economics**: Staking + quadratic voting + market-based pricing is robust
7. **Job Scheduling**: FFD for MVP, NSGA-II for multi-objective optimization
8. **Idle Compute**: Cross-platform eligibility + checkpointing is essential for mobile

---

## References (Selected Key Papers)

- Danezis & Goldberg (2009): Sphinx Mixnet Format
- Diaz, Halpin, Kiayias (2024): VRF-Based Routing in Mixnets
- Vahdat & Becker (2000): Epidemic Routing for DTN
- Maymounkov & Mazières (2002): Kademlia DHT
- Bonomi et al. (2014): Fog Computing Platform
- Dingledine et al. (2004): Tor Protocol
- Deb et al. (2002): NSGA-II Algorithm
- Anderson et al. (2002): SETI@home Volunteer Computing

---

**End of Theoretical Foundations Report**
