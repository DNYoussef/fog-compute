# FUNC-09: Daily Limit Tracking - Implementation Complete

## Overview

Comprehensive daily usage tracking system for the fog-compute platform with tier-based limits, automatic daily resets at midnight UTC, and enforcement middleware.

**Status**: COMPLETE
**Date**: 2025-11-25
**Wave**: Wave 5 (Tokenomics & Reputation)

---

## Architecture

### Components Created

1. **Database Models** (`backend/server/models/usage.py`)
   - `DailyUsage`: Tracks per-user daily consumption
   - `UsageLimit`: Defines tier-based limits

2. **Migration** (`backend/alembic/versions/006_create_usage_tracking_tables.py`)
   - Creates `daily_usage` table
   - Creates `usage_limits` table
   - Adds `tier` column to `users` table
   - Seeds default limits for free/pro/enterprise tiers

3. **Usage Tracking Service** (`backend/server/services/usage_tracking.py`)
   - Core business logic for tracking and enforcement
   - Limit checking with tier awareness
   - Usage status queries
   - Historical record management

4. **Usage Scheduler** (`backend/server/services/usage_scheduler.py`)
   - Daily reset at midnight UTC
   - Automatic retry on failure
   - Manual reset support for admins

5. **Middleware/Decorator** (`backend/server/middleware/usage_limiter.py`)
   - `@require_usage_limit()` decorator for automatic enforcement
   - Dependency injection support
   - Manual increment helpers

6. **API Router** (`backend/server/routes/usage.py`)
   - Usage status endpoint
   - Limit checking endpoint
   - Tier limits queries
   - Admin manual reset

---

## Database Schema

### daily_usage Table

```sql
CREATE TABLE daily_usage (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    date DATE NOT NULL,
    deployments_created INT DEFAULT 0,
    api_calls INT DEFAULT 0,
    compute_hours DECIMAL(10,2) DEFAULT 0.0,
    storage_gb_hours DECIMAL(10,2) DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, date)
);

CREATE INDEX ix_daily_usage_user_id ON daily_usage(user_id);
CREATE INDEX ix_daily_usage_date ON daily_usage(date);
```

### usage_limits Table

```sql
CREATE TABLE usage_limits (
    id UUID PRIMARY KEY,
    tier VARCHAR(50) NOT NULL UNIQUE,
    max_deployments_per_day INT,
    max_api_calls_per_day INT,
    max_compute_hours_per_day DECIMAL(10,2),
    max_storage_gb INT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX ix_usage_limits_tier ON usage_limits(tier);
```

### users Table (Updated)

```sql
ALTER TABLE users ADD COLUMN tier VARCHAR(50) DEFAULT 'free' NOT NULL;
CREATE INDEX ix_users_tier ON users(tier);
```

---

## Default Tier Limits

| Tier | Deployments/Day | API Calls/Day | Compute Hours/Day | Storage GB |
|------|----------------|---------------|-------------------|------------|
| **free** | 10 | 5,000 | 10.0 | 5 |
| **pro** | 50 | 50,000 | 100.0 | 50 |
| **enterprise** | Unlimited | Unlimited | Unlimited | Unlimited |

---

## API Endpoints

### GET /api/usage/status

Get current usage status for authenticated user.

**Authentication**: Required (JWT or API Key)

**Response**:
```json
{
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "date": "2025-11-25",
  "tier": "free",
  "usage": {
    "deployments_created": 5,
    "api_calls": 1000,
    "compute_hours": 2.5,
    "storage_gb_hours": 1.2
  },
  "limits": {
    "max_deployments": 10,
    "max_api_calls": 5000,
    "max_compute_hours": 10.0,
    "max_storage_gb": 5
  },
  "remaining": {
    "deployments": 5,
    "api_calls": 4000,
    "compute_hours": 7.5,
    "storage_gb": 3.8
  }
}
```

### POST /api/usage/check-limit

Check if action is allowed without incrementing counter.

**Authentication**: Required

**Request**:
```json
{
  "metric": "deployments",
  "amount": 1.0
}
```

**Response**:
```json
{
  "allowed": true,
  "reason": null,
  "current": 5,
  "limit": 10,
  "remaining": 5
}
```

### GET /api/usage/limits/{tier}

Get limits for specific tier (free, pro, enterprise).

**Response**:
```json
{
  "tier": "free",
  "max_deployments_per_day": 10,
  "max_api_calls_per_day": 5000,
  "max_compute_hours_per_day": 10.0,
  "max_storage_gb": 5
}
```

### GET /api/usage/all-limits

Get limits for all tiers.

**Response**:
```json
{
  "free": {
    "max_deployments_per_day": 10,
    "max_api_calls_per_day": 5000,
    "max_compute_hours_per_day": 10.0,
    "max_storage_gb": 5
  },
  "pro": {
    "max_deployments_per_day": 50,
    "max_api_calls_per_day": 50000,
    "max_compute_hours_per_day": 100.0,
    "max_storage_gb": 50
  },
  "enterprise": {
    "max_deployments_per_day": null,
    "max_api_calls_per_day": null,
    "max_compute_hours_per_day": null,
    "max_storage_gb": null
  }
}
```

### POST /api/usage/admin/manual-reset

Manually trigger usage reset (admin only).

**Authentication**: Required (Admin)

**Response**:
```json
{
  "success": true,
  "records_processed": 42,
  "timestamp": "2025-11-25T00:00:00Z"
}
```

### GET /api/usage/scheduler/status

Get usage scheduler status.

**Response**:
```json
{
  "running": true,
  "next_reset": "2025-11-26T00:00:00Z",
  "current_time": "2025-11-25T14:30:00Z"
}
```

---

## Usage Examples

### 1. Using the Decorator (Automatic Enforcement)

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..auth.dependencies import get_current_user
from ..models.database import User
from ..middleware.usage_limiter import require_usage_limit

router = APIRouter()

@router.post("/deploy")
@require_usage_limit("deployments", 1.0, auto_increment=True)
async def deploy_app(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Limit checked and incremented automatically
    # If limit exceeded, 429 error raised before this code runs
    return {"message": "Deployment created"}
```

### 2. Using Manual Increment

```python
from ..services.usage_tracking import usage_tracking_service

@router.post("/api-call")
async def make_api_call(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Check limit first
    limit_check = await usage_tracking_service.check_limit(
        db, str(user.id), "api_calls", 1.0
    )

    if not limit_check['allowed']:
        raise HTTPException(429, detail="API call limit exceeded")

    # Perform operation
    result = perform_operation()

    # Increment only on success
    await usage_tracking_service.increment_usage(
        db, str(user.id), "api_calls", 1.0
    )

    return result
```

### 3. Using Dependency (Check Without Increment)

```python
from ..middleware.usage_limiter import check_usage_limit_dependency

@router.post("/complex-operation")
async def complex_operation(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(check_usage_limit_dependency("compute_hours", 2.5))
):
    # Limit checked but NOT incremented
    # Manually increment based on actual usage
    actual_hours = perform_operation()

    await usage_tracking_service.increment_usage(
        db, str(user.id), "compute_hours", actual_hours
    )
```

---

## Daily Reset Mechanism

### Automatic Reset

- **Schedule**: Midnight UTC (00:00:00 UTC)
- **Behavior**: Does NOT delete records (historical data preserved)
- **Process**: New day = new records created on-demand
- **Logging**: Logs transition for monitoring

### How It Works

1. Scheduler calculates time until next midnight UTC
2. Sleeps until midnight
3. On midnight, calls `usage_tracking_service.reset_daily_usage()`
4. Service logs historical record count
5. Next day's records created on first usage

### Manual Reset

Admins can trigger reset manually via:
```bash
POST /api/usage/admin/manual-reset
```

---

## Error Handling

### Limit Exceeded (429)

```json
{
  "detail": {
    "error": "Usage limit exceeded",
    "message": "Daily deployments limit exceeded",
    "current": 10,
    "limit": 10,
    "tier": "free",
    "metric": "deployments"
  }
}
```

### Service Unavailable (503)

```json
{
  "detail": "Usage tracking service not available"
}
```

### Unauthorized (401)

```json
{
  "detail": "Authentication required for usage tracking"
}
```

---

## Integration Checklist

- [x] Database models created
- [x] Migration created and ready
- [x] Usage tracking service implemented
- [x] Daily reset scheduler implemented
- [x] Middleware/decorator for enforcement
- [x] API router with all endpoints
- [x] User model updated with tier field
- [x] Models exported in __init__.py
- [x] Service initialized in main.py startup
- [x] Scheduler started in main.py startup
- [x] Router registered in main.py
- [x] Root endpoint updated with usage URLs

---

## Testing Plan

### Unit Tests Needed

1. **Usage Tracking Service**
   - [ ] Test limit checking (within/over limit)
   - [ ] Test usage increment
   - [ ] Test tier-based limits
   - [ ] Test enterprise unlimited
   - [ ] Test daily reset logic

2. **Usage Scheduler**
   - [ ] Test midnight calculation
   - [ ] Test reset execution
   - [ ] Test retry on failure
   - [ ] Test manual reset

3. **Middleware**
   - [ ] Test decorator enforcement
   - [ ] Test auto-increment
   - [ ] Test 429 response
   - [ ] Test dependency injection

### Integration Tests Needed

1. **API Endpoints**
   - [ ] Test GET /api/usage/status
   - [ ] Test POST /api/usage/check-limit
   - [ ] Test GET /api/usage/limits/{tier}
   - [ ] Test POST /api/usage/admin/manual-reset

2. **End-to-End**
   - [ ] Test deployment creation with limits
   - [ ] Test API call tracking
   - [ ] Test midnight reset behavior
   - [ ] Test tier upgrade flow

---

## Deployment Steps

### 1. Run Migration

```bash
cd backend
alembic upgrade head
```

This will:
- Create `daily_usage` table
- Create `usage_limits` table
- Add `tier` column to `users` table
- Seed default tier limits

### 2. Restart Backend

```bash
cd backend
python -m server.main
```

Startup logs should show:
```
✅ Usage tracking service initialized successfully
✅ Usage scheduler started successfully
```

### 3. Verify Installation

```bash
# Check health endpoint
curl http://localhost:8000/health

# Check usage endpoints
curl http://localhost:8000/api/usage/all-limits

# Check scheduler status
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/usage/scheduler/status
```

---

## Monitoring

### Key Metrics

1. **Usage Tracking**
   - Daily usage records created
   - Limit violations (429 errors)
   - Manual resets triggered

2. **Scheduler Health**
   - Daily reset success/failure
   - Time drift (should reset at 00:00 UTC)
   - Retry attempts

3. **Performance**
   - Usage status query time
   - Limit check latency
   - Database query performance

### Logs to Monitor

```
Usage scheduler started - daily reset at midnight UTC
Next usage reset at 2025-11-26T00:00:00Z (in 9.5 hours)
Daily usage reset completed at 2025-11-26T00:00:00Z - 42 records from previous day now historical
Incremented deployments by 1.0 for user <uuid>
Usage limit exceeded for user <uuid>: Daily deployments limit exceeded
```

---

## Future Enhancements

### Potential Additions

1. **Advanced Limits**
   - Burst limits (requests per minute)
   - Rolling windows (last 24 hours)
   - Per-endpoint rate limits

2. **Analytics**
   - Usage trends dashboard
   - Tier upgrade recommendations
   - Anomaly detection

3. **Notifications**
   - Email alerts at 80% usage
   - Webhook for limit violations
   - Admin dashboard for monitoring

4. **Flexibility**
   - Custom limits per user
   - Temporary limit boosts
   - Scheduled limit changes

---

## Files Modified/Created

### Created
- `backend/server/models/usage.py`
- `backend/server/services/usage_tracking.py`
- `backend/server/services/usage_scheduler.py`
- `backend/server/middleware/usage_limiter.py`
- `backend/server/routes/usage.py`
- `backend/alembic/versions/006_create_usage_tracking_tables.py`
- `docs/FUNC-09-DAILY-LIMIT-TRACKING-IMPLEMENTATION.md`

### Modified
- `backend/server/models/__init__.py` (exported DailyUsage, UsageLimit)
- `backend/server/models/database.py` (added tier field to User)
- `backend/server/routes/__init__.py` (exported usage router)
- `backend/server/main.py` (integrated usage tracking)

---

## Summary

FUNC-09 is now fully implemented with:

- Database schema for tracking daily usage per user
- Tier-based limits (free/pro/enterprise)
- Automatic daily reset at midnight UTC
- Enforcement middleware with decorator support
- Comprehensive API endpoints for status/limits
- Full integration with authentication system
- Admin tools for manual reset

**Status**: READY FOR TESTING
**Next Steps**: Run migration, restart backend, verify with test suite
