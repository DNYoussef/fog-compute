# Docker Configuration Analysis

**Date:** 2025-10-21
**Analyst:** System Architecture Designer
**Scope:** Analysis of all docker-compose configurations for consolidation strategy

## Executive Summary

The project currently maintains **4 separate docker-compose files** with overlapping services, duplicate monitoring stacks, and isolated networks that prevent cross-service communication. This analysis identifies critical issues and proposes a unified deployment strategy.

### Key Findings

1. **Duplicate Monitoring Stacks**: Prometheus and Grafana defined in 3 different files
2. **Network Isolation**: Betanet services isolated from main application (cannot access shared database)
3. **Configuration Conflicts**: Port conflicts (Grafana on 3000 vs 3001) and volume naming inconsistencies
4. **Missing Integration**: Comprehensive monitoring stack (docker-compose.monitoring.yml) not referenced in main configs
5. **Environment Confusion**: Development overrides change database names but services may still reference wrong DB

---

## Service Inventory

### Base Services (docker-compose.yml)

| Service | Purpose | Image | Ports | Network |
|---------|---------|-------|-------|---------|
| **postgres** | Main database | postgres:15-alpine | 5432 | fog-network |
| **backend** | FastAPI server | Custom (backend/Dockerfile) | 8000 | fog-network |
| **frontend** | Next.js control panel | Custom (Dockerfile.dev) | 3000 | fog-network |
| **redis** | Caching layer | redis:7-alpine | 6379 | fog-network |
| **prometheus** | Metrics collection | prom/prometheus:latest | 9090 | fog-network |
| **grafana** | Visualization | grafana/grafana:latest | 3001 | fog-network |
| **loki** | Log aggregation | grafana/loki:latest | 3100 | fog-network |

**Configuration Details:**
- Backend has hot-reload enabled (`--reload` flag) even in base config
- Uses Dockerfile.dev for frontend in base (should be production)
- Database: `fog_compute`
- All services in single `fog-network` bridge network
- Named volumes: postgres_data, prometheus_data, grafana_data

### Dev Overrides (docker-compose.dev.yml)

**Purpose:** Development-specific configuration
**Usage:** `docker-compose -f docker-compose.yml -f docker-compose.dev.yml up`

| Service | Override Type | Changes |
|---------|---------------|---------|
| **postgres** | Environment | Database name changed to `fog_compute_dev` |
| **postgres** | Volume | Separate volume `postgres_dev_data` |
| **backend** | Build | Targets `development` stage |
| **backend** | Environment | DATABASE_URL points to `fog_compute_dev`, LOG_LEVEL=DEBUG |
| **backend** | Volume | Adds `backend_venv` for Python virtual environment |
| **backend** | Command | Installs backend in editable mode, enables debug logging |
| **frontend** | Volume | Named volumes for node_modules and .next cache |
| **grafana** | Environment | Adds GF_LOG_LEVEL=debug |

**Critical Issues:**
- Database name change may break if services don't reload environment variables
- Multiple overlapping volume mounts for same paths
- Build target "development" may not exist in Dockerfile

### Betanet Services (docker-compose.betanet.yml)

**Purpose:** Standalone Betanet mixnet infrastructure
**Network:** Completely isolated `betanet` network (172.30.0.0/16)

| Service | Type | Port | Node Type | Dependencies |
|---------|------|------|-----------|--------------|
| **betanet-mixnode-1** | Rust mixnode | 9001 | Entry | None |
| **betanet-mixnode-2** | Rust mixnode | 9002 | Middle | mixnode-1 |
| **betanet-mixnode-3** | Rust mixnode | 9003 | Exit | mixnode-2 |
| **prometheus** | Metrics (DUPLICATE) | 9090 | N/A | None |
| **grafana** | Visualization (DUPLICATE) | 3000 | N/A | prometheus |

**Betanet Configuration:**
- All nodes use identical build (Dockerfile.betanet)
- Differentiated by environment variables (NODE_TYPE, NODE_PORT)
- High-performance settings: 4 pipeline workers, 128 batch size, 25000 TPS target
- Sequential startup: entry -> middle -> exit
- Separate config and data volumes per node

**Prometheus Configuration:**
- Uses `config/prometheus.yml` (betanet-specific targets)
- Scrapes all 3 mixnodes on their respective ports
- Labels: node_type (entry/middle/exit), node_id (1/2/3)

### Comprehensive Monitoring Stack (docker-compose.monitoring.yml)

**Purpose:** Full observability stack (NOT currently integrated)
**Networks:** `monitoring` (internal) + `fog-compute` (external reference)

| Service | Purpose | Port | Dependencies |
|---------|---------|------|--------------|
| **prometheus** | Advanced metrics | 9090 | None |
| **grafana** | Advanced visualization | 3000 | prometheus, loki, tempo |
| **loki** | Log aggregation | 3100 | None |
| **promtail** | Log shipper | N/A | loki |
| **tempo** | Distributed tracing | 3200, 4317, 4318, 9411, 14268 | None |
| **jaeger** | Tracing UI | 16686, 14250 | None |
| **alertmanager** | Alert routing | 9093 | None |
| **node-exporter** | System metrics | 9101 | None |
| **cadvisor** | Container metrics | 9102 | None |
| **betanet-exporter** | Custom exporter | 9200 | External betanet service |
| **bitchat-exporter** | Custom exporter | 9201 | External bitchat service |
| **uptime-kuma** | Uptime monitoring | 3001 | None |
| **sentry-redis** | Error tracking cache | N/A | None |
| **sentry-postgres** | Error tracking DB | N/A | None |

**Advanced Features:**
- 90-day retention for Prometheus
- SMTP alerting configured for Grafana
- Custom exporters for Betanet and BitChat services
- Full tracing stack (Tempo + Jaeger)
- Error tracking infrastructure (Sentry components defined but not fully configured)
- Expects external network `fog-compute-network` to exist

---

## Network Architecture Analysis

### Current Configuration

```
┌─────────────────────────────────────────┐
│         fog-network (bridge)            │
│  - postgres (fog_compute DB)            │
│  - backend (API server)                 │
│  - frontend (Next.js)                   │
│  - redis (cache)                        │
│  - prometheus (base metrics)            │
│  - grafana (base visualization)         │
│  - loki (base logs)                     │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│      betanet (bridge 172.30.0.0/16)     │
│  - betanet-mixnode-1 (entry)            │
│  - betanet-mixnode-2 (middle)           │
│  - betanet-mixnode-3 (exit)             │
│  - prometheus (DUPLICATE!)              │
│  - grafana (DUPLICATE!)                 │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│        monitoring (bridge)              │
│  - Full observability stack             │
│  - NOT CONNECTED to fog-network         │
│  - References external fog-compute-net  │
└─────────────────────────────────────────┘
```

### Critical Issues

1. **Complete Network Isolation**
   - Betanet mixnodes cannot access `fog-network` postgres
   - Backend service cannot directly communicate with betanet nodes
   - Monitoring stack expects `fog-compute-network` but it's actually `fog-network`

2. **Duplicate Service Definitions**
   - **Prometheus**: Defined in base (fog-network), betanet, AND monitoring
   - **Grafana**: Defined in base (fog-network), betanet, AND monitoring
   - Port conflicts: Grafana on 3000 (betanet, monitoring) vs 3001 (base)

3. **Volume Naming Inconsistencies**
   - Base uses: `postgres_data`, `prometheus_data`, `grafana_data`
   - Betanet uses: `prometheus-data`, `grafana-data` (different naming)
   - Monitoring uses: `prometheus-data`, `grafana-data`
   - Dev overrides: `postgres_dev_data`

4. **Missing Service Discovery**
   - monitoring/prometheus.yml references `betanet:9000` (doesn't exist in betanet network)
   - config/prometheus.yml targets betanet-mixnode-1/2/3 (correct but isolated)
   - No unified service discovery across environments

---

## Configuration Comparison Matrix

### Postgres Service

| Aspect | Base | Dev Override | Betanet |
|--------|------|--------------|---------|
| Database Name | fog_compute | fog_compute_dev | NOT INCLUDED |
| Volume | postgres_data | postgres_dev_data | N/A |
| Port Exposed | 5432 | 5432 | N/A |
| Network | fog-network | fog-network | N/A |
| Health Check | Yes | Inherited | N/A |

**Issue:** Betanet services have no database access

### Backend Service

| Aspect | Base | Dev Override | Betanet |
|--------|------|--------------|---------|
| Build Stage | N/A | development | NOT INCLUDED |
| Hot Reload | Yes (--reload) | Yes (explicit) | N/A |
| Database URL | fog_compute | fog_compute_dev | N/A |
| Log Level | Default | DEBUG | N/A |
| Volume Mounts | Code only | Code + venv | N/A |

**Issue:** Base has dev features enabled, dev should be pure override

### Prometheus Service

| Aspect | Base | Betanet | Monitoring |
|--------|------|---------|------------|
| Container Name | fog-prometheus | betanet-prometheus | fog-compute-prometheus |
| Port | 9090 | 9090 | 9090 |
| Network | fog-network | betanet | monitoring |
| Config File | monitoring/prometheus/prometheus.yml | config/prometheus.yml | monitoring/prometheus.yml |
| Retention | Default | Default | 90 days |
| Admin API | No | No | Yes |

**Issue:** 3 separate Prometheus instances, different configs, port conflicts

### Grafana Service

| Aspect | Base | Betanet | Monitoring |
|--------|------|---------|------------|
| Container Name | fog-grafana | betanet-grafana | fog-compute-grafana |
| Port | 3001:3000 | 3000:3000 | 3000:3000 |
| Network | fog-network | betanet | monitoring |
| Admin Password | admin | admin | ${GRAFANA_ADMIN_PASSWORD} |
| Plugins | None | None | piechart, worldmap, clock |
| SMTP | No | No | Yes |
| Dependencies | prometheus | prometheus | prometheus, loki, tempo |

**Issue:** 3 separate Grafana instances, port conflicts (3000 vs 3001)

---

## Deployment Scenarios

### Current Usage (Inferred)

1. **Development**: `docker-compose up` (uses base config with dev features)
2. **Dev Override**: `docker-compose -f docker-compose.yml -f docker-compose.dev.yml up`
3. **Betanet Testing**: `docker-compose -f docker-compose.betanet.yml up` (isolated)
4. **Full Monitoring**: Not used (docker-compose.monitoring.yml orphaned)

### Problems with Current Approach

1. Base config contains development features (hot-reload, dev dockerfile)
2. No production configuration file
3. Betanet completely isolated - cannot integrate with main application
4. Comprehensive monitoring stack not integrated
5. Multiple ways to run "development" mode

---

## Architecture Decision Records (ADRs)

### ADR-001: Betanet Network Isolation

**Context:** Betanet mixnodes run in isolated network (172.30.0.0/16)

**Decision:** Separate network for security/privacy layer

**Consequences:**
- **Pros:**
  - Clear separation of concerns
  - Betanet can be scaled independently
  - Network-level isolation for privacy layer

- **Cons:**
  - No access to shared postgres database
  - Backend cannot directly query mixnode status
  - Requires port exposure for any inter-service communication
  - Duplicate monitoring stack required

**Recommendation:** Use multi-network attachment to allow controlled access

### ADR-002: Duplicate Monitoring Services

**Context:** Prometheus/Grafana duplicated across 3 files

**Decision:** Each environment has its own monitoring

**Consequences:**
- **Pros:**
  - Isolated metrics per environment
  - No cross-environment metric pollution

- **Cons:**
  - Port conflicts when running multiple environments
  - Wasted resources (3x memory/CPU for monitoring)
  - Different configurations = different visibility
  - No unified observability

**Recommendation:** Single monitoring stack with multi-tenancy via labels

### ADR-003: Development Override Pattern

**Context:** docker-compose.dev.yml overrides base config

**Decision:** Use Docker Compose override mechanism

**Consequences:**
- **Pros:**
  - Standard Docker Compose pattern
  - Keeps dev-specific config separate

- **Cons:**
  - Base config already has dev features
  - Database name change may break references
  - Requires `-f` flag awareness from developers
  - No clear "production" config

**Recommendation:** Create base as production, dev/betanet as overrides

---

## Identified Issues & Risks

### Critical Issues

1. **Network Isolation Breaks Integration**
   - Severity: HIGH
   - Impact: Betanet cannot store data in postgres, backend cannot query mixnode status
   - Risk: Feature development blocked, integration impossible

2. **Port Conflicts Prevent Multi-Environment**
   - Severity: HIGH
   - Impact: Cannot run base + betanet simultaneously (Prometheus/Grafana ports clash)
   - Risk: Testing full stack integration impossible

3. **Database Name Mismatch in Dev**
   - Severity: MEDIUM
   - Impact: Services may connect to wrong database if env vars not reloaded
   - Risk: Data corruption, test data in production DB

4. **Monitoring Stack Not Integrated**
   - Severity: MEDIUM
   - Impact: Advanced observability features (tracing, alerting) not available
   - Risk: Production issues harder to debug, no proactive monitoring

### Medium Issues

5. **Base Config Contains Dev Features**
   - Severity: MEDIUM
   - Impact: Production deployment uses dev dockerfile and hot-reload
   - Risk: Performance degradation, security issues in production

6. **Volume Naming Inconsistencies**
   - Severity: LOW
   - Impact: Confusing when inspecting volumes, potential data loss during migration
   - Risk: Developer mistakes, deployment script errors

7. **Missing External Network**
   - Severity: MEDIUM
   - Impact: monitoring stack expects `fog-compute-network` but it's named `fog-network`
   - Risk: Monitoring stack fails to start

### Configuration Drift

8. **Multiple Prometheus Configs**
   - monitoring/prometheus.yml: Targets backend, betanet, postgres
   - config/prometheus.yml: Targets betanet mixnodes
   - Different scrape targets = incomplete metrics

9. **Dockerfile References**
   - Base uses `Dockerfile.dev` for frontend (should be production)
   - Dev override targets "development" build stage (may not exist)

---

## Consolidation Proposal

### Recommended Architecture: Unified Base + Profile Overrides

**Core Principle:** One source of truth, environment-specific overlays, shared observability

### Proposed File Structure

```
docker-compose.yml              # Production base configuration
docker-compose.dev.yml          # Development overrides
docker-compose.betanet.yml      # Betanet services (integrated)
docker-compose.monitoring.yml   # Full observability (integrated)
docker-compose.local.yml        # Local development (all-in-one)
```

### Unified Network Strategy

```yaml
networks:
  # Main application network (all services)
  fog-network:
    driver: bridge
    name: fog-compute-network  # Explicit name

  # Betanet privacy layer (mixnodes + backend access)
  betanet-network:
    driver: bridge
    internal: true  # No external access

  # Monitoring network (observability stack)
  monitoring-network:
    driver: bridge
```

### Multi-Network Service Attachment

Services that need cross-network communication:

```yaml
# Backend connects to both fog and betanet
backend:
  networks:
    - fog-network
    - betanet-network

# Monitoring connects to both fog and betanet
prometheus:
  networks:
    - monitoring-network
    - fog-network
    - betanet-network
```

### Proposed Consolidation: Option 1 (Recommended)

#### File: docker-compose.yml (Production Base)

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: fog-postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-fog_user}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-fog_password}
      POSTGRES_DB: ${POSTGRES_DB:-fog_compute}
    volumes:
      - postgres-data:/var/lib/postgresql/data
    networks:
      - fog-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-fog_user}"]
      interval: 10s
      timeout: 5s
      retries: 5
    # Port NOT exposed in production

  redis:
    image: redis:7-alpine
    container_name: fog-redis
    volumes:
      - redis-data:/data
    networks:
      - fog-network
    # Port NOT exposed in production

  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
      target: production  # Production stage
    container_name: fog-backend
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-fog_user}:${POSTGRES_PASSWORD:-fog_password}@postgres:5432/${POSTGRES_DB:-fog_compute}
      REDIS_URL: redis://redis:6379
      API_HOST: 0.0.0.0
      API_PORT: 8000
      ENVIRONMENT: ${ENVIRONMENT:-production}
      LOG_LEVEL: ${LOG_LEVEL:-info}
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - fog-network
      - betanet-network  # Access to betanet services
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    # No hot-reload, no volume mounts in production

  frontend:
    build:
      context: ./apps/control-panel
      dockerfile: Dockerfile  # Production dockerfile
    container_name: fog-frontend
    environment:
      NEXT_PUBLIC_API_URL: ${API_URL:-http://backend:8000}
      NODE_ENV: production
    depends_on:
      backend:
        condition: service_healthy
    networks:
      - fog-network
    # No volume mounts in production

volumes:
  postgres-data:
  redis-data:

networks:
  fog-network:
    driver: bridge
    name: fog-compute-network
  betanet-network:
    driver: bridge
    internal: true
```

#### File: docker-compose.dev.yml (Development Overrides)

```yaml
version: '3.8'

services:
  postgres:
    environment:
      POSTGRES_DB: fog_compute_dev
    ports:
      - "5432:5432"  # Expose for local tools
    volumes:
      - postgres-dev-data:/var/lib/postgresql/data

  redis:
    ports:
      - "6379:6379"  # Expose for local tools

  backend:
    build:
      target: development  # Development build stage
    environment:
      DATABASE_URL: postgresql+asyncpg://fog_user:fog_password@postgres:5432/fog_compute_dev
      LOG_LEVEL: DEBUG
      ENVIRONMENT: development
    volumes:
      - ./backend:/app/backend:delegated
      - ./src:/app/src:delegated
      - backend-venv:/app/.venv
    command: >
      sh -c "pip install -e /app/backend &&
             python -m uvicorn server.main:app
             --host 0.0.0.0
             --port 8000
             --reload
             --log-level debug"
    ports:
      - "8000:8000"

  frontend:
    build:
      dockerfile: Dockerfile.dev
    environment:
      NODE_ENV: development
      NEXT_PUBLIC_API_URL: http://localhost:8000
    volumes:
      - ./apps/control-panel:/app:delegated
      - control-panel-modules:/app/node_modules
      - control-panel-next:/app/.next
    ports:
      - "3000:3000"

volumes:
  postgres-dev-data:
  backend-venv:
  control-panel-modules:
  control-panel-next:
```

#### File: docker-compose.betanet.yml (Betanet Services - Integrated)

```yaml
version: '3.8'

services:
  betanet-mixnode-1:
    build:
      context: .
      dockerfile: Dockerfile.betanet
    container_name: betanet-mixnode-1
    environment:
      - NODE_TYPE=entry
      - NODE_PORT=9001
      - RUST_LOG=${RUST_LOG:-info}
      - PIPELINE_WORKERS=${PIPELINE_WORKERS:-4}
      - BATCH_SIZE=${BATCH_SIZE:-128}
      - POOL_SIZE=${POOL_SIZE:-1024}
      - MAX_QUEUE_DEPTH=${MAX_QUEUE_DEPTH:-10000}
      - TARGET_THROUGHPUT=${TARGET_THROUGHPUT:-25000}
      # Database access (if needed)
      - DATABASE_URL=postgresql://fog_user:fog_password@postgres:5432/fog_compute
    volumes:
      - ./config/betanet-1:/config
      - ./data/betanet-1:/data
    networks:
      - betanet-network
      - fog-network  # Access to shared resources
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9001/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  betanet-mixnode-2:
    build:
      context: .
      dockerfile: Dockerfile.betanet
    container_name: betanet-mixnode-2
    environment:
      - NODE_TYPE=middle
      - NODE_PORT=9002
      - RUST_LOG=${RUST_LOG:-info}
      - PIPELINE_WORKERS=${PIPELINE_WORKERS:-4}
      - BATCH_SIZE=${BATCH_SIZE:-128}
      - POOL_SIZE=${POOL_SIZE:-1024}
      - MAX_QUEUE_DEPTH=${MAX_QUEUE_DEPTH:-10000}
      - TARGET_THROUGHPUT=${TARGET_THROUGHPUT:-25000}
    volumes:
      - ./config/betanet-2:/config
      - ./data/betanet-2:/data
    networks:
      - betanet-network
      - fog-network
    depends_on:
      - betanet-mixnode-1
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9002/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  betanet-mixnode-3:
    build:
      context: .
      dockerfile: Dockerfile.betanet
    container_name: betanet-mixnode-3
    environment:
      - NODE_TYPE=exit
      - NODE_PORT=9003
      - RUST_LOG=${RUST_LOG:-info}
      - PIPELINE_WORKERS=${PIPELINE_WORKERS:-4}
      - BATCH_SIZE=${BATCH_SIZE:-128}
      - POOL_SIZE=${POOL_SIZE:-1024}
      - MAX_QUEUE_DEPTH=${MAX_QUEUE_DEPTH:-10000}
      - TARGET_THROUGHPUT=${TARGET_THROUGHPUT:-25000}
    volumes:
      - ./config/betanet-3:/config
      - ./data/betanet-3:/data
    networks:
      - betanet-network
      - fog-network
    depends_on:
      - betanet-mixnode-2
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9003/health"]
      interval: 30s
      timeout: 10s
      retries: 3

# Only include in dev mode
profiles:
  dev:
    services:
      betanet-mixnode-1:
        ports:
          - "9001:9001"
      betanet-mixnode-2:
        ports:
          - "9002:9002"
      betanet-mixnode-3:
        ports:
          - "9003:9003"
```

#### File: docker-compose.monitoring.yml (Unified Observability - Updated)

```yaml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    container_name: fog-prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=90d'
      - '--web.enable-lifecycle'
      - '--web.enable-admin-api'
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./monitoring/alerting/rules.yml:/etc/prometheus/rules.yml
      - prometheus-data:/prometheus
    networks:
      - monitoring-network
      - fog-network      # Scrape backend, postgres
      - betanet-network  # Scrape betanet mixnodes
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:9090/-/healthy"]
      interval: 30s
      timeout: 10s
      retries: 3

  grafana:
    image: grafana/grafana:latest
    container_name: fog-grafana
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-changeme}
      - GF_INSTALL_PLUGINS=grafana-piechart-panel,grafana-worldmap-panel
    volumes:
      - grafana-data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./monitoring/grafana/datasources.yml:/etc/grafana/provisioning/datasources/datasources.yml
    networks:
      - monitoring-network
    depends_on:
      - prometheus
      - loki
      - tempo
    restart: unless-stopped

  loki:
    image: grafana/loki:latest
    container_name: fog-loki
    command: -config.file=/etc/loki/loki-config.yml
    volumes:
      - ./monitoring/loki/loki-config.yml:/etc/loki/loki-config.yml
      - loki-data:/loki
    networks:
      - monitoring-network
    restart: unless-stopped

  promtail:
    image: grafana/promtail:latest
    container_name: fog-promtail
    command: -config.file=/etc/promtail/promtail-config.yml
    volumes:
      - ./monitoring/loki/promtail-config.yml:/etc/promtail/promtail-config.yml
      - /var/log:/var/log:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
    networks:
      - monitoring-network
    depends_on:
      - loki
    restart: unless-stopped

  tempo:
    image: grafana/tempo:latest
    container_name: fog-tempo
    command: ["-config.file=/etc/tempo/tempo-config.yml"]
    volumes:
      - ./monitoring/tempo/tempo-config.yml:/etc/tempo/tempo-config.yml
      - tempo-data:/tmp/tempo
    networks:
      - monitoring-network
      - fog-network  # Receive traces from backend
    restart: unless-stopped

  alertmanager:
    image: prom/alertmanager:latest
    container_name: fog-alertmanager
    command:
      - '--config.file=/etc/alertmanager/alertmanager.yml'
      - '--storage.path=/alertmanager'
    volumes:
      - ./monitoring/alerting/alertmanager.yml:/etc/alertmanager/alertmanager.yml
      - alertmanager-data:/alertmanager
    networks:
      - monitoring-network
    restart: unless-stopped

  node-exporter:
    image: prom/node-exporter:latest
    container_name: fog-node-exporter
    command:
      - '--path.rootfs=/host'
      - '--path.procfs=/host/proc'
      - '--path.sysfs=/host/sys'
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    networks:
      - monitoring-network
    restart: unless-stopped

  cadvisor:
    image: gcr.io/cadvisor/cadvisor:latest
    container_name: fog-cadvisor
    privileged: true
    devices:
      - /dev/kmsg
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker:/var/lib/docker:ro
    networks:
      - monitoring-network
    restart: unless-stopped

  betanet-exporter:
    build:
      context: ./monitoring/exporters
      dockerfile: Dockerfile.betanet-exporter
    container_name: fog-betanet-exporter
    environment:
      - BETANET_MIXNODE_URLS=http://betanet-mixnode-1:9001,http://betanet-mixnode-2:9002,http://betanet-mixnode-3:9003
      - METRICS_PORT=9200
    networks:
      - monitoring-network
      - betanet-network  # Access betanet services
    restart: unless-stopped

# Only expose ports in dev
profiles:
  dev:
    services:
      prometheus:
        ports:
          - "9090:9090"
      grafana:
        ports:
          - "3001:3000"
      loki:
        ports:
          - "3100:3100"
      tempo:
        ports:
          - "3200:3200"
          - "4317:4317"
          - "4318:4318"
      alertmanager:
        ports:
          - "9093:9093"

volumes:
  prometheus-data:
  grafana-data:
  loki-data:
  tempo-data:
  alertmanager-data:

networks:
  monitoring-network:
    driver: bridge
```

#### File: docker-compose.local.yml (All-in-One Development)

```yaml
version: '3.8'

# Combines dev + betanet + monitoring for local full-stack development
# Usage: docker-compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.betanet.yml -f docker-compose.monitoring.yml -f docker-compose.local.yml up

services:
  # Port mappings for local access
  postgres:
    ports:
      - "5432:5432"

  redis:
    ports:
      - "6379:6379"

  backend:
    ports:
      - "8000:8000"

  frontend:
    ports:
      - "3000:3000"

  betanet-mixnode-1:
    ports:
      - "9001:9001"

  betanet-mixnode-2:
    ports:
      - "9002:9002"

  betanet-mixnode-3:
    ports:
      - "9003:9003"

  prometheus:
    ports:
      - "9090:9090"

  grafana:
    ports:
      - "3001:3000"

  loki:
    ports:
      - "3100:3100"

  alertmanager:
    ports:
      - "9093:9093"
```

### Updated Prometheus Configuration

#### File: monitoring/prometheus.yml (Unified Config)

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: 'fog-compute'
    environment: '${ENVIRONMENT:-production}'

# Alerting
alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

# Rules
rule_files:
  - /etc/prometheus/rules.yml

# Scrape configurations
scrape_configs:
  # Prometheus self-monitoring
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
        labels:
          service: 'prometheus'

  # Fog Backend API
  - job_name: 'fog-backend'
    static_configs:
      - targets: ['backend:8000']
        labels:
          service: 'backend-api'
          layer: 'application'

  # PostgreSQL Database
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']  # Requires postgres_exporter
        labels:
          service: 'database'
          layer: 'data'

  # Redis Cache
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']  # Requires redis_exporter
        labels:
          service: 'cache'
          layer: 'data'

  # Betanet Mixnodes
  - job_name: 'betanet-entry'
    static_configs:
      - targets: ['betanet-mixnode-1:9001']
        labels:
          service: 'betanet'
          layer: 'privacy'
          node_type: 'entry'
          node_id: '1'

  - job_name: 'betanet-middle'
    static_configs:
      - targets: ['betanet-mixnode-2:9002']
        labels:
          service: 'betanet'
          layer: 'privacy'
          node_type: 'middle'
          node_id: '2'

  - job_name: 'betanet-exit'
    static_configs:
      - targets: ['betanet-mixnode-3:9003']
        labels:
          service: 'betanet'
          layer: 'privacy'
          node_type: 'exit'
          node_id: '3'

  # Custom Exporters
  - job_name: 'betanet-exporter'
    static_configs:
      - targets: ['betanet-exporter:9200']
        labels:
          service: 'betanet-metrics'
          layer: 'observability'

  # System Metrics
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']
        labels:
          service: 'system-metrics'
          layer: 'infrastructure'

  # Container Metrics
  - job_name: 'cadvisor'
    static_configs:
      - targets: ['cadvisor:8080']
        labels:
          service: 'container-metrics'
          layer: 'infrastructure'
```

---

## Usage Patterns

### Production Deployment

```bash
# Start core services only
docker-compose up -d

# Add monitoring
docker-compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d

# Add betanet (if needed)
docker-compose -f docker-compose.yml -f docker-compose.betanet.yml -f docker-compose.monitoring.yml up -d
```

### Development

```bash
# Option 1: Basic development (backend + frontend + db)
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

# Option 2: Full stack with betanet
docker-compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.betanet.yml up

# Option 3: Everything (app + betanet + monitoring)
docker-compose -f docker-compose.yml \
               -f docker-compose.dev.yml \
               -f docker-compose.betanet.yml \
               -f docker-compose.monitoring.yml \
               -f docker-compose.local.yml up

# Option 4: Use profiles (when implemented)
docker-compose --profile dev --profile betanet --profile monitoring up
```

### Testing

```bash
# CI/CD testing
docker-compose -f docker-compose.yml -f docker-compose.test.yml up --abort-on-container-exit

# Betanet integration testing
docker-compose -f docker-compose.yml -f docker-compose.betanet.yml -f docker-compose.test.yml up --abort-on-container-exit
```

---

## Migration Plan

### Phase 1: Preparation (No Code Changes)

**Duration:** 1-2 hours

1. **Backup Current Configuration**
   ```bash
   cp docker-compose.yml docker-compose.yml.backup
   cp docker-compose.dev.yml docker-compose.dev.yml.backup
   cp docker-compose.betanet.yml docker-compose.betanet.yml.backup
   ```

2. **Document Current State**
   - Run `docker-compose config` for each file to capture merged configs
   - List all running containers: `docker ps -a`
   - List all volumes: `docker volume ls | grep fog`
   - List all networks: `docker network ls | grep fog`

3. **Export Data (if in use)**
   ```bash
   # Backup database
   docker exec fog-postgres pg_dump -U fog_user fog_compute > backup.sql

   # Backup volumes
   docker run --rm -v fog-postgres-data:/data -v $(pwd):/backup alpine tar czf /backup/postgres-data.tar.gz /data
   ```

### Phase 2: Network Standardization

**Duration:** 30 minutes

1. **Create Standardized Networks**
   ```bash
   docker network create fog-compute-network --driver bridge
   docker network create betanet-network --driver bridge --internal
   docker network create monitoring-network --driver bridge
   ```

2. **Update Existing Services (if running)**
   ```bash
   # Connect running containers to new networks (if needed)
   docker network connect fog-compute-network fog-backend
   docker network connect betanet-network fog-backend
   ```

### Phase 3: Configuration Consolidation

**Duration:** 2-3 hours

1. **Implement New docker-compose.yml (Production Base)**
   - Remove dev-specific features (hot-reload, exposed ports)
   - Standardize network names
   - Use environment variables for all secrets/config
   - Remove volume mounts for code

2. **Update docker-compose.dev.yml (Pure Overrides)**
   - Only include deviations from base
   - Add volume mounts for hot-reload
   - Expose ports for local access
   - Override build targets to 'development'

3. **Integrate docker-compose.betanet.yml**
   - Add multi-network attachment (fog-network + betanet-network)
   - Remove duplicate Prometheus/Grafana
   - Update environment variables to reference shared postgres

4. **Update docker-compose.monitoring.yml**
   - Fix network name (fog-compute-network instead of external)
   - Add multi-network attachment
   - Update Prometheus config with all scrape targets
   - Remove port exposure (add to local.yml instead)

5. **Create docker-compose.local.yml**
   - Port mappings only
   - No service definitions
   - Quick local development setup

### Phase 4: Testing

**Duration:** 3-4 hours

1. **Test Production Config**
   ```bash
   docker-compose -f docker-compose.yml config  # Validate syntax
   docker-compose -f docker-compose.yml up -d
   docker-compose -f docker-compose.yml ps      # Verify all healthy
   docker-compose -f docker-compose.yml logs backend
   curl http://localhost:8000/health            # SHOULD FAIL (no exposed port)
   docker-compose -f docker-compose.yml down
   ```

2. **Test Development Config**
   ```bash
   docker-compose -f docker-compose.yml -f docker-compose.dev.yml config
   docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
   curl http://localhost:8000/health            # Should succeed
   # Make code change, verify hot-reload
   docker-compose -f docker-compose.yml -f docker-compose.dev.yml down
   ```

3. **Test Betanet Integration**
   ```bash
   docker-compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.betanet.yml up -d

   # Verify betanet can access postgres
   docker exec betanet-mixnode-1 psql postgresql://fog_user:fog_password@postgres:5432/fog_compute_dev -c "SELECT 1"

   # Verify backend can access betanet
   docker exec fog-backend curl http://betanet-mixnode-1:9001/health

   docker-compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.betanet.yml down
   ```

4. **Test Full Stack with Monitoring**
   ```bash
   docker-compose -f docker-compose.yml \
                  -f docker-compose.dev.yml \
                  -f docker-compose.betanet.yml \
                  -f docker-compose.monitoring.yml \
                  -f docker-compose.local.yml up -d

   # Verify Prometheus scraping all targets
   curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'

   # Verify Grafana access
   curl http://localhost:3001/api/health

   # Verify all services reachable
   docker network inspect fog-compute-network
   docker network inspect betanet-network
   docker network inspect monitoring-network

   docker-compose -f docker-compose.yml \
                  -f docker-compose.dev.yml \
                  -f docker-compose.betanet.yml \
                  -f docker-compose.monitoring.yml \
                  -f docker-compose.local.yml down
   ```

5. **Restore Data (if backed up)**
   ```bash
   # Restore database
   docker exec -i fog-postgres psql -U fog_user fog_compute_dev < backup.sql
   ```

### Phase 5: Documentation & Deployment

**Duration:** 2 hours

1. **Update Documentation**
   - README.md: Update docker-compose usage instructions
   - DOCKER_DEPLOYMENT.md: Document all deployment scenarios
   - Create DOCKER_ARCHITECTURE.md: Diagram network topology

2. **Update CI/CD Pipelines**
   - Update GitHub Actions workflows
   - Update any deployment scripts
   - Update Kubernetes/Helm configs if applicable

3. **Update Developer Onboarding**
   - Update setup scripts
   - Update Makefile targets
   - Update .env.example with all new variables

4. **Create Helper Scripts**
   ```bash
   # scripts/docker-dev.sh
   docker-compose -f docker-compose.yml -f docker-compose.dev.yml up "$@"

   # scripts/docker-full.sh
   docker-compose -f docker-compose.yml \
                  -f docker-compose.dev.yml \
                  -f docker-compose.betanet.yml \
                  -f docker-compose.monitoring.yml \
                  -f docker-compose.local.yml up "$@"
   ```

### Phase 6: Cleanup

**Duration:** 30 minutes

1. **Remove Deprecated Files**
   - Archive old configs to `docker/archive/`
   - Remove orphaned volumes
   - Remove orphaned networks

2. **Verify No Regressions**
   - Run full test suite
   - Manual smoke testing
   - Check all dashboards/monitoring

---

## Validation Checklist

### Network Connectivity

- [ ] Backend can connect to postgres on fog-network
- [ ] Backend can connect to betanet-mixnode-1/2/3 on betanet-network
- [ ] Prometheus can scrape backend on fog-network
- [ ] Prometheus can scrape betanet nodes on betanet-network
- [ ] Betanet nodes can communicate with each other on betanet-network
- [ ] Frontend can access backend API
- [ ] Monitoring services isolated on monitoring-network

### Service Health

- [ ] All services start successfully
- [ ] All healthchecks pass
- [ ] No port conflicts
- [ ] All dependencies resolve correctly
- [ ] Database migrations run successfully

### Data Persistence

- [ ] Postgres data survives container restart
- [ ] Prometheus data survives container restart
- [ ] Grafana dashboards survive container restart
- [ ] Betanet config/data survives container restart

### Development Features

- [ ] Backend hot-reload works on code change
- [ ] Frontend hot-reload works on code change
- [ ] Volume mounts work correctly
- [ ] Debugger can attach to running containers
- [ ] Logs accessible via docker-compose logs

### Production Readiness

- [ ] No ports exposed in production config
- [ ] Secrets loaded from environment variables
- [ ] Production build stages used
- [ ] No development tools in production images
- [ ] Resource limits defined (if applicable)

### Monitoring & Observability

- [ ] Prometheus scraping all expected targets
- [ ] Grafana can query all data sources
- [ ] Loki receiving logs from all services
- [ ] Alertmanager configured correctly
- [ ] Custom exporters working

---

## Alternative Approach: Docker Profiles

**Note:** This approach uses Docker Compose profiles instead of multiple files.

### Single docker-compose.yml with Profiles

```yaml
version: '3.8'

services:
  # Core services (always run)
  postgres:
    image: postgres:15-alpine
    profiles: ["core", "dev", "full"]
    # ...

  backend:
    build: ./backend
    profiles: ["core", "dev", "full"]
    # ...

  # Development-only services
  dev-tools:
    image: custom/dev-tools
    profiles: ["dev", "full"]
    # ...

  # Betanet services
  betanet-mixnode-1:
    build: ./betanet
    profiles: ["betanet", "full"]
    # ...

  # Monitoring services
  prometheus:
    image: prom/prometheus
    profiles: ["monitoring", "full"]
    # ...
```

### Usage with Profiles

```bash
# Core only
docker-compose --profile core up

# Development
docker-compose --profile dev up

# Betanet testing
docker-compose --profile betanet up

# Full stack
docker-compose --profile full up

# Custom combination
docker-compose --profile core --profile monitoring up
```

**Pros:**
- Single file to maintain
- Clear profile-based separation
- Easier to understand what runs in each mode

**Cons:**
- Less flexible than override files
- Cannot easily override existing service configs
- All services defined in one large file

**Recommendation:** Use override files (Option 1) for this project due to complexity and need for per-environment customization.

---

## Environment Variables Strategy

### Required .env File

Create `.env` file in project root:

```bash
# Database
POSTGRES_USER=fog_user
POSTGRES_PASSWORD=<generate_secure_password>
POSTGRES_DB=fog_compute

# Application
ENVIRONMENT=production
LOG_LEVEL=info
API_URL=http://backend:8000

# Betanet
RUST_LOG=info
PIPELINE_WORKERS=4
BATCH_SIZE=128
TARGET_THROUGHPUT=25000

# Monitoring
GRAFANA_ADMIN_PASSWORD=<generate_secure_password>
SMTP_HOST=smtp.gmail.com:587
SMTP_USER=alerts@fogcompute.dev
SMTP_PASSWORD=<smtp_password>
SMTP_FROM=alerts@fogcompute.dev
```

### Environment-Specific .env Files

```
.env                 # Default/production values
.env.dev             # Development overrides
.env.test            # Testing overrides
.env.local           # Local developer overrides (git-ignored)
```

---

## Rollback Plan

If consolidation causes issues:

1. **Immediate Rollback**
   ```bash
   # Stop new config
   docker-compose down

   # Restore backups
   cp docker-compose.yml.backup docker-compose.yml
   cp docker-compose.dev.yml.backup docker-compose.dev.yml

   # Restart old config
   docker-compose up -d
   ```

2. **Data Recovery**
   ```bash
   # Restore database from backup
   docker exec -i fog-postgres psql -U fog_user fog_compute < backup.sql

   # Restore volumes from tar
   docker run --rm -v fog-postgres-data:/data -v $(pwd):/backup alpine tar xzf /backup/postgres-data.tar.gz -C /data
   ```

3. **Network Cleanup**
   ```bash
   # Remove new networks if unused
   docker network rm fog-compute-network betanet-network monitoring-network
   ```

---

## Cost-Benefit Analysis

### Benefits of Consolidation

1. **Reduced Complexity**
   - Single source of truth for base configuration
   - Clear separation of concerns (prod vs dev vs betanet)
   - Easier onboarding for new developers

2. **Improved Integration**
   - Betanet can access shared database
   - Backend can query betanet status
   - Unified monitoring across all services

3. **Resource Optimization**
   - Single Prometheus instance (saves ~200MB RAM)
   - Single Grafana instance (saves ~100MB RAM)
   - No port conflicts = can run full stack locally

4. **Better DevOps**
   - Clear deployment paths (prod vs dev)
   - Environment parity (dev mirrors prod)
   - Easier CI/CD integration

5. **Enhanced Observability**
   - All metrics in one place
   - Correlated logs and traces
   - End-to-end visibility

### Costs of Consolidation

1. **Migration Effort**
   - ~10-15 hours total effort (analysis, implementation, testing)
   - Potential downtime during migration
   - Risk of breaking existing workflows

2. **Learning Curve**
   - Developers need to learn new compose patterns
   - Documentation must be updated
   - CI/CD pipelines need adjustment

3. **Testing Overhead**
   - More combinations to test (base+dev, base+betanet, etc.)
   - Need comprehensive integration tests
   - Manual testing required

### ROI Analysis

**Time Investment:** ~15 hours
**Time Saved (per developer per month):**
- Debugging network issues: 2 hours
- Setting up monitoring: 1 hour
- Understanding deployment: 1 hour
- **Total:** 4 hours/month/developer

**Break-even:** With 2 developers, ROI positive after 2 months

---

## Recommendations

### Immediate Actions (High Priority)

1. **Fix Network Isolation** (Critical)
   - Add betanet-network to backend service
   - Enable cross-network communication
   - Update Prometheus to scrape both networks
   - **Impact:** Unblocks betanet integration features

2. **Consolidate Monitoring Stack** (High)
   - Remove duplicate Prometheus/Grafana from base and betanet files
   - Use docker-compose.monitoring.yml as single source
   - Update all configs to reference unified monitoring
   - **Impact:** Saves resources, improves observability

3. **Separate Production from Development** (High)
   - Remove hot-reload and dev features from base config
   - Create true production dockerfile
   - Move all dev features to docker-compose.dev.yml
   - **Impact:** Production deployment safety

### Medium-Term Actions

4. **Implement Unified Network Strategy**
   - Create fog-compute-network with explicit name
   - Standardize multi-network attachments
   - Document network topology
   - **Timeline:** During next major release

5. **Standardize Volume Naming**
   - Consistent naming convention (hyphens vs underscores)
   - Prefix all volumes with `fog-`
   - Document volume purposes
   - **Timeline:** During next major release

6. **Create Helper Scripts**
   - `./scripts/docker-dev.sh` for development
   - `./scripts/docker-full.sh` for full stack
   - `./scripts/docker-prod.sh` for production testing
   - **Timeline:** Immediately after consolidation

### Long-Term Actions

7. **Implement Advanced Monitoring**
   - Integrate Tempo for distributed tracing
   - Set up alerting rules
   - Create custom Grafana dashboards
   - **Timeline:** Next quarter

8. **Explore Kubernetes Migration**
   - Once docker-compose patterns stabilized
   - Leverage multi-network learnings
   - Maintain compose for local development
   - **Timeline:** 6 months

---

## Conclusion

The current docker-compose configuration has **critical architectural issues** that prevent proper service integration and waste resources through duplication. The recommended consolidation strategy:

1. **Addresses all critical issues** (network isolation, monitoring duplication)
2. **Maintains flexibility** (production, dev, betanet can run separately or combined)
3. **Improves developer experience** (clear patterns, helper scripts)
4. **Enhances observability** (unified monitoring, cross-service visibility)
5. **Reduces operational costs** (fewer duplicate services, clearer deployment paths)

**Recommended Approach:** Implement Option 1 (Unified Base + Profile Overrides) following the phased migration plan.

**Risk Level:** Medium (requires testing but rollback plan available)

**Expected Timeline:** 2-3 days for full implementation and validation

**Next Steps:**
1. Review this analysis with the team
2. Get approval for consolidation approach
3. Schedule maintenance window for migration
4. Execute Phase 1 (Preparation) immediately
5. Implement and test phases 2-4
6. Deploy to production with monitoring

---

## Appendix: Quick Reference Commands

### Current State (Before Consolidation)

```bash
# Base stack
docker-compose up -d

# Dev stack
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

# Betanet only (isolated)
docker-compose -f docker-compose.betanet.yml up

# Monitoring only (broken - network issue)
docker-compose -f monitoring/docker-compose.monitoring.yml up
```

### Proposed State (After Consolidation)

```bash
# Production
docker-compose up -d
docker-compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d  # with monitoring

# Development (basic)
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

# Development (with betanet)
docker-compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.betanet.yml up

# Full stack (everything)
./scripts/docker-full.sh up -d

# Individual service scaling
docker-compose up -d --scale betanet-mixnode-2=3  # Run 3 middle nodes
```

### Diagnostic Commands

```bash
# Check network connectivity
docker network inspect fog-compute-network
docker exec fog-backend ping betanet-mixnode-1
docker exec betanet-mixnode-1 psql postgresql://fog_user:fog_password@postgres:5432/fog_compute -c "SELECT 1"

# Check service health
docker-compose ps
docker-compose logs backend --tail=100
curl http://localhost:9090/api/v1/targets  # Prometheus targets

# Resource usage
docker stats
docker system df
```

### Cleanup Commands

```bash
# Stop and remove everything
docker-compose down -v  # Removes volumes!
docker-compose down     # Keeps volumes

# Remove orphaned resources
docker system prune -a
docker volume prune
docker network prune

# Targeted cleanup
docker volume rm $(docker volume ls -q | grep fog)
docker network rm fog-network betanet monitoring-network
```

---

**End of Analysis**
