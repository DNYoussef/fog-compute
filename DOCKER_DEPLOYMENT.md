# Docker Deployment Guide

This guide explains how to deploy the Fog Compute platform using Docker Compose.

## Architecture

The fog-compute platform consists of the following services:

### Core Services
- **PostgreSQL** (port 5432) - Primary database for persistent storage
- **Backend API** (port 8000) - FastAPI server with all core services
  - Betanet privacy network service
  - Tokenomics and DAO system
  - Batch scheduler (NSGA-II)
  - Idle compute harvesting
  - VPN/Onion routing coordination
  - P2P mesh networking
- **Frontend** (port 3000) - Next.js control panel UI
- **Redis** (port 6379) - Caching layer (optional)

### Monitoring Stack
- **Prometheus** (port 9090) - Metrics collection
- **Grafana** (port 3001) - Visualization dashboards
- **Loki** (port 3100) - Log aggregation

## Quick Start

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+
- 4GB RAM minimum (8GB recommended)
- 10GB disk space

### Development Mode

```bash
# Start all services
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

# Start in background
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Stop all services
docker-compose down
```

### Production Mode

```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# Check health
docker-compose ps

# View logs
docker-compose logs -f
```

## Service Details

### PostgreSQL Database

**Connection Details:**
- Host: `postgres` (internal) / `localhost:5432` (external)
- Database: `fog_compute`
- User: `fog_user`
- Password: `fog_password` (change in production!)

**Migrations:**
```bash
# Run database migrations
docker-compose exec backend alembic upgrade head

# Create new migration
docker-compose exec backend alembic revision --autogenerate -m "description"
```

### Backend API

**Environment Variables:**
- `DATABASE_URL` - PostgreSQL connection string
- `API_HOST` - Server bind address (default: 0.0.0.0)
- `API_PORT` - Server port (default: 8000)
- `PYTHONPATH` - Python import path (default: /app)

**Health Check:**
```bash
curl http://localhost:8000/health
```

**API Documentation:**
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

**Key Endpoints:**
- `GET /api/betanet/status` - Betanet network status
- `POST /api/betanet/deploy` - Deploy new mixnode
- `GET /api/scheduler/stats` - Batch scheduler statistics
- `POST /api/scheduler/jobs` - Submit batch job
- `GET /api/tokenomics/balance?address=0x...` - Token balance

### Frontend Control Panel

**Environment Variables:**
- `NEXT_PUBLIC_API_URL` - Backend API URL
- `NODE_ENV` - Environment (development/production)

**Access:**
- Development: http://localhost:3000
- Production: http://localhost:3000

### Monitoring

**Prometheus:**
- URL: http://localhost:9090
- Scrapes backend metrics every 15s

**Grafana:**
- URL: http://localhost:3001
- Username: `admin`
- Password: `admin` (change on first login!)
- Pre-configured dashboards in `monitoring/grafana/dashboards/`

**Loki:**
- URL: http://localhost:3100
- Integrated with Grafana for log viewing

## Common Operations

### Reset Database

```bash
# Stop all services
docker-compose down

# Remove database volume
docker volume rm fog-compute_postgres_data

# Restart with fresh database
docker-compose up -d
```

### Scale Backend

```bash
# Run 3 backend instances (requires load balancer)
docker-compose up -d --scale backend=3
```

### View Service Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend

# Last 100 lines
docker-compose logs --tail=100 backend
```

### Rebuild After Code Changes

```bash
# Rebuild specific service
docker-compose build backend

# Rebuild all services
docker-compose build

# Force rebuild without cache
docker-compose build --no-cache
```

### Execute Commands in Containers

```bash
# Backend shell
docker-compose exec backend bash

# Run Python script
docker-compose exec backend python -m script_name

# Database shell
docker-compose exec postgres psql -U fog_user -d fog_compute

# Frontend shell
docker-compose exec frontend sh
```

## Troubleshooting

### Backend won't start

**Check logs:**
```bash
docker-compose logs backend
```

**Common issues:**
- Database not ready → Wait for PostgreSQL health check
- Missing dependencies → Rebuild image: `docker-compose build backend`
- Port conflict → Change port in `docker-compose.yml`

### Database connection errors

**Verify PostgreSQL is running:**
```bash
docker-compose ps postgres
docker-compose logs postgres
```

**Test connection:**
```bash
docker-compose exec postgres pg_isready -U fog_user
```

### Frontend build failures

**Clear Next.js cache:**
```bash
docker-compose down
docker volume rm fog-compute_control_panel_next
docker-compose up --build frontend
```

### Out of disk space

**Remove unused images and volumes:**
```bash
docker system prune -a --volumes
```

**Check disk usage:**
```bash
docker system df
```

## Performance Tuning

### PostgreSQL

Edit `docker-compose.yml` to add performance settings:

```yaml
postgres:
  environment:
    POSTGRES_SHARED_BUFFERS: 256MB
    POSTGRES_MAX_CONNECTIONS: 200
    POSTGRES_WORK_MEM: 4MB
```

### Backend

Adjust worker processes:

```yaml
backend:
  command: uvicorn server.main:app --workers 4 --host 0.0.0.0
```

## Security Considerations

### Production Checklist

- [ ] Change all default passwords
- [ ] Use secrets management (Docker secrets or environment files)
- [ ] Enable HTTPS/TLS on frontend and backend
- [ ] Configure firewall rules
- [ ] Set up regular database backups
- [ ] Enable authentication on Grafana
- [ ] Use read-only volumes where possible
- [ ] Run containers as non-root users (already configured)
- [ ] Keep images updated with security patches

### Environment Variables

Create `.env` file for sensitive data:

```bash
# .env
POSTGRES_PASSWORD=<strong-password>
SECRET_KEY=<random-key>
JWT_SECRET=<jwt-secret>
```

Reference in `docker-compose.yml`:

```yaml
services:
  postgres:
    env_file:
      - .env
```

## Backup and Restore

### Backup Database

```bash
# Create backup
docker-compose exec -T postgres pg_dump -U fog_user fog_compute > backup.sql

# With compression
docker-compose exec -T postgres pg_dump -U fog_user fog_compute | gzip > backup.sql.gz
```

### Restore Database

```bash
# Restore from backup
cat backup.sql | docker-compose exec -T postgres psql -U fog_user fog_compute

# From compressed backup
gunzip -c backup.sql.gz | docker-compose exec -T postgres psql -U fog_user fog_compute
```

## Development Workflow

1. **Make code changes** in `backend/` or `apps/control-panel/`
2. **Auto-reload triggers** (volume mounts enable hot reload)
3. **Test changes** at http://localhost:3000 or http://localhost:8000/docs
4. **View logs** with `docker-compose logs -f`
5. **Commit changes** when ready

## Production Deployment

For production, consider:

1. **Use managed database** (AWS RDS, Google Cloud SQL, etc.)
2. **Container orchestration** (Kubernetes, ECS, etc.)
3. **Load balancing** (Nginx, HAProxy, cloud load balancer)
4. **CDN** for frontend static assets
5. **Monitoring** (Datadog, New Relic, Sentry)
6. **Secrets management** (Vault, AWS Secrets Manager)
7. **CI/CD pipeline** (GitHub Actions, GitLab CI)

## Resources

- Docker Compose documentation: https://docs.docker.com/compose/
- FastAPI deployment: https://fastapi.tiangolo.com/deployment/
- Next.js deployment: https://nextjs.org/docs/deployment
- PostgreSQL Docker: https://hub.docker.com/_/postgres
