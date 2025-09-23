# Control Panel Architecture

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    Fog Compute Control Panel                     │
│                        (Next.js 14 App)                          │
└─────────────────────────────────────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
        ┌──────────────────────┐    ┌──────────────────────┐
        │   Frontend (React)   │    │   API Routes         │
        │   - Pages            │    │   - Dashboard Stats  │
        │   - Components       │    │   - Betanet Status   │
        │   - 3D Visualization │    │   - Benchmark APIs   │
        └──────────────────────┘    └──────────────────────┘
                    │                           │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
        ┌──────────────────────┐    ┌──────────────────────┐
        │  Betanet Network     │    │  BitChat P2P Mesh    │
        │  (Rust Backend)      │    │  (TypeScript)        │
        │  - Mixnodes          │    │  - Peer Discovery    │
        │  - Packet Flow       │    │  - Encryption        │
        └──────────────────────┘    └──────────────────────┘
                    │
                    ▼
        ┌──────────────────────┐
        │  Benchmark Engine    │
        │  (Python API)        │
        │  - Performance Tests │
        │  - Metrics Collection│
        └──────────────────────┘
```

## Component Hierarchy

```
App Layout
├── Navigation (Global)
│
├── Dashboard (/)
│   ├── Status Cards (Betanet, BitChat, Benchmarks)
│   ├── FogMap (Geographic Distribution)
│   ├── SystemMetrics (Health Indicators)
│   └── QuickActions (Action Buttons)
│
├── Betanet (/betanet)
│   ├── BetanetTopology (3D Visualization)
│   ├── PacketFlowMonitor (Real-time Flow)
│   └── MixnodeList (Node Details)
│
├── BitChat (/bitchat)
│   └── BitChatWrapper
│       ├── Peer List Sidebar
│       ├── Chat Area
│       └── Message Input
│
└── Benchmarks (/benchmarks)
    ├── BenchmarkControls (Test Controls)
    ├── BenchmarkCharts (Performance Graphs)
    └── Metrics Summary
```

## Data Flow

```
1. User Interaction
   └──> Component Event Handler
        └──> API Call (fetch)
             └──> API Route Handler
                  └──> Backend Service
                       └──> Response Data
                            └──> State Update
                                 └──> UI Re-render

2. Real-time Updates (Polling)
   └──> useEffect Hook
        └──> setInterval
             └──> API Call (every N seconds)
                  └──> State Update
                       └──> UI Re-render
```

## File Organization

```
apps/control-panel/
│
├── app/                        # Next.js App Router
│   ├── api/                   # API Routes
│   │   ├── dashboard/
│   │   ├── betanet/
│   │   └── benchmarks/
│   ├── betanet/               # Betanet Page
│   ├── bitchat/               # BitChat Page
│   ├── benchmarks/            # Benchmarks Page
│   ├── layout.tsx             # Root Layout
│   ├── page.tsx               # Dashboard
│   └── globals.css            # Global Styles
│
├── components/                 # React Components
│   ├── Navigation.tsx
│   ├── BetanetTopology.tsx
│   ├── BenchmarkCharts.tsx
│   └── ...
│
└── lib/                        # Utilities
    └── utils.ts
```