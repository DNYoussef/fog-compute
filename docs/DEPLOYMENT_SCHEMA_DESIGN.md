# Deployment Database Schema Design

## Overview
This document describes the database schema for the fog-compute deployment system, supporting service orchestration, replica management, resource allocation, and status tracking.

## Schema Version
- **Migration**: `004_create_deployment_tables.py`
- **Revision ID**: `004_create_deployment`
- **Revises**: `003` (audit_logs)
- **Created**: 2025-11-25

---

## Table Structures

### 1. `deployments`
Main deployment records tracking service lifecycle.

**Columns:**
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique deployment identifier |
| `name` | VARCHAR(100) | NOT NULL | Deployment name (unique per user) |
| `user_id` | UUID | NOT NULL, FK(users.id) | Owner user ID |
| `container_image` | VARCHAR(500) | NOT NULL | Container image (e.g., nginx:latest) |
| `status` | ENUM | NOT NULL, DEFAULT 'pending' | Deployment status |
| `target_replicas` | INTEGER | NOT NULL, DEFAULT 1 | Desired replica count |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT now() | Creation timestamp |
| `updated_at` | TIMESTAMP | NOT NULL, DEFAULT now() | Last update timestamp |
| `deleted_at` | TIMESTAMP | NULL | Soft delete timestamp |

**Enums:**
- `status`: `pending`, `scheduled`, `running`, `stopped`, `failed`, `deleted`

**Indexes:**
- `idx_deployments_user_active`: Compound index on `(user_id, deleted_at)` for active deployments
- `idx_deployments_user_name_unique`: Unique index on `(user_id, name)` WHERE `deleted_at IS NULL`
- Index on `user_id`
- Index on `status`
- Index on `deleted_at`

**Relationships:**
- `user_id` -> `users.id` (CASCADE DELETE)
- One-to-many: `deployment_replicas`
- One-to-one: `deployment_resources`
- One-to-many: `deployment_status_history`

---

### 2. `deployment_replicas`
Individual replica instances for each deployment.

**Columns:**
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique replica identifier |
| `deployment_id` | UUID | NOT NULL, FK(deployments.id) | Parent deployment |
| `node_id` | UUID | NULL, FK(nodes.id) | Assigned fog node |
| `status` | ENUM | NOT NULL, DEFAULT 'pending' | Replica status |
| `container_id` | VARCHAR(255) | NULL | Docker/runtime container ID |
| `started_at` | TIMESTAMP | NULL | Replica start time |
| `stopped_at` | TIMESTAMP | NULL | Replica stop time |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT now() | Creation timestamp |

**Enums:**
- `status`: `pending`, `starting`, `running`, `stopping`, `stopped`, `failed`

**Indexes:**
- `idx_replicas_deployment_status`: Compound index on `(deployment_id, status)`
- Index on `deployment_id`
- Index on `node_id`
- Index on `status`

**Relationships:**
- `deployment_id` -> `deployments.id` (CASCADE DELETE)
- `node_id` -> `nodes.id` (SET NULL)

---

### 3. `deployment_resources`
Resource allocations for each deployment (one-to-one with deployments).

**Columns:**
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique resource record ID |
| `deployment_id` | UUID | NOT NULL, UNIQUE, FK(deployments.id) | Parent deployment |
| `cpu_cores` | FLOAT | NOT NULL | CPU cores (fractional allowed) |
| `memory_mb` | INTEGER | NOT NULL | Memory in megabytes |
| `gpu_units` | INTEGER | NOT NULL, DEFAULT 0 | GPU units allocated |
| `storage_gb` | INTEGER | NOT NULL | Storage in gigabytes |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT now() | Creation timestamp |
| `updated_at` | TIMESTAMP | NOT NULL, DEFAULT now() | Last update timestamp |

**Indexes:**
- Unique index on `deployment_id`

**Relationships:**
- `deployment_id` -> `deployments.id` (CASCADE DELETE)

**Validation Rules:**
- `cpu_cores`: 0.5 - 32 cores
- `memory_mb`: 512 MB - 64 GB
- `gpu_units`: 0 - 8 units
- `storage_gb`: 1 GB - 1 TB

---

### 4. `deployment_status_history`
Audit trail for deployment status changes.

**Columns:**
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique history entry ID |
| `deployment_id` | UUID | NOT NULL, FK(deployments.id) | Parent deployment |
| `old_status` | VARCHAR(50) | NOT NULL | Previous status |
| `new_status` | VARCHAR(50) | NOT NULL | New status |
| `changed_by` | UUID | NULL, FK(users.id) | User who changed status |
| `changed_at` | TIMESTAMP | NOT NULL, DEFAULT now() | Change timestamp |
| `reason` | VARCHAR(500) | NULL | Optional reason for change |

**Indexes:**
- `idx_status_history_deployment_time`: Compound index on `(deployment_id, changed_at)`
- Index on `deployment_id`
- Index on `changed_by`
- Index on `changed_at`

**Relationships:**
- `deployment_id` -> `deployments.id` (CASCADE DELETE)
- `changed_by` -> `users.id` (SET NULL)

---

## Entity Relationships

```
users
  |
  +--(1:N)--> deployments
                 |
                 +--(1:N)--> deployment_replicas
                 |              |
                 |              +--(N:1)--> nodes
                 |
                 +--(1:1)--> deployment_resources
                 |
                 +--(1:N)--> deployment_status_history
                                |
                                +--(N:1)--> users (changed_by)
```

---

## Key Features

### 1. Soft Delete Support
- `deployments.deleted_at` enables soft deletes
- Deleted deployments remain in database for audit/recovery
- Unique constraint on `(user_id, name)` excludes soft-deleted records
- Queries should filter `WHERE deleted_at IS NULL` for active deployments

### 2. Status Tracking
- **Deployment Status**: Lifecycle from pending to running/stopped/failed
- **Replica Status**: Individual container states
- **Status History**: Complete audit trail of all status changes

### 3. Resource Management
- Fractional CPU cores (e.g., 0.5, 1.5) for flexible allocation
- Optional GPU support
- Separate resource table for clean separation of concerns

### 4. Replica Orchestration
- Multiple replicas per deployment
- Node assignment tracking
- Container ID mapping for runtime integration
- Start/stop timestamps for uptime calculations

### 5. Performance Optimizations
- Compound indexes for common query patterns:
  - User's active deployments
  - Deployment's replica status
  - Status history timeline
- Partial unique index for name uniqueness (excluding deleted)
- Foreign key indexes for efficient joins

---

## Data Access Patterns

### Common Queries

1. **List user's active deployments:**
```sql
SELECT * FROM deployments
WHERE user_id = ? AND deleted_at IS NULL
ORDER BY created_at DESC;
```

2. **Get deployment with replica count:**
```sql
SELECT d.*, COUNT(r.id) as replica_count
FROM deployments d
LEFT JOIN deployment_replicas r ON d.id = r.deployment_id
WHERE d.id = ? AND d.deleted_at IS NULL
GROUP BY d.id;
```

3. **Get running replicas for deployment:**
```sql
SELECT * FROM deployment_replicas
WHERE deployment_id = ? AND status = 'running';
```

4. **Get deployment status history:**
```sql
SELECT * FROM deployment_status_history
WHERE deployment_id = ?
ORDER BY changed_at DESC
LIMIT 50;
```

5. **Soft delete deployment:**
```sql
UPDATE deployments
SET deleted_at = NOW(), status = 'deleted'
WHERE id = ? AND user_id = ?;
```

---

## Migration Application

### Apply Migration
```bash
cd backend
alembic upgrade head
```

### Rollback Migration
```bash
alembic downgrade 002_advanced_bitchat
```

### Check Current Version
```bash
alembic current
```

---

## SQLAlchemy Models

**Location**: `backend/server/models/deployment.py`

**Classes**:
- `Deployment`: Main deployment model
- `DeploymentReplica`: Replica instances
- `DeploymentResource`: Resource allocations
- `DeploymentStatusHistory`: Status audit trail
- `DeploymentStatus`: Status enum
- `ReplicaStatus`: Replica status enum

**Key Methods**:
- `to_dict()`: Convert model to dictionary for API responses
- Relationships configured with `cascade="all, delete-orphan"`

---

## Pydantic Schemas

**Location**: `backend/server/schemas/deployment.py`

**Request Schemas**:
- `DeploymentCreate`: Create new deployment
- `DeploymentUpdate`: Update existing deployment
- `DeploymentScale`: Scale replica count
- `DeploymentResourceCreate`: Resource allocation

**Response Schemas**:
- `DeploymentResponse`: Full deployment details
- `DeploymentListResponse`: Summary for listings
- `DeploymentCreateResponse`: Creation confirmation
- `DeploymentOperationResponse`: Generic operation result
- `DeploymentReplicaResponse`: Replica details
- `DeploymentResourceResponse`: Resource details
- `DeploymentStatusHistoryResponse`: Status change entry

---

## Next Steps (Wave 3)

The following items are deferred to Wave 3:
1. Update deployment routes to use new database models
2. Implement deployment CRUD operations
3. Add replica scheduling logic
4. Integrate with fog node management
5. Add resource allocation validation
6. Implement status change tracking
7. Add deployment metrics collection

**Current Status**: Schema and models complete. Routes have TODO placeholders for database integration.

---

## Testing Considerations

### Unit Tests
- Model creation and validation
- Relationship cascade deletes
- Soft delete behavior
- Status enum transitions

### Integration Tests
- Full deployment lifecycle (create -> scale -> delete)
- Replica assignment to nodes
- Status history tracking
- Resource allocation updates

### Performance Tests
- Large-scale deployment listings
- Replica count aggregations
- Status history queries
- Index effectiveness

---

## Security Considerations

1. **User Isolation**: All deployments filtered by `user_id`
2. **Soft Delete**: Prevents accidental permanent data loss
3. **Audit Trail**: Complete status change history
4. **Cascading Deletes**: Proper cleanup of related records
5. **Foreign Key Constraints**: Data integrity enforcement

---

## File Summary

**Created Files**:
1. `backend/server/models/deployment.py` - SQLAlchemy models (202 lines)
2. `backend/server/schemas/deployment.py` - Pydantic schemas (169 lines)
3. `backend/alembic/versions/003_create_deployment_tables.py` - Database migration (153 lines)
4. `docs/DEPLOYMENT_SCHEMA_DESIGN.md` - This documentation

**Updated Files**:
1. `backend/server/models/__init__.py` - Added deployment model exports
2. `backend/server/schemas/__init__.py` - Added deployment schema exports

**Total Lines of Code**: 524 lines (models + schemas + migration)
