"""
Device Authentication Service
Handles device registration, authentication, and token management for fog compute nodes

This service manages:
- Device registration with unique identifiers
- JWT token generation and validation for devices
- Device-to-owner linking
- Token refresh and revocation
"""
from datetime import datetime, timedelta, UTC
from typing import Optional, Any
from uuid import uuid4
import hashlib
import secrets
import logging
import jwt
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DeviceCredentials:
    """Device authentication credentials"""
    device_id: str
    device_secret: str  # Hashed
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    refresh_expires_at: Optional[datetime] = None
    owner_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_authenticated: Optional[datetime] = None
    is_active: bool = True
    is_revoked: bool = False


class DeviceAuthService:
    """
    Service for device authentication and authorization

    Provides:
    - Device registration with secure credentials
    - JWT token generation for device authentication
    - Token refresh and revocation
    - Device-to-owner linking
    """

    def __init__(
        self,
        secret_key: str,
        access_token_expire_minutes: int = 60,
        refresh_token_expire_days: int = 30,
        algorithm: str = "HS256"
    ):
        """
        Initialize device auth service

        Args:
            secret_key: Secret key for JWT signing
            access_token_expire_minutes: Access token expiry in minutes
            refresh_token_expire_days: Refresh token expiry in days
            algorithm: JWT signing algorithm
        """
        self.secret_key = secret_key
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days
        self.algorithm = algorithm

        # In-memory device registry (replace with database in production)
        self._devices: dict[str, DeviceCredentials] = {}
        self._refresh_tokens: dict[str, str] = {}  # refresh_token -> device_id

        logger.info("DeviceAuthService initialized")

    def _hash_secret(self, secret: str) -> str:
        """Hash a device secret for secure storage"""
        return hashlib.sha256(secret.encode()).hexdigest()

    def _generate_device_id(self, device_name: str, device_type: str) -> str:
        """Generate a unique device ID"""
        unique_part = uuid4().hex[:8]
        return f"fog-{device_type}-{unique_part}"

    def _generate_device_secret(self) -> str:
        """Generate a secure device secret"""
        return secrets.token_urlsafe(32)

    def _create_access_token(self, device_id: str, expires_delta: Optional[timedelta] = None) -> str:
        """
        Create a JWT access token for a device

        Args:
            device_id: Unique device identifier
            expires_delta: Custom expiry time

        Returns:
            JWT access token string
        """
        if expires_delta is None:
            expires_delta = timedelta(minutes=self.access_token_expire_minutes)

        expire = datetime.now(UTC) + expires_delta
        payload = {
            "sub": device_id,
            "type": "device_access",
            "exp": expire,
            "iat": datetime.now(UTC),
            "jti": uuid4().hex
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def _create_refresh_token(self, device_id: str) -> str:
        """
        Create a refresh token for a device

        Args:
            device_id: Unique device identifier

        Returns:
            JWT refresh token string
        """
        expires_delta = timedelta(days=self.refresh_token_expire_days)
        expire = datetime.now(UTC) + expires_delta

        payload = {
            "sub": device_id,
            "type": "device_refresh",
            "exp": expire,
            "iat": datetime.now(UTC),
            "jti": uuid4().hex
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    async def register_device(
        self,
        device_name: str,
        device_type: str,
        capabilities: dict[str, Any],
        owner_id: Optional[str] = None,
        region: Optional[str] = None
    ) -> tuple[str, str, str, str, datetime]:
        """
        Register a new device in the fog network

        Args:
            device_name: Human-readable device name
            device_type: Type of device (desktop, mobile, etc.)
            capabilities: Device hardware capabilities
            owner_id: Optional owner/user to link device to
            region: Optional geographic region

        Returns:
            Tuple of (device_id, device_secret, access_token, refresh_token, token_expires_at)
        """
        device_id = self._generate_device_id(device_name, device_type)
        device_secret = self._generate_device_secret()

        # Generate tokens
        access_token = self._create_access_token(device_id)
        refresh_token = self._create_refresh_token(device_id)
        token_expires_at = datetime.now(UTC) + timedelta(minutes=self.access_token_expire_minutes)
        refresh_expires_at = datetime.now(UTC) + timedelta(days=self.refresh_token_expire_days)

        # Store credentials
        credentials = DeviceCredentials(
            device_id=device_id,
            device_secret=self._hash_secret(device_secret),
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
            refresh_expires_at=refresh_expires_at,
            owner_id=owner_id,
            last_authenticated=datetime.now(UTC)
        )

        self._devices[device_id] = credentials
        self._refresh_tokens[refresh_token] = device_id

        logger.info(f"Device registered: {device_id} ({device_name})")

        return device_id, device_secret, access_token, refresh_token, token_expires_at

    async def authenticate_device(
        self,
        device_id: str,
        device_secret: str
    ) -> Optional[tuple[str, str, datetime]]:
        """
        Authenticate a device and generate new tokens

        Args:
            device_id: Device identifier
            device_secret: Device secret

        Returns:
            Tuple of (access_token, refresh_token, token_expires_at) or None if auth fails
        """
        credentials = self._devices.get(device_id)

        if not credentials:
            logger.warning(f"Authentication failed: device not found {device_id}")
            return None

        if credentials.is_revoked or not credentials.is_active:
            logger.warning(f"Authentication failed: device revoked/inactive {device_id}")
            return None

        if self._hash_secret(device_secret) != credentials.device_secret:
            logger.warning(f"Authentication failed: invalid secret for {device_id}")
            return None

        # Generate new tokens
        access_token = self._create_access_token(device_id)
        refresh_token = self._create_refresh_token(device_id)
        token_expires_at = datetime.now(UTC) + timedelta(minutes=self.access_token_expire_minutes)
        refresh_expires_at = datetime.now(UTC) + timedelta(days=self.refresh_token_expire_days)

        # Update credentials
        if credentials.refresh_token:
            self._refresh_tokens.pop(credentials.refresh_token, None)

        credentials.access_token = access_token
        credentials.refresh_token = refresh_token
        credentials.token_expires_at = token_expires_at
        credentials.refresh_expires_at = refresh_expires_at
        credentials.last_authenticated = datetime.now(UTC)

        # Update refresh token mapping
        self._refresh_tokens[refresh_token] = device_id

        logger.info(f"Device authenticated: {device_id}")

        return access_token, refresh_token, token_expires_at

    async def validate_access_token(self, token: str) -> Optional[str]:
        """
        Validate an access token and return the device ID

        Args:
            token: JWT access token

        Returns:
            Device ID if valid, None otherwise
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            if payload.get("type") != "device_access":
                logger.warning("Token validation failed: wrong token type")
                return None

            device_id = payload.get("sub")

            # Check device exists and is active
            credentials = self._devices.get(device_id)
            if not credentials or credentials.is_revoked or not credentials.is_active:
                logger.warning(f"Token validation failed: device invalid {device_id}")
                return None

            return device_id

        except jwt.ExpiredSignatureError:
            logger.debug("Token validation failed: token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Token validation failed: {e}")
            return None

    async def refresh_access_token(self, refresh_token: str) -> Optional[tuple[str, datetime]]:
        """
        Use refresh token to get a new access token

        Args:
            refresh_token: JWT refresh token

        Returns:
            Tuple of (new_access_token, token_expires_at) or None if refresh fails
        """
        try:
            payload = jwt.decode(refresh_token, self.secret_key, algorithms=[self.algorithm])

            if payload.get("type") != "device_refresh":
                logger.warning("Refresh failed: wrong token type")
                return None

            device_id = payload.get("sub")

            # Verify refresh token is in our registry
            if self._refresh_tokens.get(refresh_token) != device_id:
                logger.warning(f"Refresh failed: token not in registry {device_id}")
                return None

            # Check device exists and is active
            credentials = self._devices.get(device_id)
            if not credentials or credentials.is_revoked or not credentials.is_active:
                logger.warning(f"Refresh failed: device invalid {device_id}")
                return None

            if credentials.refresh_token != refresh_token:
                logger.warning(f"Refresh failed: token superseded for {device_id}")
                return None

            # Generate new access token
            access_token = self._create_access_token(device_id)
            token_expires_at = datetime.now(UTC) + timedelta(minutes=self.access_token_expire_minutes)

            # Update credentials
            credentials.access_token = access_token
            credentials.token_expires_at = token_expires_at

            logger.info(f"Access token refreshed for device: {device_id}")

            return access_token, token_expires_at

        except jwt.ExpiredSignatureError:
            logger.debug("Refresh failed: refresh token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Refresh failed: {e}")
            return None

    async def revoke_device(self, device_id: str) -> bool:
        """
        Revoke a device's access

        Args:
            device_id: Device identifier

        Returns:
            True if device was revoked, False if not found
        """
        credentials = self._devices.get(device_id)

        if not credentials:
            return False

        credentials.is_revoked = True
        credentials.is_active = False

        # Remove refresh token
        if credentials.refresh_token and credentials.refresh_token in self._refresh_tokens:
            del self._refresh_tokens[credentials.refresh_token]

        logger.info(f"Device revoked: {device_id}")

        return True

    async def link_to_owner(self, device_id: str, owner_id: str) -> bool:
        """
        Link a device to an owner

        Args:
            device_id: Device identifier
            owner_id: Owner/user ID

        Returns:
            True if link was created, False if device not found
        """
        credentials = self._devices.get(device_id)

        if not credentials:
            return False

        credentials.owner_id = owner_id

        logger.info(f"Device {device_id} linked to owner {owner_id}")

        return True

    async def get_device_info(self, device_id: str) -> Optional[dict[str, Any]]:
        """
        Get device information (excluding secrets)

        Args:
            device_id: Device identifier

        Returns:
            Device info dict or None if not found
        """
        credentials = self._devices.get(device_id)

        if not credentials:
            return None

        return {
            "device_id": credentials.device_id,
            "owner_id": credentials.owner_id,
            "created_at": credentials.created_at.isoformat(),
            "last_authenticated": credentials.last_authenticated.isoformat() if credentials.last_authenticated else None,
            "is_active": credentials.is_active,
            "is_revoked": credentials.is_revoked,
            "token_expires_at": credentials.token_expires_at.isoformat() if credentials.token_expires_at else None
        }

    async def list_owner_devices(self, owner_id: str) -> list[dict[str, Any]]:
        """
        List all devices linked to an owner

        Args:
            owner_id: Owner/user ID

        Returns:
            List of device info dicts
        """
        devices = []

        for device_id, credentials in self._devices.items():
            if credentials.owner_id == owner_id:
                info = await self.get_device_info(device_id)
                if info:
                    devices.append(info)

        return devices

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics"""
        active_devices = sum(1 for c in self._devices.values() if c.is_active and not c.is_revoked)
        revoked_devices = sum(1 for c in self._devices.values() if c.is_revoked)

        return {
            "total_devices": len(self._devices),
            "active_devices": active_devices,
            "revoked_devices": revoked_devices,
            "active_refresh_tokens": len(self._refresh_tokens)
        }


# Create global instance
device_auth_service: Optional[DeviceAuthService] = None


def get_device_auth_service() -> DeviceAuthService:
    """Get or create the device auth service instance"""
    global device_auth_service

    if device_auth_service is None:
        from ..config import settings
        device_auth_service = DeviceAuthService(
            secret_key=settings.SECRET_KEY,
            access_token_expire_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    return device_auth_service
