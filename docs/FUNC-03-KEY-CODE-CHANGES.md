# FUNC-03: Key Code Changes

## File: backend/server/routes/deployment.py

### 1. Import Updates (Line 16)

**Before:**
```python
from ..models.deployment import Deployment, DeploymentReplica, DeploymentResource, ReplicaStatus
```

**After:**
```python
from ..models.deployment import Deployment, DeploymentReplica, DeploymentResource, ReplicaStatus, DeploymentStatusHistory, DeploymentStatus as DeploymentStatusEnum
```

### 2. Function Signature (Lines 221-226)

**Before:**
```python
@router.get("/status/{deployment_id}", response_model=DeploymentStatus)
async def get_deployment_status(deployment_id: str) -> DeploymentStatus:
```

**After:**
```python
@router.get("/status/{deployment_id}")
async def get_deployment_status(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
```

### 3. Core Implementation (Lines 251-377)

**Before (Mock Response):**
```python
try:
    # TODO: Implement actual status lookup
    return DeploymentStatus(
        deployment_id=deployment_id,
        name=f"service-{deployment_id}",
        status="running",
        replicas=3,
        replicas_ready=3,
        resources=ResourceLimits(cpu=2, memory=4096),
        created_at=datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        updated_at=datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    )
except Exception as e:
    logger.error(f"Failed to get deployment status: {e}", exc_info=True)
    raise HTTPException(status_code=404, detail=f"Deployment {deployment_id} not found")
```

**After (Real Database Queries):**
```python
try:
    # Convert string to UUID for query
    try:
        from uuid import UUID
        deployment_uuid = UUID(deployment_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Invalid deployment ID format")

    # Query deployment with user_id check
    deployment_query = select(Deployment).where(
        and_(
            Deployment.id == deployment_uuid,
            Deployment.user_id == current_user.id,
            Deployment.deleted_at.is_(None)
        )
    )
    deployment_result = await db.execute(deployment_query)
    deployment = deployment_result.scalar_one_or_none()

    if not deployment:
        raise HTTPException(
            status_code=404,
            detail=f"Deployment {deployment_id} not found or access denied"
        )

    # Query all replicas for this deployment
    replicas_query = select(DeploymentReplica).where(
        DeploymentReplica.deployment_id == deployment_uuid
    )
    replicas_result = await db.execute(replicas_query)
    replicas = replicas_result.scalars().all()

    # Query resource allocation
    resources_query = select(DeploymentResource).where(
        DeploymentResource.deployment_id == deployment_uuid
    )
    resources_result = await db.execute(resources_query)
    resources = resources_result.scalar_one_or_none()

    # Query last 10 status changes
    history_query = select(DeploymentStatusHistory).where(
        DeploymentStatusHistory.deployment_id == deployment_uuid
    ).order_by(DeploymentStatusHistory.changed_at.desc()).limit(10)
    history_result = await db.execute(history_query)
    status_history = history_result.scalars().all()

    # Calculate health status based on replica health
    health_status = "healthy"
    if replicas:
        running_count = sum(1 for r in replicas if r.status == ReplicaStatus.RUNNING)
        failed_count = sum(1 for r in replicas if r.status == ReplicaStatus.FAILED)

        if failed_count > 0 or running_count < deployment.target_replicas:
            health_status = "degraded"
        if failed_count == len(replicas) or running_count == 0:
            health_status = "unhealthy"
    else:
        health_status = "unhealthy"

    # Build replica response
    replica_list = [
        {
            "id": str(replica.id),
            "node_id": str(replica.node_id) if replica.node_id else None,
            "status": replica.status.value if isinstance(replica.status, ReplicaStatus) else replica.status,
            "container_id": replica.container_id,
            "started_at": replica.started_at.isoformat() if replica.started_at else None,
            "stopped_at": replica.stopped_at.isoformat() if replica.stopped_at else None
        }
        for replica in replicas
    ]

    # Build resources response
    resources_dict = {
        "cpu_cores": resources.cpu_cores if resources else 0.0,
        "memory_mb": resources.memory_mb if resources else 0,
        "gpu_units": resources.gpu_units if resources else 0,
        "storage_gb": resources.storage_gb if resources else 0
    }

    # Build status history response
    history_list = [
        {
            "old_status": entry.old_status,
            "new_status": entry.new_status,
            "changed_at": entry.changed_at.isoformat() if entry.changed_at else None,
            "reason": entry.reason
        }
        for entry in status_history
    ]

    # Build comprehensive response
    response = {
        "deployment_id": str(deployment.id),
        "name": deployment.name,
        "status": deployment.status.value if isinstance(deployment.status, DeploymentStatusEnum) else deployment.status,
        "health": health_status,
        "target_replicas": deployment.target_replicas,
        "replicas": replica_list,
        "resources": resources_dict,
        "recent_status_changes": history_list,
        "created_at": deployment.created_at.isoformat() if deployment.created_at else None,
        "updated_at": deployment.updated_at.isoformat() if deployment.updated_at else None
    }

    logger.info(
        f"Retrieved deployment status for {deployment.name} (user: {current_user.username}): "
        f"status={deployment.status.value}, health={health_status}, "
        f"replicas={len(replicas)}/{deployment.target_replicas}"
    )

    return response

except HTTPException:
    raise
except Exception as e:
    logger.error(f"Failed to get deployment status: {e}", exc_info=True)
    raise HTTPException(
        status_code=500,
        detail=f"Failed to retrieve deployment status: {str(e)}"
    )
```

## Health Aggregation Logic

### Algorithm
```python
health_status = "healthy"  # Default

if replicas:
    running = count(replicas with status == RUNNING)
    failed = count(replicas with status == FAILED)

    # Degraded conditions
    if failed > 0 OR running < target_replicas:
        health_status = "degraded"

    # Unhealthy conditions (overrides degraded)
    if failed == total_replicas OR running == 0:
        health_status = "unhealthy"
else:
    health_status = "unhealthy"  # No replicas = unhealthy
```

### Health States

| Condition | Health Status |
|-----------|---------------|
| All target replicas running, no failures | `healthy` |
| Some replicas failed | `degraded` |
| Running < target replicas | `degraded` |
| All replicas failed | `unhealthy` |
| No running replicas | `unhealthy` |
| No replicas exist | `unhealthy` |

## Security Changes

### Authentication Added
- **JWT Required**: `get_current_active_user` dependency
- **User Isolation**: Query filters by `current_user.id`
- **Access Denied**: Returns 404 if deployment belongs to another user

### Query Filter
```python
and_(
    Deployment.id == deployment_uuid,
    Deployment.user_id == current_user.id,  # User isolation
    Deployment.deleted_at.is_(None)         # Soft delete protection
)
```

## Response Structure Changes

### Before (Mock)
```json
{
  "deployment_id": "string",
  "name": "string",
  "status": "string",
  "replicas": 3,
  "replicas_ready": 3,
  "resources": {"cpu": 2, "memory": 4096},
  "created_at": "string",
  "updated_at": "string"
}
```

### After (Real)
```json
{
  "deployment_id": "uuid",
  "name": "string",
  "status": "pending|scheduled|running|stopped|failed",
  "health": "healthy|degraded|unhealthy",  // NEW
  "target_replicas": 3,
  "replicas": [  // NEW: Full replica details
    {
      "id": "uuid",
      "node_id": "uuid",
      "status": "running",
      "container_id": "docker-id",
      "started_at": "timestamp",
      "stopped_at": null
    }
  ],
  "resources": {  // NEW: Full resource details
    "cpu_cores": 2.0,
    "memory_mb": 4096,
    "gpu_units": 0,
    "storage_gb": 50
  },
  "recent_status_changes": [  // NEW: Status history
    {
      "old_status": "pending",
      "new_status": "running",
      "changed_at": "timestamp",
      "reason": "All replicas started"
    }
  ],
  "created_at": "timestamp",
  "updated_at": "timestamp"
}
```

## Database Tables Used

1. **deployments**: Main deployment record
   - Fields: id, name, user_id, status, target_replicas, created_at, updated_at, deleted_at

2. **deployment_replicas**: Individual replica instances
   - Fields: id, deployment_id, node_id, status, container_id, started_at, stopped_at

3. **deployment_resources**: Resource allocation
   - Fields: id, deployment_id, cpu_cores, memory_mb, gpu_units, storage_gb

4. **deployment_status_history**: Status change audit trail
   - Fields: id, deployment_id, old_status, new_status, changed_at, reason

## Summary Statistics

- **Lines Changed**: ~160 lines
- **Database Queries Added**: 4 (deployment, replicas, resources, history)
- **Security Features**: 2 (JWT auth, user isolation)
- **Health States**: 3 (healthy, degraded, unhealthy)
- **Response Fields**: 10 top-level fields
- **Status History Limit**: 10 most recent changes
- **Import Updates**: 2 new imports (DeploymentStatusHistory, DeploymentStatus as enum)
