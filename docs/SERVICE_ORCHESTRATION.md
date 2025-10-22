# Service Orchestration System

## Overview

The Enhanced Service Orchestration System provides comprehensive lifecycle management, health monitoring, and dependency resolution for all FOG Compute backend services.

## Architecture

### Components

1. **Enhanced Service Manager** (`enhanced_service_manager.py`)
   - Central orchestration hub
   - Lifecycle management (start, stop, restart)
   - Auto-restart with exponential backoff
   - Graceful shutdown with 30s timeout

2. **Dependency Graph** (`dependencies.py`)
   - Service dependency resolution
   - Topological sorting for startup order
   - Circular dependency detection
   - Layer-based service organization

3. **Health Check System** (`health_checks.py`)
   - Per-service health monitoring (30s interval)
   - Composite health status
   - Health history tracking (100 checks)
   - Failure detection and alerting

4. **Service Registry** (`registry.py`)
   - Service discovery
   - Metadata management
   - Heartbeat tracking (60s interval)
   - Service status tracking

5. **Orchestration API** (`routes/orchestration.py`)
   - REST endpoints for service management
   - Health check endpoints
   - Dependency visualization
   - Service metrics

## Service Dependency Graph

```
Service Dependency Graph:
==================================================

Layer 0 (Startup Priority):
  • dao

Layer 1 (Startup Priority):
  • edge [optional: dao]
  • scheduler [optional: dao]

Layer 2 (Startup Priority):
  • fog_coordinator
  • harvest <- edge

Layer 3 (Startup Priority):
  • onion <- fog_coordinator
  • p2p [optional: fog_coordinator]

Layer 4 (Startup Priority):
  • vpn_coordinator <- fog_coordinator, onion

Layer 5 (Startup Priority):
  • betanet [optional: onion, p2p]
  • bitchat [optional: p2p]
```

### Startup Order

Services start in dependency order:
1. **Layer 0**: DAO (tokenomics)
2. **Layer 1**: Scheduler, Edge Manager
3. **Layer 2**: FOG Coordinator, Harvest Manager
4. **Layer 3**: Onion Router, P2P System
5. **Layer 4**: VPN Coordinator
6. **Layer 5**: Betanet, BitChat

### Shutdown Order

Services shutdown in **reverse** dependency order (dependents before dependencies):
1. Betanet, BitChat
2. VPN Coordinator
3. Onion Router, P2P
4. FOG Coordinator, Harvest
5. Scheduler, Edge
6. DAO

## Health Check Configuration

### Per-Service Settings

```python
HealthCheckConfig(
    service_name="service_name",
    check_interval=30,        # Health check every 30 seconds
    timeout=5,                # 5 second timeout
    failure_threshold=3,      # 3 consecutive failures = unhealthy
    recovery_threshold=2,     # 2 consecutive successes = recovered
    auto_recovery=True        # Enable auto-restart
)
```

### Health Status Levels

- **HEALTHY**: Service operational, all checks passing
- **DEGRADED**: Service running but experiencing issues (1-2 failures)
- **UNHEALTHY**: Service failed (3+ consecutive failures)
- **UNKNOWN**: No health data available

### Composite Health

Overall system health determined by:
- **HEALTHY**: All services healthy
- **DEGRADED**: Some services degraded
- **UNHEALTHY**: Any service unhealthy
- **UNKNOWN**: No health data

## Auto-Restart Mechanism

### Configuration

- **Max Attempts**: 3 restart attempts
- **Backoff Strategy**: Exponential (base: 2.0)
- **Backoff Schedule**:
  - 1st restart: 2s delay
  - 2nd restart: 4s delay
  - 3rd restart: 8s delay

### Recovery Process

1. **Failure Detection**: Health check fails 3 times consecutively
2. **Initiate Restart**: Stop service gracefully
3. **Backoff Delay**: Wait exponential backoff time
4. **Restart Service**: Re-initialize service
5. **Track Attempt**: Increment restart counter
6. **Resume Monitoring**: Continue health checks

### Restart Limits

- Services exceeding 3 restart attempts marked as **FAILED**
- Manual restart with `force=true` required to override limit
- Restart counter resets on manual restart

## Graceful Shutdown

### Shutdown Process

1. **Signal Shutdown**: Set shutdown event
2. **Stop Health Monitoring**: Halt all health checks
3. **Shutdown Services**: Stop in reverse dependency order
4. **Timeout Handling**: 30s timeout per service
5. **Force Stop**: Kill unresponsive services
6. **Cleanup**: Clear service instances
7. **Stop Registry**: Halt heartbeat monitoring

### Shutdown Timeout

- **Per-Service**: 30 seconds for graceful shutdown
- **Force Kill**: After timeout, force stop service
- **Total Time**: ~5 minutes for all services (10 services × 30s)

## API Endpoints

### GET /api/orchestration/services

List all services with status.

**Response:**
```json
{
  "success": true,
  "total_services": 10,
  "services": {
    "dao": {
      "status": "running",
      "restart_count": 0,
      "last_restart": null,
      "last_error": null,
      "is_critical": true
    }
  },
  "is_ready": true,
  "initialized": true
}
```

### GET /api/orchestration/health

Get comprehensive health status.

**Response:**
```json
{
  "status": "ok",
  "composite_health": "healthy",
  "services": {
    "dao": {
      "status": "healthy",
      "last_check": {...},
      "consecutive_failures": 0,
      "uptime_1h": 99.5
    }
  },
  "unhealthy_services": [],
  "degraded_services": []
}
```

### POST /api/orchestration/restart/{service_name}

Restart a specific service.

**Request:**
```json
{
  "force": false
}
```

**Response:**
```json
{
  "success": true,
  "service": "betanet",
  "status": "running",
  "restart_count": 1,
  "last_restart": "2025-10-22T04:00:00Z",
  "message": "Service 'betanet' restarted successfully"
}
```

### GET /api/orchestration/dependencies

Get service dependency graph.

**Response:**
```json
{
  "success": true,
  "startup_order": ["dao", "scheduler", "edge", ...],
  "shutdown_order": ["bitchat", "betanet", ...],
  "dependencies": {
    "harvest": {
      "type": "harvest",
      "dependencies": ["edge"],
      "optional_dependencies": [],
      "dependents": [],
      "layer": 2
    }
  },
  "visualization": "Service Dependency Graph:\n..."
}
```

### GET /api/orchestration/metrics

Get service metrics.

**Response:**
```json
{
  "success": true,
  "metrics": {
    "total_services": 10,
    "running_services": 8,
    "failed_services": 0,
    "stopped_services": 2,
    "total_restarts": 3,
    "healthy_services": 8,
    "unhealthy_services": 0,
    "is_ready": true,
    "initialized": true
  },
  "registry_stats": {...},
  "service_details": {...}
}
```

### GET /api/orchestration/service/{service_name}

Get detailed service information.

**Response:**
```json
{
  "success": true,
  "service": "betanet",
  "status": "running",
  "restart_count": 0,
  "last_restart": null,
  "last_error": null,
  "is_critical": false,
  "dependencies": {
    "required": [],
    "optional": ["p2p", "onion"],
    "dependents": [],
    "layer": 5
  },
  "health_history": [...],
  "registry_metadata": {...}
}
```

### POST /api/orchestration/health/check-now

Force immediate health check on all services.

**Response:**
```json
{
  "success": true,
  "timestamp": "2025-10-22T04:00:00Z",
  "composite_health": "healthy",
  "results": {
    "dao": {
      "service_name": "dao",
      "status": "healthy",
      "timestamp": "2025-10-22T04:00:00Z",
      "message": "Service health check passed",
      "details": {...},
      "response_time_ms": 12.5
    }
  }
}
```

## Integration with Main Application

### main.py Lifespan Integration

```python
from backend.server.services.enhanced_service_manager import enhanced_service_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await enhanced_service_manager.initialize()

    yield

    # Shutdown
    await enhanced_service_manager.shutdown()
```

### Route Registration

```python
from backend.server.routes import orchestration

app.include_router(orchestration.router)
```

## Testing

### Test Coverage

- ✅ Dependency graph creation and validation
- ✅ Topological sorting
- ✅ Circular dependency detection
- ✅ Service layer calculation
- ✅ Health check on healthy/unhealthy services
- ✅ Health check timeout handling
- ✅ Failure threshold detection
- ✅ Health history tracking
- ✅ Service registry registration/deregistration
- ✅ Heartbeat tracking
- ✅ Service alive checking
- ✅ Registry statistics

### Running Tests

```bash
# Run all orchestration tests
pytest backend/tests/test_orchestration.py -v

# Run specific test
pytest backend/tests/test_orchestration.py::test_dependency_graph_topological_sort -v

# Run with coverage
pytest backend/tests/test_orchestration.py --cov=backend.server.services --cov-report=html
```

## Monitoring and Observability

### Health Check Metrics

- Response time per service (milliseconds)
- Consecutive failures/successes
- Uptime percentage (1h, 24h, 7d)
- Health check history (last 100 checks)

### Service Metrics

- Total restarts per service
- Last restart timestamp
- Service status distribution
- Registry heartbeat status
- Dependency resolution times

### Alerting

- Unhealthy service detection
- Degraded service warnings
- Restart attempt threshold alerts
- Heartbeat timeout notifications

## Best Practices

### Service Design

1. **Implement Health Checks**: Add `get_health()` or `is_healthy()` method
2. **Graceful Shutdown**: Implement `stop()` or `close()` method
3. **Minimal Dependencies**: Reduce required dependencies where possible
4. **Idempotent Initialization**: Support multiple initialization attempts

### Dependency Management

1. **Declare Dependencies**: Explicitly list all service dependencies
2. **Use Optional Dependencies**: Mark non-critical dependencies as optional
3. **Avoid Circular Dependencies**: Design services to prevent cycles
4. **Test Startup Order**: Validate dependency resolution

### Health Monitoring

1. **Quick Health Checks**: Keep health checks under 1 second
2. **Meaningful Status**: Return detailed health information
3. **Track Metrics**: Include performance metrics in health data
4. **Handle Failures**: Gracefully handle health check failures

## Troubleshooting

### Service Won't Start

1. Check dependencies are running
2. Review service logs for errors
3. Verify configuration is correct
4. Check resource availability (ports, files, etc.)

### Service Keeps Restarting

1. Review health check logs
2. Check for resource exhaustion
3. Verify external dependencies
4. Increase failure threshold if transient issues

### Shutdown Hangs

1. Check which service is timing out
2. Review service shutdown logic
3. Reduce shutdown timeout if needed
4. Force kill stuck services

### Health Checks Failing

1. Verify service is actually running
2. Check health check timeout
3. Review health check implementation
4. Monitor service logs during checks

## Future Enhancements

- [ ] Circuit breaker pattern for failing services
- [ ] Service versioning and blue-green deployments
- [ ] Dynamic dependency injection
- [ ] Service mesh integration
- [ ] Distributed health checks across nodes
- [ ] Advanced recovery strategies (backup services)
- [ ] Performance profiling integration
- [ ] Real-time dashboard for service status

## References

- [Service Lifecycle Pattern](https://microservices.io/patterns/service-registry.html)
- [Health Check API Pattern](https://microservices.io/patterns/observability/health-check-api.html)
- [Circuit Breaker Pattern](https://martinfowler.com/bliki/CircuitBreaker.html)
- [Dependency Injection](https://en.wikipedia.org/wiki/Dependency_injection)
