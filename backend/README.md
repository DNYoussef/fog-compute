# Fog Compute Backend API Server

FastAPI-based backend server that integrates all fog compute services and provides a unified REST API and WebSocket interface for the control panel frontend.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ Frontend (Next.js :3000)                                        │
│  └─ Fetches from /api/* routes                                 │
└─────────────────────────────────────────────────────────────────┘
           ↓ HTTP/WebSocket
┌─────────────────────────────────────────────────────────────────┐
│ Backend API Server (FastAPI :8000) ← THIS SERVER               │
│  ├─ REST API Endpoints                                         │
│  ├─ WebSocket Metrics Stream                                   │
│  ├─ Service Orchestration                                      │
│  └─ Database Connection                                        │
└─────────────────────────────────────────────────────────────────┘
           ↓ Direct imports & HTTP
┌─────────────────────────────────────────────────────────────────┐
│ Backend Services                                                │
│  ├─ Tokenomics (Python) - DAO, staking, rewards                │
│  ├─ Batch Scheduler (Python) - NSGA-II optimization            │
│  ├─ Idle Compute (Python) - Device harvesting                  │
│  ├─ VPN/Onion (Python) - Circuit management                    │
│  ├─ P2P System (Python) - Unified transport                    │
│  └─ Betanet (Rust :9000) - Privacy network (HTTP)              │
└─────────────────────────────────────────────────────────────────┘
           ↓ Persist to
┌─────────────────────────────────────────────────────────────────┐
│ PostgreSQL Database (:5432)                                     │
└─────────────────────────────────────────────────────────────────┘
```

## Features

✅ **Integrated Services**
- All Python services imported and initialized on startup
- Betanet Rust service accessed via HTTP client
- Graceful error handling when services unavailable

✅ **REST API**
- 14 real endpoints (replacing mock data)
- OpenAPI/Swagger documentation at `/docs`
- CORS enabled for frontend

✅ **WebSocket**
- Real-time metrics streaming
- 1Hz update rate
- Auto-reconnection support

✅ **Database Ready**
- PostgreSQL with SQLAlchemy
- Async database support
- Migration scripts ready

## API Endpoints

### Dashboard
- `GET /api/dashboard/stats` - Aggregated statistics from all services

### Betanet
- `GET /api/betanet/status` - Network status and mixnode metrics
- `POST /api/betanet/deploy` - Deploy new mixnode

### Tokenomics
- `GET /api/tokenomics/stats` - Token supply, staking, DAO metrics
- `GET /api/tokenomics/balance?address={addr}` - Get wallet balance
- `POST /api/tokenomics/stake` - Stake tokens
- `POST /api/tokenomics/unstake` - Unstake tokens
- `GET /api/tokenomics/proposals` - Get DAO proposals
- `POST /api/tokenomics/proposals` - Create proposal
- `POST /api/tokenomics/vote` - Vote on proposal
- `GET /api/tokenomics/rewards?address={addr}` - Get pending rewards

### Scheduler
- `GET /api/scheduler/stats` - Job queue and SLA metrics
- `GET /api/scheduler/jobs` - Get all jobs
- `POST /api/scheduler/jobs` - Submit new job
- `GET /api/scheduler/jobs/{id}` - Get job details
- `PATCH /api/scheduler/jobs/{id}` - Update job status
- `DELETE /api/scheduler/jobs/{id}` - Cancel job
- `GET /api/scheduler/nodes` - Get compute nodes

### Idle Compute
- `GET /api/idle-compute/stats` - Device harvesting metrics
- `GET /api/idle-compute/devices` - List all devices
- `POST /api/idle-compute/devices` - Register device
- `GET /api/idle-compute/devices/{id}` - Get device details
- `POST /api/idle-compute/devices/{id}/heartbeat` - Update heartbeat
- `DELETE /api/idle-compute/devices/{id}` - Unregister device

### Privacy/VPN
- `GET /api/privacy/stats` - Circuit and VPN metrics
- `GET /api/privacy/circuits` - List active circuits

### P2P
- `GET /api/p2p/stats` - P2P network metrics

### Benchmarks
- `GET /api/benchmarks/data` - Real-time benchmark data
- `POST /api/benchmarks/start` - Start benchmark test
- `POST /api/benchmarks/stop` - Stop benchmark

### WebSocket
- `WS /ws/metrics` - Real-time metrics stream

## Quick Start

### Option 1: Docker Compose (Recommended)

```bash
# Start all services (backend + postgres + frontend)
docker-compose up -d

# View logs
docker-compose logs -f backend

# Stop services
docker-compose down
```

### Option 2: Local Development

```bash
# 1. Install dependencies
cd backend
pip install -r requirements.txt

# 2. Set environment variables
export DATABASE_URL="postgresql+asyncpg://fog_user:fog_password@localhost:5432/fog_compute"
export BETANET_URL="http://localhost:9000"

# 3. Start PostgreSQL (if needed)
docker run -d \
  --name fog-postgres \
  -e POSTGRES_USER=fog_user \
  -e POSTGRES_PASSWORD=fog_password \
  -e POSTGRES_DB=fog_compute \
  -p 5432:5432 \
  postgres:15-alpine

# 4. Run the server
python -m uvicorn backend.server.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API**: http://localhost:8000
- **Swagger Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **WebSocket**: ws://localhost:8000/ws/metrics

## Configuration

Edit `backend/server/config.py` or use environment variables:

```bash
# API Server
API_HOST=0.0.0.0
API_PORT=8000

# Database
DATABASE_URL=postgresql+asyncpg://fog_user:fog_password@localhost:5432/fog_compute

# Betanet
BETANET_URL=http://localhost:9000

# CORS
CORS_ORIGINS=["http://localhost:3000"]
```

## Service Initialization

On startup, the server initializes all services:

1. ✅ Tokenomics DAO System
2. ✅ NSGA-II Batch Scheduler
3. ✅ Edge Manager & Harvest Manager
4. ✅ VPN/Onion Circuit Service
5. ✅ Unified P2P System
6. ✅ Betanet HTTP Client

If a service fails to initialize, the API will continue to run but that service's endpoints will return 503 (Service Unavailable).

## Development

### Adding a New Endpoint

1. Create route in `backend/server/routes/{service}.py`
2. Import service from `service_manager`
3. Add error handling
4. Include router in `main.py`

Example:
```python
from fastapi import APIRouter, HTTPException
from ..services.service_manager import service_manager

router = APIRouter(prefix="/api/myservice", tags=["myservice"])

@router.get("/stats")
async def get_stats():
    service = service_manager.get('myservice')
    if service is None:
        raise HTTPException(status_code=503, detail="Service unavailable")

    return service.get_stats()
```

### Testing WebSocket

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/metrics');

ws.onmessage = (event) => {
  const metrics = JSON.parse(event.data);
  console.log('Metrics:', metrics);
};
```

## Production Deployment

1. **Environment Variables**: Set production values
2. **Database**: Use managed PostgreSQL (AWS RDS, etc.)
3. **SSL/TLS**: Enable HTTPS
4. **Logging**: Configure production logging
5. **Monitoring**: Add Prometheus/Grafana
6. **Scaling**: Use multiple workers

```bash
# Production run with multiple workers
uvicorn backend.server.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --proxy-headers \
  --forwarded-allow-ips '*'
```

## Troubleshooting

### Service Unavailable Errors

If you get 503 errors, check which services failed to initialize:

```bash
# Check logs
docker-compose logs backend

# Check health endpoint
curl http://localhost:8000/health
```

### Database Connection Issues

```bash
# Test database connection
docker exec -it fog-postgres psql -U fog_user -d fog_compute

# Check if database is running
docker ps | grep postgres
```

### WebSocket Connection Refused

- Ensure backend is running
- Check CORS settings
- Verify WebSocket URL (ws:// not http://)

## Next Steps

- [ ] Add authentication (JWT)
- [ ] Implement database models
- [ ] Add caching layer (Redis)
- [ ] Create API rate limiting
- [ ] Add comprehensive logging
- [ ] Set up monitoring (Prometheus)
- [ ] Write integration tests
- [ ] Generate API client SDK

## License

See main repository LICENSE file.

---

**Generated with Claude Code**
**Co-Authored-By**: Claude <noreply@anthropic.com>
