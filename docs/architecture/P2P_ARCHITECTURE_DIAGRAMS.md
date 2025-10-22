# P2P Architecture Diagrams

## System Architecture Overview

### High-Level System Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ Control Panel│  │ Mobile Apps  │  │   CLI Tools  │       │
│  │    (Next.js) │  │ (React Native│  │   (Python)   │       │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘       │
└─────────┼──────────────────┼──────────────────┼───────────────┘
          │                  │                  │
          └──────────────────┼──────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                  P2P UNIFIED SYSTEM                             │
│                (Protocol Coordinator)                           │
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐   │
│  │            Message Router & Orchestrator               │   │
│  │  • Transport selection (BitChat, BetaNet, Mesh)       │   │
│  │  • Protocol switching (online ↔ offline)              │   │
│  │  • Message routing & relay                            │   │
│  │  • Store-and-forward queue                            │   │
│  │  • Peer discovery & management                        │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────── Transport Registry ──────────────────┐  │
│  │                                                          │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │  │
│  │  │  BitChat     │  │  BetaNet     │  │  Mesh        │ │  │
│  │  │  Transport   │  │  Transport   │  │  Transport   │ │  │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │  │
│  └─────────┼──────────────────┼──────────────────┼─────────┘  │
└────────────┼──────────────────┼──────────────────┼────────────┘
             │                  │                  │
┌────────────▼──────────────────▼──────────────────▼────────────┐
│                    TRANSPORT LAYER                             │
│                                                                │
│  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────┐ │
│  │ BLE Mesh Network │  │ HTX Privacy Net  │  │ Direct Mesh │ │
│  │  • 7-hop routing │  │  • Sphinx crypto │  │  • TCP/UDP  │ │
│  │  • Offline mode  │  │  • Mixnet relay  │  │  • Low lat. │ │
│  │  • Multi-hop     │  │  • VRF selection │  │  • Direct   │ │
│  └──────────────────┘  └──────────────────┘  └─────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

---

## Transport Integration Architecture

### BitChat as P2P Transport Module

```
┌─────────────────────────────────────────────────────────────┐
│                  P2P UNIFIED SYSTEM                         │
│                                                             │
│  await p2p.send_message(                                   │
│      receiver_id="peer1",                                  │
│      payload=b"Hello",                                     │
│      requires_privacy=False                                │
│  )                                                         │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐ │
│  │  Transport Selection Logic:                          │ │
│  │  • Check internet connectivity                       │ │
│  │  • Evaluate message requirements                     │ │
│  │  • Select optimal transport                          │ │
│  └────────────────┬─────────────────────────────────────┘ │
└───────────────────┼───────────────────────────────────────┘
                    │
        ┌───────────┼───────────┐
        │           │           │
┌───────▼──────┐ ┌──▼────────┐ ┌▼──────────┐
│ BitChat      │ │ BetaNet   │ │ Mesh      │
│ Transport    │ │ Transport │ │ Transport │
│              │ │           │ │           │
│ implements   │ │ implements│ │ implements│
│ Transport    │ │ Transport │ │ Transport │
│ Interface    │ │ Interface │ │ Interface │
└──────┬───────┘ └─────┬─────┘ └────┬──────┘
       │               │              │
┌──────▼───────────────▼──────────────▼─────┐
│       Backend Services Layer              │
│                                            │
│  ┌──────────────┐  ┌──────────────┐      │
│  │ BitChat      │  │ BetaNet      │      │
│  │ Backend      │  │ Rust Server  │      │
│  │              │  │              │      │
│  │ • REST API   │  │ • HTTP API   │      │
│  │ • WebSocket  │  │ • HTX Proto  │      │
│  │ • Database   │  │ • Sphinx     │      │
│  └──────────────┘  └──────────────┘      │
└───────────────────────────────────────────┘
```

---

## Message Flow Diagrams

### 1. Online Message (BetaNet HTX)

```
User App              P2P System           BetaNet Transport      BetaNet Server
   │                      │                       │                     │
   │─── send_message ────▶│                       │                     │
   │  {to: "peer2",       │                       │                     │
   │   payload: "Hi",     │                       │                     │
   │   privacy: true}     │                       │                     │
   │                      │                       │                     │
   │                      │─── select_transport ─▶│                     │
   │                      │    (BetaNet: privacy) │                     │
   │                      │                       │                     │
   │                      │                       │─── build_sphinx ───▶│
   │                      │                       │    packet w/ route  │
   │                      │                       │                     │
   │                      │                       │◀─── relay route ────│
   │                      │                       │                     │
   │                      │◀──── success ─────────│                     │
   │◀──── ack ────────────│                       │                     │
```

### 2. Offline Message (BitChat BLE)

```
User App              P2P System           BitChat Transport      BitChat Backend
   │                      │                       │                     │
   │─── send_message ────▶│                       │                     │
   │  {to: "peer2",       │                       │                     │
   │   payload: "Hi"}     │                       │                     │
   │                      │                       │                     │
   │                      │─── detect_offline ───▶│                     │
   │                      │                       │                     │
   │                      │─── select_transport ─▶│                     │
   │                      │    (BitChat: offline) │                     │
   │                      │                       │                     │
   │                      │                       │─── POST /send ─────▶│
   │                      │                       │                     │
   │                      │                       │◀─── queued ─────────│
   │                      │                       │  (store-forward)    │
   │                      │◀──── queued ──────────│                     │
   │◀──── queued ─────────│                       │                     │
   │                      │                       │                     │
   │  [peer2 comes online]                        │                     │
   │                      │                       │◀─── deliver ────────│
   │                      │◀──── delivered ───────│    (WebSocket)      │
```

### 3. Protocol Switching (Online → Offline)

```
Time   P2P System           Active Transport        Backup Transport
───────────────────────────────────────────────────────────────────
T=0    Using BetaNet ──────▶ BetaNet HTX            BitChat (standby)
       (internet available)  ✓ Connected

T=10   Sending message ─────▶ BetaNet HTX            BitChat (standby)
                             ✓ Sending...

T=11   Internet lost ────────▶ ❌ Connection failed   BitChat (standby)

T=12   Detect failure ───────▶ ❌ Transport down      BitChat (standby)

T=13   Initiate failover ────────────────────────────▶ BitChat BLE
       Switch to BitChat                               ↻ Activating...

T=14   Retry message ────────────────────────────────▶ BitChat BLE
                                                        ✓ Offline mode
                                                        ✓ Queued

T=15   Confirm delivery ─────────────────────────────◀ BitChat BLE
       ✓ Message queued                                ✓ Store-forward
```

---

## Transport Capabilities Comparison

```
┌─────────────────────────────────────────────────────────────────┐
│                  TRANSPORT CAPABILITIES                         │
├────────────────┬───────────────┬────────────────┬───────────────┤
│   Capability   │   BitChat     │    BetaNet     │     Mesh      │
│                │   (BLE Mesh)  │  (HTX/Sphinx)  │  (Direct P2P) │
├────────────────┼───────────────┼────────────────┼───────────────┤
│ Unicast        │      ✅       │      ✅        │      ✅       │
│ Broadcast      │      ✅       │      ❌        │      ✅       │
│ Multicast      │      ✅       │      ❌        │      ✅       │
├────────────────┼───────────────┼────────────────┼───────────────┤
│ Max Size       │    64 KB      │    1 MB        │    1 MB       │
│ Latency        │   2000 ms     │    500 ms      │    100 ms     │
│ Bandwidth      │   0.1 Mbps    │   10 Mbps      │   100 Mbps    │
├────────────────┼───────────────┼────────────────┼───────────────┤
│ Offline Mode   │      ✅       │      ❌        │      ❌       │
│ Internet Req   │      ❌       │      ✅        │      ✅       │
│ Cellular       │      ❌       │      ✅        │      ✅       │
│ WiFi           │      ✅       │      ✅        │      ✅       │
├────────────────┼───────────────┼────────────────┼───────────────┤
│ Encryption     │      ✅       │      ✅        │      ⚠️       │
│ Fwd Secrecy    │      ❌       │      ✅        │      ❌       │
│ Anonymity      │     Low       │     High       │     None      │
├────────────────┼───────────────┼────────────────┼───────────────┤
│ Multi-hop      │  ✅ (7 hops)  │  ✅ (5 hops)   │      ❌       │
│ Store-forward  │      ✅       │      ❌        │      ❌       │
├────────────────┼───────────────┼────────────────┼───────────────┤
│ Battery Impact │    Medium     │     Low        │     Low       │
│ Data Cost      │     Low       │    Medium      │    Medium     │
├────────────────┼───────────────┼────────────────┼───────────────┤
│ Best For       │ Offline mode  │ Privacy comms  │ Low latency   │
│                │ Local mesh    │ Internet P2P   │ Direct conns  │
└────────────────┴───────────────┴────────────────┴───────────────┘
```

---

## Transport Selection Decision Tree

```
                    ┌─────────────────┐
                    │  Send Message   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ Has Internet?   │
                    └────┬────────┬───┘
                         │        │
                      NO │        │ YES
                         │        │
                   ┌─────▼───┐    │
                   │ BitChat │    │
                   │  (BLE)  │    │
                   └─────────┘    │
                                  │
                       ┌──────────▼──────────┐
                       │ Requires Privacy?   │
                       └──────┬──────────┬───┘
                              │          │
                           YES│          │NO
                              │          │
                      ┌───────▼──────┐   │
                      │   BetaNet    │   │
                      │   (Sphinx)   │   │
                      └──────────────┘   │
                                         │
                              ┌──────────▼──────────┐
                              │  Is Broadcast?      │
                              └──────┬──────────┬───┘
                                     │          │
                                  YES│          │NO
                                     │          │
                              ┌──────▼──────┐   │
                              │  BitChat    │   │
                              │ (broadcast) │   │
                              └─────────────┘   │
                                                │
                                     ┌──────────▼──────────┐
                                     │  Optimize for?      │
                                     │ • Latency → Mesh    │
                                     │ • Privacy → BetaNet │
                                     │ • Battery → BetaNet │
                                     └─────────────────────┘
```

---

## Store-and-Forward Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                  STORE-AND-FORWARD SYSTEM                      │
│                     (BitChat Transport)                        │
└────────────────────────────────────────────────────────────────┘

SCENARIO: Offline message delivery

Step 1: Sender sends while receiver offline
┌──────────┐                    ┌──────────┐
│ Sender   │─── Message ───────▶│ BitChat  │
│ (online) │   "Hello peer2"    │ Backend  │
└──────────┘                    └────┬─────┘
                                     │
                                     │ Store in database
                                     ▼
                              ┌─────────────┐
                              │  Message    │
                              │  Queue      │
                              │  (SQLite)   │
                              └─────────────┘

Step 2: Receiver comes online
┌──────────┐                    ┌──────────┐
│ Receiver │◀─── Connect ───────│ BitChat  │
│ (online) │    WebSocket       │ Backend  │
└──────────┘                    └────┬─────┘
                                     │
                                     │ Check queue
                                     ▼
                              ┌─────────────┐
                              │  Message    │
                              │  Queue      │
                              │  Found: 1   │
                              └────┬────────┘
                                   │
Step 3: Deliver queued messages    │
┌──────────┐                    ┌──▼──────┐
│ Receiver │◀─── Deliver ────────│ BitChat  │
│          │   "Hello peer2"    │ Backend  │
│          │   via WebSocket    │          │
└────┬─────┘                    └──────────┘
     │
     │ Send ACK
     ▼
┌──────────┐
│ BitChat  │
│ Backend  │──▶ Mark delivered
└──────────┘
```

---

## Multi-Transport Routing

```
┌────────────────────────────────────────────────────────────────┐
│              MULTI-TRANSPORT MESSAGE ROUTING                   │
└────────────────────────────────────────────────────────────────┘

SCENARIO: High-priority message with redundancy

┌──────────┐                  ┌─────────────────────┐
│  Sender  │─── Message ─────▶│   P2P Orchestrator  │
│          │   priority=HIGH  │                     │
└──────────┘   redundant=2    └──────────┬──────────┘
                                          │
                              Split to multiple transports
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    │                     │                     │
            ┌───────▼───────┐     ┌───────▼───────┐     ┌──────▼──────┐
            │   BitChat     │     │   BetaNet     │     │    Mesh     │
            │   Transport   │     │   Transport   │     │  Transport  │
            │               │     │               │     │             │
            │  Route: BLE   │     │  Route: HTX   │     │ Route: TCP  │
            └───────┬───────┘     └───────┬───────┘     └──────┬──────┘
                    │                     │                     │
                    └─────────────────────┼─────────────────────┘
                                          │
                              First to deliver wins
                                          │
                    ┌─────────────────────▼─────────────────────┐
                    │         P2P Orchestrator                  │
                    │   • Track delivery status                 │
                    │   • Cancel duplicate routes               │
                    │   • Record fastest transport              │
                    └───────────────────────────────────────────┘
```

---

## Security Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                    SECURITY LAYERS                             │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│  Application Layer                                             │
│  • End-to-end encryption (optional)                            │
│  • Message signing                                             │
└────────────────────┬───────────────────────────────────────────┘
                     │
┌────────────────────▼───────────────────────────────────────────┐
│  P2P Layer                                                     │
│  • Transport selection                                         │
│  • Peer authentication                                         │
│  • Access control                                              │
└────────────────────┬───────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
┌───────▼──────┐ ┌───▼────────┐ ┌▼──────────┐
│ BitChat      │ │ BetaNet    │ │ Mesh      │
│              │ │            │ │           │
│ • AES-256    │ │ • Sphinx   │ │ • TLS     │
│ • GCM mode   │ │ • Noise XK │ │ • Certs   │
│ • Per-peer   │ │ • Forward  │ │ • PSK     │
│   keys       │ │   secrecy  │ │           │
└──────────────┘ └────────────┘ └───────────┘
```

---

**Generated**: 2025-10-21
**Version**: 1.0
**Status**: Complete
