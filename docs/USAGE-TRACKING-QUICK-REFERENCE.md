# Usage Tracking Quick Reference

## For Backend Developers

### Quick Start: Add Usage Tracking to Your Endpoint

**Option 1: Automatic (Recommended)**
```python
from ..middleware.usage_limiter import require_usage_limit

@router.post("/my-endpoint")
@require_usage_limit("deployments", 1.0)  # Auto-checks and increments
async def my_endpoint(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Your code here
    return {"message": "success"}
```

**Option 2: Manual Control**
```python
from ..services.usage_tracking import usage_tracking_service

@router.post("/my-endpoint")
async def my_endpoint(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Check limit
    limit_check = await usage_tracking_service.check_limit(
        db, str(user.id), "api_calls", 1.0
    )
    if not limit_check['allowed']:
        raise HTTPException(429, detail=limit_check['reason'])

    # Do work...

    # Increment on success
    await usage_tracking_service.increment_usage(
        db, str(user.id), "api_calls", 1.0
    )
```

---

## Metrics Available

| Metric | Description | Use For |
|--------|-------------|---------|
| `deployments` | Number of deployments created | POST /deploy endpoints |
| `api_calls` | API requests made | General API usage |
| `compute_hours` | CPU/compute time used | Long-running tasks |
| `storage` | Storage consumed | File uploads, data storage |

---

## Tier System

| Tier | Who Gets It | Limits |
|------|-------------|--------|
| `free` | Default new users | 10 deploys, 5K API calls, 10 compute hrs |
| `pro` | Paid users | 50 deploys, 50K API calls, 100 compute hrs |
| `enterprise` | Custom contracts | Unlimited everything |

---

## Common Patterns

### 1. Single Operation
```python
@require_usage_limit("deployments", 1.0)
```

### 2. Bulk Operations
```python
@require_usage_limit("api_calls", 10.0)  # Check 10 calls at once
```

### 3. Variable Usage (Compute)
```python
# Check first
limit_check = await usage_tracking_service.check_limit(
    db, str(user.id), "compute_hours", estimated_hours
)

# Do work...
actual_hours = compute_task()

# Increment with actual
await usage_tracking_service.increment_usage(
    db, str(user.id), "compute_hours", actual_hours
)
```

---

## Error Responses

### 429 Too Many Requests
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

**What to do**: User needs to upgrade tier or wait until midnight UTC

---

## Testing Locally

### Check Your Limits
```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/usage/status
```

### Check Specific Metric
```bash
curl -X POST -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"metric": "deployments", "amount": 1}' \
  http://localhost:8000/api/usage/check-limit
```

### Manual Reset (Admin Only)
```bash
curl -X POST -H "Authorization: Bearer <admin-token>" \
  http://localhost:8000/api/usage/admin/manual-reset
```

---

## Database Queries

### Check User's Usage
```sql
SELECT * FROM daily_usage
WHERE user_id = '<uuid>'
AND date = CURRENT_DATE;
```

### Check User's Tier
```sql
SELECT username, tier FROM users
WHERE id = '<uuid>';
```

### View Tier Limits
```sql
SELECT * FROM usage_limits;
```

### Update User Tier
```sql
UPDATE users
SET tier = 'pro'
WHERE id = '<uuid>';
```

---

## Troubleshooting

### "Service not available" error
- Check backend logs for initialization errors
- Verify usage_tracking_service started correctly
- Check database connection

### Limits not resetting
- Check usage_scheduler is running
- Verify logs show daily reset at midnight UTC
- Check system clock is correct (UTC)

### Wrong limits applied
- Verify user's tier: `SELECT tier FROM users WHERE id = '<uuid>'`
- Check usage_limits table has correct values
- May need to restart backend after tier changes

---

## Migration Commands

### Apply Migration
```bash
cd backend
alembic upgrade head
```

### Check Current Version
```bash
alembic current
```

### Rollback (if needed)
```bash
alembic downgrade -1
```

---

## Monitoring Queries

### Today's Top Users
```sql
SELECT u.username, du.deployments_created, du.api_calls
FROM daily_usage du
JOIN users u ON du.user_id = u.id
WHERE du.date = CURRENT_DATE
ORDER BY du.api_calls DESC
LIMIT 10;
```

### Users Near Limits
```sql
SELECT u.username, u.tier,
       du.deployments_created, ul.max_deployments_per_day,
       du.api_calls, ul.max_api_calls_per_day
FROM daily_usage du
JOIN users u ON du.user_id = u.id
JOIN usage_limits ul ON u.tier = ul.tier
WHERE du.date = CURRENT_DATE
  AND (du.deployments_created > ul.max_deployments_per_day * 0.8
    OR du.api_calls > ul.max_api_calls_per_day * 0.8);
```

### Historical Usage (Last 7 Days)
```sql
SELECT date, COUNT(*) as active_users,
       SUM(deployments_created) as total_deployments,
       SUM(api_calls) as total_api_calls
FROM daily_usage
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY date
ORDER BY date DESC;
```
