# FUNC-02 Testing Guide

Quick reference for testing the deployment scaling implementation.

---

## Prerequisites

1. **Apply Migration**:
   ```bash
   cd C:\Users\17175\Desktop\fog-compute\backend
   alembic upgrade head
   ```

2. **Start Backend**:
   ```bash
   cd C:\Users\17175\Desktop\fog-compute\backend
   uvicorn server.main:app --reload --port 8000
   ```

3. **Get JWT Token**:
   ```bash
   # Login to get token
   curl -X POST http://localhost:8000/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username": "testuser", "password": "password123"}'

   # Save token
   export TOKEN="<your_jwt_token>"
   ```

---

## Test 1: Create Deployment

```bash
curl -X POST http://localhost:8000/api/deployment/deploy \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test-scaling",
    "type": "compute",
    "container_image": "nginx:latest",
    "replicas": 3,
    "resources": {
      "cpu": 1.0,
      "memory": 1024,
      "gpu": 0,
      "storage": 10
    },
    "region": "us-east"
  }'
```

**Expected Response**:
```json
{
  "success": true,
  "deployment_id": "a1b2c3d4-...",
  "status": "pending",
  "replicas": 3,
  "message": "Deployment queued for scheduling..."
}
```

**Save Deployment ID**:
```bash
export DEPLOYMENT_ID="<deployment_id_from_response>"
```

---

## Test 2: Check Initial Status

```bash
curl http://localhost:8000/api/deployment/status/$DEPLOYMENT_ID \
  -H "Authorization: Bearer $TOKEN"
```

**Expected Response**:
```json
{
  "deployment_id": "a1b2c3d4-...",
  "name": "test-scaling",
  "status": "running",
  "health": "healthy",
  "target_replicas": 3,
  "replicas": [
    {"id": "...", "status": "running", "node_id": "..."},
    {"id": "...", "status": "running", "node_id": "..."},
    {"id": "...", "status": "running", "node_id": "..."}
  ],
  "resources": {
    "cpu_cores": 1.0,
    "memory_mb": 1024,
    "gpu_units": 0,
    "storage_gb": 10
  }
}
```

---

## Test 3: Scale Up (3 -> 5 replicas)

```bash
curl -X POST http://localhost:8000/api/deployment/scale/$DEPLOYMENT_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"replicas": 5}'
```

**Expected Response**:
```json
{
  "success": true,
  "deployment_id": "a1b2c3d4-...",
  "status": "running",
  "replicas": 5,
  "message": "Scaled up to 5 replicas (2 added)"
}
```

---

## Test 4: Verify Scale-Up

```bash
curl http://localhost:8000/api/deployment/status/$DEPLOYMENT_ID \
  -H "Authorization: Bearer $TOKEN"
```

**Expected**:
- `target_replicas`: 5
- `replicas` array: 5 items (3 old + 2 new)
- `recent_status_changes`: Should include scale-up entry with reason

---

## Test 5: Scale Down (5 -> 2 replicas)

```bash
curl -X POST http://localhost:8000/api/deployment/scale/$DEPLOYMENT_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"replicas": 2}'
```

**Expected Response**:
```json
{
  "success": true,
  "deployment_id": "a1b2c3d4-...",
  "status": "running",
  "replicas": 2,
  "message": "Scaled down to 2 replicas (3 removed)"
}
```

---

## Test 6: Verify Scale-Down

```bash
curl http://localhost:8000/api/deployment/status/$DEPLOYMENT_ID \
  -H "Authorization: Bearer $TOKEN"
```

**Expected**:
- `target_replicas`: 2
- `replicas` array: 5 items (2 running + 3 stopped)
- Running replicas: 2 (newest 2 from scale-up)
- Stopped replicas: 3 (oldest removed first)

---

## Test 7: Idempotent Scaling (2 -> 2)

```bash
curl -X POST http://localhost:8000/api/deployment/scale/$DEPLOYMENT_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"replicas": 2}'
```

**Expected Response**:
```json
{
  "success": true,
  "deployment_id": "a1b2c3d4-...",
  "status": "running",
  "replicas": 2,
  "message": "Deployment already at 2 replicas"
}
```

---

## Test 8: Invalid Replica Count

**Test Minimum Violation**:
```bash
curl -X POST http://localhost:8000/api/deployment/scale/$DEPLOYMENT_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"replicas": 0}'
```

**Expected**: 422 Validation Error

**Test Maximum Violation**:
```bash
curl -X POST http://localhost:8000/api/deployment/scale/$DEPLOYMENT_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"replicas": 101}'
```

**Expected**: 422 Validation Error

---

## Test 9: Insufficient Nodes (Scale to 100)

```bash
curl -X POST http://localhost:8000/api/deployment/scale/$DEPLOYMENT_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"replicas": 100}'
```

**Expected Response** (if insufficient nodes):
```json
{
  "detail": "Insufficient nodes for scale-up: need 98, found 10 with capacity"
}
```

**Status Code**: 503 Service Unavailable

---

## Test 10: Status History Verification

```bash
curl http://localhost:8000/api/deployment/status/$DEPLOYMENT_ID \
  -H "Authorization: Bearer $TOKEN" | jq '.recent_status_changes'
```

**Expected Output**:
```json
[
  {
    "old_status": "running",
    "new_status": "running",
    "changed_at": "2025-11-25T10:35:00Z",
    "reason": "Scaled down from 5 to 2 replicas (3 removed)"
  },
  {
    "old_status": "running",
    "new_status": "running",
    "changed_at": "2025-11-25T10:30:00Z",
    "reason": "Scaled up from 3 to 5 replicas (2 added)"
  },
  {
    "old_status": "scheduled",
    "new_status": "running",
    "changed_at": "2025-11-25T10:25:00Z",
    "reason": "All 3 replicas started successfully"
  }
]
```

---

## Test 11: Unauthorized Access

```bash
# Try to scale another user's deployment
curl -X POST http://localhost:8000/api/deployment/scale/<other_user_deployment_id> \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"replicas": 5}'
```

**Expected**: 404 Not Found (deployment not found or access denied)

---

## Database Verification

**Check Replicas**:
```sql
SELECT id, deployment_id, status, created_at, updated_at, stopped_at
FROM deployment_replicas
WHERE deployment_id = '<deployment_id>'
ORDER BY created_at ASC;
```

**Expected**:
- 5 replicas total
- 2 with status = 'running'
- 3 with status = 'stopped', stopped_at populated
- updated_at timestamps reflecting state changes

**Check Status History**:
```sql
SELECT old_status, new_status, reason, changed_at
FROM deployment_status_history
WHERE deployment_id = '<deployment_id>'
ORDER BY changed_at DESC;
```

**Expected**:
- Multiple entries with scaling reasons
- changed_by = authenticated user's ID

---

## Load Testing (Optional)

**Rapid Scale Operations**:
```bash
# Scale up and down rapidly
for i in {1..5}; do
  curl -X POST http://localhost:8000/api/deployment/scale/$DEPLOYMENT_ID \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"replicas\": $((3 + i))}"
  sleep 1
done
```

**Verify**:
- All status changes recorded
- No race conditions
- Database integrity maintained

---

## Cleanup

```bash
# Delete deployment
curl -X DELETE http://localhost:8000/api/deployment/$DEPLOYMENT_ID \
  -H "Authorization: Bearer $TOKEN"
```

---

## Common Issues

### Issue: Migration Not Applied
**Symptom**: Error: `column deployment_replicas.updated_at does not exist`
**Fix**:
```bash
cd backend
alembic upgrade head
```

### Issue: No Nodes Available
**Symptom**: 503 Insufficient nodes for scale-up
**Fix**: Check node availability:
```sql
SELECT node_id, status, cpu_cores, memory_mb
FROM nodes
WHERE status IN ('idle', 'active');
```

### Issue: Invalid Token
**Symptom**: 401 Unauthorized
**Fix**: Re-authenticate and get new JWT token

### Issue: Deployment Not Found
**Symptom**: 404 Deployment not found
**Fix**: Verify deployment_id is correct and belongs to authenticated user

---

## Success Criteria

All tests should pass with:
- Scale-up: Creates new replicas, updates target_replicas
- Scale-down: Stops oldest replicas, updates target_replicas
- Validation: Rejects invalid replica counts (0, 101)
- Idempotency: No-op when already at target
- Audit: All changes recorded in status history
- Authorization: Only owner can scale deployment
- Capacity: Returns 503 when insufficient nodes

---

## Next: FUNC-05

Once all tests pass, proceed to FUNC-05 (Health Checks & Status API) which will:
- Aggregate replica health status
- Compute deployment-level health (healthy/degraded/unhealthy)
- Expose health metrics API
