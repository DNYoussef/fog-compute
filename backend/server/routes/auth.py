"""
Authentication API Routes
User registration, login, token management, and account security.
Implements:
- JWT access tokens with blacklist support
- Refresh token rotation
- Account lockout after failed attempts
- MFA (Multi-Factor Authentication) for admin accounts
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
from ..schemas.auth import (
    UserCreate, UserLogin, UserResponse, Token, MFAVerifyRequest,
    PasswordResetRequest, PasswordResetConfirm, PasswordResetResponse
)
from ..auth import create_access_token, get_password_hash, verify_password, get_current_active_user, verify_token
from ..config import settings
from ..services.token_service import get_token_service
from ..services.mfa_service import get_mfa_service
from ..services.email_service import get_email_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["authentication"])
security = HTTPBearer(auto_error=False)

# MFA temp token prefix for Redis
MFA_TEMP_TOKEN_PREFIX = "mfa_pending:"
MFA_TEMP_TOKEN_EXPIRE_SECONDS = 300  # 5 minutes


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

    # Check if MFA is required for this user (admin with MFA enabled)
    if user.is_admin and user.mfa_enabled and user.mfa_verified:
        # Generate a temporary token for MFA verification
        import secrets
        temp_token = secrets.token_urlsafe(32)

        # Store temp token in Redis with user_id (5 min expiry)
        if token_service.is_connected:
            key = f"{MFA_TEMP_TOKEN_PREFIX}{temp_token}"
            await token_service._redis.setex(
                key,
                MFA_TEMP_TOKEN_EXPIRE_SECONDS,
                str(user.id)
            )
        else:
            # In-memory fallback (for dev/testing)
            if not hasattr(token_service, '_mfa_pending'):
                token_service._mfa_pending = {}
            token_service._mfa_pending[temp_token] = {
                'user_id': str(user.id),
                'expires': datetime.now(timezone.utc) + timedelta(seconds=MFA_TEMP_TOKEN_EXPIRE_SECONDS)
            }

        logger.info(f"MFA required for admin user: {user.username}")

        return {
            "mfa_required": True,
            "temp_token": temp_token,
            "message": "MFA verification required. Use /api/auth/login/mfa to complete login.",
            "expires_in": MFA_TEMP_TOKEN_EXPIRE_SECONDS
        }

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


@router.post("/login/mfa")
async def complete_mfa_login(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Complete MFA login with TOTP code.

    **Request Body:**
    - temp_token: Temporary token from initial login
    - mfa_code: 6-digit TOTP code or backup code

    **Returns:**
    - JWT access token
    - Refresh token
    - Token type
    - Expiration time
    """
    try:
        body = await request.json()
        temp_token = body.get("temp_token")
        mfa_code = body.get("mfa_code")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request body"
        )

    if not temp_token or not mfa_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="temp_token and mfa_code are required"
        )

    token_service = await get_token_service()

    # Retrieve user_id from temp token
    user_id = None
    if token_service.is_connected:
        key = f"{MFA_TEMP_TOKEN_PREFIX}{temp_token}"
        user_id = await token_service._redis.get(key)
        if user_id:
            await token_service._redis.delete(key)  # One-time use
    else:
        # In-memory fallback
        if hasattr(token_service, '_mfa_pending') and temp_token in token_service._mfa_pending:
            pending = token_service._mfa_pending[temp_token]
            if pending['expires'] > datetime.now(timezone.utc):
                user_id = pending['user_id']
            del token_service._mfa_pending[temp_token]

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired MFA token. Please login again."
        )

    # Get user from database
    from uuid import UUID
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    # Verify MFA code
    mfa_service = get_mfa_service()
    code = mfa_code.strip()
    mfa_valid = False
    backup_used = False

    # Try TOTP first
    if mfa_service.verify_totp(user.mfa_secret, code):
        mfa_valid = True
    elif user.mfa_backup_codes:
        # Try backup code
        import hashlib
        def hash_code(c): return hashlib.sha256(c.encode()).hexdigest()
        is_valid, used_index = mfa_service.verify_backup_code(code, user.mfa_backup_codes, hash_code)
        if is_valid and used_index is not None:
            mfa_valid = True
            backup_used = True
            user.mfa_backup_codes[used_index] = None
            remaining = sum(1 for c in user.mfa_backup_codes if c)
            logger.warning(f"Backup code used during login for {user.username}. {remaining} remaining.")

    if not mfa_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MFA code"
        )

    # Update last login
    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    # Create access token
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username}
    )

    # Create refresh token
    refresh_token, _ = await token_service.create_refresh_token(str(user.id))

    logger.info(f"MFA login completed for admin user: {user.username}")

    response = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

    if backup_used:
        remaining = sum(1 for c in user.mfa_backup_codes if c) if user.mfa_backup_codes else 0
        response["warning"] = f"Backup code used. {remaining} backup codes remaining."

    return response


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


# Rate limiting for password reset requests (in-memory, simple)
_reset_request_counts: dict = {}
_RESET_RATE_LIMIT = 3  # Max requests per email per hour
_RESET_RATE_WINDOW = 3600  # 1 hour in seconds


@router.post("/password-reset/request", response_model=PasswordResetResponse)
async def request_password_reset(
    request_data: PasswordResetRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Request a password reset email.

    **Request Body:**
    - email: Email address associated with the account

    **Returns:**
    - Success message (always returns success to prevent email enumeration)

    **Security Features:**
    - Rate limited: 3 requests per email per hour
    - Generic response prevents email enumeration attacks
    - Token expires in 60 minutes
    - Token is single-use
    """
    email = request_data.email.lower()

    # Rate limiting check
    import time
    current_time = time.time()
    if email in _reset_request_counts:
        requests = _reset_request_counts[email]
        # Clean old requests
        requests = [t for t in requests if current_time - t < _RESET_RATE_WINDOW]
        _reset_request_counts[email] = requests

        if len(requests) >= _RESET_RATE_LIMIT:
            logger.warning(f"Rate limit exceeded for password reset: {email}")
            # Still return success to prevent enumeration
            return PasswordResetResponse(
                message="If an account exists with that email, a password reset link has been sent."
            )
    else:
        _reset_request_counts[email] = []

    # Record this request
    _reset_request_counts[email].append(current_time)

    # Look up user by email
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        # Don't reveal that the email doesn't exist
        logger.info(f"Password reset requested for non-existent email: {email}")
        return PasswordResetResponse(
            message="If an account exists with that email, a password reset link has been sent."
        )

    if not user.is_active:
        # Don't reveal that the account is disabled
        logger.info(f"Password reset requested for disabled account: {email}")
        return PasswordResetResponse(
            message="If an account exists with that email, a password reset link has been sent."
        )

    # Create password reset token
    token_service = await get_token_service()
    token_data = await token_service.create_password_reset_token(
        user_id=str(user.id),
        email=email
    )

    # Send password reset email
    email_service = get_email_service()
    email_sent = await email_service.send_password_reset_email(
        to_email=email,
        reset_token=token_data.token,
        username=user.username
    )

    if not email_sent:
        logger.error(f"Failed to send password reset email to: {email}")
        # Still return success to prevent enumeration
        return PasswordResetResponse(
            message="If an account exists with that email, a password reset link has been sent."
        )

    logger.info(f"Password reset email sent to: {email}")

    return PasswordResetResponse(
        message="If an account exists with that email, a password reset link has been sent."
    )


@router.post("/password-reset/confirm", response_model=PasswordResetResponse)
async def confirm_password_reset(
    request_data: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db)
):
    """
    Reset password using a valid reset token.

    **Request Body:**
    - token: Password reset token from email
    - new_password: New password (8+ chars, uppercase, lowercase, digit)

    **Returns:**
    - Success message on password reset

    **Security Features:**
    - Token is validated and consumed (single-use)
    - All user's other reset tokens are invalidated
    - All existing refresh tokens are revoked (logout everywhere)
    - Password complexity is validated
    """
    token_service = await get_token_service()

    # Validate reset token
    token_data = await token_service.validate_password_reset_token(request_data.token)

    if not token_data:
        logger.warning(f"Invalid or expired password reset token used")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )

    # Get user from database
    from uuid import UUID
    try:
        user_uuid = UUID(token_data.user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token"
        )

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()

    if not user:
        logger.warning(f"Password reset attempted for non-existent user: {token_data.user_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token"
        )

    if not user.is_active:
        logger.warning(f"Password reset attempted for disabled account: {user.username}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )

    # Consume the reset token (mark as used)
    consumed = await token_service.consume_password_reset_token(request_data.token)
    if not consumed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has already been used"
        )

    # Invalidate all other pending reset tokens for this user
    await token_service.invalidate_user_reset_tokens(str(user.id))

    # Update the user's password
    user.hashed_password = get_password_hash(request_data.new_password)
    await db.commit()

    # Revoke all refresh tokens for this user (security: logout everywhere)
    await token_service.revoke_all_user_tokens(str(user.id))

    logger.info(f"Password reset completed for user: {user.username}")

    return PasswordResetResponse(
        message="Password has been reset successfully. Please log in with your new password."
    )
