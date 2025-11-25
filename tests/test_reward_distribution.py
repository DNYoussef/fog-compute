"""
Unit Tests for Reward Distribution Service (FUNC-08)

Tests the critical reward distribution functionality to ensure
rewards are never lost during cleanup operations.
"""

import pytest
from decimal import Decimal
from datetime import datetime, UTC
from uuid import uuid4, UUID
from unittest.mock import AsyncMock, MagicMock, patch

import sys
import os
backend_path = os.path.join(os.path.dirname(__file__), '..', 'backend', 'server')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from services.rewards import (
    RewardDistributionService,
    PendingReward,
    DistributionResult,
    CleanupResult
)


@pytest.fixture
def mock_token_system():
    """Mock token system for testing"""
    token_system = MagicMock()
    token_system.accounts = {
        "user_1": {
            "balance": 1000.0,
            "staked": 500.0,
            "last_reward_time": datetime.now(UTC)
        },
        "user_2": {
            "balance": 2000.0,
            "staked": 1000.0,
            "last_reward_time": datetime.now(UTC)
        },
        "treasury": {
            "balance": 1000000.0,
            "staked": 0.0
        }
    }
    token_system.staking_apy = 0.05
    token_system.transfer = AsyncMock(return_value=True)
    return token_system


@pytest.fixture
def mock_audit_service():
    """Mock audit service for testing"""
    audit_service = MagicMock()
    audit_service.log_event = AsyncMock(return_value=True)
    return audit_service


@pytest.fixture
def reward_service(mock_token_system, mock_audit_service):
    """Create reward distribution service with mocked dependencies"""
    return RewardDistributionService(
        token_system=mock_token_system,
        audit_service=mock_audit_service
    )


class TestPendingReward:
    """Test PendingReward dataclass"""

    def test_pending_reward_creation(self):
        """Test creating a pending reward"""
        reward = PendingReward(
            reward_id="test_reward_1",
            account_id="user_1",
            amount=Decimal("100.5"),
            reason="Test reward"
        )

        assert reward.reward_id == "test_reward_1"
        assert reward.account_id == "user_1"
        assert reward.amount == Decimal("100.5")
        assert reward.reason == "Test reward"
        assert isinstance(reward.created_at, datetime)

    def test_pending_reward_amount_conversion(self):
        """Test that amount is converted to Decimal"""
        reward = PendingReward(
            reward_id="test_reward_2",
            account_id="user_2",
            amount=50.75,  # Float input
            reason="Test reward"
        )

        assert isinstance(reward.amount, Decimal)
        assert reward.amount == Decimal("50.75")


class TestGetPendingRewards:
    """Test get_pending_rewards functionality"""

    @pytest.mark.asyncio
    async def test_get_pending_rewards_no_rewards(self, reward_service, mock_token_system):
        """Test when there are no pending rewards"""
        # Set up token system with no pending rewards
        mock_token_system.accounts = {
            "treasury": {"balance": 1000000.0, "staked": 0.0}
        }

        rewards = await reward_service.get_pending_rewards()

        assert len(rewards) == 0

    @pytest.mark.asyncio
    async def test_get_pending_rewards_staking_rewards(self, reward_service, mock_token_system):
        """Test getting pending staking rewards"""
        # Mock staking rewards
        from datetime import timedelta
        past_time = datetime.now(UTC) - timedelta(hours=10)

        mock_token_system.accounts["user_1"]["last_reward_time"] = past_time
        mock_token_system.accounts["user_1"]["staked"] = 1000.0

        rewards = await reward_service.get_pending_rewards(user_id=UUID("00000000-0000-0000-0000-000000000001"))

        # Should find staking rewards for 10 hours
        assert len(rewards) > 0

    @pytest.mark.asyncio
    async def test_get_pending_rewards_filtered_by_user(self, reward_service):
        """Test filtering pending rewards by user_id"""
        user_id = uuid4()

        rewards = await reward_service.get_pending_rewards(user_id=user_id)

        # Should only return rewards for specified user
        for reward in rewards:
            assert reward.account_id == str(user_id)


class TestDistributePendingRewards:
    """Test distribute_pending_rewards functionality"""

    @pytest.mark.asyncio
    async def test_distribute_no_rewards(self, reward_service):
        """Test distributing when there are no rewards"""
        result = await reward_service.distribute_pending_rewards([])

        assert result.success is True
        assert result.total_rewards_distributed == 0
        assert result.total_amount_distributed == Decimal("0")

    @pytest.mark.asyncio
    async def test_distribute_single_reward_success(self, reward_service, mock_token_system):
        """Test successfully distributing a single reward"""
        reward = PendingReward(
            reward_id="test_reward_1",
            account_id="user_1",
            amount=Decimal("50.0"),
            reason="Test reward distribution"
        )

        result = await reward_service.distribute_pending_rewards([reward])

        assert result.success is True
        assert result.total_rewards_distributed == 1
        assert result.total_amount_distributed == Decimal("50.0")
        assert len(result.failed_distributions) == 0
        assert len(result.audit_log) == 1

        # Verify token transfer was called
        mock_token_system.transfer.assert_called_once_with(
            from_account="treasury",
            to_account="user_1",
            amount=50.0,
            description="Test reward distribution"
        )

    @pytest.mark.asyncio
    async def test_distribute_multiple_rewards_success(self, reward_service, mock_token_system):
        """Test successfully distributing multiple rewards"""
        rewards = [
            PendingReward(
                reward_id=f"reward_{i}",
                account_id=f"user_{i}",
                amount=Decimal(f"{i * 10}.0"),
                reason=f"Reward {i}"
            )
            for i in range(1, 4)
        ]

        result = await reward_service.distribute_pending_rewards(rewards)

        assert result.success is True
        assert result.total_rewards_distributed == 3
        assert result.total_amount_distributed == Decimal("60.0")  # 10 + 20 + 30
        assert len(result.audit_log) == 3

    @pytest.mark.asyncio
    async def test_distribute_rewards_with_failure_triggers_rollback(
        self, reward_service, mock_token_system
    ):
        """Test that distribution failure triggers rollback of previous distributions"""
        # Set up mock to fail on second transfer
        mock_token_system.transfer = AsyncMock(side_effect=[True, False])

        rewards = [
            PendingReward(
                reward_id="reward_1",
                account_id="user_1",
                amount=Decimal("50.0"),
                reason="Reward 1"
            ),
            PendingReward(
                reward_id="reward_2",
                account_id="user_2",
                amount=Decimal("75.0"),
                reason="Reward 2"
            )
        ]

        result = await reward_service.distribute_pending_rewards(rewards)

        assert result.success is False
        assert result.total_rewards_distributed == 0  # Rolled back
        assert len(result.failed_distributions) == 1
        assert result.error_message is not None

        # Verify rollback was attempted (2 transfers + 1 rollback = 3 calls)
        assert mock_token_system.transfer.call_count == 3

    @pytest.mark.asyncio
    async def test_distribute_rewards_no_token_system(self):
        """Test distribution when token system is not available"""
        service = RewardDistributionService(token_system=None, audit_service=None)

        reward = PendingReward(
            reward_id="reward_1",
            account_id="user_1",
            amount=Decimal("50.0"),
            reason="Test reward"
        )

        result = await service.distribute_pending_rewards([reward])

        assert result.success is False
        assert "Token system not available" in result.error_message


class TestCleanupWithDistribution:
    """Test cleanup_with_distribution lifecycle hook"""

    @pytest.mark.asyncio
    async def test_cleanup_with_distribution_no_pending_rewards(
        self, reward_service, mock_token_system
    ):
        """Test cleanup when there are no pending rewards"""
        deployment_id = uuid4()
        user_id = uuid4()

        # Mock database session
        mock_db = MagicMock()

        with patch.object(reward_service, 'get_pending_rewards', return_value=[]):
            result = await reward_service.cleanup_with_distribution(
                deployment_id=deployment_id,
                user_id=user_id,
                db=mock_db
            )

        assert result.success is True
        assert result.rewards_distributed == 0
        assert result.cleanup_completed is True
        assert result.rollback_occurred is False

    @pytest.mark.asyncio
    async def test_cleanup_with_distribution_success(
        self, reward_service, mock_token_system
    ):
        """Test successful cleanup with reward distribution"""
        deployment_id = uuid4()
        user_id = uuid4()
        mock_db = MagicMock()

        pending_rewards = [
            PendingReward(
                reward_id="reward_1",
                account_id=str(user_id),
                amount=Decimal("100.0"),
                reason="Deployment rewards"
            )
        ]

        with patch.object(reward_service, 'get_pending_rewards', return_value=pending_rewards):
            result = await reward_service.cleanup_with_distribution(
                deployment_id=deployment_id,
                user_id=user_id,
                db=mock_db
            )

        assert result.success is True
        assert result.rewards_distributed == 1
        assert result.rewards_amount == Decimal("100.0")
        assert result.cleanup_completed is True
        assert result.rollback_occurred is False

    @pytest.mark.asyncio
    async def test_cleanup_with_distribution_failure_aborts_cleanup(
        self, reward_service, mock_token_system
    ):
        """Test that distribution failure aborts cleanup"""
        deployment_id = uuid4()
        user_id = uuid4()
        mock_db = MagicMock()

        # Make token transfer fail
        mock_token_system.transfer = AsyncMock(return_value=False)

        pending_rewards = [
            PendingReward(
                reward_id="reward_1",
                account_id=str(user_id),
                amount=Decimal("100.0"),
                reason="Deployment rewards"
            )
        ]

        with patch.object(reward_service, 'get_pending_rewards', return_value=pending_rewards):
            result = await reward_service.cleanup_with_distribution(
                deployment_id=deployment_id,
                user_id=user_id,
                db=mock_db
            )

        # Cleanup should be aborted to protect rewards
        assert result.success is False
        assert result.cleanup_completed is False
        assert result.error_message is not None


class TestRollback:
    """Test rollback functionality"""

    @pytest.mark.asyncio
    async def test_rollback_distributions(self, reward_service, mock_token_system):
        """Test rolling back distributed rewards"""
        distributed_rewards = [
            PendingReward(
                reward_id="reward_1",
                account_id="user_1",
                amount=Decimal("50.0"),
                reason="Test reward"
            ),
            PendingReward(
                reward_id="reward_2",
                account_id="user_2",
                amount=Decimal("75.0"),
                reason="Test reward 2"
            )
        ]

        await reward_service._rollback_distributions(distributed_rewards)

        # Should have called transfer twice for rollback
        assert mock_token_system.transfer.call_count == 2

        # Verify rollback transfers (from user back to treasury)
        calls = mock_token_system.transfer.call_args_list
        assert calls[0].kwargs['from_account'] == "user_1"
        assert calls[0].kwargs['to_account'] == "treasury"
        assert calls[1].kwargs['from_account'] == "user_2"
        assert calls[1].kwargs['to_account'] == "treasury"


class TestMetrics:
    """Test metrics tracking"""

    @pytest.mark.asyncio
    async def test_metrics_updated_on_distribution(self, reward_service, mock_token_system):
        """Test that metrics are updated after distribution"""
        reward = PendingReward(
            reward_id="reward_1",
            account_id="user_1",
            amount=Decimal("100.0"),
            reason="Test reward"
        )

        await reward_service.distribute_pending_rewards([reward])

        metrics = reward_service.get_metrics()

        assert metrics["successful_distributions"] == 1
        assert metrics["total_distributions"] == 1
        assert float(metrics["total_amount_distributed"]) == 100.0

    @pytest.mark.asyncio
    async def test_audit_log_populated(self, reward_service, mock_token_system):
        """Test that audit log is populated during distribution"""
        reward = PendingReward(
            reward_id="reward_1",
            account_id="user_1",
            amount=Decimal("50.0"),
            reason="Test reward"
        )

        await reward_service.distribute_pending_rewards([reward])

        audit_log = reward_service.get_audit_log()

        assert len(audit_log) == 1
        assert audit_log[0]["reward_id"] == "reward_1"
        assert audit_log[0]["account_id"] == "user_1"
        assert audit_log[0]["amount"] == 50.0
        assert audit_log[0]["status"] == "success"


class TestIntegration:
    """Integration tests simulating real-world scenarios"""

    @pytest.mark.asyncio
    async def test_full_deployment_deletion_flow(self, reward_service, mock_token_system):
        """Test full deployment deletion with reward distribution"""
        deployment_id = uuid4()
        user_id = uuid4()
        mock_db = MagicMock()

        # Simulate pending rewards from deployment runtime
        pending_rewards = [
            PendingReward(
                reward_id=f"deployment_{deployment_id}_reward",
                account_id=str(user_id),
                amount=Decimal("250.0"),
                reason="Deployment runtime rewards",
                deployment_id=deployment_id
            )
        ]

        with patch.object(reward_service, 'get_pending_rewards', return_value=pending_rewards):
            # Execute cleanup with distribution
            result = await reward_service.cleanup_with_distribution(
                deployment_id=deployment_id,
                user_id=user_id,
                db=mock_db
            )

        # Verify successful flow
        assert result.success is True
        assert result.rewards_distributed == 1
        assert result.rewards_amount == Decimal("250.0")
        assert result.cleanup_completed is True

        # Verify token transfer occurred
        mock_token_system.transfer.assert_called_once()

        # Verify metrics updated
        metrics = reward_service.get_metrics()
        assert metrics["successful_distributions"] == 1
        assert float(metrics["total_amount_distributed"]) == 250.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
