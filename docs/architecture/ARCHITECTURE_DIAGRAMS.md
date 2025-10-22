# Docker Compose Architecture - Visual Diagrams

**Version:** 1.0.0
**Date:** 2025-10-21

---

## Table of Contents

1. [Current Architecture Problems](#current-architecture-problems)
2. [Proposed Architecture Solution](#proposed-architecture-solution)
3. [Network Topology Comparison](#network-topology-comparison)
4. [Deployment Flow Diagrams](#deployment-flow-diagrams)
5. [Service Dependency Graph](#service-dependency-graph)

---

## Current Architecture Problems

### File Structure (Current)

```
┌────────────────────────────────────────────────────────────────┐
│                    docker-compose.yml                          │
│                   (Mixed Dev/Prod)                             │
├────────────────────────────────────────────────────────────────┤
│ ❌ Development configuration in base                           │
│ ❌ Hardcoded credentials                                       │
│ ❌ All ports exposed                                           │
│ ❌ Bind mounts for hot-reload                                  │
│                                                                 │
│ Services:                                                       │
│   postgres:       5432 EXPOSED                                │
│   backend:        8000 EXPOSED, --reload, bind mounts         │
│   frontend:       3000 EXPOSED, Dockerfile.dev                │
│   redis:          6379 EXPOSED, no auth                       │
│   prometheus:     9090 EXPOSED  ◄─────┐                       │
│   grafana:        3001:3000    ◄─────┼─── DUPLICATE           │
│   loki:           3100 EXPOSED        │                        │
│                                        │                        │
│ Network: fog-network (single)         │                        │
└────────────────────────────────────────┼───────────────────────┘
                                         │
┌────────────────────────────────────────┼───────────────────────┐
│              docker-compose.dev.yml    │                        │
│                (Dev Overrides)         │                        │
├────────────────────────────────────────┼───────────────────────┤
│ ⚠️  Redundant port exposures           │                        │
│ ⚠️  Some overrides, some redundancy    │                        │
│                                         │                        │
│ Overrides:                              │                        │
│   postgres:       Different DB name    │                        │
│   backend:        Debug logs, explicit reload                  │
│   frontend:       Dev telemetry settings                       │
│                                         │                        │
│ Network: fog-network (same)            │                        │
└─────────────────────────────────────────┼──────────────────────┘
                                          │
┌─────────────────────────────────────────┼──────────────────────┐
│          docker-compose.betanet.yml     │                       │
│              (3-Node Mixnet)            │                       │
├─────────────────────────────────────────┼──────────────────────┤
│ ❌ Duplicate Prometheus          ◄──────┘                       │
│ ❌ Duplicate Grafana             ◄──────┐                       │
│ ❌ PORT CONFLICT (9090)                  │                       │
│ ❌ Inconsistent volume naming            │                       │
│                                          │                       │
│ Services:                                │                       │
│   betanet-mixnode-1:  9001              │                       │
│   betanet-mixnode-2:  9002              │                       │
│   betanet-mixnode-3:  9003              │                       │
│   prometheus:         9090 ◄────── CONFLICT!                   │
│   grafana:            3000:3000 ◄─ Different port mapping      │
│                                                                  │
│ Network: betanet (172.30.0.0/16)                               │
│   ↑                                                             │
│   └──── ISOLATED - Cannot scrape fog-network services          │
└─────────────────────────────────────────────────────────────────┘

RESULT: ❌ Cannot run docker-compose.yml + docker-compose.betanet.yml together
        ❌ Two separate monitoring stacks
        ❌ No unified dashboard
```

---

## Proposed Architecture Solution

### File Structure (Proposed)

```
┌─────────────────────────────────────────────────────────────────┐
│                    docker-compose.yml                           │
│                  (Production Base)                              │
├─────────────────────────────────────────────────────────────────┤
│ ✅ Production-ready defaults                                    │
│ ✅ Environment variables for all config                         │
│ ✅ No exposed ports (security)                                  │
│ ✅ No bind mounts (immutable)                                   │
│                                                                  │
│ Services:                                                        │
│   postgres:       Internal only, health check                  │
│   backend:        Production build, no reload                  │
│   frontend:       Production build, no hot-reload              │
│   redis:          Auth required, persistence                   │
│   prometheus:     Multi-network scraping  ◄────┐               │
│   grafana:        Single instance            ◄─┼─── UNIFIED    │
│   loki:           Centralized logging           │               │
│   promtail:       Log shipping                  │               │
│                                                  │               │
│ Networks:                                        │               │
│   - internal    (postgres, redis, backend)      │               │
│   - public      (backend, frontend)             │               │
│   - monitoring  (prometheus, grafana) ◄─────────┘               │
│   - betanet     (mixnodes)                                      │
└─────────────────────────────────────────────────────────────────┘
                          │
                          │ Auto-loads in dev
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│              docker-compose.override.yml                        │
│              (Development - Auto-loaded)                        │
├─────────────────────────────────────────────────────────────────┤
│ ✅ Development conveniences only                                │
│ ✅ Hot-reload for rapid iteration                               │
│ ✅ Debug tools included                                         │
│                                                                  │
│ Overrides:                                                       │
│   postgres:       5432 EXPOSED, dev database                   │
│   backend:        8000 EXPOSED, bind mounts, debug logs        │
│   frontend:       3000 EXPOSED, bind mounts, hot-reload        │
│   redis:          6379 EXPOSED (no auth for dev)               │
│   prometheus:     9090 EXPOSED                                 │
│   grafana:        3001:3000 EXPOSED                            │
│                                                                  │
│ Adds Dev Tools:                                                 │
│   pgadmin:        5050 EXPOSED                                 │
│   redis-commander: 8081 EXPOSED                                │
│   mailhog:        1025 SMTP, 8025 UI                           │
│                                                                  │
│ Volumes: Caches for venv, node_modules                         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│              docker-compose.prod.yml                            │
│              (Production - Explicit)                            │
├─────────────────────────────────────────────────────────────────┤
│ ✅ Security hardening                                           │
│ ✅ Resource limits                                              │
│ ✅ Secrets from files                                           │
│                                                                  │
│ Overrides:                                                       │
│   All services:   Resource limits (CPU, memory)                │
│   postgres:       Secrets from files                           │
│   backend:        Production build, workers=4                  │
│   frontend:       Production build, optimized                  │
│   grafana:        Secrets, SMTP alerts                         │
│                                                                  │
│ Adds Production Services:                                       │
│   nginx:          80, 443 (reverse proxy, SSL)                 │
│   certbot:        SSL certificate renewal                      │
│   node-exporter:  System metrics                               │
│   cadvisor:       Container metrics                            │
│   alertmanager:   Alert routing                                │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│            docker-compose.betanet.yml                           │
│            (Betanet Add-on - No Duplicates)                     │
├─────────────────────────────────────────────────────────────────┤
│ ✅ No duplicate monitoring services                             │
│ ✅ Uses shared monitoring network                               │
│ ✅ DRY with YAML anchors                                        │
│                                                                  │
│ Services:                                                        │
│   betanet-mixnode-1:  9001, metrics 9091                       │
│   betanet-mixnode-2:  9002, metrics 9091                       │
│   betanet-mixnode-3:  9003, metrics 9091                       │
│   betanet-monitor:    8080 (status dashboard)                  │
│   betanet-loadgen:    (testing - profile)                      │
│                                                                  │
│ Networks:                                                        │
│   - betanet      (172.30.0.0/16)                               │
│   - monitoring   (SHARED with base) ◄───────────────────────┐  │
│                                                              │  │
│ Configuration:                                                │  │
│   YAML anchors for reusable config                           │  │
│   Health-based dependencies (1 → 2 → 3)                      │  │
│   Environment variables for tuning                           │  │
│                                                              │  │
│ Prometheus scrapes mixnodes via monitoring network ◄─────────┘  │
└─────────────────────────────────────────────────────────────────┘

RESULT: ✅ Can run any combination of environments
        ✅ Single monitoring stack for all services
        ✅ Unified Grafana dashboard
        ✅ Clear separation of concerns
```

---

## Network Topology Comparison

### Current Network Topology (Isolated)

```
┌──────────────────────────────────────────────────────────────────┐
│                        fog-network                               │
│                      (Bridge Network)                            │
│                                                                   │
│  ┌──────────┐   ┌─────────┐   ┌──────────┐   ┌────────┐        │
│  │ Postgres │   │ Backend │   │ Frontend │   │ Redis  │        │
│  │  :5432   │◄──│  :8000  │◄──│  :3000   │   │ :6379  │        │
│  └──────────┘   └─────────┘   └──────────┘   └────────┘        │
│                                                                   │
│  ┌────────────┐  ┌─────────┐   ┌──────┐                         │
│  │ Prometheus │  │ Grafana │   │ Loki │                         │
│  │   :9090    │──│  :3000  │   │:3100 │                         │
│  └────────────┘  └─────────┘   └──────┘                         │
│       │                                                           │
│       └──► Scrapes: backend, postgres                           │
└──────────────────────────────────────────────────────────────────┘
                          ╳
                          ╳  NO COMMUNICATION
                          ╳
┌──────────────────────────────────────────────────────────────────┐
│                         betanet                                  │
│                   (172.30.0.0/16)                                │
│                                                                   │
│  ┌───────────┐      ┌───────────┐      ┌───────────┐           │
│  │ Mixnode 1 │─────▶│ Mixnode 2 │─────▶│ Mixnode 3 │           │
│  │   :9001   │      │   :9002   │      │   :9003   │           │
│  └───────────┘      └───────────┘      └───────────┘           │
│                                                                   │
│  ┌────────────┐  ┌─────────┐                                    │
│  │ Prometheus │  │ Grafana │  ◄─── DUPLICATE SERVICES          │
│  │   :9090    │──│  :3000  │                                    │
│  └────────────┘  └─────────┘                                    │
│       │                                                           │
│       └──► Scrapes: mixnode 1, 2, 3 only                        │
└──────────────────────────────────────────────────────────────────┘

Problems:
  ❌ Two Prometheus instances (port conflict)
  ❌ Two Grafana instances (separate dashboards)
  ❌ Cannot visualize full system in one place
  ❌ Duplicate configuration and maintenance
```

### Proposed Network Topology (Bridged)

```
┌──────────────────────────────────────────────────────────────────┐
│                         internal                                 │
│                    (Internal-only Network)                       │
│                                                                   │
│                  ┌──────────┐                                    │
│                  │ Postgres │                                    │
│                  │  :5432   │                                    │
│                  └─────┬────┘                                    │
│                        │                                          │
│                  ┌─────▼────┐           ┌────────┐              │
│                  │ Backend  │───────────│ Redis  │              │
│                  │  :8000   │           │ :6379  │              │
│                  └──────────┘           └────────┘              │
│                       ▲                                           │
└───────────────────────┼──────────────────────────────────────────┘
                        │
┌───────────────────────┼──────────────────────────────────────────┐
│                       │      public                              │
│                       │  (External-facing Network)               │
│                       │                                           │
│  ┌─────────┐    ┌────┴─────┐    ┌──────────┐                   │
│  │  Nginx  │───▶│ Backend  │    │ Frontend │                   │
│  │ :80:443 │    │  :8000   │◄───│  :3000   │                   │
│  └─────────┘    └──────────┘    └──────────┘                   │
│   (prod)                                                          │
└──────────────────────────────────────────────────────────────────┘
                        │
                        │ Metrics
                        ▼
┌──────────────────────────────────────────────────────────────────┐
│                      monitoring                                  │
│                 (Cross-network Bridge)                           │
│                                                                   │
│  ┌────────────┐      ┌─────────┐      ┌──────┐                 │
│  │ Prometheus │─────▶│ Grafana │◄─────│ Loki │                 │
│  │   :9090    │      │  :3000  │      │:3100 │                 │
│  └─────┬──────┘      └─────────┘      └──────┘                 │
│        │                                                          │
│        │ Scrapes all networks                                    │
│        │                                                          │
│        ├─────────────────┬──────────────────┬──────────────┐   │
│        ▼                 ▼                  ▼              ▼   │
│    Backend          Mixnode 1          Mixnode 2      Mixnode 3│
│    (internal)       (betanet)          (betanet)      (betanet)│
└──────────────────────────────────────────────────────────────────┘
                        │
┌───────────────────────┼──────────────────────────────────────────┐
│                       │       betanet                            │
│                       │   (172.30.0.0/16)                        │
│                       │  (Mixnet Routing)                        │
│                       ▼                                           │
│  ┌───────────┐      ┌───────────┐      ┌───────────┐           │
│  │ Mixnode 1 │─────▶│ Mixnode 2 │─────▶│ Mixnode 3 │           │
│  │   :9001   │      │   :9002   │      │   :9003   │           │
│  │ metrics   │      │ metrics   │      │ metrics   │           │
│  │   :9091   │      │   :9091   │      │   :9091   │           │
│  └───────────┘      └───────────┘      └───────────┘           │
└──────────────────────────────────────────────────────────────────┘

Benefits:
  ✅ Single Prometheus scrapes all services
  ✅ Single Grafana with unified dashboard
  ✅ Network isolation maintained (internal has no internet)
  ✅ Monitoring bridges all networks for observability
  ✅ Betanet isolated but observable
```

---

## Deployment Flow Diagrams

### Development Workflow

```
Developer runs: docker-compose up
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│  Docker Compose auto-merges:                            │
│    1. docker-compose.yml (base)                         │
│    2. docker-compose.override.yml (auto-loaded)         │
└─────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│  Services Started:                                       │
│    ✓ Postgres (dev DB, port 5432 exposed)              │
│    ✓ Backend (hot-reload, debug logs, port 8000)       │
│    ✓ Frontend (hot-reload, port 3000)                  │
│    ✓ Redis (no auth, port 6379)                        │
│    ✓ Prometheus (port 9090)                            │
│    ✓ Grafana (port 3001)                               │
│    ✓ Loki (port 3100)                                  │
│    ✓ pgAdmin (port 5050)                               │
│    ✓ Redis Commander (port 8081)                       │
│    ✓ Mailhog (ports 1025, 8025)                        │
└─────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│  Developer Experience:                                   │
│    • Edit code → Auto-reload                            │
│    • Access http://localhost:3000 (frontend)            │
│    • Access http://localhost:8000/docs (API)            │
│    • Access http://localhost:3001 (Grafana)             │
│    • Use pgAdmin for database queries                   │
│    • View metrics in real-time                          │
└─────────────────────────────────────────────────────────┘
```

### Production Deployment

```
Deploy command: docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│  Docker Compose merges:                                  │
│    1. docker-compose.yml (base)                         │
│    2. docker-compose.prod.yml (production overrides)    │
└─────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│  Pre-checks:                                             │
│    ✓ Secrets files exist (/secrets/*.txt)              │
│    ✓ SSL certificates present (/nginx/ssl/)            │
│    ✓ .env.prod configured                              │
└─────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│  Services Started:                                       │
│    ✓ Postgres (internal only, secrets from file)       │
│    ✓ Backend (production build, 4 workers)             │
│    ✓ Frontend (production build, optimized)            │
│    ✓ Redis (auth required, persistence)                │
│    ✓ Nginx (ports 80, 443 - reverse proxy)             │
│    ✓ Prometheus (90 day retention)                     │
│    ✓ Grafana (SMTP alerts configured)                  │
│    ✓ Node Exporter (system metrics)                    │
│    ✓ cAdvisor (container metrics)                      │
│    ✓ Alertmanager (alert routing)                      │
└─────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│  Production Features:                                    │
│    • HTTPS via nginx (Let's Encrypt)                    │
│    • Resource limits enforced                           │
│    • Auto-restart on failure                            │
│    • Centralized logging                                │
│    • Alert notifications                                │
│    • No source code exposure                            │
└─────────────────────────────────────────────────────────┘
```

### Betanet Testing

```
Command: docker-compose -f docker-compose.yml \
                        -f docker-compose.override.yml \
                        -f docker-compose.betanet.yml up
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│  Docker Compose merges (in order):                       │
│    1. docker-compose.yml (base)                         │
│    2. docker-compose.override.yml (dev tools)           │
│    3. docker-compose.betanet.yml (mixnet)               │
└─────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│  Services Started:                                       │
│    ✓ All base services (postgres, backend, frontend)   │
│    ✓ All dev tools (pgAdmin, etc.)                     │
│    ✓ Betanet Mixnode 1 (entry) - waits for health      │
│         │                                                │
│         └──▶ ✓ Betanet Mixnode 2 (middle)              │
│                   │                                      │
│                   └──▶ ✓ Betanet Mixnode 3 (exit)      │
│    ✓ Betanet Monitor (dashboard)                       │
│    ✓ Shared Prometheus (scrapes all)                   │
│    ✓ Shared Grafana (unified view)                     │
└─────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│  Testing Experience:                                     │
│    • Access http://localhost:9001/health (entry)        │
│    • Access http://localhost:9002/health (middle)       │
│    • Access http://localhost:9003/health (exit)         │
│    • View topology at http://localhost:8080             │
│    • Monitor metrics in Grafana                         │
│    • All services visible in one dashboard              │
└─────────────────────────────────────────────────────────┘
```

---

## Service Dependency Graph

### Current Dependencies (Fragmented)

```
fog-network:
  postgres (healthy) ──┐
                       └──▶ backend (healthy) ──┐
                                                  └──▶ frontend

  prometheus ──┐
               └──▶ grafana

  loki (standalone)
  redis (standalone)

betanet:
  betanet-mixnode-1 (healthy) ──┐
                                 └──▶ betanet-mixnode-2 (healthy) ──┐
                                                                      └──▶ betanet-mixnode-3

  prometheus-betanet ──┐
                        └──▶ grafana-betanet
```

### Proposed Dependencies (Unified)

```
Shared across all networks:

  postgres (healthy)
    └──▶ backend (healthy)
         ├──▶ frontend
         └──▶ nginx (production)

  redis (standalone)

  loki
    └──▶ promtail

  prometheus ◄────────┬──────────┬──────────┬──────────┐
    │                 │          │          │          │
    │                 │          │          │          │
    │              backend  betanet-1  betanet-2  betanet-3
    │              (scrape) (scrape)  (scrape)  (scrape)
    │
    └──▶ grafana
         └──▶ alertmanager (production)

  betanet-mixnode-1 (healthy)
    └──▶ betanet-mixnode-2 (healthy)
         └──▶ betanet-mixnode-3 (healthy)
              └──▶ betanet-monitor

  Production only:
    nginx ──┐
            ├──▶ backend
            ├──▶ frontend
            └──▶ grafana

    certbot (renews nginx SSL)

    node-exporter ──┐
    cadvisor       ─┼──▶ prometheus
```

---

## Volume Management Comparison

### Current Volume Strategy (Inconsistent)

```
docker-compose.yml:
  ├── postgres_data               (underscore)
  ├── prometheus_data             (underscore)
  └── grafana_data                (underscore)

docker-compose.dev.yml:
  ├── postgres_dev_data           (underscore)
  ├── backend_venv                (underscore)
  └── control_panel_modules       (underscore)

docker-compose.betanet.yml:
  ├── prometheus-data             (hyphen) ❌ INCONSISTENT
  └── grafana-data                (hyphen) ❌ INCONSISTENT
```

### Proposed Volume Strategy (Consistent)

```
docker-compose.yml (Base):
  ├── postgres_data               ✅ Production DB
  ├── redis_data                  ✅ Cache persistence
  ├── prometheus_data             ✅ Metrics history
  ├── grafana_data                ✅ Dashboards
  └── loki_data                   ✅ Logs

docker-compose.override.yml (Dev):
  ├── postgres_dev_data           ✅ Separate dev DB
  ├── backend_venv                ✅ Python deps cache
  ├── control_panel_modules       ✅ Node deps cache
  ├── control_panel_next          ✅ Next.js build cache
  └── pgadmin_data                ✅ pgAdmin config

docker-compose.prod.yml:
  ├── nginx_logs                  ✅ Access/error logs
  └── alertmanager_data           ✅ Alert state

docker-compose.betanet.yml:
  ├── betanet_1_config            ✅ Node 1 config
  ├── betanet_1_data              ✅ Node 1 state
  ├── betanet_1_logs              ✅ Node 1 logs
  ├── betanet_2_config            ✅ Node 2 config
  ├── betanet_2_data              ✅ Node 2 state
  ├── betanet_2_logs              ✅ Node 2 logs
  ├── betanet_3_config            ✅ Node 3 config
  ├── betanet_3_data              ✅ Node 3 state
  └── betanet_3_logs              ✅ Node 3 logs

All use underscores consistently ✅
```

---

## Security Architecture

### Current Security Issues

```
┌─────────────────────────────────────────────────────────────┐
│                    Exposed Attack Surface                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Internet                                                    │
│      │                                                        │
│      ├──▶ :5432  Postgres  ❌ DB exposed                    │
│      ├──▶ :8000  Backend   ❌ Direct API access             │
│      ├──▶ :3000  Frontend  ❌ No CDN/caching                │
│      ├──▶ :6379  Redis     ❌ No auth, exposed              │
│      ├──▶ :9090  Prometheus ❌ Metrics exposed              │
│      ├──▶ :3001  Grafana   ❌ Monitoring exposed            │
│      └──▶ :3100  Loki      ❌ Logs exposed                  │
│                                                              │
│  Credentials: Hardcoded in YAML ❌                           │
│  Network: Single flat network ❌                             │
│  Volumes: World-readable ❌                                  │
└─────────────────────────────────────────────────────────────┘
```

### Proposed Security Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Minimal Attack Surface                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Internet                                                    │
│      │                                                        │
│      └──▶ :80,:443  Nginx ✅ Reverse proxy only             │
│             │                                                 │
│             ├──▶ Frontend (internal)                        │
│             ├──▶ Backend API (internal)                     │
│             └──▶ Grafana (internal)                         │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Internal Network (no internet access)               │  │
│  │    - Postgres (no exposed port)                      │  │
│  │    - Redis (auth required)                           │  │
│  │    - Backend (via nginx only)                        │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Betanet Network (isolated)                          │  │
│  │    - Mixnodes (172.30.0.0/16)                        │  │
│  │    - Only monitoring bridge                          │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  Credentials: Secrets from files ✅                          │
│  Network: Multi-layer isolation ✅                           │
│  Volumes: Proper permissions ✅                              │
│  Resource limits: Enforced ✅                                │
│  SSL/TLS: Let's Encrypt ✅                                   │
└─────────────────────────────────────────────────────────────┘
```

---

**End of Architecture Diagrams**
