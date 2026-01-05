"""
Token Service
Manages JWT token blacklist, refresh tokens, and account lockout.
Uses Redis for distributed token blacklist storage.
"""
import asyncio
import logging
import uuid
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Token configuration constants
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
PASSWORD_RESET_EXPIRE_MINUTES = 60
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 30
TOKEN_BLACKLIST_PREFIX = "token_blacklist:"
REFRESH_TOKEN_PREFIX = "refresh_token:"
LOGIN_ATTEMPTS_PREFIX = "login_attempts:"
PASSWORD_RESET_PREFIX = "password_reset:"


@dataclass
class RefreshTokenData:
    """Refresh token metadata"""
    token_id: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    revoked: bool = False
    revoked_at: Optional[datetime] = None


@dataclass
class LoginAttemptData:
    """Login attempt tracking"""
    user_id: str
    attempts: int
    last_attempt: datetime
    locked_until: Optional[datetime] = None


@dataclass
class PasswordResetTokenData:
    """Password reset token metadata"""
    token: str
    user_id: str
    email: str
    created_at: datetime
    expires_at: datetime
    used: bool = False


class TokenService:
    """
    Service for managing JWT token lifecycle:
    - Token blacklist (for logout/revocation)
    - Refresh token generation and validation
    - Account lockout after failed logins
    """

    def __init__(self):
        self._redis = None
        self._connected = False
        # In-memory fallback when Redis unavailable
        self._blacklist: Dict[str, datetime] = {}
        self._refresh_tokens: Dict[str, RefreshTokenData] = {}
        self._login_attempts: Dict[str, LoginAttemptData] = {}
        self._password_reset_tokens: Dict[str, PasswordResetTokenData] = {}

    async def connect(self) -> bool:
        """Connect to Redis for distributed token storage"""
        try:
            import redis.asyncio as aioredis
            import os

            redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
            self._redis = aioredis.from_url(redis_url, decode_responses=True)
            await self._redis.ping()
            self._connected = True
            logger.info("TokenService connected to Redis")
            return True
        except ImportError:
            logger.warning("redis package not installed. Using in-memory storage.")
            return False
        except Exception as e:
            logger.warning(f"Cannot connect to Redis: {e}. Using in-memory storage.")
            self._redis = None
            self._connected = False
            return False

    async def disconnect(self):
        """Disconnect from Redis"""
        if self._redis:
            await self._redis.close()
            self._redis = None
            self._connected = False
            logger.info("TokenService disconnected from Redis")

    @property
    def is_connected(self) -> bool:
        """Check if connected to Redis"""
        return self._connected and self._redis is not None

    # =========================================================================
    # Token Blacklist Operations
    # =========================================================================

    async def blacklist_token(self, token_jti: str, expires_at: datetime) -> bool:
        """
        Add a token to the blacklist (for logout/revocation).

        Args:
            token_jti: JWT ID (jti claim) to blacklist
            expires_at: Token expiration time (blacklist entry auto-expires after this)

        Returns:
            True if successfully blacklisted
        """
        try:
            ttl_seconds = int((expires_at - datetime.now(timezone.utc)).total_seconds())
            if ttl_seconds <= 0:
                # Token already expired, no need to blacklist
                return True

            if self.is_connected:
                key = f"{TOKEN_BLACKLIST_PREFIX}{token_jti}"
                await self._redis.setex(key, ttl_seconds, "1")
                logger.debug(f"Token {token_jti[:8]}... blacklisted for {ttl_seconds}s")
            else:
                # In-memory fallback
                self._blacklist[token_jti] = expires_at
                logger.debug(f"Token {token_jti[:8]}... blacklisted (in-memory)")

            return True
        except Exception as e:
            logger.error(f"Failed to blacklist token: {e}")
            return False

    async def is_token_blacklisted(self, token_jti: str) -> bool:
        """
        Check if a token is blacklisted.

        Args:
            token_jti: JWT ID to check

        Returns:
            True if token is blacklisted
        """
        try:
            if self.is_connected:
                key = f"{TOKEN_BLACKLIST_PREFIX}{token_jti}"
                result = await self._redis.exists(key)
                return result > 0
            else:
                # In-memory fallback with expiry cleanup
                if token_jti in self._blacklist:
                    if self._blacklist[token_jti] > datetime.now(timezone.utc):
                        return True
                    else:
                        del self._blacklist[token_jti]
                return False
        except Exception as e:
            logger.error(f"Failed to check token blacklist: {e}")
            return False

    # =========================================================================
    # Refresh Token Operations
    # =========================================================================

    async def create_refresh_token(self, user_id: str) -> Tuple[str, RefreshTokenData]:
        """
        Create a new refresh token for a user.

        Args:
            user_id: User ID to create token for

        Returns:
            Tuple of (token_string, token_data)
        """
        token_id = str(uuid.uuid4())
        token_string = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

        token_data = RefreshTokenData(
            token_id=token_id,
            user_id=user_id,
            created_at=now,
            expires_at=expires_at
        )

        try:
            if self.is_connected:
                key = f"{REFRESH_TOKEN_PREFIX}{token_string}"
                ttl_seconds = int((expires_at - now).total_seconds())
                await self._redis.setex(
                    key,
                    ttl_seconds,
                    f"{token_id}:{user_id}:{expires_at.isoformat()}"
                )
                logger.info(f"Created refresh token for user {user_id}")
            else:
                # In-memory fallback
                self._refresh_tokens[token_string] = token_data
                logger.info(f"Created refresh token for user {user_id} (in-memory)")

            return token_string, token_data

        except Exception as e:
            logger.error(f"Failed to create refresh token: {e}")
            raise

    async def validate_refresh_token(self, token_string: str) -> Optional[RefreshTokenData]:
        """
        Validate a refresh token.

        Args:
            token_string: Refresh token to validate

        Returns:
            RefreshTokenData if valid, None otherwise
        """
        try:
            if self.is_connected:
                key = f"{REFRESH_TOKEN_PREFIX}{token_string}"
                data = await self._redis.get(key)
                if not data:
                    return None

                parts = data.split(":", 2)
                if len(parts) != 3:
                    return None

                token_id, user_id, expires_str = parts
                expires_at = datetime.fromisoformat(expires_str)

                if expires_at < datetime.now(timezone.utc):
                    await self._redis.delete(key)
                    return None

                return RefreshTokenData(
                    token_id=token_id,
                    user_id=user_id,
                    created_at=datetime.now(timezone.utc),  # Not stored
                    expires_at=expires_at
                )
            else:
                # In-memory fallback
                token_data = self._refresh_tokens.get(token_string)
                if not token_data:
                    return None

                if token_data.expires_at < datetime.now(timezone.utc):
                    del self._refresh_tokens[token_string]
                    return None

                if token_data.revoked:
                    return None

                return token_data

        except Exception as e:
            logger.error(f"Failed to validate refresh token: {e}")
            return None

    async def revoke_refresh_token(self, token_string: str) -> bool:
        """
        Revoke a refresh token.

        Args:
            token_string: Token to revoke

        Returns:
            True if successfully revoked
        """
        try:
            if self.is_connected:
                key = f"{REFRESH_TOKEN_PREFIX}{token_string}"
                result = await self._redis.delete(key)
                return result > 0
            else:
                if token_string in self._refresh_tokens:
                    self._refresh_tokens[token_string].revoked = True
                    self._refresh_tokens[token_string].revoked_at = datetime.now(timezone.utc)
                    return True
                return False

        except Exception as e:
            logger.error(f"Failed to revoke refresh token: {e}")
            return False

    async def revoke_all_user_tokens(self, user_id: str) -> int:
        """
        Revoke all refresh tokens for a user (e.g., on password change).

        Args:
            user_id: User ID to revoke tokens for

        Returns:
            Number of tokens revoked
        """
        revoked_count = 0
        try:
            if self.is_connected:
                # Scan for user's tokens (requires iteration)
                cursor = 0
                while True:
                    cursor, keys = await self._redis.scan(
                        cursor,
                        match=f"{REFRESH_TOKEN_PREFIX}*",
                        count=100
                    )
                    for key in keys:
                        data = await self._redis.get(key)
                        if data and f":{user_id}:" in data:
                            await self._redis.delete(key)
                            revoked_count += 1

                    if cursor == 0:
                        break
            else:
                # In-memory fallback
                tokens_to_revoke = [
                    token for token, data in self._refresh_tokens.items()
                    if data.user_id == user_id and not data.revoked
                ]
                for token in tokens_to_revoke:
                    self._refresh_tokens[token].revoked = True
                    self._refresh_tokens[token].revoked_at = datetime.now(timezone.utc)
                    revoked_count += 1

            logger.info(f"Revoked {revoked_count} refresh tokens for user {user_id}")
            return revoked_count

        except Exception as e:
            logger.error(f"Failed to revoke user tokens: {e}")
            return revoked_count

    # =========================================================================
    # Account Lockout Operations
    # =========================================================================

    async def record_login_attempt(self, user_id: str, success: bool) -> LoginAttemptData:
        """
        Record a login attempt (successful or failed).

        Args:
            user_id: User ID attempting login
            success: Whether login succeeded

        Returns:
            Current login attempt data
        """
        now = datetime.now(timezone.utc)

        try:
            if self.is_connected:
                key = f"{LOGIN_ATTEMPTS_PREFIX}{user_id}"

                if success:
                    # Reset attempts on successful login
                    await self._redis.delete(key)
                    return LoginAttemptData(user_id=user_id, attempts=0, last_attempt=now)

                # Increment failed attempts
                pipe = self._redis.pipeline()
                pipe.hincrby(key, "attempts", 1)
                pipe.hset(key, "last_attempt", now.isoformat())
                pipe.expire(key, LOCKOUT_DURATION_MINUTES * 60)
                results = await pipe.execute()

                attempts = results[0]

                # Check if account should be locked
                locked_until = None
                if attempts >= MAX_LOGIN_ATTEMPTS:
                    locked_until = now + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
                    await self._redis.hset(key, "locked_until", locked_until.isoformat())
                    logger.warning(f"Account {user_id} locked until {locked_until}")

                return LoginAttemptData(
                    user_id=user_id,
                    attempts=attempts,
                    last_attempt=now,
                    locked_until=locked_until
                )

            else:
                # In-memory fallback
                if success:
                    if user_id in self._login_attempts:
                        del self._login_attempts[user_id]
                    return LoginAttemptData(user_id=user_id, attempts=0, last_attempt=now)

                attempt_data = self._login_attempts.get(user_id)
                if attempt_data:
                    # Check if lockout expired
                    if attempt_data.locked_until and attempt_data.locked_until < now:
                        attempt_data.attempts = 0
                        attempt_data.locked_until = None

                    attempt_data.attempts += 1
                    attempt_data.last_attempt = now
                else:
                    attempt_data = LoginAttemptData(user_id=user_id, attempts=1, last_attempt=now)
                    self._login_attempts[user_id] = attempt_data

                # Check if account should be locked
                if attempt_data.attempts >= MAX_LOGIN_ATTEMPTS:
                    attempt_data.locked_until = now + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
                    logger.warning(f"Account {user_id} locked until {attempt_data.locked_until}")

                return attempt_data

        except Exception as e:
            logger.error(f"Failed to record login attempt: {e}")
            return LoginAttemptData(user_id=user_id, attempts=0, last_attempt=now)

    async def is_account_locked(self, user_id: str) -> Tuple[bool, Optional[datetime]]:
        """
        Check if an account is locked.

        Args:
            user_id: User ID to check

        Returns:
            Tuple of (is_locked, locked_until_datetime)
        """
        now = datetime.now(timezone.utc)

        try:
            if self.is_connected:
                key = f"{LOGIN_ATTEMPTS_PREFIX}{user_id}"
                locked_until_str = await self._redis.hget(key, "locked_until")

                if not locked_until_str:
                    return False, None

                locked_until = datetime.fromisoformat(locked_until_str)
                if locked_until > now:
                    return True, locked_until

                # Lockout expired, clear it
                await self._redis.hdel(key, "locked_until")
                return False, None

            else:
                attempt_data = self._login_attempts.get(user_id)
                if not attempt_data or not attempt_data.locked_until:
                    return False, None

                if attempt_data.locked_until > now:
                    return True, attempt_data.locked_until

                # Lockout expired
                attempt_data.locked_until = None
                attempt_data.attempts = 0
                return False, None

        except Exception as e:
            logger.error(f"Failed to check account lock: {e}")
            return False, None

    async def clear_login_attempts(self, user_id: str) -> bool:
        """
        Clear login attempts for a user (e.g., after admin unlock).

        Args:
            user_id: User ID to clear

        Returns:
            True if cleared
        """
        try:
            if self.is_connected:
                key = f"{LOGIN_ATTEMPTS_PREFIX}{user_id}"
                await self._redis.delete(key)
            else:
                if user_id in self._login_attempts:
                    del self._login_attempts[user_id]

            logger.info(f"Cleared login attempts for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to clear login attempts: {e}")
            return False

    # =========================================================================
    # Password Reset Token Operations
    # =========================================================================

    async def create_password_reset_token(
        self,
        user_id: str,
        email: str
    ) -> PasswordResetTokenData:
        """
        Create a password reset token.

        Args:
            user_id: User ID requesting reset
            email: User's email address

        Returns:
            PasswordResetTokenData with token details
        """
        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES)

        token_data = PasswordResetTokenData(
            token=token,
            user_id=user_id,
            email=email,
            created_at=now,
            expires_at=expires_at
        )

        try:
            if self.is_connected:
                key = f"{PASSWORD_RESET_PREFIX}{token}"
                ttl_seconds = int((expires_at - now).total_seconds())
                await self._redis.setex(
                    key,
                    ttl_seconds,
                    f"{user_id}:{email}:{expires_at.isoformat()}"
                )
                logger.info(f"Created password reset token for user {user_id}")
            else:
                # In-memory fallback
                self._password_reset_tokens[token] = token_data
                logger.info(f"Created password reset token for user {user_id} (in-memory)")

            return token_data

        except Exception as e:
            logger.error(f"Failed to create password reset token: {e}")
            raise

    async def validate_password_reset_token(
        self,
        token: str
    ) -> Optional[PasswordResetTokenData]:
        """
        Validate a password reset token.

        Args:
            token: Reset token to validate

        Returns:
            PasswordResetTokenData if valid, None otherwise
        """
        try:
            if self.is_connected:
                key = f"{PASSWORD_RESET_PREFIX}{token}"
                data = await self._redis.get(key)
                if not data:
                    return None

                parts = data.split(":", 2)
                if len(parts) != 3:
                    return None

                user_id, email, expires_str = parts
                expires_at = datetime.fromisoformat(expires_str)

                if expires_at < datetime.now(timezone.utc):
                    await self._redis.delete(key)
                    return None

                return PasswordResetTokenData(
                    token=token,
                    user_id=user_id,
                    email=email,
                    created_at=datetime.now(timezone.utc),  # Not stored
                    expires_at=expires_at
                )
            else:
                # In-memory fallback
                token_data = self._password_reset_tokens.get(token)
                if not token_data:
                    return None

                if token_data.expires_at < datetime.now(timezone.utc):
                    del self._password_reset_tokens[token]
                    return None

                if token_data.used:
                    return None

                return token_data

        except Exception as e:
            logger.error(f"Failed to validate password reset token: {e}")
            return None

    async def consume_password_reset_token(self, token: str) -> bool:
        """
        Mark a password reset token as used (single-use).

        Args:
            token: Token to consume

        Returns:
            True if token was valid and consumed
        """
        try:
            if self.is_connected:
                key = f"{PASSWORD_RESET_PREFIX}{token}"
                result = await self._redis.delete(key)
                if result > 0:
                    logger.info(f"Consumed password reset token")
                    return True
                return False
            else:
                # In-memory fallback
                token_data = self._password_reset_tokens.get(token)
                if token_data and not token_data.used:
                    token_data.used = True
                    logger.info(f"Consumed password reset token (in-memory)")
                    return True
                return False

        except Exception as e:
            logger.error(f"Failed to consume password reset token: {e}")
            return False

    async def invalidate_user_reset_tokens(self, user_id: str) -> int:
        """
        Invalidate all pending password reset tokens for a user.
        Called when user successfully resets password.

        Args:
            user_id: User ID to invalidate tokens for

        Returns:
            Number of tokens invalidated
        """
        invalidated_count = 0
        try:
            if self.is_connected:
                cursor = 0
                while True:
                    cursor, keys = await self._redis.scan(
                        cursor,
                        match=f"{PASSWORD_RESET_PREFIX}*",
                        count=100
                    )
                    for key in keys:
                        data = await self._redis.get(key)
                        if data and data.startswith(f"{user_id}:"):
                            await self._redis.delete(key)
                            invalidated_count += 1

                    if cursor == 0:
                        break
            else:
                # In-memory fallback
                tokens_to_invalidate = [
                    token for token, data in self._password_reset_tokens.items()
                    if data.user_id == user_id and not data.used
                ]
                for token in tokens_to_invalidate:
                    self._password_reset_tokens[token].used = True
                    invalidated_count += 1

            if invalidated_count > 0:
                logger.info(f"Invalidated {invalidated_count} reset tokens for user {user_id}")
            return invalidated_count

        except Exception as e:
            logger.error(f"Failed to invalidate reset tokens: {e}")
            return invalidated_count


# Global singleton instance
token_service = TokenService()


async def get_token_service() -> TokenService:
    """
    Get token service instance.
    Ensures connection is attempted on first use.
    """
    if not token_service._connected and token_service._redis is None:
        await token_service.connect()
    return token_service
