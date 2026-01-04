"""
Authentication Dependencies
FastAPI dependency injection for protected routes
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from .jwt_utils import verify_token
from ..database import get_db
from ..models.database import User
from ..services.token_service import get_token_service

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token.
    Checks token validity and blacklist status.

    Args:
        credentials: HTTP Bearer token from request
        db: Database session

    Returns:
        Authenticated user object

    Raises:
        HTTPException: If token is invalid, blacklisted, or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Verify token
    token = credentials.credentials
    payload = verify_token(token)

    if payload is None:
        raise credentials_exception

    # Check if token is blacklisted (for logout/revocation)
    token_jti = payload.get("jti")
    if token_jti:
        token_service = await get_token_service()
        if await token_service.is_token_blacklisted(token_jti):
            logger.warning(f"Blacklisted token used: {token_jti[:8]}...")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Extract user ID from token
    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    # Fetch user from database
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current active user (not disabled)

    Args:
        current_user: Current authenticated user

    Returns:
        Active user object

    Raises:
        HTTPException: If user is disabled
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )

    return current_user


def require_auth(user: User = Depends(get_current_active_user)) -> User:
    """
    Simplified dependency for requiring authentication

    Args:
        user: Current active user

    Returns:
        Authenticated and active user
    """
    return user
