"""
API Key Management Routes
Create, list, and revoke API keys for service account authentication
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from typing import List, Optional
from uuid import UUID
import logging

from ..database import get_db
from ..models.database import APIKey, User
from ..auth.dependencies import get_current_active_user
from ..auth.api_key import APIKeyManager
from ..schemas.api_keys import (
    APIKeyCreate,
    APIKeyResponse,
    APIKeyWithSecret,
    APIKeyList
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/keys", tags=["api-keys"])


@router.post("/", response_model=APIKeyWithSecret, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    key_data: APIKeyCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new API key for the current user

    **Authentication:** JWT token required

    **Request Body:**
    - name: Descriptive name for the key (e.g., "Production Server", "CI/CD Pipeline")
    - expires_in_days: Optional expiration in days (null = no expiration)
    - rate_limit: Requests per hour limit (default: 1000)

    **Returns:**
    - API key object with the secret key (SHOWN ONLY ONCE!)

    **Important:**
    - The secret key is displayed ONLY on creation and cannot be retrieved again
    - Store the key securely immediately after creation
    - The key is hashed in the database and cannot be recovered

    **Example Response:**
    ```json
    {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "name": "Production Server",
        "secret_key": "fog_sk_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v",
        "rate_limit": 1000,
        "is_active": true,
        "created_at": "2024-01-15T10:30:00Z",
        "expires_at": "2024-07-15T10:30:00Z"
    }
    ```
    """
    # Create the key
    plain_key, api_key = await APIKeyManager.create_key(
        user_id=str(current_user.id),
        name=key_data.name,
        db=db,
        expires_in_days=key_data.expires_in_days,
        rate_limit=key_data.rate_limit
    )

    logger.info(
        f"API key created: {key_data.name} for user {current_user.username} "
        f"(expires: {api_key.expires_at if api_key.expires_at else 'never'})"
    )

    # Return with secret key (ONLY TIME IT'S VISIBLE)
    return APIKeyWithSecret(
        id=str(api_key.id),
        name=api_key.name,
        secret_key=plain_key,  # Plain text key - shown only once!
        rate_limit=api_key.rate_limit,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        last_used=api_key.last_used,
        expires_at=api_key.expires_at
    )


@router.get("/", response_model=APIKeyList)
async def list_api_keys(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    include_inactive: bool = False
):
    """
    List all API keys for the current user

    **Authentication:** JWT token required

    **Query Parameters:**
    - include_inactive: Include revoked/inactive keys (default: false)

    **Returns:**
    - List of API key metadata (secret keys are NOT included)

    **Security Note:**
    - Secret keys are never returned in list operations
    - Only metadata like name, creation date, and usage stats are shown
    """
    # Build query
    query = select(APIKey).where(APIKey.user_id == current_user.id)

    if not include_inactive:
        query = query.where(APIKey.is_active == True)

    # Execute query
    result = await db.execute(query.order_by(APIKey.created_at.desc()))
    api_keys = result.scalars().all()

    # Convert to response models
    keys_response = [
        APIKeyResponse(
            id=str(key.id),
            name=key.name,
            rate_limit=key.rate_limit,
            is_active=key.is_active,
            created_at=key.created_at,
            last_used=key.last_used,
            expires_at=key.expires_at
        )
        for key in api_keys
    ]

    return APIKeyList(keys=keys_response, total=len(keys_response))


@router.get("/{key_id}", response_model=APIKeyResponse)
async def get_api_key(
    key_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get details of a specific API key

    **Authentication:** JWT token required

    **Path Parameters:**
    - key_id: UUID of the API key

    **Returns:**
    - API key metadata (secret key is NOT included)

    **Errors:**
    - 404: Key not found or doesn't belong to current user
    """
    # Parse UUID
    try:
        key_uuid = UUID(key_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid key ID format"
        )

    # Query key
    result = await db.execute(
        select(APIKey).where(
            APIKey.id == key_uuid,
            APIKey.user_id == current_user.id
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )

    return APIKeyResponse(
        id=str(api_key.id),
        name=api_key.name,
        rate_limit=api_key.rate_limit,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        last_used=api_key.last_used,
        expires_at=api_key.expires_at
    )


@router.delete("/{key_id}", status_code=status.HTTP_200_OK)
async def revoke_api_key(
    key_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Revoke (deactivate) an API key

    **Authentication:** JWT token required

    **Path Parameters:**
    - key_id: UUID of the API key to revoke

    **Returns:**
    - Success message

    **Errors:**
    - 404: Key not found or doesn't belong to current user

    **Security Note:**
    - Revocation is permanent - the key cannot be reactivated
    - Create a new key if you need to restore access
    - Revoked keys remain in the database for audit purposes
    """
    # Parse UUID
    try:
        key_uuid = UUID(key_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid key ID format"
        )

    # Verify key belongs to user
    result = await db.execute(
        select(APIKey).where(
            APIKey.id == key_uuid,
            APIKey.user_id == current_user.id
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )

    # Revoke the key
    success = await APIKeyManager.revoke_key(key_id, db)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke API key"
        )

    logger.info(
        f"API key revoked: {api_key.name} by user {current_user.username}"
    )

    return {
        "success": True,
        "message": f"API key '{api_key.name}' has been revoked",
        "key_id": key_id
    }
