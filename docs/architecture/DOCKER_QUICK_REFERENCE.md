# Docker Compose - Quick Reference Card

**Version:** 2.0 (Consolidated Architecture)
**Last Updated:** 2025-10-21

---

## File Structure

```
docker-compose.yml              # Base (production defaults)
docker-compose.override.yml     # Development (auto-loaded)
docker-compose.prod.yml         # Production overrides
docker-compose.betanet.yml      # Betanet mixnet add-on
.env                            # Environment variables (gitignored)
.env.example                    # Template
```

---

## Common Commands

### Development (Default)

```bash
# Start dev environment
docker-compose up

# Start in background
docker-compose up -d

# Stop all services
docker-compose down

# View logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f backend

# Restart a service
docker-compose restart backend

# Rebuild and restart
docker-compose up -d --build backend

# Shell into a service
docker-compose exec backend bash
docker-compose exec postgres psql -U fog_user -d fog_compute_dev

# View running services
docker-compose ps

# View resource usage
docker stats
```

### Production

```bash
# Start production environment
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f

# Restart service (zero-downtime)
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-deps --build backend

# Stop production
docker-compose -f docker-compose.yml -f docker-compose.prod.yml down
```

### Betanet

```bash
# Start betanet only
docker-compose -f docker-compose.yml -f docker-compose.betanet.yml up

# Start betanet + development tools
docker-compose \
  -f docker-compose.yml \
  -f docker-compose.override.yml \
  -f docker-compose.betanet.yml \
  up -d

# View betanet logs
docker-compose -f docker-compose.yml -f docker-compose.betanet.yml logs -f betanet-mixnode-1

# Check betanet health
curl http://localhost:9001/health
curl http://localhost:9002/health
curl http://localhost:9003/health
```

### Database Operations

```bash
# Backup database
docker-compose exec postgres pg_dump -U fog_user fog_compute_dev > backup_$(date +%Y%m%d).sql

# Restore database
cat backup_20251021.sql | docker-compose exec -T postgres psql -U fog_user -d fog_compute_dev

# Access database shell
docker-compose exec postgres psql -U fog_user -d fog_compute_dev

# Reset database (DESTRUCTIVE)
docker-compose down -v
docker-compose up -d postgres
# Wait for postgres to be healthy, then run migrations
```

### Maintenance

```bash
# View all volumes
docker volume ls

# Remove unused volumes
docker volume prune

# Remove all stopped containers
docker container prune

# Remove unused images
docker image prune -a

# Full cleanup (CAREFUL)
docker system prune -a --volumes

# View disk usage
docker system df
```

---

## Service Endpoints

### Development

| Service | URL | Credentials |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | - |
| Backend API | http://localhost:8000 | - |
| API Docs | http://localhost:8000/docs | - |
| Grafana | http://localhost:3001 | admin / (see .env) |
| Prometheus | http://localhost:9090 | - |
| pgAdmin | http://localhost:5050 | (see .env) |
| Redis Commander | http://localhost:8081 | - |
| Mailhog | http://localhost:8025 | - |

### Betanet

| Service | URL | Purpose |
|---------|-----|---------|
| Mixnode 1 (Entry) | http://localhost:9001 | Entry node |
| Mixnode 2 (Middle) | http://localhost:9002 | Relay node |
| Mixnode 3 (Exit) | http://localhost:9003 | Exit node |
| Betanet Monitor | http://localhost:8080 | Status dashboard |

### Production

| Service | URL | Notes |
|---------|-----|-------|
| Frontend | https://fogcompute.io | Via nginx |
| Backend API | https://api.fogcompute.io | Via nginx |
| Grafana | https://grafana.fogcompute.io | Via nginx |

---

## Environment Variables

### Quick Setup

```bash
# Copy template
cp .env.example .env

# Edit configuration
nano .env

# Generate secure passwords
openssl rand -hex 32
```

### Essential Variables

```bash
# Database
POSTGRES_USER=fog_user
POSTGRES_PASSWORD=<strong-password>
POSTGRES_DB=fog_compute_dev

# Backend
LOG_LEVEL=DEBUG
API_PORT=8000

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000

# Monitoring
GF_SECURITY_ADMIN_PASSWORD=<admin-password>
```

See `.env.example` for complete list.

---

## Troubleshooting

### Port Already in Use

```bash
# Find process using port
sudo lsof -i :8000

# Kill process
kill -9 <PID>

# Or change port in .env
echo "BACKEND_PORT=8001" >> .env
```

### Service Won't Start

```bash
# Check logs
docker-compose logs backend

# Check health status
docker-compose ps

# Restart service
docker-compose restart backend

# Rebuild from scratch
docker-compose down
docker-compose build --no-cache backend
docker-compose up -d
```

### Database Connection Failed

```bash
# Check postgres is running
docker-compose ps postgres

# Check postgres logs
docker-compose logs postgres

# Test connection
docker-compose exec backend python -c "from server.models.database import engine; print(engine)"

# Verify DATABASE_URL
docker-compose exec backend env | grep DATABASE_URL
```

### Out of Disk Space

```bash
# Check disk usage
docker system df

# Clean up
docker system prune -a --volumes

# Remove specific volume
docker volume rm fog-compute_postgres_data
```

### Hot-Reload Not Working

```bash
# Check volume mounts
docker-compose config | grep volumes

# Restart with rebuild
docker-compose down
docker-compose up --build

# For Windows/Mac: Check Docker Desktop file sharing settings
```

---

## Networks

| Network | Purpose | Services |
|---------|---------|----------|
| `internal` | Internal communication only | postgres, backend, redis |
| `public` | External-facing services | backend, frontend, nginx |
| `monitoring` | Cross-stack observability | prometheus, grafana, loki, mixnodes |
| `betanet` | Mixnet routing (172.30.0.0/16) | betanet-mixnode-1/2/3 |

### Network Debugging

```bash
# List networks
docker network ls

# Inspect network
docker network inspect fog-compute_monitoring

# Test connectivity
docker-compose exec backend ping postgres
docker-compose exec betanet-mixnode-1 ping betanet-mixnode-2
```

---

## Volumes

| Volume | Purpose | Backup Priority |
|--------|---------|-----------------|
| `postgres_data` | Production database | HIGH |
| `postgres_dev_data` | Development database | MEDIUM |
| `grafana_data` | Dashboards and config | MEDIUM |
| `prometheus_data` | Metrics history | LOW |
| `redis_data` | Cache data | LOW |
| `betanet_*_data` | Mixnode state | MEDIUM |

### Volume Backup

```bash
# Backup volume
docker run --rm -v postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_data.tar.gz /data

# Restore volume
docker run --rm -v postgres_data:/data -v $(pwd):/backup alpine tar xzf /backup/postgres_data.tar.gz -C /
```

---

## Health Checks

### Check All Services

```bash
# View health status
docker-compose ps

# Test backend health
curl http://localhost:8000/health

# Test database health
docker-compose exec postgres pg_isready -U fog_user

# Test redis health
docker-compose exec redis redis-cli ping

# Test betanet health
curl http://localhost:9001/health
curl http://localhost:9002/health
curl http://localhost:9003/health
```

### Prometheus Targets

```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'

# Expected targets:
# - backend
# - betanet-mixnode-1
# - betanet-mixnode-2
# - betanet-mixnode-3
# - node-exporter (production)
# - cadvisor (production)
```

---

## Performance Tuning

### Resource Limits (Production)

Edit `docker-compose.prod.yml`:

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 4G
```

### Database Performance

```bash
# View active connections
docker-compose exec postgres psql -U fog_user -c "SELECT count(*) FROM pg_stat_activity;"

# View slow queries
docker-compose exec postgres psql -U fog_user -c "SELECT query, calls, total_time FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"

# Analyze table
docker-compose exec postgres psql -U fog_user -d fog_compute -c "ANALYZE VERBOSE;"
```

### Betanet Tuning

Edit `.env`:

```bash
# Increase throughput
PIPELINE_WORKERS=8
BATCH_SIZE=256
POOL_SIZE=2048
TARGET_THROUGHPUT=50000

# Restart betanet
docker-compose -f docker-compose.yml -f docker-compose.betanet.yml up -d --no-deps betanet-mixnode-1 betanet-mixnode-2 betanet-mixnode-3
```

---

## Security

### Production Secrets

```bash
# Create secrets directory
mkdir -p secrets
chmod 700 secrets

# Generate secrets
openssl rand -hex 32 > secrets/postgres_password.txt
openssl rand -hex 32 > secrets/grafana_password.txt
openssl rand -hex 32 > secrets/grafana_secret_key.txt

# Secure permissions
chmod 600 secrets/*.txt

# Deploy with secrets
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Network Security

```bash
# Verify internal network has no external access
docker network inspect fog-compute_internal | jq '.[0].Internal'
# Should be: true

# Check exposed ports
docker-compose ps
# Production: Only nginx ports 80/443 should be exposed
```

---

## Monitoring & Metrics

### Grafana Dashboards

1. **Overview Dashboard** - System health, request rates, error rates
2. **Betanet Performance** - Throughput, latency, packet processing
3. **Betanet Security** - VRF delays, relay selection, cover traffic

### Prometheus Queries

```promql
# Request rate
rate(http_requests_total[5m])

# Error rate
rate(http_requests_total{status=~"5.."}[5m])

# Betanet throughput
rate(betanet_packets_processed_total[5m])

# Database connections
pg_stat_database_numbackends
```

### Logs

```bash
# Grafana Loki (via Grafana UI)
http://localhost:3001/explore

# Or raw Loki API
curl -G -s "http://localhost:3100/loki/api/v1/query_range" \
  --data-urlencode 'query={container_name="fog-backend"}' | jq
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Deploy to production
        run: |
          docker-compose -f docker-compose.yml -f docker-compose.prod.yml pull
          docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

---

## Support

**Documentation:**
- Full Analysis: `docs/architecture/DOCKER_CONSOLIDATION_ANALYSIS.md`
- Migration Guide: `docs/architecture/MIGRATION_GUIDE.md`
- Summary: `docs/architecture/CONSOLIDATION_SUMMARY.md`

**Contacts:**
- DevOps Team: devops@fogcompute.io
- GitHub Issues: https://github.com/your-org/fog-compute/issues

---

## Cheat Sheet

```bash
# Development
docker-compose up                                    # Start dev
docker-compose logs -f backend                       # View logs
docker-compose restart backend                       # Restart service

# Production
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Betanet
docker-compose -f docker-compose.yml -f docker-compose.betanet.yml up

# Database
docker-compose exec postgres psql -U fog_user       # Access DB
docker-compose exec postgres pg_dump ... > backup   # Backup

# Cleanup
docker-compose down                                  # Stop all
docker-compose down -v                              # Stop + remove volumes
docker system prune -a --volumes                    # Full cleanup

# Debugging
docker-compose config                               # Validate config
docker-compose ps                                   # View status
docker-compose logs -f                              # View all logs
docker stats                                        # View resources
```

---

**Quick Reference Version:** 2.0
**Last Updated:** 2025-10-21
