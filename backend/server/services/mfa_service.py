"""
MFA Service
Multi-Factor Authentication using TOTP (Time-based One-Time Password).
Implements RFC 6238 TOTP with pyotp.
"""
import secrets
import logging
from datetime import datetime, timezone
from typing import Optional, List, Tuple
from dataclasses import dataclass

import pyotp

logger = logging.getLogger(__name__)

# MFA Configuration
MFA_ISSUER = "FogCompute"
MFA_DIGITS = 6
MFA_INTERVAL = 30  # seconds
BACKUP_CODE_COUNT = 10
BACKUP_CODE_LENGTH = 8


@dataclass
class MFASetupData:
    """MFA setup response data"""
    secret: str
    provisioning_uri: str
    backup_codes: List[str]


@dataclass
class MFAStatus:
    """MFA status for a user"""
    enabled: bool
    verified: bool
    backup_codes_remaining: int
    created_at: Optional[datetime] = None


class MFAService:
    """
    Service for managing Multi-Factor Authentication.

    Features:
    - TOTP setup and verification
    - Backup codes for recovery
    - Admin-only enforcement (configurable)
    """

    def generate_secret(self) -> str:
        """
        Generate a new TOTP secret.

        Returns:
            Base32-encoded secret key
        """
        return pyotp.random_base32()

    def generate_provisioning_uri(
        self,
        secret: str,
        username: str,
        issuer: str = MFA_ISSUER
    ) -> str:
        """
        Generate QR code provisioning URI for authenticator apps.

        Args:
            secret: TOTP secret
            username: User's username/email for display
            issuer: Service name (e.g., "FogCompute")

        Returns:
            otpauth:// URI for QR code generation
        """
        totp = pyotp.TOTP(secret, digits=MFA_DIGITS, interval=MFA_INTERVAL)
        return totp.provisioning_uri(name=username, issuer_name=issuer)

    def verify_totp(self, secret: str, code: str, valid_window: int = 1) -> bool:
        """
        Verify a TOTP code.

        Args:
            secret: User's TOTP secret
            code: 6-digit code from authenticator
            valid_window: Number of 30-second windows to check (default: 1)

        Returns:
            True if code is valid
        """
        if not secret or not code:
            return False

        try:
            totp = pyotp.TOTP(secret, digits=MFA_DIGITS, interval=MFA_INTERVAL)
            # valid_window=1 allows for clock drift (current + 1 previous/next)
            return totp.verify(code, valid_window=valid_window)
        except Exception as e:
            logger.error(f"TOTP verification error: {e}")
            return False

    def generate_backup_codes(self, count: int = BACKUP_CODE_COUNT) -> List[str]:
        """
        Generate backup codes for MFA recovery.

        Args:
            count: Number of backup codes to generate

        Returns:
            List of backup codes (plaintext - hash before storing)
        """
        codes = []
        for _ in range(count):
            # Generate 8-character alphanumeric code
            code = secrets.token_hex(BACKUP_CODE_LENGTH // 2).upper()
            # Format as XXXX-XXXX for readability
            formatted = f"{code[:4]}-{code[4:]}"
            codes.append(formatted)
        return codes

    def verify_backup_code(
        self,
        code: str,
        stored_hashes: List[str],
        hash_func
    ) -> Tuple[bool, Optional[int]]:
        """
        Verify a backup code against stored hashes.

        Args:
            code: Backup code to verify (with or without dash)
            stored_hashes: List of hashed backup codes
            hash_func: Function to hash the code for comparison

        Returns:
            Tuple of (is_valid, index_of_used_code)
        """
        # Normalize code (remove dashes, uppercase)
        normalized = code.replace("-", "").upper()
        # Re-add dash for consistent hashing
        formatted = f"{normalized[:4]}-{normalized[4:]}" if len(normalized) >= 8 else code

        code_hash = hash_func(formatted)

        for i, stored_hash in enumerate(stored_hashes):
            if stored_hash and secrets.compare_digest(code_hash, stored_hash):
                return True, i

        return False, None

    def get_current_code(self, secret: str) -> str:
        """
        Get current TOTP code (for testing/admin purposes).

        Args:
            secret: TOTP secret

        Returns:
            Current 6-digit code
        """
        totp = pyotp.TOTP(secret, digits=MFA_DIGITS, interval=MFA_INTERVAL)
        return totp.now()

    def setup_mfa(self, username: str) -> MFASetupData:
        """
        Initialize MFA setup for a user.

        Args:
            username: User's username/email

        Returns:
            MFASetupData with secret, URI, and backup codes
        """
        secret = self.generate_secret()
        provisioning_uri = self.generate_provisioning_uri(secret, username)
        backup_codes = self.generate_backup_codes()

        return MFASetupData(
            secret=secret,
            provisioning_uri=provisioning_uri,
            backup_codes=backup_codes
        )


# Global singleton instance
mfa_service = MFAService()


def get_mfa_service() -> MFAService:
    """Get MFA service instance."""
    return mfa_service
