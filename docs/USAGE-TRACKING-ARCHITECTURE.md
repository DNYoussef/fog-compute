# Usage Tracking System Architecture

## System Overview

```
+------------------+
|    User API      |
|   Request        |
+------------------+
         |
         v
+------------------+
| FastAPI Router   |
| /api/usage/*     |
+------------------+
         |
         v
+------------------+
|  Auth Middleware |
|  (JWT/API Key)   |
+------------------+
         |
         v
+------------------+
| Usage Limiter    |
| @require_usage   |
| _limit()         |
+------------------+
         |
         v
+------------------+
| Usage Tracking   |
| Service          |
+------------------+
         |
         v
+------------------+
| PostgreSQL DB    |
| - daily_usage    |
| - usage_limits   |
| - users (tier)   |
+------------------+
```

---

## Component Flow

### 1. Request Processing

```
Client Request
    |
    v
[Authentication] --> 401 if fails
    |
    v
[Usage Limiter Decorator]
    |
    +---> check_limit()
    |        |
    |        v
    |    [Get User Tier] --> users.tier
    |        |
    |        v
    |    [Get Tier Limits] --> usage_limits table
    |        |
    |        v
    |    [Get Current Usage] --> daily_usage table
    |        |
    |        v
    |    [Calculate: current + amount <= limit?]
    |        |
    |        +---> YES --> Continue
    |        |
    |        +---> NO --> 429 Too Many Requests
    |
    v
[Auto Increment if enabled]
    |
    v
[Execute Endpoint Logic]
    |
    v
Response to Client
```

### 2. Limit Checking Logic

```
Input: (user_id, metric, amount)
    |
    v
[Load User] --> Get user.tier
    |
    v
[Load Limits] --> Get usage_limits[tier]
    |
    v
[Load Usage] --> Get/Create daily_usage[user_id, today]
    |
    v
[Check Limit]
    |
    +---> If limit is NULL --> ALLOW (unlimited)
    |
    +---> If current + amount <= limit --> ALLOW
    |
    +---> If current + amount > limit --> DENY (429)
```

### 3. Daily Reset Scheduler

```
Startup
    |
    v
[Calculate next midnight UTC]
    |
    v
[Sleep until midnight]
    |
    v
Midnight UTC
    |
    v
[Call reset_daily_usage()]
    |
    v
[Log historical record count]
    |
    v
[New records created on-demand]
    |
    v
[Calculate next midnight]
    |
    v
[Sleep until midnight] --> Loop
```

---

## Data Flow

### Write Path (Increment Usage)

```
increment_usage(user_id, metric, amount)
    |
    v
[check_limit()] --> Verify allowed
    |
    v
[Get/Create daily_usage record]
    |
    v
[Increment appropriate counter]
    |   deployments_created += amount
    |   api_calls += amount
    |   compute_hours += amount
    |   storage_gb_hours += amount
    |
    v
[UPDATE daily_usage SET updated_at = NOW()]
    |
    v
[COMMIT transaction]
    |
    v
Return updated record
```

### Read Path (Get Usage Status)

```
get_usage_status(user_id)
    |
    v
[Load User] --> users table
    |        (id, tier)
    |
    v
[Load Limits] --> usage_limits table
    |            (tier -> limits)
    |
    v
[Load Usage] --> daily_usage table
    |           (user_id, today -> usage)
    |
    v
[Calculate Remaining]
    |   remaining = limit - current
    |   (for each metric)
    |
    v
Return {usage, limits, remaining}
```

---

## Database Schema Relationships

```
+----------------+
|    users       |
|----------------|
| id (PK)        |<------+
| username       |       |
| email          |       |
| tier           |----+  |
+----------------+    |  |
                      |  |
                      v  |
              +-----------------+
              | usage_limits    |
              |-----------------|
              | tier (PK)       |
              | max_deployments |
              | max_api_calls   |
              | max_compute_hrs |
              | max_storage_gb  |
              +-----------------+

                      |
                      | (FK)
                      v
              +-----------------+
              | daily_usage     |
              |-----------------|
              | user_id (FK)    |
              | date            |
              | deployments     |
              | api_calls       |
              | compute_hours   |
              | storage_gb_hours|
              +-----------------+
              UNIQUE(user_id, date)
```

---

## Tier System

```
+-------------+     +-------------+     +-------------+
|    FREE     |     |     PRO     |     | ENTERPRISE  |
|-------------|     |-------------|     |-------------|
| Default     |     | Paid        |     | Custom      |
|-------------|     |-------------|     |-------------|
| 10 deploys  |     | 50 deploys  |     | Unlimited   |
| 5K API      |     | 50K API     |     | Unlimited   |
| 10 hrs CPU  |     | 100 hrs CPU |     | Unlimited   |
| 5 GB store  |     | 50 GB store |     | Unlimited   |
+-------------+     +-------------+     +-------------+
```

---

## Usage Enforcement Patterns

### Pattern 1: Automatic (Decorator)

```python
@router.post("/deploy")
@require_usage_limit("deployments", 1.0)
async def deploy_app(user, db):
    # Limit checked and incremented automatically
    # 429 raised if limit exceeded
    return create_deployment()
```

**Flow**:
1. Request arrives
2. Decorator runs BEFORE endpoint
3. check_limit() called
4. If allowed: increment_usage() called
5. Endpoint executes
6. Response returned

**Use when**: Simple operations with fixed cost

---

### Pattern 2: Manual (Service)

```python
@router.post("/api-call")
async def make_call(user, db):
    # Check limit
    limit_check = await check_limit(db, user.id, "api_calls", 1.0)
    if not limit_check['allowed']:
        raise HTTPException(429)

    # Do work
    result = perform_operation()

    # Increment only on success
    await increment_usage(db, user.id, "api_calls", 1.0)

    return result
```

**Flow**:
1. Request arrives
2. Endpoint executes check_limit()
3. If denied: return 429 immediately
4. Perform operation
5. If successful: increment_usage()
6. Response returned

**Use when**:
- Need to increment only on success
- Variable usage amounts
- Complex error handling

---

### Pattern 3: Dependency (Check Only)

```python
@router.post("/compute")
async def compute_task(
    user,
    db,
    _: None = Depends(check_usage_limit_dependency("compute_hours", 2.5))
):
    # Limit checked but NOT incremented
    # Manually increment with actual usage
    actual_hours = perform_compute()

    await increment_usage(db, user.id, "compute_hours", actual_hours)
```

**Flow**:
1. Request arrives
2. Dependency checks limit BEFORE endpoint
3. If denied: 429 raised, endpoint never runs
4. Endpoint executes
5. Measure actual usage
6. Increment with actual value
7. Response returned

**Use when**:
- Usage varies based on execution
- Need to check upfront but measure actual
- Estimated vs actual usage

---

## Scheduler Architecture

```
+------------------+
| Usage Scheduler  |
+------------------+
         |
         | startup()
         v
+------------------+
| Calculate Next   |
| Midnight UTC     |
+------------------+
         |
         v
+------------------+
| asyncio.sleep()  |
| (until midnight) |
+------------------+
         |
         | Midnight UTC
         v
+------------------+
| reset_daily_     |
| usage()          |
+------------------+
         |
         v
+------------------+
| Query yesterday  |
| records          |
+------------------+
         |
         v
+------------------+
| Log count        |
| (no deletion)    |
+------------------+
         |
         v
+------------------+
| Loop back to     |
| calculate next   |
+------------------+
```

---

## Error Handling Flow

```
Request with Usage Tracking
    |
    v
Try: check_limit()
    |
    +---> Limit OK
    |        |
    |        v
    |    Try: increment_usage()
    |        |
    |        +---> Success --> Continue
    |        |
    |        +---> DB Error --> 500
    |
    +---> Limit Exceeded --> 429
    |
    +---> User Not Found --> 401
    |
    +---> Service Unavailable --> 503
```

### Error Responses

**429 Too Many Requests**:
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

**503 Service Unavailable**:
```json
{
  "detail": "Usage tracking service not available"
}
```

**401 Unauthorized**:
```json
{
  "detail": "Authentication required for usage tracking"
}
```

---

## Integration Points

### 1. Authentication Layer
```
JWT/API Key Middleware
    |
    v
get_current_user() --> User object
    |
    v
Usage Limiter (has access to user.id, user.tier)
```

### 2. Database Layer
```
AsyncSession (SQLAlchemy)
    |
    v
usage_tracking_service
    |
    +---> SELECT daily_usage
    |
    +---> SELECT usage_limits
    |
    +---> UPDATE daily_usage
    |
    +---> INSERT daily_usage (if not exists)
```

### 3. Scheduler Integration
```
main.py lifespan
    |
    +---> startup:
    |        - usage_tracking_service.initialize()
    |        - usage_scheduler.start()
    |
    +---> shutdown:
             - usage_scheduler.stop()
```

---

## Performance Optimizations

### Database Indexes

```sql
-- Fast user lookup
CREATE INDEX ix_daily_usage_user_id ON daily_usage(user_id);

-- Fast date filtering
CREATE INDEX ix_daily_usage_date ON daily_usage(date);

-- Fast tier lookup
CREATE INDEX ix_usage_limits_tier ON usage_limits(tier);

-- Fast user tier lookup
CREATE INDEX ix_users_tier ON users(tier);
```

### Unique Constraints

```sql
-- Prevent duplicate daily records
UNIQUE(user_id, date) on daily_usage

-- One limit per tier
UNIQUE(tier) on usage_limits
```

### On-Demand Creation

- Daily usage records NOT pre-created
- Created on first usage per user per day
- Reduces storage for inactive users

---

## Monitoring Points

### Service Health

```
1. usage_tracking_service.initialized
   - Should be True
   - Check on startup

2. usage_scheduler.is_running
   - Should be True
   - Check continuously

3. Daily reset logs
   - Should appear at 00:00 UTC
   - Check timestamp accuracy
```

### Usage Metrics

```
1. 429 error count
   - Track by user, tier, metric
   - Alert if sudden spike

2. Records per day
   - Track growth over time
   - Plan storage capacity

3. Tier distribution
   - Monitor free vs paid ratio
   - Identify upgrade opportunities
```

### Performance Metrics

```
1. check_limit() latency
   - Target: < 50ms
   - Alert if > 100ms

2. get_usage_status() latency
   - Target: < 100ms
   - Alert if > 200ms

3. Daily reset duration
   - Target: < 5s
   - Alert if > 30s
```

---

## Summary

The usage tracking system is designed with:

- **Modularity**: Separate services for tracking, scheduling, enforcement
- **Flexibility**: Multiple usage patterns (decorator, manual, dependency)
- **Scalability**: Indexed database, on-demand record creation
- **Reliability**: Automatic retry, graceful degradation
- **Observability**: Comprehensive logging, metrics, error handling

**Key Design Principles**:
1. Fail open (service unavailable = allow request)
2. Explicit over implicit (clear error messages)
3. Separation of concerns (tracking vs scheduling vs enforcement)
4. Developer ergonomics (simple decorator API)
5. Production ready (logging, monitoring, error handling)
