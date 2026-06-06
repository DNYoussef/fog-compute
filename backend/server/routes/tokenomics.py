"""
Tokenomics API Routes
Handles token balances, DAO governance, staking, and rewards
"""
import logging
import math
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..services.enhanced_service_manager import enhanced_service_manager as service_manager
from ..database import get_db
from ..middleware.api_key_auth import require_api_key
from ..models.database import TokenBalance

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tokenomics", tags=["tokenomics"])


def get_tokenomics_service():
    """
    Helper function to get and verify tokenomics service
    Raises HTTPException if service is unavailable or not initialized
    """
    dao = service_manager.get('dao')

    if dao is None:
        raise HTTPException(status_code=503, detail="Tokenomics service unavailable")

    if not getattr(dao, 'initialized', False):
        raise HTTPException(status_code=503, detail="Tokenomics service not initialized")

    return dao


def _finite_number(value: Any) -> float | None:
    """Return a finite numeric value, or None when the metric is unavailable."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
        if math.isfinite(numeric):
            return numeric
    return None


def _first_real_metric(source: Any, *names: str) -> float | None:
    for name in names:
        value = _finite_number(getattr(source, name, None))
        if value is not None:
            return value
    return None


class StakeRequest(BaseModel):
    address: str
    amount: float


class ProposalRequest(BaseModel):
    title: str
    description: str
    proposer: str


class VoteRequest(BaseModel):
    proposal_id: str
    voter: str
    vote: bool


@router.get("/stats")
async def get_tokenomics_stats() -> Dict[str, Any]:
    """
    Get overall tokenomics statistics

    Returns:
        - Total supply
        - Circulating supply
        - Staked tokens
        - Active stakers
        - Active proposals
        - Market cap
    """
    dao = get_tokenomics_service()

    try:
        # Get data from UnifiedDAOTokenomicsSystem
        total_supply = getattr(dao.token_manager, 'total_supply', 0)
        stakes = getattr(dao.token_manager, 'stakes', {})
        proposals = getattr(dao, 'proposals', {})

        # Calculate metrics
        total_staked = sum(stake.get('amount', 0) for stake in stakes.values())
        active_proposals = len([p for p in proposals.values() if p.get('status') == 'active'])

        token_price = _first_real_metric(
            dao.token_manager,
            "token_price",
            "price_usd",
            "current_price",
            "market_price",
        )
        staking_apr = _first_real_metric(
            dao.token_manager,
            "staking_apr",
            "reward_apr",
            "apr",
        )
        market_cap = total_supply * token_price if token_price is not None else None

        return {
            "totalSupply": total_supply,
            "circulatingSupply": total_supply - total_staked,
            "stakedTokens": total_staked,
            "activeStakers": len(stakes),
            "proposalsActive": active_proposals,
            "proposalsTotal": len(proposals),
            "tokenPrice": token_price,
            "marketCap": market_cap,
            "stakingAPR": staking_apr,
            "evidenceStatus": {
                "marketCap": "measured" if market_cap is not None else "unavailable_no_live_price_feed",
                "stakingAPR": "measured" if staking_apr is not None else "unavailable_no_reward_rate_model",
            },
        }
    except Exception as e:
        logger.error(f"Error fetching tokenomics stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/balance")
async def get_balance(address: str, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Get token balance for an address

    Args:
        address: Wallet address
        db: Database session

    Returns:
        Balance, staked amount, and total
    """
    try:
        # Try to get from database first
        from sqlalchemy import select
        result = await db.execute(select(TokenBalance).where(TokenBalance.address == address))
        token_balance = result.scalar_one_or_none()

        if token_balance:
            return token_balance.to_dict()

        # If not in database, try the DAO service
        dao = service_manager.get('dao')
        if dao is not None:
            try:
                balance = dao.token_manager.get_balance(address)
                stakes = dao.token_manager.stakes.get(address, {})
                staked = stakes.get('amount', 0)

                return {
                    "address": address,
                    "balance": balance,
                    "staked": staked,
                    "total": balance + staked,
                    "rewards": stakes.get('rewards', 0)
                }
            except Exception as e:
                logger.warning(f"DAO service error: {e}")

        # Return default balance if address not found
        return {
            "address": address,
            "balance": 0.0,
            "staked": 0.0,
            "rewards": 0.0,
            "total": 0.0,
            "updated_at": None
        }
    except Exception as e:
        logger.error(f"Error fetching balance for {address}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stake")
async def stake_tokens(
    request: StakeRequest,
    _api_key: Dict[str, Any] = Depends(require_api_key),
) -> Dict[str, Any]:
    """
    Stake tokens for rewards

    Args:
        address: Wallet address
        amount: Amount to stake

    Returns:
        Success status and new stake amount
    """
    dao = get_tokenomics_service()

    try:
        # Call stake method
        result = dao.token_manager.stake(request.address, request.amount)

        return {
            "success": True,
            "address": request.address,
            "stakedAmount": request.amount,
            "totalStaked": result.get('total_staked', request.amount)
        }
    except Exception as e:
        logger.error(f"Error staking tokens: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/unstake")
async def unstake_tokens(
    request: StakeRequest,
    _api_key: Dict[str, Any] = Depends(require_api_key),
) -> Dict[str, Any]:
    """Unstake tokens"""
    dao = get_tokenomics_service()

    try:
        result = dao.token_manager.unstake(request.address, request.amount)

        return {
            "success": True,
            "address": request.address,
            "unstakedAmount": request.amount,
            "totalStaked": result.get('total_staked', 0)
        }
    except Exception as e:
        logger.error(f"Error unstaking tokens: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/proposals")
async def get_proposals() -> Dict[str, Any]:
    """Get all DAO proposals"""
    dao = get_tokenomics_service()

    try:
        proposals = dao.proposals

        return {
            "proposals": [
                {
                    "id": prop_id,
                    "title": prop.get('title'),
                    "description": prop.get('description'),
                    "proposer": prop.get('proposer'),
                    "status": prop.get('status'),
                    "votesFor": prop.get('votes_for', 0),
                    "votesAgainst": prop.get('votes_against', 0),
                    "createdAt": prop.get('created_at')
                }
                for prop_id, prop in proposals.items()
            ]
        }
    except Exception as e:
        logger.error(f"Error fetching proposals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/proposals")
async def create_proposal(
    request: ProposalRequest,
    _api_key: Dict[str, Any] = Depends(require_api_key),
) -> Dict[str, Any]:
    """Create a new DAO proposal"""
    dao = get_tokenomics_service()

    try:
        proposal_id = dao.create_proposal(
            title=request.title,
            description=request.description,
            proposer=request.proposer
        )

        return {
            "success": True,
            "proposalId": proposal_id
        }
    except Exception as e:
        logger.error(f"Error creating proposal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vote")
async def vote_on_proposal(
    request: VoteRequest,
    _api_key: Dict[str, Any] = Depends(require_api_key),
) -> Dict[str, Any]:
    """Vote on a DAO proposal"""
    dao = get_tokenomics_service()

    try:
        dao.vote(
            proposal_id=request.proposal_id,
            voter=request.voter,
            vote=request.vote
        )

        return {
            "success": True,
            "proposalId": request.proposal_id,
            "vote": "for" if request.vote else "against"
        }
    except Exception as e:
        logger.error(f"Error voting: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rewards")
async def get_rewards(address: str) -> Dict[str, Any]:
    """Get pending rewards for an address"""
    dao = get_tokenomics_service()

    try:
        rewards = dao.token_manager.get_pending_rewards(address)

        rewards_rate = _first_real_metric(
            dao.token_manager,
            "rewards_rate",
            "staking_apr",
            "reward_apr",
            "apr",
        )

        return {
            "address": address,
            "pendingRewards": rewards,
            "rewardsRate": rewards_rate,
            "evidenceStatus": {
                "rewardsRate": "measured" if rewards_rate is not None else "unavailable_no_reward_rate_model",
            },
        }
    except Exception as e:
        logger.error(f"Error fetching rewards: {e}")
        raise HTTPException(status_code=500, detail=str(e))
