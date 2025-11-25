"""
API Key Authentication Utilities
Secure generation, hashing, and validation of API keys
"""
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..models.database import APIKey, User


class APIKeyManager:
    """Manager for API key generation and validation"""

    # Key format: fog_sk_<32 random bytes base64>
    KEY_PREFIX = "fog_sk_"
    KEY_LENGTH = 32  # bytes (256 bits)

    @classmethod
    def generate_key(cls) -> str:
        """
        Generate a secure random API key

        Returns:
            String in format: fog_sk_<random_base64>

        Example:
            fog_sk_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
        """
        # Generate 32 random bytes (256 bits)
        random_bytes = secrets.token_bytes(cls.KEY_LENGTH)
        # Convert to URL-safe base64 (no padding)
        random_str = secrets.token_urlsafe(cls.KEY_LENGTH)[:43]  # 43 chars for 32 bytes

        return f"{cls.KEY_PREFIX}{random_str}"

    @classmethod
    def hash_key(cls, api_key: str) -> str:
        """
        Hash an API key using SHA-256

        Args:
            api_key: Plain text API key

        Returns:
            Hexadecimal hash string

        Note:
            We use SHA-256 instead of bcrypt because:
            1. API keys are already high-entropy (256 bits)
            2. SHA-256 is faster for API request validation
            3. No need for bcrypt's adaptive cost (keys are not user passwords)
        """
        return hashlib.sha256(api_key.encode('utf-8')).hexdigest()

    @classmethod
    def verify_key_format(cls, api_key: str) -> bool:
        """
        Verify API key has correct format

        Args:
            api_key: API key to verify

        Returns:
            True if format is valid, False otherwise
        """
        if not api_key.startswith(cls.KEY_PREFIX):
            return False

        # Check length (prefix + 43 chars)
        expected_length = len(cls.KEY_PREFIX) + 43
        if len(api_key) != expected_length:
            return False

        # Check key part is alphanumeric + URL-safe chars
        key_part = api_key[len(cls.KEY_PREFIX):]
        return all(c.isalnum() or c in '-_' for c in key_part)

    @classmethod
    async def validate_key(
        cls,
        api_key: str,
        db: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """
        Validate an API key against database

        Args:
            api_key: Plain text API key from request
            db: Database session

        Returns:
            Dictionary with user and key metadata if valid, None otherwise

        Validation checks:
        1. Format is correct
        2. Hash exists in database
        3. Key is active
        4. Key has not expired
        5. User is active
        """
        # Check format first (fast rejection)
        if not cls.verify_key_format(api_key):
            return None

        # Hash the key
        key_hash = cls.hash_key(api_key)

        # Query database for matching hash
        result = await db.execute(
            select(APIKey, User)
            .join(User, APIKey.user_id == User.id)
            .where(APIKey.key_hash == key_hash)
        )
        row = result.first()

        if not row:
            return None

        api_key_obj, user = row

        # Validate key is active
        if not api_key_obj.is_active:
            return None

        # Validate key has not expired
        if api_key_obj.expires_at and api_key_obj.expires_at < datetime.utcnow():
            return None

        # Validate user is active
        if not user.is_active:
            return None

        # Update last_used timestamp (async, non-blocking)
        api_key_obj.last_used = datetime.utcnow()
        await db.commit()

        return {
            'user': user,
            'key_id': api_key_obj.id,
            'key_name': api_key_obj.name,
            'rate_limit': api_key_obj.rate_limit,
            'created_at': api_key_obj.created_at,
            'expires_at': api_key_obj.expires_at,
        }

    @classmethod
    async def create_key(
        cls,
        user_id: str,
        name: str,
        db: AsyncSession,
        expires_in_days: Optional[int] = None,
        rate_limit: int = 1000
    ) -> tuple[str, APIKey]:
        """
        Create a new API key for a user

        Args:
            user_id: User ID to associate with key
            name: Descriptive name for the key
            db: Database session
            expires_in_days: Optional expiration in days (None = no expiration)
            rate_limit: Requests per hour limit (default: 1000)

        Returns:
            Tuple of (plain_text_key, api_key_object)

        Note:
            The plain text key is returned ONCE and must be saved by the caller.
            It cannot be retrieved again after this function returns.
        """
        # Generate new key
        plain_key = cls.generate_key()
        key_hash = cls.hash_key(plain_key)

        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        # Create database record
        api_key = APIKey(
            user_id=user_id,
            key_hash=key_hash,
            name=name,
            is_active=True,
            rate_limit=rate_limit,
            created_at=datetime.utcnow(),
            expires_at=expires_at
        )

        db.add(api_key)
        await db.commit()
        await db.refresh(api_key)

        return plain_key, api_key

    @classmethod
    async def revoke_key(cls, key_id: str, db: AsyncSession) -> bool:
        """
        Revoke an API key by marking it as inactive

        Args:
            key_id: API key ID to revoke
            db: Database session

        Returns:
            True if key was revoked, False if not found
        """
        result = await db.execute(
            select(APIKey).where(APIKey.id == key_id)
        )
        api_key = result.scalar_one_or_none()

        if not api_key:
            return False

        api_key.is_active = False
        await db.commit()

        return True
