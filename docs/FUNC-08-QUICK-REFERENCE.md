# FUNC-08 Quick Reference Guide

**Quick guide for developers working with the reward distribution system.**

---

## Import and Initialize

```python
from services.rewards import get_reward_service

# Get service instance
reward_service = get_reward_service()
```

---

## Common Operations

### 1. Query Pending Rewards

```python
# Get all pending rewards for a user
rewards = await reward_service.get_pending_rewards(user_id=user_uuid)

# Get all pending rewards for a deployment
rewards = await reward_service.get_pending_rewards(
    deployment_id=deployment_uuid,
    db=db_session
)

# Get all pending rewards (entire system)
rewards = await reward_service.get_pending_rewards()
```

### 2. Distribute Rewards

```python
# Distribute a list of rewards
result = await reward_service.distribute_pending_rewards(
    rewards=pending_rewards,
    db=db_session
)

if result.success:
    print(f"Distributed {result.total_rewards_distributed} rewards")
    print(f"Total amount: {result.total_amount_distributed}")
else:
    print(f"Distribution failed: {result.error_message}")
    print(f"Failed rewards: {result.failed_distributions}")
```

### 3. Cleanup with Distribution (Critical)

```python
# ALWAYS use this when deleting deployments or cleaning up resources
cleanup_result = await reward_service.cleanup_with_distribution(
    deployment_id=deployment_uuid,
    user_id=user_uuid,
    db=db_session
)

if not cleanup_result.success:
    # ABORT cleanup - rewards not safe
    await db.rollback()
    raise Exception(f"Cannot cleanup: {cleanup_result.error_message}")

# Proceed with cleanup only if rewards are distributed
# ... perform actual cleanup operations ...
```

---

## Data Structures

### PendingReward

```python
from services.rewards import PendingReward
from decimal import Decimal

reward = PendingReward(
    reward_id="unique_reward_id",
    account_id="user_account_id",
    amount=Decimal("100.50"),
    reason="Staking rewards for 10 hours",
    deployment_id=deployment_uuid,  # Optional
    metadata={                        # Optional
        "reward_type": "staking",
        "hours": 10
    }
)
```

### DistributionResult

```python
class DistributionResult:
    success: bool
    total_rewards_distributed: int
    total_amount_distributed: Decimal
    failed_distributions: List[dict]
    error_message: Optional[str]
    audit_log: List[dict]
```

### CleanupResult

```python
class CleanupResult:
    success: bool
    rewards_distributed: int
    rewards_amount: Decimal
    cleanup_completed: bool
    rollback_occurred: bool
    error_message: Optional[str]
```

---

## Integration Examples

### Example 1: Deployment Deletion

```python
@router.delete("/{deployment_id}")
async def delete_deployment(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Validate deployment
    deployment = await get_deployment_or_404(deployment_id, current_user.id, db)

    # CRITICAL: Distribute rewards BEFORE cleanup
    from services.rewards import get_reward_service
    reward_service = get_reward_service()

    cleanup_result = await reward_service.cleanup_with_distribution(
        deployment_id=UUID(deployment_id),
        user_id=current_user.id,
        db=db
    )

    if not cleanup_result.success:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Cannot delete: {cleanup_result.error_message}"
        )

    # Proceed with cleanup
    await stop_replicas(deployment)
    await release_resources(deployment)
    deployment.deleted_at = datetime.utcnow()
    await db.commit()

    return {
        "success": True,
        "rewards_distributed": cleanup_result.rewards_distributed,
        "rewards_amount": float(cleanup_result.rewards_amount)
    }
```

### Example 2: Service Shutdown

```python
async def cleanup(self):
    """Service cleanup with reward distribution"""
    try:
        from services.rewards import get_reward_service
        reward_service = get_reward_service()

        # Get all pending rewards
        pending_rewards = await reward_service.get_pending_rewards()

        if pending_rewards:
            logger.info(f"Distributing {len(pending_rewards)} pending rewards before shutdown")

            result = await reward_service.distribute_pending_rewards(pending_rewards)

            if result.success:
                logger.info(f"Distributed {result.total_rewards_distributed} rewards")
            else:
                logger.error(f"Failed to distribute rewards: {result.error_message}")
                logger.warning("MANUAL INTERVENTION MAY BE REQUIRED")

        # Proceed with cleanup
        await self._cleanup_resources()

    except Exception as e:
        logger.error(f"Cleanup error: {e}")
```

### Example 3: Manual Distribution (Admin)

```python
@router.post("/api/rewards/distribute", dependencies=[Depends(require_admin)])
async def manual_distribute(
    deployment_id: Optional[str] = None,
    user_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Manually trigger reward distribution (admin only)"""
    from services.rewards import get_reward_service
    reward_service = get_reward_service()

    # Query pending rewards
    rewards = await reward_service.get_pending_rewards(
        user_id=UUID(user_id) if user_id else None,
        deployment_id=UUID(deployment_id) if deployment_id else None,
        db=db
    )

    if not rewards:
        return {"message": "No pending rewards found"}

    # Distribute
    result = await reward_service.distribute_pending_rewards(rewards, db)

    return {
        "success": result.success,
        "rewards_distributed": result.total_rewards_distributed,
        "total_amount": float(result.total_amount_distributed),
        "failed_distributions": result.failed_distributions,
        "error_message": result.error_message
    }
```

---

## Monitoring

### Get Service Metrics

```python
metrics = reward_service.get_metrics()

# Available metrics:
{
    "total_distributions": 142,
    "successful_distributions": 138,
    "failed_distributions": 4,
    "total_amount_distributed": Decimal("15420.50"),
    "rollbacks_performed": 2
}
```

### Get Audit Log

```python
# Get last 50 entries
audit_log = reward_service.get_audit_log(limit=50)

# Example entry:
{
    "reward_id": "staking_user_123_1732543200",
    "account_id": "user_123",
    "amount": 125.0,
    "reason": "Accumulated staking rewards",
    "timestamp": "2025-11-25T10:00:00Z",
    "status": "success"
}
```

---

## Database Queries

### Query Reward Distributions

```python
from models.rewards import RewardDistribution

# Get all distributions for a user
distributions = await db.execute(
    select(RewardDistribution)
    .where(RewardDistribution.user_id == user_uuid)
    .order_by(RewardDistribution.created_at.desc())
)

# Get distributions for a deployment
distributions = await db.execute(
    select(RewardDistribution)
    .where(RewardDistribution.deployment_id == deployment_uuid)
)

# Get failed distributions
failed = await db.execute(
    select(RewardDistribution)
    .where(RewardDistribution.status == 'failed')
)
```

### Query Audit Log

```python
from models.rewards import RewardDistributionAuditLog

# Get audit log for a reward
log_entries = await db.execute(
    select(RewardDistributionAuditLog)
    .where(RewardDistributionAuditLog.reward_id == reward_id)
    .order_by(RewardDistributionAuditLog.timestamp.asc())
)

# Get recent failed distributions
failed_events = await db.execute(
    select(RewardDistributionAuditLog)
    .where(
        and_(
            RewardDistributionAuditLog.event_type == 'distribution_failed',
            RewardDistributionAuditLog.timestamp >= datetime.utcnow() - timedelta(hours=24)
        )
    )
)
```

---

## Error Handling

### Distribution Failure

```python
result = await reward_service.distribute_pending_rewards(rewards)

if not result.success:
    # Log error
    logger.error(f"Distribution failed: {result.error_message}")

    # Check failed distributions
    for failed in result.failed_distributions:
        logger.error(
            f"Failed reward {failed['reward_id']}: "
            f"{failed['account_id']} - {failed['error']}"
        )

    # Take action
    if "Token system not available" in result.error_message:
        # Wait for token system to recover
        await asyncio.sleep(60)
        # Retry distribution
        result = await reward_service.distribute_pending_rewards(rewards)
```

### Cleanup Failure

```python
cleanup_result = await reward_service.cleanup_with_distribution(...)

if not cleanup_result.success:
    # DO NOT proceed with cleanup
    await db.rollback()

    # Log for manual intervention
    logger.critical(
        f"Cleanup aborted for deployment {deployment_id}: "
        f"{cleanup_result.error_message}. "
        f"Pending rewards NOT distributed. MANUAL INTERVENTION REQUIRED."
    )

    # Notify admins
    await send_alert(
        severity="critical",
        message=f"Reward distribution failed for deployment {deployment_id}"
    )

    # Return error to user
    raise HTTPException(
        status_code=500,
        detail="Cannot delete deployment: reward distribution failed. Please try again later."
    )
```

---

## Testing

### Unit Test Template

```python
import pytest
from services.rewards import RewardDistributionService, PendingReward
from decimal import Decimal

@pytest.mark.asyncio
async def test_my_reward_scenario():
    # Setup
    reward_service = RewardDistributionService(
        token_system=mock_token_system,
        audit_service=mock_audit_service
    )

    reward = PendingReward(
        reward_id="test_reward_1",
        account_id="user_1",
        amount=Decimal("100.0"),
        reason="Test reward"
    )

    # Execute
    result = await reward_service.distribute_pending_rewards([reward])

    # Assert
    assert result.success is True
    assert result.total_rewards_distributed == 1
    assert result.total_amount_distributed == Decimal("100.0")
```

### Integration Test Template

```python
@pytest.mark.asyncio
async def test_deployment_deletion_with_rewards(client, db):
    # Create deployment
    deployment = await create_test_deployment(db)

    # Wait for rewards to accumulate
    await asyncio.sleep(5)

    # Delete deployment (should trigger reward distribution)
    response = await client.delete(
        f"/api/deployment/{deployment.id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["rewards_distributed"] > 0
    assert data["rewards_amount"] > 0
```

---

## Best Practices

### DO

- Always use `cleanup_with_distribution()` when deleting resources
- Check `result.success` before proceeding with cleanup
- Log all distribution failures
- Use `Decimal` for all amount calculations
- Rollback database transactions on distribution failure

### DON'T

- Don't skip reward distribution before cleanup
- Don't proceed with cleanup if distribution fails
- Don't use `float` for amounts (precision loss)
- Don't ignore failed distributions
- Don't distribute rewards without rollback protection

---

## Troubleshooting

### Problem: Distribution always fails

**Cause**: Token system not initialized

**Solution**:
```python
# Check token system availability
dao = service_manager.get('dao')
if dao and hasattr(dao, 'token_manager'):
    print("Token system available")
else:
    print("Token system NOT available - initialize it first")
```

### Problem: Rollback not working

**Cause**: Token system transfer method not async

**Solution**:
```python
# Ensure token system transfer is async
class FogTokenSystem:
    async def transfer(self, from_account, to_account, amount, description):
        # Async implementation
        ...
```

### Problem: Rewards not detected

**Cause**: No pending rewards in token system

**Solution**:
```python
# Check token system accounts
for account_id, account_data in token_system.accounts.items():
    print(f"Account {account_id}:")
    print(f"  Staked: {account_data.get('staked', 0)}")
    print(f"  Last reward time: {account_data.get('last_reward_time')}")
```

---

## Quick Commands

```bash
# Run tests
pytest tests/test_reward_distribution.py -v

# Run database migration
alembic upgrade 005

# Check service logs
tail -f /var/log/fog-compute/backend.log | grep "reward"

# Query pending rewards (SQL)
psql -d fog_compute -c "SELECT * FROM pending_reward_queue WHERE status = 'queued';"

# Query recent distributions (SQL)
psql -d fog_compute -c "SELECT * FROM reward_distributions ORDER BY created_at DESC LIMIT 10;"
```

---

## Links

- Full documentation: `docs/FUNC-08-REWARD-DISTRIBUTION.md`
- Implementation: `backend/server/services/rewards.py`
- Tests: `tests/test_reward_distribution.py`
- Database models: `backend/server/models/rewards.py`
- Migration: `backend/alembic/versions/005_create_reward_tables.py`
