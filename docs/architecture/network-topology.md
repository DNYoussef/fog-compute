# Docker Network Topology - FOG Compute Platform

## Multi-Network Architecture Overview

This document provides detailed network topology diagrams for the FOG Compute platform's Docker infrastructure.

---

## Network Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│                        FOG-NETWORK (172.28.0.0/16)                           │
│                     Primary Application Network Layer                        │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐         ┌─────────────────┐         ┌──────────────┐  │
│  │   Frontend      │         │    Backend      │         │    Redis     │  │
│  │   (Next.js)     │────────>│   (FastAPI)     │────────>│   (Cache)    │  │
│  │                 │         │                 │         │              │  │
│  │  Port: 3000     │         │  Port: 8000     │         │  Port: 6379  │  │
│  │  Container:     │         │  Container:     │         │  Container:  │  │
│  │  fog-frontend   │         │  fog-backend    │         │  fog-redis   │  │
│  └─────────────────┘         └────────┬────────┘         └──────────────┘  │
│                                       │                                     │
│                                       │                                     │
│                                       ↓                                     │
│                              ┌────────────────┐                             │
│                              │   PostgreSQL   │ ←─────────────┐             │
│                              │   (Database)   │                │             │
│                              │                │                │             │
│                              │  Port: 5432    │                │             │
│                              │  Container:    │                │             │
│                              │  fog-postgres  │                │             │
│                              └───────┬────────┘                │             │
│                                      │                         │             │
│                                      │ MULTI-NETWORK           │             │
│                                      │ BRIDGE                  │             │
│                                      │                         │             │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    UNIFIED MONITORING STACK                            │ │
│  │                                                                        │ │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐            │ │
│  │  │  Prometheus  │    │   Grafana    │    │     Loki     │            │ │
│  │  │  (Metrics)   │───>│(Dashboards)  │<───│    (Logs)    │            │ │
│  │  │              │    │              │    │              │            │ │
│  │  │ Port: 9090   │    │ Port: 3000   │    │ Port: 3100   │            │ │
│  │  │ Container:   │    │ External:    │    │ Container:   │            │ │
│  │  │ fog-         │    │ 3001         │    │ fog-loki     │            │ │
│  │  │ prometheus   │    │ fog-grafana  │    │              │            │ │
│  │  └──────────────┘    └──────────────┘    └──────────────┘            │ │
│  │                                                                        │ │
│  │  Multi-Network: Attached to BOTH fog-network AND betanet-network      │ │
│  │  Capability: Scrapes metrics and logs from ALL services               │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                      ║                         ║             │
│                                      ║                         ║             │
└──────────────────────────────────────╬─────────────────────────╬─────────────┘
                                       ║                         ║
                        MULTI-NETWORK  ║  BRIDGE                 ║
                        (5 Services)   ║  LAYER                  ║
                                       ║                         ║
┌──────────────────────────────────────╬─────────────────────────╬─────────────┐
│                                      ║                         ║             │
│                   BETANET-NETWORK (172.30.0.0/16)              ║             │
│                  Anonymous Mixnode Communication Network        ║             │
│                                      ║                         ║             │
├──────────────────────────────────────╩─────────────────────────╩─────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │              BETANET MIXNODE CASCADE (3-Layer Anonymity)             │   │
│  │                                                                      │   │
│  │  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐         │   │
│  │  │  Mixnode 1  │      │  Mixnode 2  │      │  Mixnode 3  │         │   │
│  │  │   (Entry)   │─────>│  (Middle)   │─────>│   (Exit)    │         │   │
│  │  │             │      │             │      │             │         │   │
│  │  │ Port: 9001  │      │ Port: 9002  │      │ Port: 9003  │         │   │
│  │  │ Container:  │      │ Container:  │      │ Container:  │         │   │
│  │  │ betanet-    │      │ betanet-    │      │ betanet-    │         │   │
│  │  │ mixnode-1   │      │ mixnode-2   │      │ mixnode-3   │         │   │
│  │  └─────┬───────┘      └─────┬───────┘      └─────┬───────┘         │   │
│  │        │                    │                    │                 │   │
│  │        │  Database Access   │  Database Access   │  Database       │   │
│  │        │  (via fog-network) │  (via fog-network) │  Access         │   │
│  │        │                    │                    │                 │   │
│  │        └────────────────────┴────────────────────┘                 │   │
│  │                             │                                      │   │
│  │                             ↓                                      │   │
│  │              Access PostgreSQL via Multi-Network Bridge            │   │
│  │                      (fog-network connection)                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  METRICS COLLECTION:                                                         │
│  Prometheus scrapes betanet mixnodes via betanet-network attachment         │
│                                                                              │
│  LOG AGGREGATION:                                                            │
│  Loki receives logs from mixnodes via betanet-network attachment            │
│                                                                              │
│  VISUALIZATION:                                                              │
│  Grafana displays unified dashboards for both fog and betanet services      │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Network Isolation Zones

### Zone 1: FOG-NETWORK (172.28.0.0/16)
**Purpose**: Core application services

**Services (7)**:
1. Frontend (fog-frontend) - User interface
2. Backend (fog-backend) - API server
3. PostgreSQL (fog-postgres) - Database
4. Redis (fog-redis) - Cache
5. Prometheus (fog-prometheus) - Metrics
6. Grafana (fog-grafana) - Dashboards
7. Loki (fog-loki) - Logs

**Characteristics**:
- Default network for application services
- Production: No exposed ports
- Development: All ports exposed for debugging
- Security: Isolated from external networks

### Zone 2: BETANET-NETWORK (172.30.0.0/16)
**Purpose**: Anonymous mixnode communication

**Services (3 dedicated + 5 shared)**:
1. Betanet-Mixnode-1 (Entry) - First layer anonymity
2. Betanet-Mixnode-2 (Middle) - Second layer anonymity
3. Betanet-Mixnode-3 (Exit) - Third layer anonymity
4. PostgreSQL (shared) - Database access
5. Backend (shared) - API access
6. Prometheus (shared) - Metrics collection
7. Grafana (shared) - Dashboard visualization
8. Loki (shared) - Log aggregation

**Characteristics**:
- Dedicated subnet for mixnode traffic
- Multi-network bridge for resource access
- Metrics/logs aggregated via shared monitoring
- Isolated from direct internet access

### Zone 3: MULTI-NETWORK BRIDGE
**Purpose**: Enable controlled cross-network communication

**Bridged Services (5)**:
1. **PostgreSQL**: Database for all services
2. **Backend**: API bridge between networks
3. **Prometheus**: Metrics from both networks
4. **Grafana**: Unified dashboards
5. **Loki**: Centralized logs

**Benefits**:
- Eliminates duplicate database instances
- Unified monitoring across all services
- Maintains network isolation while allowing controlled access
- Reduces resource usage (550 MB RAM saved)

---

## Service Connectivity Matrix

| From Service | To Service | Network Path | Purpose |
|--------------|------------|--------------|---------|
| Frontend | Backend | fog-network | API calls |
| Backend | PostgreSQL | fog-network | Database queries |
| Backend | Redis | fog-network | Cache operations |
| Mixnode-1 | PostgreSQL | betanet-network → fog-network | Data storage |
| Mixnode-1 | Backend | betanet-network → fog-network | API access |
| Mixnode-1 | Mixnode-2 | betanet-network | Packet routing |
| Mixnode-2 | Mixnode-3 | betanet-network | Packet routing |
| Prometheus | Backend | fog-network | Metric scraping |
| Prometheus | Mixnode-1 | betanet-network | Metric scraping |
| Prometheus | Mixnode-2 | betanet-network | Metric scraping |
| Prometheus | Mixnode-3 | betanet-network | Metric scraping |
| Grafana | Prometheus | fog-network | Dashboard queries |
| Loki | All Services | Both networks | Log collection |

---

## Port Mapping Details

### Production Mode (No Exposed Ports)
All services communicate via internal Docker networks. No external access.

```
┌──────────────────────────────────────┐
│  External Network (No Access)        │
└──────────────────────────────────────┘
                  ╳
                  ╳ No exposed ports
                  ╳
┌──────────────────────────────────────┐
│  Docker Internal Networks            │
│  - fog-network: 172.28.0.0/16        │
│  - betanet-network: 172.30.0.0/16    │
│                                      │
│  All services: Internal only         │
└──────────────────────────────────────┘
```

### Development Mode (All Ports Exposed)
```
┌──────────────────────────────────────┐
│  External Network (localhost)        │
├──────────────────────────────────────┤
│  3000 → Frontend (Next.js dev)       │
│  8000 → Backend (FastAPI)            │
│  5432 → PostgreSQL (database)        │
│  6379 → Redis (cache)                │
│  9090 → Prometheus (metrics)         │
│  3001 → Grafana (dashboards)         │
│  3100 → Loki (logs)                  │
└──────────────────────────────────────┘
                  ↓
┌──────────────────────────────────────┐
│  Docker Internal Networks            │
│  (same internal ports)               │
└──────────────────────────────────────┘
```

### Betanet Mode (Mixnode Ports Exposed)
```
┌──────────────────────────────────────┐
│  External Network (localhost)        │
├──────────────────────────────────────┤
│  9001 → Mixnode-1 (entry)            │
│  9002 → Mixnode-2 (middle)           │
│  9003 → Mixnode-3 (exit)             │
│  (base services internal only)       │
└──────────────────────────────────────┘
```

---

## Data Flow Examples

### Example 1: User Request (fog-network)
```
User Browser
    ↓ HTTP GET http://localhost:3000
Frontend (fog-frontend)
    ↓ API call http://backend:8000/api/data
Backend (fog-backend)
    ↓ SQL query postgresql://postgres:5432
PostgreSQL (fog-postgres)
    ↓ Result
Backend
    ↓ JSON response
Frontend
    ↓ HTML page
User Browser
```

### Example 2: Anonymous Message (betanet-network)
```
Message Input
    ↓
Mixnode-1 (Entry)
    ↓ Encrypted packet (betanet-network)
Mixnode-2 (Middle)
    ↓ Re-encrypted packet (betanet-network)
Mixnode-3 (Exit)
    ↓ Database write (via fog-network bridge)
PostgreSQL (fog-postgres)
    ↓ Confirmation
Mixnode-3 → Mixnode-2 → Mixnode-1
    ↓
Message Output
```

### Example 3: Metrics Collection (multi-network)
```
Prometheus (fog-prometheus)
    ↓ Scrape fog-network services
    ├─> Backend:8000/metrics
    ├─> PostgreSQL:5432/metrics
    └─> Redis:6379/metrics
    ↓ Scrape betanet-network services
    ├─> Mixnode-1:9001/metrics
    ├─> Mixnode-2:9002/metrics
    └─> Mixnode-3:9003/metrics
    ↓ Store metrics
Prometheus TSDB
    ↓ Query
Grafana (fog-grafana)
    ↓ Render dashboards
User Browser
```

---

## Network Security

### Isolation Boundaries

```
┌─────────────────────────────────────────────────┐
│  External Network (Internet)                    │
│  - No direct access to containers               │
│  - Only mapped ports accessible                 │
└────────────────┬────────────────────────────────┘
                 │
                 ↓ Only in development mode
┌─────────────────────────────────────────────────┐
│  Docker Bridge Networks                         │
│  ┌──────────────────┬──────────────────┐        │
│  │  fog-network     │  betanet-network │        │
│  │  172.28.0.0/16   │  172.30.0.0/16   │        │
│  │                  │                  │        │
│  │  Default deny    │  Default deny    │        │
│  │  inter-network   │  inter-network   │        │
│  │                  │                  │        │
│  │  Exceptions:     │  Exceptions:     │        │
│  │  - PostgreSQL    │  - PostgreSQL    │        │
│  │  - Backend       │  - Backend       │        │
│  │  - Monitoring    │  - Monitoring    │        │
│  └──────────────────┴──────────────────┘        │
└─────────────────────────────────────────────────┘
```

### Security Features

1. **Network Isolation**: Separate subnets prevent unauthorized access
2. **Multi-Network Whitelist**: Only specific services bridge networks
3. **No External Ports (Production)**: All services internal
4. **Health Checks**: Continuous availability monitoring
5. **Restart Policies**: Automatic recovery from failures
6. **Read-Only Configs**: Monitoring configs immutable
7. **Volume Isolation**: Separate data for dev/prod

---

## Scaling Considerations

### Horizontal Scaling (Docker Swarm)
```
                Load Balancer
                      ↓
    ┌─────────────────┼─────────────────┐
    ↓                 ↓                 ↓
Backend-1        Backend-2        Backend-3
    ↓                 ↓                 ↓
    └─────────────────┼─────────────────┘
                      ↓
                PostgreSQL
             (single instance)
```

### Network Topology for Swarm
```
Overlay Network: fog-swarm (10.0.0.0/24)
├── Backend replicas: 3
├── Frontend replicas: 2
├── PostgreSQL: 1 (with replication)
├── Redis: 1 (with persistence)
└── Monitoring: 1 (centralized)

Overlay Network: betanet-swarm (10.1.0.0/24)
├── Mixnode-1 replicas: 2
├── Mixnode-2 replicas: 2
└── Mixnode-3 replicas: 2
```

---

## Monitoring Architecture

### Metric Flow
```
┌─────────────────────────────────────────────────┐
│  Services (Exporters)                           │
│  - Backend: /metrics endpoint                   │
│  - PostgreSQL: postgres_exporter                │
│  - Redis: redis_exporter                        │
│  - Mixnodes: /metrics endpoints                 │
│  - Node: node_exporter (monitoring mode)        │
│  - Containers: cAdvisor (monitoring mode)       │
└────────────────┬────────────────────────────────┘
                 ↓ HTTP scrape (15s interval)
┌────────────────────────────────────────────────┐
│  Prometheus (fog-prometheus)                   │
│  - Time-series database                        │
│  - 30 day retention (production)               │
│  - 7 day retention (development)               │
│  - Multi-network scraping                      │
└────────────────┬───────────────────────────────┘
                 ↓ PromQL queries
┌────────────────────────────────────────────────┐
│  Grafana (fog-grafana)                         │
│  - Dashboard visualization                     │
│  - Alerting (with Alertmanager)                │
│  - Unified view: fog + betanet metrics         │
└────────────────────────────────────────────────┘
```

### Log Flow
```
┌─────────────────────────────────────────────────┐
│  Services (Log Producers)                       │
│  - All containers: stdout/stderr                │
│  - Docker log driver: json-file                 │
└────────────────┬────────────────────────────────┘
                 ↓ Docker logging driver
┌────────────────────────────────────────────────┐
│  Loki (fog-loki)                                │
│  - Log aggregation                              │
│  - Index-free storage                           │
│  - Multi-network collection                     │
└────────────────┬───────────────────────────────┘
                 ↓ LogQL queries
┌────────────────────────────────────────────────┐
│  Grafana Explore                                │
│  - Log search and filtering                     │
│  - Correlation with metrics                     │
│  - Unified dashboard integration                │
└────────────────────────────────────────────────┘
```

---

## Summary

### Network Architecture Benefits

1. **Resource Efficiency**: 61% RAM reduction through shared monitoring
2. **Simplified Management**: Single monitoring stack for all environments
3. **Security**: Network isolation with controlled bridge access
4. **Scalability**: Multi-network design supports future scaling
5. **Observability**: Unified metrics and logs across all services
6. **Maintainability**: Clean configuration hierarchy
7. **Flexibility**: Support for production, development, betanet modes

### Key Design Principles

- **Separation of Concerns**: Dedicated networks for different traffic types
- **DRY (Don't Repeat Yourself)**: No duplicate services
- **Security by Default**: Production has no exposed ports
- **Observability First**: Comprehensive monitoring built-in
- **Multi-Tenancy**: Services can participate in multiple networks
- **Configuration as Code**: All topology defined in docker-compose.yml

This multi-network architecture provides a solid foundation for the FOG Compute platform, balancing security, efficiency, and functionality.
