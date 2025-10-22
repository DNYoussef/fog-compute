# Docker Compose Consolidation - Migration Guide

**Version:** 1.0.0
**Date:** 2025-10-21
**Estimated Time:** 30-45 minutes
**Downtime Required:** Yes (5-10 minutes)

---

## Overview

This guide walks through migrating from the current 3-file Docker Compose structure to the new consolidated 4-file architecture.

**From:**
- `docker-compose.yml` (mixed dev/prod)
- `docker-compose.dev.yml` (dev overrides with duplicates)
- `docker-compose.betanet.yml` (3-node mixnet with duplicated monitoring)

**To:**
- `docker-compose.yml` (production-ready base)
- `docker-compose.override.yml` (dev overrides, auto-loaded)
- `docker-compose.prod.yml` (production hardening)
- `docker-compose.betanet.yml` (betanet-only, no duplicates)

**Benefits:**
- ✅ Eliminates duplicate Prometheus and Grafana services
- ✅ Resolves port conflicts (Prometheus 9090, Grafana 3000/3001)
- ✅ Single monitoring stack for all services
- ✅ Environment-specific configurations clear and maintainable
- ✅ Production-ready defaults with security by default

---

## Pre-Migration Checklist

### 1. Backup Current State

```bash
# Create backup branch
git checkout -b backup/pre-consolidation
git add -A
git commit -m "Backup before Docker Compose consolidation"
git push origin backup/pre-consolidation

# Export current running configuration
docker-compose config > backup/docker-compose.current.yml
docker-compose -f docker-compose.yml -f docker-compose.dev.yml config > backup/docker-compose.dev.current.yml
docker-compose -f docker-compose.yml -f docker-compose.betanet.yml config > backup/docker-compose.betanet.current.yml
```

### 2. Backup Data Volumes

```bash
# Create backup directory
mkdir -p backup/volumes

# Export PostgreSQL data
docker-compose exec postgres pg_dumpall -U fog_user > backup/volumes/postgres_backup_$(date +%Y%m%d_%H%M%S).sql

# Backup Grafana dashboards (if customized)
docker cp fog-grafana:/var/lib/grafana backup/volumes/grafana_data

# Backup Prometheus data (optional - large)
# docker cp fog-prometheus:/prometheus backup/volumes/prometheus_data

# List all volumes to backup
docker volume ls | grep fog
docker volume ls | grep betanet
```

### 3. Document Current Environment

```bash
# Export environment variables
docker-compose exec backend env > backup/backend.env
docker-compose exec frontend env > backup/frontend.env

# Document current ports
docker-compose ps | tee backup/ports.txt

# Document current networks
docker network ls | grep -E 'fog|betanet' | tee backup/networks.txt
```

### 4. Stop Current Services

```bash
# Stop all running services
docker-compose down

# Verify all stopped
docker-compose ps
# Should show no running containers
```

---

## Migration Steps

### Step 1: Create Migration Branch

```bash
git checkout -b feature/docker-compose-consolidation
```

### Step 2: Move Old Files

```bash
# Rename existing compose files
mv docker-compose.yml docker-compose.yml.old
mv docker-compose.dev.yml docker-compose.dev.yml.old
mv docker-compose.betanet.yml docker-compose.betanet.yml.old

# Keep old files for reference during migration
```

### Step 3: Copy Proposed Files

```bash
# Copy new compose files from docs/architecture
cp docs/architecture/docker-compose.yml.proposed docker-compose.yml
cp docs/architecture/docker-compose.override.yml.proposed docker-compose.override.yml
cp docs/architecture/docker-compose.prod.yml.proposed docker-compose.prod.yml
cp docs/architecture/docker-compose.betanet.yml.proposed docker-compose.betanet.yml

# Copy environment template
cp docs/architecture/.env.example.proposed .env.example
```

### Step 4: Create Environment File

```bash
# Copy template to .env
cp .env.example .env

# Edit .env with your configuration
nano .env
# OR
code .env
```

**Required Changes in .env:**

```bash
# Generate strong passwords
POSTGRES_PASSWORD=$(openssl rand -hex 32)
REDIS_PASSWORD=$(openssl rand -hex 32)
GF_SECURITY_ADMIN_PASSWORD=$(openssl rand -hex 16)

# Set environment
ENVIRONMENT=development

# Verify database name matches your current setup
POSTGRES_DB=fog_compute_dev  # or fog_compute for production

# Check other settings match your needs
```

### Step 5: Update Monitoring Configuration

The new architecture uses a shared monitoring network. Update Prometheus configuration to scrape both fog-network and betanet services.

**Edit `monitoring/prometheus/prometheus.yml`:**

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  # Backend API metrics
  - job_name: 'backend'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: '/metrics'

  # PostgreSQL exporter (if added)
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres:9187']

  # Redis exporter (if added)
  - job_name: 'redis'
    static_configs:
      - targets: ['redis:9121']

  # Betanet mixnodes
  - job_name: 'betanet-mixnode-1'
    static_configs:
      - targets: ['betanet-mixnode-1:9091']
    metrics_path: '/metrics'

  - job_name: 'betanet-mixnode-2'
    static_configs:
      - targets: ['betanet-mixnode-2:9091']
    metrics_path: '/metrics'

  - job_name: 'betanet-mixnode-3'
    static_configs:
      - targets: ['betanet-mixnode-3:9091']
    metrics_path: '/metrics'

  # Node exporter (system metrics - production)
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']

  # cAdvisor (container metrics - production)
  - job_name: 'cadvisor'
    static_configs:
      - targets: ['cadvisor:8080']
```

**Update Grafana datasource `monitoring/grafana/datasources/prometheus.yml`:**

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
```

### Step 6: Create Production Secrets (If Deploying to Production)

```bash
# Create secrets directory
mkdir -p secrets
chmod 700 secrets

# Generate secrets
echo "$(openssl rand -hex 32)" > secrets/postgres_password.txt
echo "$(openssl rand -hex 32)" > secrets/grafana_password.txt
echo "$(openssl rand -hex 32)" > secrets/grafana_secret_key.txt

# Secure permissions
chmod 600 secrets/*.txt

# Add secrets to .gitignore
echo "secrets/" >> .gitignore
```

### Step 7: Validate Configuration

```bash
# Validate base configuration
docker-compose config

# Validate dev configuration (base + override)
docker-compose -f docker-compose.yml -f docker-compose.override.yml config

# Validate production configuration
docker-compose -f docker-compose.yml -f docker-compose.prod.yml config

# Validate betanet configuration
docker-compose -f docker-compose.yml -f docker-compose.betanet.yml config

# Check for errors - should output valid YAML
```

### Step 8: Create Monitoring Network

The new architecture requires a shared monitoring network.

```bash
# Create monitoring network manually (will be created automatically on first up, but explicit is better)
docker network create fog-compute_monitoring
```

### Step 9: Start Development Environment

```bash
# Start with dev overrides (automatic)
docker-compose up -d

# Verify all services are healthy
docker-compose ps

# Check logs for errors
docker-compose logs -f

# Wait for health checks to pass (30-60 seconds)
```

**Expected Services:**
- postgres (healthy)
- backend (healthy)
- frontend (healthy)
- redis (healthy)
- prometheus (healthy)
- grafana (healthy)
- loki (healthy)
- promtail (running)
- pgadmin (running - dev only)
- redis-commander (running - dev only)
- mailhog (running - dev only)

### Step 10: Restore Data (If Needed)

```bash
# Restore PostgreSQL backup
cat backup/volumes/postgres_backup_*.sql | docker-compose exec -T postgres psql -U fog_user -d fog_compute_dev

# Verify data restored
docker-compose exec postgres psql -U fog_user -d fog_compute_dev -c "\dt"
```

### Step 11: Test Development Environment

**Access Points:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Grafana: http://localhost:3001 (admin / password from .env)
- Prometheus: http://localhost:9090
- pgAdmin: http://localhost:5050
- Redis Commander: http://localhost:8081

**Test Checklist:**
- [ ] Frontend loads and displays dashboard
- [ ] Backend API responds to health check
- [ ] Database connection works (check API logs)
- [ ] Grafana dashboards show metrics
- [ ] Prometheus shows all targets as UP
- [ ] Hot-reload works (edit backend/frontend code)
- [ ] Logs appear in Loki (check Grafana Explore)

### Step 12: Test Betanet Environment (Optional)

```bash
# Stop development environment
docker-compose down

# Start with betanet
docker-compose -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.betanet.yml up -d

# Verify betanet nodes
docker-compose ps | grep betanet

# Check health
curl http://localhost:9001/health
curl http://localhost:9002/health
curl http://localhost:9003/health

# Verify Prometheus scrapes betanet
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job | contains("betanet"))'
```

**Expected Services:**
- All dev services from Step 9
- betanet-mixnode-1 (healthy)
- betanet-mixnode-2 (healthy)
- betanet-mixnode-3 (healthy)
- betanet-monitor (running)

### Step 13: Test Production Configuration (Staging)

**DO NOT RUN IN PRODUCTION YET - Test in staging environment first**

```bash
# Stop dev environment
docker-compose down

# Build production images
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build

# Start production environment
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Verify services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps

# Check logs
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f

# Access via nginx (port 80/443)
curl http://localhost/health
```

**Expected Differences from Dev:**
- ❌ No bind mounts (code in container, not hot-reload)
- ❌ No exposed database ports (security)
- ❌ No dev tools (pgadmin, redis-commander)
- ✅ Nginx reverse proxy (port 80/443)
- ✅ Resource limits enforced
- ✅ Secrets from files (not env vars)
- ✅ Production build (optimized)

---

## Post-Migration Tasks

### 1. Update CI/CD Pipelines

**GitHub Actions Example:**

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy-staging:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Deploy to staging
        run: |
          docker-compose -f docker-compose.yml -f docker-compose.prod.yml pull
          docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

  deploy-production:
    runs-on: ubuntu-latest
    environment: production
    needs: deploy-staging
    steps:
      - uses: actions/checkout@v3

      - name: Deploy to production
        run: |
          docker-compose -f docker-compose.yml -f docker-compose.prod.yml pull
          docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build --no-deps backend frontend
```

### 2. Update Documentation

**Files to update:**
- `README.md` - Update getting started instructions
- `CONTRIBUTING.md` - Update development setup
- `docs/DEPLOYMENT.md` - Update deployment procedures
- `docs/QUICK_REFERENCE.md` - Update Docker commands

### 3. Clean Up Old Files

**ONLY after successful migration and testing:**

```bash
# Remove old compose files
rm docker-compose.yml.old
rm docker-compose.dev.yml.old
rm docker-compose.betanet.yml.old

# Remove old volumes (if not needed)
docker volume rm fog-postgres_data  # old base volume
docker volume rm prometheus-data     # old betanet volume (hyphen)
docker volume rm grafana-data        # old betanet volume (hyphen)

# Clean up unused Docker resources
docker system prune -a --volumes
```

### 4. Commit Changes

```bash
# Stage new files
git add docker-compose.yml
git add docker-compose.override.yml
git add docker-compose.prod.yml
git add docker-compose.betanet.yml
git add .env.example
git add monitoring/
git add .gitignore

# Commit
git commit -m "feat: Consolidate Docker Compose configuration

- Eliminate duplicate Prometheus and Grafana services
- Resolve port conflicts (Prometheus 9090, Grafana 3000/3001)
- Implement 4-file architecture: base, override, prod, betanet
- Add production hardening with secrets and resource limits
- Create shared monitoring network for cross-stack observability
- Add development tools: pgAdmin, Redis Commander, Mailhog
- Improve DRY with YAML anchors and environment variables

BREAKING CHANGE: New file structure requires .env file creation
Migration guide: docs/architecture/MIGRATION_GUIDE.md"

# Push to remote
git push origin feature/docker-compose-consolidation
```

---

## Rollback Procedure

**If migration fails or issues are discovered:**

### Option 1: Rollback to Old Files

```bash
# Stop new environment
docker-compose down

# Restore old files
mv docker-compose.yml.old docker-compose.yml
mv docker-compose.dev.yml.old docker-compose.dev.yml
mv docker-compose.betanet.yml.old docker-compose.betanet.yml

# Restore data if needed
cat backup/volumes/postgres_backup_*.sql | docker-compose exec -T postgres psql -U fog_user -d fog_compute

# Start old environment
docker-compose up -d
```

### Option 2: Restore from Git

```bash
# Stop all services
docker-compose down

# Checkout backup branch
git checkout backup/pre-consolidation

# Start services
docker-compose up -d
```

### Option 3: Restore from Volume Backup

```bash
# List volume backups
ls -lh backup/volumes/

# Stop services
docker-compose down -v

# Restore PostgreSQL data
docker volume create postgres_data
docker run --rm -v postgres_data:/restore -v $(pwd)/backup/volumes:/backup alpine sh -c "cp -r /backup/postgres_data/* /restore/"

# Restart services
docker-compose up -d
```

---

## Troubleshooting

### Issue: Port Conflicts

**Error:** `bind: address already in use`

**Solution:**
```bash
# Find what's using the port
sudo lsof -i :9090  # or whichever port

# Stop conflicting service
docker-compose down

# Or change port in .env
echo "PROMETHEUS_PORT=9091" >> .env
```

### Issue: Network Not Found

**Error:** `network fog-compute_monitoring not found`

**Solution:**
```bash
# Create network manually
docker network create fog-compute_monitoring

# Or let docker-compose create it
docker-compose up -d
```

### Issue: Volume Permission Denied

**Error:** `Permission denied` when accessing volumes

**Solution:**
```bash
# Fix permissions (Linux)
sudo chown -R $USER:$USER ./backend ./apps ./monitoring

# Or run with correct user ID in Dockerfile
# USER 1000:1000
```

### Issue: Services Not Healthy

**Error:** Health check timeout

**Solution:**
```bash
# Check logs
docker-compose logs backend
docker-compose logs postgres

# Increase health check timeout in compose file
# healthcheck:
#   start_period: 60s

# Manually test health endpoint
docker-compose exec backend curl http://localhost:8000/health
```

### Issue: Grafana Can't Connect to Prometheus

**Error:** `Prometheus server is not reachable`

**Solution:**
```bash
# Verify Prometheus is up
docker-compose exec grafana ping prometheus

# Check datasource configuration
cat monitoring/grafana/datasources/prometheus.yml

# Verify both are on monitoring network
docker network inspect fog-compute_monitoring
```

### Issue: Betanet Nodes Can't Communicate

**Error:** Connection refused between mixnodes

**Solution:**
```bash
# Check betanet network
docker network inspect fog-compute_betanet

# Verify nodes are on same network
docker-compose -f docker-compose.yml -f docker-compose.betanet.yml ps

# Test connectivity
docker-compose exec betanet-mixnode-1 ping betanet-mixnode-2
docker-compose exec betanet-mixnode-1 curl http://betanet-mixnode-2:9002/health
```

---

## Validation Checklist

**Before considering migration complete:**

### Development Environment
- [ ] All services start without errors
- [ ] Health checks pass for all services
- [ ] Frontend accessible at http://localhost:3000
- [ ] Backend API accessible at http://localhost:8000
- [ ] Database connection works
- [ ] Hot-reload works for backend code changes
- [ ] Hot-reload works for frontend code changes
- [ ] Grafana shows metrics from all services
- [ ] Prometheus shows all targets as UP
- [ ] Logs appear in Loki/Grafana
- [ ] pgAdmin can connect to PostgreSQL
- [ ] Redis Commander shows Redis data

### Betanet Environment
- [ ] All 3 mixnodes start and are healthy
- [ ] Sequential startup works (1 -> 2 -> 3)
- [ ] Health checks pass for all mixnodes
- [ ] Nodes can communicate (1 -> 2 -> 3)
- [ ] Prometheus scrapes betanet metrics
- [ ] Grafana shows betanet dashboards
- [ ] No port conflicts with base services
- [ ] Betanet network isolated from fog-network
- [ ] Monitoring network bridges both networks

### Production Environment (Staging)
- [ ] All services build successfully
- [ ] No bind mounts present
- [ ] Secrets loaded from files
- [ ] Resource limits enforced
- [ ] Nginx reverse proxy works
- [ ] SSL/TLS configured (if applicable)
- [ ] No unnecessary ports exposed
- [ ] Logs are structured JSON
- [ ] Metrics collected properly
- [ ] Alerts configured (if using alertmanager)

### Documentation
- [ ] README.md updated
- [ ] DEPLOYMENT.md updated
- [ ] CI/CD pipelines updated
- [ ] .env.example complete and accurate
- [ ] Migration guide tested
- [ ] Rollback procedure tested

---

## Support

**Questions or issues during migration?**

1. Check troubleshooting section above
2. Review logs: `docker-compose logs -f`
3. Validate configuration: `docker-compose config`
4. Check GitHub issues: [fog-compute/issues](https://github.com/your-org/fog-compute/issues)
5. Contact DevOps team: devops@fogcompute.io

**Migration completed successfully?**

Please update the migration status in the project tracking system and notify the team.

---

**End of Migration Guide**
