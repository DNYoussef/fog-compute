"""
Authentication API Routes
User registration, login, and token management
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
import logging

from ..database import get_db
from ..models.database import User
from ..schemas.auth import UserCreate, UserLogin, UserResponse, Token
from ..auth import create_access_token, get_password_hash, verify_password, get_current_active_user
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["authentication"])


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
        created_at=datetime.utcnow()
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


@router.post("/login", response_model=Token)
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    """
    Authenticate user and return JWT token

    **Request Body:**
    - username: User's username
    - password: User's password

    **Returns:**
    - JWT access token
    - Token type (bearer)
    - Expiration time in seconds
    """
    # Find user
    result = await db.execute(select(User).where(User.username == credentials.username.lower()))
    user = result.scalar_one_or_none()

    # Verify user exists and password is correct
    if not user or not verify_password(credentials.password, user.hashed_password):
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

    # Update last login
    user.last_login = datetime.utcnow()
    await db.commit()

    # Create access token
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username}
    )

    logger.info(f"User logged in: {user.username}")

    return {
        "access_token": access_token,
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
async def logout():
    """
    Logout user (idempotent operation)

    **Authentication:** Optional - logout succeeds with or without valid token

    **Returns:**
    - 200: Logout successful (always succeeds)

    **Design Rationale:**
    Logout is idempotent and follows senior-grade API standards:
    - Always returns 200 OK regardless of token validity
    - No token required (already logged out scenario)
    - Invalid token accepted (token expired/revoked scenario)
    - Fail-safe design (errors don't block logout)

    **Security Model:**
    JWTs are stateless and client-side managed. Logout is primarily a
    client-side operation (delete token from storage). For server-side
    token revocation, implement:
    - Token blacklist with Redis cache
    - Refresh token revocation in database
    - Shorter token expiration times (current: 30min)

    **Future Enhancements:**
    - Clear refresh token cookie if using cookie-based sessions
    - Revoke refresh tokens from database
    - Clear user sessions from cache
    - Emit logout event for audit logging
    """
    try:
        # Log successful logout attempt (no user context required)
        # If we had refresh token cookies, clear them here:
        # response.delete_cookie(
        #     key="refresh_token",
        #     path="/",
        #     secure=True,
        #     httponly=True,
        #     samesite="lax"
        # )

        logger.info("Logout request processed successfully")

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
