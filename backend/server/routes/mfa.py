"""
MFA (Multi-Factor Authentication) API Routes
TOTP-based MFA for admin accounts using pyotp.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
import hashlib
import logging

from ..database import get_db
from ..models.database import User
from ..schemas.auth import (
    MFASetupResponse,
    MFAVerifyRequest,
    MFAVerifyResponse,
    MFAStatusResponse,
    MFADisableRequest,
)
from ..auth import get_current_active_user, verify_password
from ..services.mfa_service import get_mfa_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth/mfa", tags=["mfa"])


def hash_backup_code(code: str) -> str:
    """Hash a backup code for secure storage."""
    return hashlib.sha256(code.encode()).hexdigest()


@router.get("/status", response_model=MFAStatusResponse)
async def get_mfa_status(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get MFA status for current user.

    **Requires:** Valid JWT token

    **Returns:**
    - Whether MFA is enabled and verified
    - Number of remaining backup codes
    """
    backup_count = 0
    if current_user.mfa_backup_codes:
        # Count non-null (unused) backup codes
        backup_count = sum(1 for code in current_user.mfa_backup_codes if code)

    return MFAStatusResponse(
        mfa_enabled=current_user.mfa_enabled,
        mfa_verified=current_user.mfa_verified,
        backup_codes_remaining=backup_count,
        enabled_at=current_user.mfa_enabled_at
    )


@router.post("/setup", response_model=MFASetupResponse)
async def setup_mfa(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Initialize MFA setup for admin account.

    **Requires:** Valid JWT token, admin privileges

    **Returns:**
    - TOTP secret (store securely, shown only once)
    - Provisioning URI for QR code
    - Backup codes (store securely, shown only once)

    **Note:** MFA is required for admin accounts.
    """
    # Check if user is admin
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MFA is currently only available for admin accounts"
        )

    # Check if MFA is already enabled
    if current_user.mfa_enabled and current_user.mfa_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is already enabled. Disable it first to set up again."
        )

    mfa_service = get_mfa_service()

    # Generate MFA setup data
    setup_data = mfa_service.setup_mfa(current_user.email)

    # Hash backup codes for storage
    hashed_backup_codes = [hash_backup_code(code) for code in setup_data.backup_codes]

    # Store secret and hashed backup codes (not yet verified)
    current_user.mfa_secret = setup_data.secret
    current_user.mfa_backup_codes = hashed_backup_codes
    current_user.mfa_enabled = False  # Will be enabled after verification
    current_user.mfa_verified = False

    await db.commit()

    logger.info(f"MFA setup initiated for user {current_user.username}")

    return MFASetupResponse(
        secret=setup_data.secret,
        provisioning_uri=setup_data.provisioning_uri,
        backup_codes=setup_data.backup_codes,
        message="Scan QR code with authenticator app, then verify with /api/auth/mfa/verify"
    )


@router.post("/verify", response_model=MFAVerifyResponse)
async def verify_mfa_setup(
    request: MFAVerifyRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Verify MFA setup with a TOTP code.

    **Requires:** Valid JWT token, MFA setup initiated

    **Request Body:**
    - code: 6-digit code from authenticator app

    **Returns:**
    - Verification status
    - Number of backup codes remaining
    """
    if not current_user.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA setup not initiated. Call /api/auth/mfa/setup first."
        )

    if current_user.mfa_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is already verified."
        )

    mfa_service = get_mfa_service()

    # Verify the TOTP code
    if not mfa_service.verify_totp(current_user.mfa_secret, request.code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MFA code. Please try again."
        )

    # Enable MFA
    current_user.mfa_enabled = True
    current_user.mfa_verified = True
    current_user.mfa_enabled_at = datetime.now(timezone.utc)

    await db.commit()

    backup_count = len(current_user.mfa_backup_codes) if current_user.mfa_backup_codes else 0

    logger.info(f"MFA enabled for user {current_user.username}")

    return MFAVerifyResponse(
        verified=True,
        message="MFA has been successfully enabled for your account.",
        backup_codes_remaining=backup_count
    )


@router.post("/validate", response_model=MFAVerifyResponse)
async def validate_mfa_code(
    request: MFAVerifyRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Validate an MFA code (TOTP or backup code).

    **Requires:** Valid JWT token, MFA enabled

    **Request Body:**
    - code: 6-digit TOTP or XXXX-XXXX backup code

    **Returns:**
    - Validation status
    - Remaining backup codes (if backup code was used)
    """
    if not current_user.mfa_enabled or not current_user.mfa_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is not enabled for this account."
        )

    mfa_service = get_mfa_service()
    code = request.code.strip()

    # First try TOTP
    if mfa_service.verify_totp(current_user.mfa_secret, code):
        return MFAVerifyResponse(
            verified=True,
            message="MFA code verified successfully."
        )

    # Try backup code
    if current_user.mfa_backup_codes:
        is_valid, used_index = mfa_service.verify_backup_code(
            code,
            current_user.mfa_backup_codes,
            hash_backup_code
        )

        if is_valid and used_index is not None:
            # Invalidate used backup code
            current_user.mfa_backup_codes[used_index] = None
            await db.commit()

            remaining = sum(1 for c in current_user.mfa_backup_codes if c)
            logger.warning(f"Backup code used for user {current_user.username}. {remaining} remaining.")

            return MFAVerifyResponse(
                verified=True,
                message=f"Backup code accepted. {remaining} backup codes remaining.",
                backup_codes_remaining=remaining
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid MFA code."
    )


@router.post("/disable")
async def disable_mfa(
    request: MFADisableRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Disable MFA for current user.

    **Requires:** Valid JWT token, password confirmation, valid MFA code

    **Request Body:**
    - password: Current password for confirmation
    - code: Valid TOTP code

    **Returns:**
    - Success status
    """
    if not current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is not enabled for this account."
        )

    # Verify password
    if not verify_password(request.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password."
        )

    mfa_service = get_mfa_service()

    # Verify MFA code
    if not mfa_service.verify_totp(current_user.mfa_secret, request.code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MFA code."
        )

    # Disable MFA
    current_user.mfa_secret = None
    current_user.mfa_enabled = False
    current_user.mfa_verified = False
    current_user.mfa_backup_codes = None
    current_user.mfa_enabled_at = None

    await db.commit()

    logger.info(f"MFA disabled for user {current_user.username}")

    return {
        "success": True,
        "message": "MFA has been disabled for your account."
    }


@router.post("/regenerate-backup-codes")
async def regenerate_backup_codes(
    request: MFAVerifyRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Regenerate backup codes (invalidates old ones).

    **Requires:** Valid JWT token, MFA enabled, valid TOTP code

    **Request Body:**
    - code: Current TOTP code for verification

    **Returns:**
    - New backup codes (store securely, shown only once)
    """
    if not current_user.mfa_enabled or not current_user.mfa_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is not enabled for this account."
        )

    mfa_service = get_mfa_service()

    # Verify TOTP code
    if not mfa_service.verify_totp(current_user.mfa_secret, request.code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MFA code."
        )

    # Generate new backup codes
    new_backup_codes = mfa_service.generate_backup_codes()
    hashed_codes = [hash_backup_code(code) for code in new_backup_codes]

    current_user.mfa_backup_codes = hashed_codes
    await db.commit()

    logger.info(f"Backup codes regenerated for user {current_user.username}")

    return {
        "success": True,
        "backup_codes": new_backup_codes,
        "message": "New backup codes generated. Store them securely - they will not be shown again."
    }
