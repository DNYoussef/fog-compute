# Deployment Scheduling Quick Start Guide

## Overview

The fog-compute deployment scheduler automatically allocates container deployments to available fog nodes using resource-based scheduling.

---

## Basic Usage

### 1. Deploy a Service

**Endpoint**: `POST /api/deployment/deploy`

**Authentication**: Required (JWT Bearer token)

**Request**:
```bash
curl -X POST http://localhost:8000/api/deployment/deploy \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "web-api",
    "type": "compute",
    "container_image": "nginx:latest",
    "replicas": 3,
    "resources": {
      "cpu": 2.0,
      "memory": 2048,
      "gpu": 0,
      "storage": 20
    },
    "region": "us-east"
  }'
```

**Response** (202 Accepted):
```json
{
  "success": true,
  "deployment_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "pending",
  "replicas": 3,
  "message": "Deployment queued for scheduling. Use /status/{deployment_id} to track progress."
}
```

### 2. Check Deployment Status

**Endpoint**: `GET /api/deployment/status/{deployment_id}`

**Request**:
```bash
curl -X GET http://localhost:8000/api/deployment/status/a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response**:
```json
{
  "deployment_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "name": "web-api",
  "status": "running",
  "health": "healthy",
  "target_replicas": 3,
  "replicas": [
    {
      "id": "replica-1-uuid",
      "node_id": "node-01-uuid",
      "status": "running",
      "container_id": "stub-container-xyz",
      "started_at": "2025-11-25T10:30:00Z"
    },
    {
      "id": "replica-2-uuid",
      "node_id": "node-02-uuid",
      "status": "running",
      "container_id": "stub-container-abc",
      "started_at": "2025-11-25T10:30:01Z"
    },
    {
      "id": "replica-3-uuid",
      "node_id": "node-03-uuid",
      "status": "running",
      "container_id": "stub-container-def",
      "started_at": "2025-11-25T10:30:02Z"
    }
  ],
  "resources": {
    "cpu_cores": 2.0,
    "memory_mb": 2048,
    "gpu_units": 0,
    "storage_gb": 20
  },
  "recent_status_changes": [
    {
      "old_status": "scheduled",
      "new_status": "running",
      "changed_at": "2025-11-25T10:30:02Z",
      "reason": "All 3 replicas started successfully"
    },
    {
      "old_status": "pending",
      "new_status": "scheduled",
      "changed_at": "2025-11-25T10:30:00Z",
      "reason": "Scheduled 3 replicas across nodes"
    },
    {
      "old_status": "none",
      "new_status": "pending",
      "changed_at": "2025-11-25T10:29:58Z",
      "reason": "Deployment created by user"
    }
  ],
  "created_at": "2025-11-25T10:29:58Z",
  "updated_at": "2025-11-25T10:30:02Z"
}
```

### 3. List Your Deployments

**Endpoint**: `GET /api/deployment/list`

**Request**:
```bash
curl -X GET http://localhost:8000/api/deployment/list?limit=10 \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response**:
```json
[
  {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "name": "web-api",
    "status": "running",
    "target_replicas": 3,
    "running_replicas": 3,
    "created_at": "2025-11-25T10:29:58Z",
    "updated_at": "2025-11-25T10:30:02Z"
  }
]
```

---

## Status Lifecycle

```
[PENDING] - Deployment created, queued for scheduling
    |
    v
[SCHEDULED] - Nodes selected, replicas allocated
    |
    v
[RUNNING] - All replicas started successfully

OR

[FAILED] - Scheduling failed (insufficient capacity, errors)
```

**Typical Timeline**:
- PENDING: 0-2 seconds (queue processing)
- SCHEDULED: 1-5 seconds (node selection, DB operations)
- RUNNING: 5-10 seconds (container orchestration)

**Total**: ~10-15 seconds from request to running

---

## Resource Requirements

### CPU Cores
- **Minimum**: 0.5 cores
- **Maximum**: 16 cores
- **Typical**: 1-4 cores per replica

### Memory
- **Minimum**: 512 MB
- **Maximum**: 16,384 MB (16 GB)
- **Typical**: 1024-4096 MB per replica

### GPU Units
- **Minimum**: 0 (optional)
- **Maximum**: 8 GPUs
- **Note**: Node must have `gpu_available = true`

### Storage
- **Minimum**: 1 GB
- **Maximum**: 1000 GB (1 TB)
- **Typical**: 10-50 GB per replica

---

## Service Types

- **compute**: General-purpose compute workloads (web servers, APIs, batch jobs)
- **storage**: Storage services (databases, file servers, caches)
- **gateway**: API gateways and load balancers
- **mixnode**: Privacy network nodes (handled by Betanet service)

---

## Scheduling Algorithm

### 1. Node Selection Criteria

Nodes are eligible if:
- Status is `idle` or `active` (not `busy`, `offline`, `maintenance`)
- CPU cores available >= required
- Memory available >= required
- Storage available >= required
- GPU available (if required)

### 2. Node Scoring (0.0 to 1.0)

```
total_score = (
    resource_availability * 0.4  # 40% weight
    + low_cpu_usage * 0.15       # 15% weight
    + low_memory_usage * 0.15    # 15% weight
    + network_locality * 0.3     # 30% weight (future)
)
```

**Higher score = Better candidate for deployment**

### 3. Replica Distribution

- Top N nodes are selected (N = target_replicas)
- Each replica gets its own node (no co-location)
- Scoring ensures balanced load distribution

---

## Examples

### Simple Web Server (1 replica)

```json
{
  "name": "nginx-server",
  "type": "compute",
  "container_image": "nginx:1.24",
  "replicas": 1,
  "resources": {
    "cpu": 1.0,
    "memory": 512,
    "gpu": 0,
    "storage": 5
  }
}
```

### High-Availability API (3 replicas)

```json
{
  "name": "api-service",
  "type": "compute",
  "container_image": "myapp:v2.1",
  "replicas": 3,
  "resources": {
    "cpu": 2.0,
    "memory": 2048,
    "gpu": 0,
    "storage": 10
  }
}
```

### GPU-Accelerated ML Service (2 replicas)

```json
{
  "name": "ml-inference",
  "type": "compute",
  "container_image": "tensorflow:latest-gpu",
  "replicas": 2,
  "resources": {
    "cpu": 4.0,
    "memory": 8192,
    "gpu": 1,
    "storage": 50
  }
}
```

### Storage Service (5 replicas)

```json
{
  "name": "distributed-storage",
  "type": "storage",
  "container_image": "ceph:latest",
  "replicas": 5,
  "resources": {
    "cpu": 2.0,
    "memory": 4096,
    "gpu": 0,
    "storage": 500
  }
}
```

---

## Error Handling

### Insufficient Capacity

**Scenario**: Not enough nodes with required resources

**Response**:
```json
{
  "success": false,
  "error": "Insufficient nodes: need 5, found 2 with capacity",
  "available_nodes": 2
}
```

**Status**: Deployment marked as `FAILED`

**Solution**:
- Reduce replica count
- Lower resource requirements
- Add more fog nodes to cluster
- Wait for existing deployments to complete

### Authentication Failure

**Scenario**: Missing or invalid JWT token

**Response** (401 Unauthorized):
```json
{
  "detail": "Not authenticated"
}
```

**Solution**: Login via `/api/auth/login` to get valid JWT token

### Invalid Service Type

**Scenario**: Unsupported service type

**Response** (400 Bad Request):
```json
{
  "detail": "Invalid type. Must be one of: ['compute', 'storage', 'gateway', 'mixnode']"
}
```

---

## Monitoring

### Logs

Check scheduler logs for debugging:

```bash
# View scheduler logs
docker logs fog-compute-backend | grep "Scheduling deployment"

# View successful scheduling
docker logs fog-compute-backend | grep "Successfully scheduled"

# View failures
docker logs fog-compute-backend | grep "Scheduling failed"
```

### Database Queries

```sql
-- View all deployments
SELECT id, name, status, target_replicas, created_at
FROM deployments
WHERE deleted_at IS NULL
ORDER BY created_at DESC;

-- View replica distribution
SELECT d.name, n.node_id, r.status
FROM deployments d
JOIN deployment_replicas r ON d.id = r.deployment_id
JOIN nodes n ON r.node_id = n.id
WHERE d.status = 'running';

-- View status history
SELECT d.name, h.old_status, h.new_status, h.changed_at, h.reason
FROM deployments d
JOIN deployment_status_history h ON d.id = h.deployment_id
ORDER BY h.changed_at DESC;
```

---

## Troubleshooting

### Deployment Stuck in PENDING

**Possible Causes**:
1. Scheduler background worker not running
2. Database connection issues
3. No available nodes

**Diagnosis**:
```bash
# Check scheduler status
curl http://localhost:8000/health

# Check logs
docker logs fog-compute-backend | grep "Scheduler worker"

# Check for errors
docker logs fog-compute-backend | grep ERROR
```

### Deployment Marked as FAILED

**Check status history for reason**:
```bash
curl -X GET http://localhost:8000/api/deployment/status/{deployment_id} \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Look at** `recent_status_changes[0].reason` for details

### Cannot Deploy GPU Workload

**Possible Causes**:
1. No nodes with `gpu_available = true`
2. All GPU nodes busy

**Solution**:
```sql
-- Check GPU node availability
SELECT node_id, status, gpu_available, cpu_usage_percent, memory_usage_percent
FROM nodes
WHERE gpu_available = true;
```

---

## Best Practices

### 1. Start Small

Test with 1 replica first, then scale up:

```bash
# Deploy 1 replica
POST /api/deployment/deploy
{
  "name": "test-service",
  "replicas": 1,
  ...
}

# Once verified, scale to 3
POST /api/deployment/scale/{deployment_id}
{
  "replicas": 3
}
```

### 2. Monitor Status Actively

Poll status endpoint every 2-5 seconds during deployment:

```bash
while true; do
  curl http://localhost:8000/api/deployment/status/{id} \
    -H "Authorization: Bearer $TOKEN" | jq '.status'
  sleep 2
done
```

### 3. Right-Size Resources

Don't over-allocate:
- Test locally to determine actual resource usage
- Start with minimum resources
- Monitor and adjust based on performance

### 4. Use Descriptive Names

```json
{
  "name": "web-api-v2.1-production",  // Good
  "name": "test123"                    // Bad
}
```

### 5. Check Capacity First

```bash
# Before large deployment, check node availability
curl http://localhost:8000/api/orchestration/services \
  -H "Authorization: Bearer $TOKEN"
```

---

## API Reference

### POST /api/deployment/deploy

**Headers**:
- `Authorization: Bearer <JWT_TOKEN>`
- `Content-Type: application/json`

**Body Parameters**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Deployment name (1-100 chars) |
| type | string | Yes | Service type (compute, storage, gateway, mixnode) |
| container_image | string | Yes | Container image (e.g., nginx:latest) |
| replicas | integer | Yes | Number of replicas (1-10) |
| resources | object | Yes | Resource allocation |
| resources.cpu | float | Yes | CPU cores (0.5-16.0) |
| resources.memory | integer | Yes | Memory MB (512-16384) |
| resources.gpu | integer | No | GPU units (0-8), default: 0 |
| resources.storage | integer | No | Storage GB (1-1000), default: 10 |
| env | object | No | Environment variables |
| region | string | No | Deployment region, default: "us-east" |

**Response Codes**:
- `202 Accepted`: Deployment queued successfully
- `400 Bad Request`: Invalid parameters
- `401 Unauthorized`: Authentication failed
- `500 Internal Server Error`: Server error

### GET /api/deployment/status/{deployment_id}

**Path Parameters**:
- `deployment_id` (UUID): Deployment identifier

**Query Parameters**: None

**Response**: See "Check Deployment Status" example above

### GET /api/deployment/list

**Query Parameters**:
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| status | string | None | Filter by status |
| name | string | None | Filter by name (partial match) |
| created_after | datetime | None | Filter by created_at >= date |
| created_before | datetime | None | Filter by created_at <= date |
| sort_by | string | created_at | Sort field (created_at, name, status) |
| sort_order | string | desc | Sort order (asc, desc) |
| limit | integer | 20 | Results per page (1-100) |
| offset | integer | 0 | Results to skip |

---

## Support

**Documentation**: `fog-compute/docs/FUNC-01-DEPLOYMENT-SCHEDULING-IMPLEMENTATION.md`

**Issues**: Check logs at `/var/log/fog-compute/` or Docker logs

**Debugging**: Enable verbose logging in `config.py`:
```python
logging.basicConfig(level=logging.DEBUG)
```
