# Deployment Schema Quick Reference

## Quick Start

### Apply Migration
```bash
cd backend
alembic upgrade head
```

### Import Models
```python
from server.models import (
    Deployment,
    DeploymentReplica,
    DeploymentResource,
    DeploymentStatusHistory,
    DeploymentStatus,
    ReplicaStatus
)
```

### Import Schemas
```python
from server.schemas import (
    DeploymentCreate,
    DeploymentResponse,
    DeploymentScale,
    DeploymentStatusEnum
)
```

---

## Quick Examples

### Create Deployment
```python
from server.models import Deployment, DeploymentResource, DeploymentStatus
from server.database import get_db_context
import uuid

async def create_deployment(user_id: uuid.UUID, name: str, image: str):
    async with get_db_context() as db:
        # Create deployment
        deployment = Deployment(
            name=name,
            user_id=user_id,
            container_image=image,
            status=DeploymentStatus.PENDING,
            target_replicas=3
        )
        db.add(deployment)
        await db.flush()  # Get deployment.id

        # Create resource allocation
        resources = DeploymentResource(
            deployment_id=deployment.id,
            cpu_cores=2.0,
            memory_mb=4096,
            gpu_units=0,
            storage_gb=10
        )
        db.add(resources)
        await db.commit()
        await db.refresh(deployment)

        return deployment
```

### Query Active Deployments
```python
from sqlalchemy import select
from server.models import Deployment

async def get_user_deployments(user_id: uuid.UUID):
    async with get_db_context() as db:
        result = await db.execute(
            select(Deployment)
            .where(Deployment.user_id == user_id)
            .where(Deployment.deleted_at.is_(None))
            .order_by(Deployment.created_at.desc())
        )
        return result.scalars().all()
```

### Create Replica
```python
from server.models import DeploymentReplica, ReplicaStatus

async def create_replica(deployment_id: uuid.UUID, node_id: uuid.UUID):
    async with get_db_context() as db:
        replica = DeploymentReplica(
            deployment_id=deployment_id,
            node_id=node_id,
            status=ReplicaStatus.PENDING
        )
        db.add(replica)
        await db.commit()
        await db.refresh(replica)
        return replica
```

### Track Status Change
```python
from server.models import DeploymentStatusHistory

async def track_status_change(
    deployment_id: uuid.UUID,
    old_status: str,
    new_status: str,
    changed_by: uuid.UUID,
    reason: str = None
):
    async with get_db_context() as db:
        history = DeploymentStatusHistory(
            deployment_id=deployment_id,
            old_status=old_status,
            new_status=new_status,
            changed_by=changed_by,
            reason=reason
        )
        db.add(history)
        await db.commit()
```

### Soft Delete
```python
from datetime import datetime

async def soft_delete_deployment(deployment_id: uuid.UUID):
    async with get_db_context() as db:
        result = await db.execute(
            select(Deployment).where(Deployment.id == deployment_id)
        )
        deployment = result.scalar_one()
        deployment.deleted_at = datetime.utcnow()
        deployment.status = DeploymentStatus.DELETED
        await db.commit()
```

### Get Replica Count
```python
from sqlalchemy import func, select
from server.models import Deployment, DeploymentReplica, ReplicaStatus

async def get_deployment_with_counts(deployment_id: uuid.UUID):
    async with get_db_context() as db:
        # Query deployment with replica counts
        result = await db.execute(
            select(
                Deployment,
                func.count(DeploymentReplica.id).label('total_replicas'),
                func.sum(
                    func.cast(
                        DeploymentReplica.status == ReplicaStatus.RUNNING,
                        Integer
                    )
                ).label('running_replicas')
            )
            .outerjoin(DeploymentReplica, Deployment.id == DeploymentReplica.deployment_id)
            .where(Deployment.id == deployment_id)
            .group_by(Deployment.id)
        )
        return result.first()
```

---

## Table Reference

### deployments
```sql
CREATE TABLE deployments (
    id UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    container_image VARCHAR(500) NOT NULL,
    status deploymentstatus NOT NULL DEFAULT 'pending',
    target_replicas INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now(),
    deleted_at TIMESTAMP NULL
);
```

### deployment_replicas
```sql
CREATE TABLE deployment_replicas (
    id UUID PRIMARY KEY,
    deployment_id UUID NOT NULL REFERENCES deployments(id) ON DELETE CASCADE,
    node_id UUID NULL REFERENCES nodes(id) ON DELETE SET NULL,
    status replicastatus NOT NULL DEFAULT 'pending',
    container_id VARCHAR(255) NULL,
    started_at TIMESTAMP NULL,
    stopped_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);
```

### deployment_resources
```sql
CREATE TABLE deployment_resources (
    id UUID PRIMARY KEY,
    deployment_id UUID NOT NULL UNIQUE REFERENCES deployments(id) ON DELETE CASCADE,
    cpu_cores FLOAT NOT NULL,
    memory_mb INTEGER NOT NULL,
    gpu_units INTEGER NOT NULL DEFAULT 0,
    storage_gb INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);
```

### deployment_status_history
```sql
CREATE TABLE deployment_status_history (
    id UUID PRIMARY KEY,
    deployment_id UUID NOT NULL REFERENCES deployments(id) ON DELETE CASCADE,
    old_status VARCHAR(50) NOT NULL,
    new_status VARCHAR(50) NOT NULL,
    changed_by UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    changed_at TIMESTAMP NOT NULL DEFAULT now(),
    reason VARCHAR(500) NULL
);
```

---

## Status Enums

### DeploymentStatus
- `pending`: Initial state after creation
- `scheduled`: Resources allocated, awaiting deployment
- `running`: Active and serving traffic
- `stopped`: Intentionally stopped by user
- `failed`: Deployment failed (check logs)
- `deleted`: Soft deleted (deleted_at set)

### ReplicaStatus
- `pending`: Created but not yet started
- `starting`: Container initialization in progress
- `running`: Healthy and serving traffic
- `stopping`: Graceful shutdown in progress
- `stopped`: Fully stopped
- `failed`: Replica crashed or unhealthy

---

## Index Reference

| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| `idx_deployments_user_active` | `(user_id, deleted_at)` | Compound | List active deployments per user |
| `idx_deployments_user_name_unique` | `(user_id, name)` WHERE deleted_at IS NULL | Unique | Enforce unique names per user |
| `idx_replicas_deployment_status` | `(deployment_id, status)` | Compound | Count replicas by status |
| `idx_status_history_deployment_time` | `(deployment_id, changed_at)` | Compound | Status change timeline |

---

## Common Patterns

### Get Deployment with Full Details
```python
from sqlalchemy.orm import selectinload

result = await db.execute(
    select(Deployment)
    .options(
        selectinload(Deployment.replicas),
        selectinload(Deployment.resources),
        selectinload(Deployment.status_history)
    )
    .where(Deployment.id == deployment_id)
)
deployment = result.scalar_one()
```

### Scale Deployment
```python
async def scale_deployment(deployment_id: uuid.UUID, target_replicas: int):
    async with get_db_context() as db:
        # Update target
        result = await db.execute(
            select(Deployment).where(Deployment.id == deployment_id)
        )
        deployment = result.scalar_one()
        old_target = deployment.target_replicas
        deployment.target_replicas = target_replicas

        # Track change
        history = DeploymentStatusHistory(
            deployment_id=deployment_id,
            old_status=f"replicas:{old_target}",
            new_status=f"replicas:{target_replicas}",
            reason="User-initiated scaling"
        )
        db.add(history)
        await db.commit()
```

### Filter Active Replicas
```python
# Get only running replicas
result = await db.execute(
    select(DeploymentReplica)
    .where(DeploymentReplica.deployment_id == deployment_id)
    .where(DeploymentReplica.status == ReplicaStatus.RUNNING)
)
running_replicas = result.scalars().all()
```

---

## Migration Commands

```bash
# Apply all migrations
alembic upgrade head

# Rollback one version
alembic downgrade -1

# Rollback to specific version
alembic downgrade 002_advanced_bitchat

# Show current version
alembic current

# Show migration history
alembic history

# Show SQL without executing
alembic upgrade head --sql
```

---

## Files Created

1. **Models**: `backend/server/models/deployment.py`
2. **Schemas**: `backend/server/schemas/deployment.py`
3. **Migration**: `backend/alembic/versions/003_create_deployment_tables.py`
4. **Docs**:
   - `docs/DEPLOYMENT_SCHEMA_DESIGN.md` (detailed)
   - `docs/DEPLOYMENT_SCHEMA_QUICK_REFERENCE.md` (this file)

---

## Wave 3 Integration Points

When implementing deployment routes (Wave 3), integrate with:

1. **Create Endpoint** (`/api/deployment/deploy`):
   - Create `Deployment` record
   - Create `DeploymentResource` record
   - Create initial `DeploymentReplica` records
   - Track status change in `DeploymentStatusHistory`

2. **Scale Endpoint** (`/api/deployment/scale/{id}`):
   - Update `Deployment.target_replicas`
   - Add/remove `DeploymentReplica` records
   - Track scaling in `DeploymentStatusHistory`

3. **Status Endpoint** (`/api/deployment/status/{id}`):
   - Query `Deployment` with eager-loaded relationships
   - Count replicas by status
   - Return full details

4. **List Endpoint** (`/api/deployment/list`):
   - Query with `deleted_at IS NULL` filter
   - Join with `deployment_replicas` for counts
   - Paginate results

5. **Delete Endpoint** (`/api/deployment/{id}`):
   - Set `deleted_at = NOW()`
   - Set `status = 'deleted'`
   - Track in `DeploymentStatusHistory`

---

## Validation Rules (from Pydantic schemas)

- **name**: 1-100 chars, alphanumeric + hyphens/underscores
- **container_image**: 1-500 chars
- **target_replicas**: 1-100 replicas
- **cpu_cores**: 0.5-32 cores (fractional allowed)
- **memory_mb**: 512-65536 MB (0.5-64 GB)
- **gpu_units**: 0-8 units
- **storage_gb**: 1-1000 GB (1 GB - 1 TB)

---

## Testing Checklist

- [ ] Migration applies cleanly
- [ ] Migration rolls back cleanly
- [ ] Soft delete preserves data
- [ ] Unique constraint on (user_id, name) works
- [ ] Cascade deletes work correctly
- [ ] Status enums validate properly
- [ ] Pydantic schemas validate input
- [ ] Relationships load correctly
- [ ] Indexes improve query performance
- [ ] Foreign keys enforce referential integrity
