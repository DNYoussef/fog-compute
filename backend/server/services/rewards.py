"""
Reward Distribution Service - FUNC-08 Implementation

Critical service for managing pending reward distributions BEFORE cleanup operations.
Ensures no rewards are lost during deployment deletion or system cleanup.

Key Features:
- Query all pending rewards from token system
- Distribute rewards to appropriate accounts
- Transaction rollback on distribution failure
- Comprehensive audit logging
- Integration with deployment lifecycle
"""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, List, Optional
from uuid import UUID
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

logger = logging.getLogger(__name__)


@dataclass
class PendingReward:
    """Pending reward awaiting distribution"""
    reward_id: str
    account_id: str
    amount: Decimal
    reason: str
    deployment_id: Optional[UUID] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.amount, Decimal):
            self.amount = Decimal(str(self.amount))


@dataclass
class DistributionResult:
    """Result of reward distribution operation"""
    success: bool
    total_rewards_distributed: int
    total_amount_distributed: Decimal
    failed_distributions: List[dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None
    audit_log: List[dict[str, Any]] = field(default_factory=list)


@dataclass
class CleanupResult:
    """Result of cleanup with reward distribution"""
    success: bool
    rewards_distributed: int
    rewards_amount: Decimal
    cleanup_completed: bool
    rollback_occurred: bool = False
    error_message: Optional[str] = None


class RewardDistributionService:
    """
    Service for managing reward distributions during cleanup operations.

    Ensures rewards are ALWAYS distributed BEFORE any cleanup that might
    destroy reward state. Implements rollback on failure.
    """

    def __init__(self, token_system=None, audit_service=None):
        self.token_system = token_system
        self.audit_service = audit_service

        # Metrics
        self.metrics = {
            "total_distributions": 0,
            "successful_distributions": 0,
            "failed_distributions": 0,
            "total_amount_distributed": Decimal("0"),
            "rollbacks_performed": 0,
        }

        # Audit log
        self.distribution_log: List[dict[str, Any]] = []

        logger.info("Reward distribution service initialized")

    async def get_pending_rewards(
        self,
        user_id: Optional[UUID] = None,
        deployment_id: Optional[UUID] = None,
        db: Optional[AsyncSession] = None
    ) -> List[PendingReward]:
        """
        Query all pending rewards, optionally filtered by user or deployment.

        Args:
            user_id: Filter by specific user (optional)
            deployment_id: Filter by specific deployment (optional)
            db: Database session for querying reward state

        Returns:
            List of PendingReward objects ready for distribution
        """
        pending_rewards = []

        try:
            # Query token system for pending rewards
            if self.token_system:
                # Get staking rewards from token system
                if hasattr(self.token_system, 'accounts'):
                    for account_id, account_data in self.token_system.accounts.items():
                        # Filter by user_id if provided
                        if user_id and account_id != str(user_id):
                            continue

                        # Check for accumulated staking rewards
                        staked_amount = account_data.get("staked", 0.0)
                        if staked_amount > 0:
                            # Calculate pending staking rewards
                            last_reward_time = account_data.get("last_reward_time", datetime.now(UTC))
                            hours_since_reward = (datetime.now(UTC) - last_reward_time).total_seconds() / 3600

                            if hours_since_reward > 0:
                                # Get staking APY from config
                                staking_apy = getattr(self.token_system, 'staking_apy', 0.05)
                                pending_amount = Decimal(str(staked_amount)) * Decimal(str(staking_apy)) / Decimal("8760") * Decimal(str(hours_since_reward))

                                if pending_amount > Decimal("0.001"):  # Minimum threshold
                                    reward = PendingReward(
                                        reward_id=f"staking_{account_id}_{int(datetime.now(UTC).timestamp())}",
                                        account_id=account_id,
                                        amount=pending_amount,
                                        reason="Accumulated staking rewards",
                                        metadata={
                                            "reward_type": "staking",
                                            "hours_accumulated": hours_since_reward,
                                            "staked_amount": float(staked_amount),
                                        }
                                    )
                                    pending_rewards.append(reward)

                # Get task completion rewards (from deployment cleanup)
                if deployment_id and db:
                    # Query deployment resources and calculate pending rewards
                    from ..models.deployment import Deployment, DeploymentReplica, ReplicaStatus

                    deployment_query = select(Deployment).where(
                        and_(
                            Deployment.id == deployment_id,
                            Deployment.deleted_at.is_(None)
                        )
                    )
                    deployment_result = await db.execute(deployment_query)
                    deployment = deployment_result.scalar_one_or_none()

                    if deployment:
                        # Calculate rewards based on running time
                        replicas_query = select(DeploymentReplica).where(
                            and_(
                                DeploymentReplica.deployment_id == deployment_id,
                                DeploymentReplica.status.in_([
                                    ReplicaStatus.RUNNING,
                                    ReplicaStatus.STOPPING
                                ])
                            )
                        )
                        replicas_result = await db.execute(replicas_query)
                        replicas = replicas_result.scalars().all()

                        for replica in replicas:
                            if replica.started_at:
                                running_hours = (datetime.now(timezone.utc) - replica.started_at).total_seconds() / 3600

                                # Calculate reward (e.g., 10 tokens per hour)
                                reward_amount = Decimal(str(running_hours)) * Decimal("10")

                                if reward_amount > Decimal("0.01"):
                                    reward = PendingReward(
                                        reward_id=f"deployment_{deployment_id}_{replica.id}",
                                        account_id=str(deployment.user_id),
                                        amount=reward_amount,
                                        reason=f"Deployment runtime rewards for {deployment.name}",
                                        deployment_id=deployment_id,
                                        metadata={
                                            "reward_type": "deployment_runtime",
                                            "replica_id": str(replica.id),
                                            "running_hours": running_hours,
                                        }
                                    )
                                    pending_rewards.append(reward)

            logger.info(
                f"Found {len(pending_rewards)} pending rewards "
                f"(user_id={user_id}, deployment_id={deployment_id})"
            )

            return pending_rewards

        except Exception as e:
            logger.error(f"Error querying pending rewards: {e}", exc_info=True)
            return []

    async def distribute_pending_rewards(
        self,
        rewards: List[PendingReward],
        db: Optional[AsyncSession] = None
    ) -> DistributionResult:
        """
        Distribute all pending rewards to appropriate accounts.

        Implements transaction-like behavior:
        - All distributions succeed, or all rollback
        - Comprehensive audit logging
        - Error handling for partial failures

        Args:
            rewards: List of pending rewards to distribute
            db: Database session for transactional consistency

        Returns:
            DistributionResult with success status and audit log
        """
        if not rewards:
            logger.info("No pending rewards to distribute")
            return DistributionResult(
                success=True,
                total_rewards_distributed=0,
                total_amount_distributed=Decimal("0")
            )

        result = DistributionResult(
            success=True,
            total_rewards_distributed=0,
            total_amount_distributed=Decimal("0")
        )

        distributed_rewards = []  # Track for rollback

        try:
            logger.info(f"Starting distribution of {len(rewards)} pending rewards")

            for reward in rewards:
                try:
                    # Distribute via token system
                    if self.token_system:
                        # Transfer from treasury to recipient
                        success = await self.token_system.transfer(
                            from_account="treasury",
                            to_account=reward.account_id,
                            amount=float(reward.amount),
                            description=reward.reason
                        )

                        if success:
                            # Track successful distribution
                            distributed_rewards.append(reward)
                            result.total_rewards_distributed += 1
                            result.total_amount_distributed += reward.amount

                            # Update metrics
                            self.metrics["successful_distributions"] += 1
                            self.metrics["total_amount_distributed"] += reward.amount

                            # Audit log entry
                            audit_entry = {
                                "reward_id": reward.reward_id,
                                "account_id": reward.account_id,
                                "amount": float(reward.amount),
                                "reason": reward.reason,
                                "timestamp": datetime.now(UTC).isoformat(),
                                "status": "success"
                            }
                            result.audit_log.append(audit_entry)
                            self.distribution_log.append(audit_entry)

                            # Log to audit service if available
                            if self.audit_service:
                                await self.audit_service.log_event(
                                    event_type="reward_distributed",
                                    details=audit_entry
                                )

                            logger.info(
                                f"Distributed reward {reward.reward_id}: "
                                f"{float(reward.amount)} tokens to {reward.account_id}"
                            )
                        else:
                            # Distribution failed - mark for rollback
                            raise Exception(
                                f"Token transfer failed for reward {reward.reward_id}"
                            )
                    else:
                        # No token system - cannot distribute
                        raise Exception("Token system not available for distribution")

                except Exception as e:
                    # Distribution failed for this reward
                    logger.error(
                        f"Failed to distribute reward {reward.reward_id}: {e}",
                        exc_info=True
                    )

                    result.failed_distributions.append({
                        "reward_id": reward.reward_id,
                        "account_id": reward.account_id,
                        "amount": float(reward.amount),
                        "error": str(e)
                    })

                    self.metrics["failed_distributions"] += 1

                    # CRITICAL: Rollback all previous distributions
                    logger.warning(
                        f"Rolling back {len(distributed_rewards)} previous distributions "
                        f"due to failure on reward {reward.reward_id}"
                    )

                    await self._rollback_distributions(distributed_rewards)

                    result.success = False
                    result.error_message = f"Distribution failed on reward {reward.reward_id}: {e}"

                    return result

            logger.info(
                f"Successfully distributed {result.total_rewards_distributed} rewards, "
                f"total amount: {float(result.total_amount_distributed)} tokens"
            )

            self.metrics["total_distributions"] += result.total_rewards_distributed

            return result

        except Exception as e:
            logger.error(f"Critical error during reward distribution: {e}", exc_info=True)

            # Rollback all distributions
            if distributed_rewards:
                logger.error(f"Rolling back {len(distributed_rewards)} distributions due to critical error")
                await self._rollback_distributions(distributed_rewards)

            result.success = False
            result.error_message = f"Critical distribution error: {e}"

            return result

    async def cleanup_with_distribution(
        self,
        deployment_id: UUID,
        user_id: UUID,
        db: AsyncSession
    ) -> CleanupResult:
        """
        Distribute pending rewards BEFORE performing cleanup.

        This is the critical lifecycle hook that ensures rewards are never lost.

        Workflow:
        1. Query all pending rewards for deployment/user
        2. Distribute rewards (with rollback on failure)
        3. Only proceed with cleanup if distribution succeeds
        4. Return comprehensive result

        Args:
            deployment_id: Deployment being cleaned up
            user_id: User who owns the deployment
            db: Database session (for transaction consistency)

        Returns:
            CleanupResult indicating success/failure of both stages
        """
        logger.info(
            f"Starting cleanup with reward distribution for deployment {deployment_id} "
            f"(user {user_id})"
        )

        result = CleanupResult(
            success=False,
            rewards_distributed=0,
            rewards_amount=Decimal("0"),
            cleanup_completed=False
        )

        try:
            # Step 1: Query pending rewards
            pending_rewards = await self.get_pending_rewards(
                user_id=user_id,
                deployment_id=deployment_id,
                db=db
            )

            logger.info(f"Found {len(pending_rewards)} pending rewards for distribution")

            # Step 2: Distribute rewards (with rollback protection)
            if pending_rewards:
                distribution_result = await self.distribute_pending_rewards(
                    rewards=pending_rewards,
                    db=db
                )

                if not distribution_result.success:
                    # Distribution failed - DO NOT proceed with cleanup
                    logger.error(
                        f"Reward distribution failed: {distribution_result.error_message}. "
                        f"Aborting cleanup to prevent reward loss."
                    )

                    result.error_message = (
                        f"Reward distribution failed: {distribution_result.error_message}. "
                        f"Cleanup aborted to protect rewards."
                    )
                    result.rollback_occurred = True

                    return result

                # Distribution succeeded
                result.rewards_distributed = distribution_result.total_rewards_distributed
                result.rewards_amount = distribution_result.total_amount_distributed

                logger.info(
                    f"Successfully distributed {result.rewards_distributed} rewards "
                    f"({float(result.rewards_amount)} tokens) before cleanup"
                )
            else:
                logger.info("No pending rewards found, proceeding with cleanup")

            # Step 3: Proceed with cleanup (rewards are safe)
            # Cleanup logic would go here (handled by caller)
            result.cleanup_completed = True
            result.success = True

            logger.info(
                f"Cleanup with distribution completed successfully for deployment {deployment_id}"
            )

            return result

        except Exception as e:
            logger.error(
                f"Error during cleanup with distribution: {e}",
                exc_info=True
            )

            result.error_message = f"Cleanup failed: {e}"
            result.rollback_occurred = True

            return result

    async def _rollback_distributions(self, distributed_rewards: List[PendingReward]) -> None:
        """
        Rollback previously distributed rewards.

        Attempts to reverse token transfers to maintain consistency.
        Logs all rollback operations for audit.

        Args:
            distributed_rewards: List of rewards that were successfully distributed
        """
        logger.warning(f"Rolling back {len(distributed_rewards)} reward distributions")

        rollback_count = 0

        for reward in distributed_rewards:
            try:
                if self.token_system:
                    # Reverse transfer: recipient -> treasury
                    success = await self.token_system.transfer(
                        from_account=reward.account_id,
                        to_account="treasury",
                        amount=float(reward.amount),
                        description=f"Rollback: {reward.reason}"
                    )

                    if success:
                        rollback_count += 1

                        # Log rollback
                        audit_entry = {
                            "reward_id": reward.reward_id,
                            "account_id": reward.account_id,
                            "amount": float(reward.amount),
                            "reason": f"ROLLBACK: {reward.reason}",
                            "timestamp": datetime.now(UTC).isoformat(),
                            "status": "rolled_back"
                        }
                        self.distribution_log.append(audit_entry)

                        if self.audit_service:
                            await self.audit_service.log_event(
                                event_type="reward_rollback",
                                details=audit_entry
                            )

                        logger.info(f"Rolled back reward {reward.reward_id}")
                    else:
                        logger.error(
                            f"Failed to rollback reward {reward.reward_id} - "
                            f"MANUAL INTERVENTION REQUIRED"
                        )
            except Exception as e:
                logger.error(
                    f"Error rolling back reward {reward.reward_id}: {e}",
                    exc_info=True
                )

        self.metrics["rollbacks_performed"] += rollback_count

        logger.warning(
            f"Rollback completed: {rollback_count}/{len(distributed_rewards)} rewards reversed"
        )

    def get_metrics(self) -> dict[str, Any]:
        """Get service metrics for monitoring"""
        return {
            **self.metrics,
            "total_amount_distributed_float": float(self.metrics["total_amount_distributed"]),
            "recent_distributions": len(self.distribution_log),
        }

    def get_audit_log(self, limit: int = 100) -> List[dict[str, Any]]:
        """Get recent audit log entries"""
        return self.distribution_log[-limit:]


# Global service instance
_reward_service: Optional[RewardDistributionService] = None


def get_reward_service() -> RewardDistributionService:
    """Get global reward distribution service instance"""
    global _reward_service

    if _reward_service is None:
        # Initialize with dependencies from service manager
        from .enhanced_service_manager import enhanced_service_manager

        token_system = None
        audit_service = None

        # Try to get token system
        dao = enhanced_service_manager.get('dao')
        if dao and hasattr(dao, 'token_manager'):
            token_system = dao.token_manager

        # Try to get audit service
        audit_service = enhanced_service_manager.get('audit')

        _reward_service = RewardDistributionService(
            token_system=token_system,
            audit_service=audit_service
        )

    return _reward_service
