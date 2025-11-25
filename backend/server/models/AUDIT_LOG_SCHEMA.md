# Audit Log Database Schema

## Overview

The audit log system provides immutable, comprehensive tracking of all security-relevant events in the fog-compute platform. This document describes the database schema, usage patterns, and operational considerations.

## Schema Design

### Table: `audit_logs`

**Key Characteristics:**
- **Immutable**: Append-only table enforced via PostgreSQL trigger
- **Indexed**: Optimized for common query patterns
- **Flexible**: JSONB metadata field for extensible context
- **Timezone-aware**: Timestamps stored with timezone information

### Columns

| Column | Type | Nullable | Indexed | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | No | Primary Key | Unique identifier for audit entry |
| `timestamp` | TIMESTAMP(TZ) | No | Yes | When the event occurred (UTC) |
| `user_id` | UUID | Yes | Yes | User who performed action (null for system/anonymous) |
| `action` | VARCHAR(100) | No | Yes | Action performed (login, deploy, delete, etc.) |
| `resource_type` | VARCHAR(100) | Yes | Compound | Type of resource affected (deployment, user, node, etc.) |
| `resource_id` | UUID | Yes | Compound | ID of resource affected |
| `ip_address` | VARCHAR(45) | No | No | Client IP address (IPv4 or IPv6) |
| `user_agent` | VARCHAR(500) | Yes | No | Client user agent string |
| `correlation_id` | UUID | Yes | Yes | Request correlation ID for distributed tracing |
| `request_method` | VARCHAR(10) | Yes | No | HTTP method (GET, POST, PUT, DELETE, PATCH) |
| `request_path` | VARCHAR(500) | Yes | No | HTTP request path |
| `response_status` | INTEGER | Yes | No | HTTP response status code |
| `duration_ms` | INTEGER | Yes | No | Request duration in milliseconds |
| `metadata` | JSONB | Yes | No | Flexible additional context |

### Indexes

**Single-column indexes:**
- `idx_audit_timestamp` - Time-range queries
- `idx_audit_user_id` - User activity tracking
- `idx_audit_action` - Action-specific queries
- `idx_audit_correlation` - Request tracing

**Compound indexes:**
- `idx_audit_resource` (resource_type, resource_id) - Resource audit trail
- `idx_audit_user_timestamp` (user_id, timestamp) - User activity over time
- `idx_audit_action_timestamp` (action, timestamp) - Action trends over time

## Immutability Protection

### Database Trigger

A PostgreSQL trigger prevents UPDATE and DELETE operations:

```sql
CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'audit_logs table is immutable: UPDATE operations are not allowed';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'audit_logs table is immutable: DELETE operations are not allowed';
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
```

**Result**: Any attempt to modify or delete audit logs will raise an exception:
```
ERROR: audit_logs table is immutable: UPDATE operations are not allowed
```

## Usage Examples

### Python Service (audit_service.py)

```python
from server.services.audit_service import log_audit_event
from uuid import UUID

# Log a user login
await log_audit_event(
    action="login",
    ip_address="192.168.1.100",
    user_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
    user_agent="Mozilla/5.0...",
    correlation_id=UUID("7a9e8b12-3c45-6d78-9e01-2f34567890ab"),
    request_method="POST",
    request_path="/api/auth/login",
    response_status=200,
    duration_ms=45,
    metadata={"event_type": "authentication"}
)

# Log a deployment action
await log_audit_event(
    action="deploy",
    ip_address="10.0.0.5",
    user_id=UUID("660e8400-e29b-41d4-a716-446655440001"),
    resource_type="deployment",
    resource_id=UUID("770e8400-e29b-41d4-a716-446655440002"),
    correlation_id=UUID("8a9e8b12-3c45-6d78-9e01-2f34567890ac"),
    request_method="POST",
    request_path="/api/deployments",
    response_status=201,
    duration_ms=1250,
    metadata={
        "deployment_name": "production-v2",
        "region": "us-west-2",
        "node_count": 5
    }
)

# Log a failed permission check
await log_audit_event(
    action="permission_denied",
    ip_address="203.0.113.42",
    user_id=UUID("880e8400-e29b-41d4-a716-446655440003"),
    resource_type="node",
    resource_id=UUID("990e8400-e29b-41d4-a716-446655440004"),
    correlation_id=UUID("9a9e8b12-3c45-6d78-9e01-2f34567890ad"),
    request_method="DELETE",
    request_path="/api/nodes/990e8400-e29b-41d4-a716-446655440004",
    response_status=403,
    duration_ms=12,
    metadata={"required_role": "admin", "user_role": "operator"}
)
```

### Automatic HTTP Request Logging (audit_middleware.py)

The middleware automatically logs all API requests:

```python
# Middleware configuration in main.py
from server.middleware.audit_middleware import AuditMiddleware

app.add_middleware(
    AuditMiddleware,
    excluded_paths=['/health', '/metrics', '/docs'],
    log_successful_reads=False  # Set to True to log all GET requests
)
```

**What gets logged automatically:**
- All POST, PUT, PATCH, DELETE requests
- Failed requests (4xx, 5xx)
- Authentication attempts
- Admin/audit endpoint access
- Optional: Successful GET requests

## Query Examples

### Find all actions by a specific user in the last 24 hours

```sql
SELECT
    timestamp, action, resource_type, request_path, response_status
FROM audit_logs
WHERE user_id = '550e8400-e29b-41d4-a716-446655440000'
  AND timestamp > NOW() - INTERVAL '24 hours'
ORDER BY timestamp DESC;
```

### Track all modifications to a specific resource

```sql
SELECT
    timestamp, user_id, action, request_method, response_status, metadata
FROM audit_logs
WHERE resource_type = 'deployment'
  AND resource_id = '770e8400-e29b-41d4-a716-446655440002'
ORDER BY timestamp DESC;
```

### Find failed authentication attempts

```sql
SELECT
    timestamp, ip_address, user_agent, metadata
FROM audit_logs
WHERE action IN ('login_failed', 'permission_denied')
  AND timestamp > NOW() - INTERVAL '1 hour'
ORDER BY timestamp DESC;
```

### Trace a request across services using correlation_id

```sql
SELECT
    timestamp, action, request_path, response_status, duration_ms
FROM audit_logs
WHERE correlation_id = '7a9e8b12-3c45-6d78-9e01-2f34567890ab'
ORDER BY timestamp ASC;
```

### Performance analysis - slow requests

```sql
SELECT
    action, request_method, request_path, AVG(duration_ms) as avg_ms, COUNT(*)
FROM audit_logs
WHERE duration_ms IS NOT NULL
  AND timestamp > NOW() - INTERVAL '1 day'
GROUP BY action, request_method, request_path
HAVING AVG(duration_ms) > 1000
ORDER BY avg_ms DESC;
```

## Metadata Field

The `metadata` JSONB field provides flexibility for additional context:

**Common metadata patterns:**

```json
{
  "event_type": "authentication",
  "session_id": "abc-123-def",
  "api_key_id": "550e8400-...",
  "old_value": {"status": "inactive"},
  "new_value": {"status": "active"},
  "error_message": "Connection timeout",
  "deployment_name": "prod-cluster",
  "node_count": 5,
  "region": "us-west-2"
}
```

**Querying JSONB:**

```sql
-- Find all events with specific error
SELECT * FROM audit_logs
WHERE metadata->>'error_message' LIKE '%timeout%';

-- Find deployments in specific region
SELECT * FROM audit_logs
WHERE resource_type = 'deployment'
  AND metadata->>'region' = 'us-west-2';
```

## Partitioning (Optional)

For large-scale deployments, enable time-based partitioning in the migration:

**Benefits:**
- Improved query performance on time-range queries
- Easier archival/deletion of old data
- Better index efficiency

**Trade-offs:**
- Additional complexity
- Requires monthly partition creation
- Only beneficial for >10M rows

**Enable in migration:** Uncomment the partitioning section in `003_create_audit_log_table.py`

## Data Retention

**Recommended retention policies:**

- **Active logs**: Last 90 days (hot storage, full indexes)
- **Archive logs**: 90 days - 7 years (cold storage, minimal indexes)
- **Compliance**: Retain based on regulatory requirements (GDPR, HIPAA, etc.)

**Archival strategy:**

```sql
-- Archive logs older than 90 days to separate table
CREATE TABLE audit_logs_archive (LIKE audit_logs INCLUDING ALL);

INSERT INTO audit_logs_archive
SELECT * FROM audit_logs
WHERE timestamp < NOW() - INTERVAL '90 days';

-- Note: Cannot delete from audit_logs due to immutability trigger
-- Instead, drop and recreate partitions (if using partitioning)
```

## Security Considerations

1. **Access Control**: Restrict SELECT permissions on `audit_logs` to security/audit roles only
2. **Backup**: Regular backups are critical (immutable means no recovery from accidental deletion)
3. **Encryption**: Enable PostgreSQL encryption-at-rest for sensitive audit data
4. **Network**: Isolate audit log access via VPN/private network
5. **Monitoring**: Alert on unauthorized access attempts to audit logs

## Migration

**Run migration:**

```bash
cd backend
alembic upgrade head
```

**Verify:**

```sql
-- Check table exists
\d audit_logs

-- Check trigger exists
\df prevent_audit_log_modification

-- Test immutability
INSERT INTO audit_logs (id, timestamp, action, ip_address)
VALUES (gen_random_uuid(), NOW(), 'test', '127.0.0.1');

-- This should fail:
UPDATE audit_logs SET action = 'modified' WHERE action = 'test';
-- Expected: ERROR: audit_logs table is immutable
```

## Performance Tuning

**For high-volume deployments (>1000 events/sec):**

1. **Batch writes**: Audit service already batches (default: 10 entries, 5s flush)
2. **Connection pooling**: Configure PostgreSQL connection pool (pgbouncer)
3. **Async writes**: Already implemented (non-blocking)
4. **Partitioning**: Enable time-based partitioning
5. **Index maintenance**: Run VACUUM ANALYZE regularly

**Monitor with:**

```sql
-- Check table size
SELECT pg_size_pretty(pg_total_relation_size('audit_logs'));

-- Check index usage
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE tablename = 'audit_logs'
ORDER BY idx_scan DESC;
```

## Compliance Mapping

| Requirement | Implementation |
|-------------|----------------|
| **GDPR Article 5(2)** (Accountability) | All data access logged with user_id |
| **SOC 2 CC6.1** (Logical Access) | Authentication attempts tracked |
| **HIPAA 164.312(b)** (Audit Controls) | Immutable audit trail with timestamps |
| **PCI DSS 10.2** (Audit Trails) | All user actions logged with IP |
| **ISO 27001 A.12.4.1** (Event Logging) | Comprehensive event taxonomy |

## Troubleshooting

**Issue: Migration fails with "table already exists"**
- Resolution: Check if audit_logs exists: `\d audit_logs`
- If exists but different schema: Drop table manually and re-run migration

**Issue: Trigger prevents legitimate maintenance**
- Resolution: Temporarily disable trigger:
  ```sql
  ALTER TABLE audit_logs DISABLE TRIGGER prevent_audit_modification;
  -- Perform maintenance
  ALTER TABLE audit_logs ENABLE TRIGGER prevent_audit_modification;
  ```

**Issue: High disk usage**
- Resolution: Enable partitioning and archive old partitions

**Issue: Slow queries**
- Resolution: Check index usage (`pg_stat_user_indexes`), add custom indexes if needed

## References

- **SQLAlchemy Model**: `backend/server/models/audit_log.py`
- **Service Layer**: `backend/server/services/audit_service.py`
- **Middleware**: `backend/server/middleware/audit_middleware.py`
- **Migration**: `backend/alembic/versions/003_create_audit_log_table.py`
