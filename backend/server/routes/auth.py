"""
Authentication API Routes
User registration, login, token management, and account security.
Implements:
- JWT access tokens with blacklist support
- Refresh token rotation
- Account lockout after failed attempts
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta, timezone
from typing import Optional
import logging

from ..database import get_db
from ..models.database import User
from ..schemas.auth import UserCreate, UserLogin, UserResponse, Token
from ..auth import create_access_token, get_password_hash, verify_password, get_current_active_user, verify_token
from ..config import settings
from ..services.token_service import get_token_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["authentication"])
security = HTTPBearer(auto_error=False)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Register a new user

    **Request Body:**
    - username: Alphanumeric username (3-50 chars)
    - email: Valid email address
    - password: Strong password (8+ chars, uppercase, lowercase, digit)

    **Returns:**
    - User object with ID and metadata
    """
    # Check if username exists
    result = await db.execute(select(User).where(User.username == user_data.username.lower()))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    # Check if email exists
    result = await db.execute(select(User).where(User.email == user_data.email.lower()))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create new user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        username=user_data.username.lower(),
        email=user_data.email.lower(),
        hashed_password=hashed_password,
        is_active=True,
        is_admin=False,
        created_at=datetime.now(timezone.utc)
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    logger.info(f"New user registered: {new_user.username}")

    # Manually convert to response model with UUID handling
    return UserResponse(
        id=str(new_user.id),
        username=new_user.username,
        email=new_user.email,
        is_active=new_user.is_active,
        is_admin=new_user.is_admin,
        created_at=new_user.created_at
    )


@router.post("/login")
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    """
    Authenticate user and return JWT tokens.

    **Request Body:**
    - username: User's username
    - password: User's password

    **Returns:**
    - JWT access token (30 min expiry)
    - Refresh token (7 day expiry)
    - Token type (bearer)
    - Expiration time in seconds

    **Security Features:**
    - Account lockout after 5 failed attempts
    - 30 minute lockout duration
    - Refresh token for session extension
    """
    token_service = await get_token_service()

    # Find user first to get user_id for lockout tracking
    result = await db.execute(select(User).where(User.username == credentials.username.lower()))
    user = result.scalar_one_or_none()

    # Check account lockout before verifying password
    if user:
        is_locked, locked_until = await token_service.is_account_locked(str(user.id))
        if is_locked:
            remaining_minutes = int((locked_until - datetime.now(timezone.utc)).total_seconds() / 60)
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Account locked due to too many failed attempts. Try again in {remaining_minutes} minutes."
            )

    # Verify user exists and password is correct
    if not user or not verify_password(credentials.password, user.hashed_password):
        # Record failed login attempt
        if user:
            attempt_data = await token_service.record_login_attempt(str(user.id), success=False)
            remaining_attempts = 5 - attempt_data.attempts
            if remaining_attempts > 0:
                logger.warning(f"Failed login for {credentials.username}: {remaining_attempts} attempts remaining")
            else:
                logger.warning(f"Account {credentials.username} locked after too many failed attempts")

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )

    # Record successful login (clears failed attempts)
    await token_service.record_login_attempt(str(user.id), success=True)

    # Update last login
    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    # Create access token
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username}
    )

    # Create refresh token
    refresh_token, _ = await token_service.create_refresh_token(str(user.id))

    logger.info(f"User logged in: {user.username}")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """
    Get current authenticated user's information

    **Requires:** Valid JWT token in Authorization header

    **Returns:**
    - Current user's profile data
    """
    # Manually convert to response model with UUID handling
    return UserResponse(
        id=str(current_user.id),
        username=current_user.username,
        email=current_user.email,
        is_active=current_user.is_active,
        is_admin=current_user.is_admin,
        created_at=current_user.created_at
    )


@router.post("/logout")
async def logout(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """
    Logout user and blacklist current access token.

    **Authentication:** Optional - logout succeeds with or without valid token

    **Returns:**
    - 200: Logout successful (always succeeds)

    **Security Features:**
    - Adds access token to blacklist (prevents reuse)
    - Blacklist entries auto-expire with token
    - Idempotent operation (safe to call multiple times)
    """
    try:
        if credentials:
            token = credentials.credentials
            payload = verify_token(token)

            if payload:
                token_jti = payload.get("jti")
                token_exp = payload.get("exp")

                if token_jti and token_exp:
                    # Add token to blacklist
                    token_service = await get_token_service()
                    expires_at = datetime.fromtimestamp(token_exp, tz=timezone.utc)
                    await token_service.blacklist_token(token_jti, expires_at)

                    # Also revoke refresh tokens for this user
                    user_id = payload.get("sub")
                    if user_id:
                        await token_service.revoke_all_user_tokens(user_id)

                    logger.info(f"User logged out, token blacklisted: {token_jti[:8]}...")

        return {
            "success": True,
            "message": "Successfully logged out"
        }

    except Exception as e:
        # Even on error, return 200 (logout is idempotent and fail-safe)
        logger.error(f"Logout error (non-blocking): {e}", exc_info=True)
        return {
            "success": True,
            "message": "Successfully logged out"
        }


@router.post("/refresh")
async def refresh_token(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using a valid refresh token.

    **Request Body:**
    - refresh_token: Valid refresh token from login

    **Returns:**
    - New JWT access token
    - New refresh token (token rotation)
    - Token type (bearer)
    - Expiration time in seconds

    **Security Features:**
    - Refresh token rotation (old token invalidated)
    - User validation (ensures user still exists and is active)
    """
    try:
        body = await request.json()
        refresh_token_str = body.get("refresh_token")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request body"
        )

    if not refresh_token_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refresh token is required"
        )

    token_service = await get_token_service()

    # Validate refresh token
    token_data = await token_service.validate_refresh_token(refresh_token_str)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify user still exists and is active
    result = await db.execute(select(User).where(User.id == token_data.user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )

    # Revoke old refresh token (token rotation)
    await token_service.revoke_refresh_token(refresh_token_str)

    # Create new access token
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username}
    )

    # Create new refresh token
    new_refresh_token, _ = await token_service.create_refresh_token(str(user.id))

    logger.info(f"Token refreshed for user: {user.username}")

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }
