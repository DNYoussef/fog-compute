"""
Mesh Persistence Service
Database operations for device mesh tokens and registry

PHASE0-SEC-001 (lg03): Token Persistence in SQLite
- Provides async database operations for mesh data
- Handles token hashing and validation
- Manages device state persistence
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Any
import logging

from sqlalchemy import select, update, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import AsyncSessionLocal
from ..models.mesh import MeshToken, MeshDevice, MeshEnrollmentCode
from ..schemas.device_mesh import (
    DeviceProfile,
    DeviceRole,
    DeviceStatus,
    DeviceState,
    LivenessState,
)

logger = logging.getLogger(__name__)

# Token lifetime constants (PHASE0-SEC-003)
ACCESS_TOKEN_LIFETIME_MINUTES = 15
REFRESH_TOKEN_LIFETIME_DAYS = 7


def hash_token(token: str) -> str:
    """Hash a token using SHA-256 for secure storage"""
    return hashlib.sha256(token.encode()).hexdigest()


def generate_token() -> tuple[str, str]:
    """Generate a secure token and its hash.

    Returns:
        Tuple of (plaintext_token, token_hash)
    """
    token = secrets.token_urlsafe(32)  # 256-bit token
    return token, hash_token(token)


class MeshPersistenceService:
    """
    Async persistence service for mesh tokens and devices.

    Provides atomic database operations with proper error handling.
    """

    # === Token Operations ===

    async def store_token(
        self,
        device_id: str,
        token_hash: str,
        token_type: str = "mesh_auth",
        expires_in_hours: Optional[int] = 24 * 7,  # Default 7 days
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> MeshToken:
        """Store a new token in the database.

        Args:
            device_id: The device this token authenticates
            token_hash: SHA-256 hash of the token (NOT plaintext!)
            token_type: Type of token (mesh_auth, refresh, enrollment)
            expires_in_hours: Hours until expiration (None = no expiry)
            ip_address: Client IP address
            user_agent: Client user agent string

        Returns:
            The created MeshToken record
        """
        async with AsyncSessionLocal() as session:
            expires_at = None
            if expires_in_hours is not None:
                expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)

            token = MeshToken(
                token_hash=token_hash,
                device_id=device_id,
                token_type=token_type,
                expires_at=expires_at,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            session.add(token)
            await session.commit()
            await session.refresh(token)

            logger.info(f"Stored token for device {device_id}, type={token_type}, expires={expires_at}")
            return token

    async def validate_token(self, token: str) -> Optional[str]:
        """Validate a token and return the device_id if valid.

        Args:
            token: The plaintext token to validate

        Returns:
            device_id if token is valid, None otherwise
        """
        token_hash = hash_token(token)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(MeshToken).where(MeshToken.token_hash == token_hash)
            )
            db_token = result.scalar_one_or_none()

            if db_token is None:
                return None

            if not db_token.is_valid:
                logger.debug(f"Token invalid for device {db_token.device_id}: expired or revoked")
                return None

            # Update usage tracking
            db_token.last_used_at = datetime.now(timezone.utc)
            db_token.use_count += 1
            await session.commit()

            return db_token.device_id

    async def get_device_by_token(self, token: str) -> Optional[str]:
        """Alias for validate_token for API compatibility."""
        return await self.validate_token(token)

    async def revoke_token(
        self,
        token_hash: str,
        reason: str = "manual_revocation"
    ) -> bool:
        """Revoke a token by its hash.

        Args:
            token_hash: Hash of the token to revoke
            reason: Reason for revocation

        Returns:
            True if token was revoked, False if not found
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                update(MeshToken)
                .where(MeshToken.token_hash == token_hash)
                .values(
                    revoked_at=datetime.now(timezone.utc),
                    revocation_reason=reason
                )
            )
            await session.commit()
            return result.rowcount > 0

    async def revoke_device_tokens(
        self,
        device_id: str,
        reason: str = "device_removed"
    ) -> int:
        """Revoke all tokens for a device.

        Args:
            device_id: The device whose tokens to revoke
            reason: Reason for revocation

        Returns:
            Number of tokens revoked
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                update(MeshToken)
                .where(
                    and_(
                        MeshToken.device_id == device_id,
                        MeshToken.revoked_at.is_(None)
                    )
                )
                .values(
                    revoked_at=datetime.now(timezone.utc),
                    revocation_reason=reason
                )
            )
            await session.commit()
            logger.info(f"Revoked {result.rowcount} tokens for device {device_id}")
            return result.rowcount

    async def cleanup_expired_tokens(self) -> int:
        """Delete tokens that expired more than 7 days ago.

        Returns:
            Number of tokens deleted
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                delete(MeshToken).where(
                    or_(
                        MeshToken.expires_at < cutoff,
                        MeshToken.revoked_at < cutoff
                    )
                )
            )
            await session.commit()
            logger.info(f"Cleaned up {result.rowcount} expired/revoked tokens")
            return result.rowcount

    async def get_token_record(self, token: str) -> Optional[MeshToken]:
        """Get full token record for validation.

        Args:
            token: The plaintext token

        Returns:
            MeshToken record or None if not found
        """
        token_hash = hash_token(token)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(MeshToken).where(MeshToken.token_hash == token_hash)
            )
            return result.scalar_one_or_none()

    async def refresh_access_token(
        self,
        refresh_token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[tuple[str, datetime, str, datetime]]:
        """Refresh an access token using a valid refresh token.

        PHASE0-SEC-003: Implements token refresh flow.

        Args:
            refresh_token: The plaintext refresh token
            ip_address: Client IP for new token
            user_agent: Client user agent for new token

        Returns:
            Tuple of (new_access_token, access_expires_at, new_refresh_token, refresh_expires_at)
            or None if refresh token is invalid
        """
        refresh_hash = hash_token(refresh_token)

        async with AsyncSessionLocal() as session:
            # Validate refresh token
            result = await session.execute(
                select(MeshToken).where(MeshToken.token_hash == refresh_hash)
            )
            db_refresh = result.scalar_one_or_none()

            if db_refresh is None:
                logger.warning("Refresh token not found")
                return None

            if not db_refresh.is_valid:
                logger.warning(f"Refresh token invalid for device {db_refresh.device_id}")
                return None

            if db_refresh.token_type != "refresh":
                logger.warning(f"Token is not a refresh token: {db_refresh.token_type}")
                return None

            device_id = db_refresh.device_id

            # Generate new access token (15 minutes)
            access_token, access_hash = generate_token()
            access_expires_at = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_LIFETIME_MINUTES)

            new_access = MeshToken(
                token_hash=access_hash,
                device_id=device_id,
                token_type="mesh_auth",
                expires_at=access_expires_at,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            session.add(new_access)

            # Rotate refresh token (optional but recommended for security)
            # Revoke old refresh token
            db_refresh.revoked_at = datetime.now(timezone.utc)
            db_refresh.revocation_reason = "rotated"

            # Generate new refresh token (7 days)
            new_refresh_token, new_refresh_hash = generate_token()
            refresh_expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_LIFETIME_DAYS)

            new_refresh = MeshToken(
                token_hash=new_refresh_hash,
                device_id=device_id,
                token_type="refresh",
                expires_at=refresh_expires_at,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            session.add(new_refresh)

            # Update old refresh token usage
            db_refresh.last_used_at = datetime.now(timezone.utc)
            db_refresh.use_count += 1

            await session.commit()

            logger.info(f"Refreshed tokens for device {device_id}")
            return access_token, access_expires_at, new_refresh_token, refresh_expires_at

    async def create_token_pair(
        self,
        device_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> tuple[str, datetime, str, datetime]:
        """Create access + refresh token pair for a device.

        PHASE0-SEC-003: Used during join/enrollment.

        Args:
            device_id: Device to create tokens for
            ip_address: Client IP
            user_agent: Client user agent

        Returns:
            Tuple of (access_token, access_expires_at, refresh_token, refresh_expires_at)
        """
        async with AsyncSessionLocal() as session:
            # Generate access token (15 minutes)
            access_token, access_hash = generate_token()
            access_expires_at = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_LIFETIME_MINUTES)

            access_record = MeshToken(
                token_hash=access_hash,
                device_id=device_id,
                token_type="mesh_auth",
                expires_at=access_expires_at,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            session.add(access_record)

            # Generate refresh token (7 days)
            refresh_token, refresh_hash = generate_token()
            refresh_expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_LIFETIME_DAYS)

            refresh_record = MeshToken(
                token_hash=refresh_hash,
                device_id=device_id,
                token_type="refresh",
                expires_at=refresh_expires_at,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            session.add(refresh_record)

            await session.commit()

            logger.info(f"Created token pair for device {device_id}")
            return access_token, access_expires_at, refresh_token, refresh_expires_at

    # === Device Operations ===

    async def store_device(
        self,
        device_id: str,
        device_name: str,
        profile: DeviceProfile,
        role: DeviceRole = DeviceRole.WORKER,
        zone: str = "default",
        public_key: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> MeshDevice:
        """Store a new device in the registry.

        Args:
            device_id: Unique device identifier
            device_name: Human-readable device name
            profile: Device hardware/software profile
            role: Device role in the mesh
            zone: Geographic/logical zone
            public_key: Public key for secure communication
            owner_id: Owner/user who controls this device

        Returns:
            The created MeshDevice record
        """
        async with AsyncSessionLocal() as session:
            device = MeshDevice(
                device_id=device_id,
                device_name=device_name,
                role=role.value,
                status=DeviceStatus.ONLINE.value,
                zone=zone,
                profile_json=profile.model_dump(),
                cpu_cores=profile.cpu_cores,
                ram_gb=profile.ram_gb,
                max_concurrent_tasks=profile.max_concurrent_tasks,
                public_key=public_key,
                owner_id=owner_id,
                last_heartbeat=datetime.now(timezone.utc),
            )
            session.add(device)
            await session.commit()
            await session.refresh(device)

            logger.info(f"Stored device {device_id} ({device_name}) in zone {zone}")
            return device

    async def get_device(self, device_id: str) -> Optional[MeshDevice]:
        """Get a device by its ID.

        Args:
            device_id: The device ID to look up

        Returns:
            MeshDevice record or None if not found
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(MeshDevice).where(MeshDevice.device_id == device_id)
            )
            return result.scalar_one_or_none()

    async def get_device_state(self, device_id: str) -> Optional[DeviceState]:
        """Get full device state as Pydantic model.

        Args:
            device_id: The device ID to look up

        Returns:
            DeviceState or None if not found
        """
        device = await self.get_device(device_id)
        if device is None:
            return None

        return self._db_to_device_state(device)

    async def update_device_heartbeat(
        self,
        device_id: str,
        status: DeviceStatus,
        current_load: float,
        active_tasks: list[str],
        pending_sync_count: int,
        latency_ms: float = 0.0,
    ) -> bool:
        """Update device state from heartbeat.

        Args:
            device_id: Device sending heartbeat
            status: Current device status
            current_load: CPU/resource load (0.0-1.0)
            active_tasks: List of active task IDs
            pending_sync_count: Number of pending sync items
            latency_ms: Heartbeat latency in milliseconds

        Returns:
            True if device was updated, False if not found
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(MeshDevice).where(MeshDevice.device_id == device_id)
            )
            device = result.scalar_one_or_none()

            if device is None:
                return False

            # Update liveness tracking
            device.status = status.value
            device.current_load = current_load
            device.active_tasks_json = active_tasks
            device.pending_sync_count = pending_sync_count
            device.last_heartbeat = datetime.now(timezone.utc)
            device.last_heartbeat_latency_ms = latency_ms

            # Update consecutive counters
            device.consecutive_successes += 1
            device.consecutive_misses = 0

            # Update average latency (exponential moving average)
            alpha = 0.2
            device.avg_latency_ms = alpha * latency_ms + (1 - alpha) * device.avg_latency_ms

            await session.commit()
            return True

    async def mark_device_missed_heartbeat(self, device_id: str) -> int:
        """Increment missed heartbeat counter for a device.

        Args:
            device_id: Device that missed heartbeat

        Returns:
            New consecutive miss count, or -1 if device not found
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(MeshDevice).where(MeshDevice.device_id == device_id)
            )
            device = result.scalar_one_or_none()

            if device is None:
                return -1

            device.consecutive_misses += 1
            device.consecutive_successes = 0

            # Mark offline if too many misses
            if device.consecutive_misses >= 3:
                device.status = DeviceStatus.OFFLINE.value

            await session.commit()
            return device.consecutive_misses

    async def update_device(
        self,
        device_id: str,
        device_name: Optional[str] = None,
        role: Optional[DeviceRole] = None,
        profile: Optional[DeviceProfile] = None,
        max_concurrent_tasks: Optional[int] = None,
    ) -> Optional[MeshDevice]:
        """Update device properties.

        Args:
            device_id: Device to update
            device_name: New device name (optional)
            role: New role (optional)
            profile: New profile (optional)
            max_concurrent_tasks: New task limit (optional)

        Returns:
            Updated MeshDevice or None if not found
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(MeshDevice).where(MeshDevice.device_id == device_id)
            )
            device = result.scalar_one_or_none()

            if device is None:
                return None

            if device_name is not None:
                device.device_name = device_name
            if role is not None:
                device.role = role.value
            if profile is not None:
                device.profile_json = profile.model_dump()
                device.cpu_cores = profile.cpu_cores
                device.ram_gb = profile.ram_gb
            if max_concurrent_tasks is not None:
                device.max_concurrent_tasks = max_concurrent_tasks

            await session.commit()
            await session.refresh(device)
            return device

    async def remove_device(self, device_id: str, reason: str = "removed") -> bool:
        """Remove a device from the mesh (soft delete).

        Args:
            device_id: Device to remove
            reason: Reason for removal

        Returns:
            True if device was removed, False if not found
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                update(MeshDevice)
                .where(MeshDevice.device_id == device_id)
                .values(
                    status=DeviceStatus.OFFLINE.value,
                    left_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()

            if result.rowcount > 0:
                # Also revoke all tokens for this device
                await self.revoke_device_tokens(device_id, reason)
                logger.info(f"Removed device {device_id}: {reason}")
                return True
            return False

    async def list_devices(
        self,
        zone: Optional[str] = None,
        status: Optional[DeviceStatus] = None,
        role: Optional[DeviceRole] = None,
        include_offline: bool = True,
    ) -> list[MeshDevice]:
        """List devices with optional filters.

        Args:
            zone: Filter by zone (optional)
            status: Filter by status (optional)
            role: Filter by role (optional)
            include_offline: Include offline/left devices

        Returns:
            List of matching MeshDevice records
        """
        async with AsyncSessionLocal() as session:
            query = select(MeshDevice)

            conditions = []
            if zone is not None:
                conditions.append(MeshDevice.zone == zone)
            if status is not None:
                conditions.append(MeshDevice.status == status.value)
            if role is not None:
                conditions.append(MeshDevice.role == role.value)
            if not include_offline:
                conditions.append(MeshDevice.left_at.is_(None))
                conditions.append(MeshDevice.status != DeviceStatus.OFFLINE.value)

            if conditions:
                query = query.where(and_(*conditions))

            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_primary_device(self) -> Optional[MeshDevice]:
        """Get the current primary device.

        Returns:
            Primary MeshDevice or None if no primary exists
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(MeshDevice).where(
                    and_(
                        MeshDevice.role == DeviceRole.PRIMARY.value,
                        MeshDevice.status != DeviceStatus.OFFLINE.value,
                        MeshDevice.left_at.is_(None)
                    )
                )
            )
            return result.scalar_one_or_none()

    # === Enrollment Code Operations (for SEC-002) ===

    async def create_enrollment_code(
        self,
        created_by_device_id: Optional[str],
        intended_device_name: Optional[str] = None,
        intended_role: DeviceRole = DeviceRole.WORKER,
        expires_in_hours: float = 24.0,
    ) -> tuple[str, MeshEnrollmentCode]:
        """Create a one-time enrollment code.

        Args:
            created_by_device_id: Device creating this code (usually primary)
            intended_device_name: Suggested name for enrolling device
            intended_role: Role for the new device
            expires_in_hours: Hours until code expires

        Returns:
            Tuple of (plaintext_code, MeshEnrollmentCode record)
        """
        code, code_hash = generate_token()

        async with AsyncSessionLocal() as session:
            enrollment = MeshEnrollmentCode(
                code_hash=code_hash,
                created_by_device_id=created_by_device_id,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=expires_in_hours),
                intended_device_name=intended_device_name,
                intended_role=intended_role.value,
            )
            session.add(enrollment)
            await session.commit()
            await session.refresh(enrollment)

            logger.info(f"Created enrollment code for {intended_device_name or 'unnamed device'}")
            return code, enrollment

    async def validate_enrollment_code(self, code: str) -> Optional[MeshEnrollmentCode]:
        """Validate an enrollment code.

        Args:
            code: Plaintext enrollment code

        Returns:
            MeshEnrollmentCode if valid, None otherwise
        """
        code_hash = hash_token(code)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(MeshEnrollmentCode).where(MeshEnrollmentCode.code_hash == code_hash)
            )
            enrollment = result.scalar_one_or_none()

            if enrollment is None or not enrollment.is_valid:
                return None

            return enrollment

    async def use_enrollment_code(
        self,
        code: str,
        used_by_device_id: str
    ) -> bool:
        """Mark an enrollment code as used.

        Args:
            code: Plaintext enrollment code
            used_by_device_id: Device that used the code

        Returns:
            True if code was marked as used, False if invalid
        """
        code_hash = hash_token(code)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(MeshEnrollmentCode).where(
                    and_(
                        MeshEnrollmentCode.code_hash == code_hash,
                        MeshEnrollmentCode.used_at.is_(None)
                    )
                )
            )
            enrollment = result.scalar_one_or_none()

            if enrollment is None or not enrollment.is_valid:
                return False

            enrollment.used_at = datetime.now(timezone.utc)
            enrollment.used_by_device_id = used_by_device_id
            await session.commit()

            logger.info(f"Enrollment code used by device {used_by_device_id}")
            return True

    async def list_enrollment_codes(
        self,
        include_used: bool = False,
        include_expired: bool = False,
    ) -> list[MeshEnrollmentCode]:
        """List enrollment codes with optional filters.

        Args:
            include_used: Include codes that have been used
            include_expired: Include codes that have expired

        Returns:
            List of MeshEnrollmentCode records
        """
        async with AsyncSessionLocal() as session:
            conditions = []

            if not include_used:
                conditions.append(MeshEnrollmentCode.used_at.is_(None))

            if not include_expired:
                conditions.append(MeshEnrollmentCode.expires_at > datetime.now(timezone.utc))

            query = select(MeshEnrollmentCode)
            if conditions:
                query = query.where(and_(*conditions))

            query = query.order_by(MeshEnrollmentCode.created_at.desc())

            result = await session.execute(query)
            return list(result.scalars().all())

    async def revoke_enrollment_code(self, code_id: str) -> bool:
        """Revoke an enrollment code by its ID.

        Args:
            code_id: UUID of the enrollment code to revoke

        Returns:
            True if code was revoked, False if not found
        """
        from uuid import UUID

        try:
            code_uuid = UUID(code_id)
        except ValueError:
            return False

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                update(MeshEnrollmentCode)
                .where(MeshEnrollmentCode.id == code_uuid)
                .values(
                    used_at=datetime.now(timezone.utc),
                    used_by_device_id="REVOKED"
                )
            )
            await session.commit()

            if result.rowcount > 0:
                logger.info(f"Enrollment code {code_id} revoked")
                return True
            return False

    # === Helper Methods ===

    def _db_to_device_state(self, device: MeshDevice) -> DeviceState:
        """Convert database model to Pydantic DeviceState.

        Args:
            device: MeshDevice database record

        Returns:
            DeviceState Pydantic model
        """
        profile = DeviceProfile(**device.profile_json)

        liveness = LivenessState(
            device_id=device.device_id,
            last_seen=device.last_heartbeat or device.joined_at,
            status=DeviceStatus(device.status),
            is_healthy=device.is_healthy,
            consecutive_misses=device.consecutive_misses,
            consecutive_successes=device.consecutive_successes,
            avg_latency_ms=device.avg_latency_ms,
            last_heartbeat_latency_ms=device.last_heartbeat_latency_ms,
        )

        return DeviceState(
            device_id=device.device_id,
            device_name=device.device_name,
            role=DeviceRole(device.role),
            status=DeviceStatus(device.status),
            zone=device.zone,
            profile=profile,
            liveness=liveness,
            joined_at=device.joined_at,
            last_heartbeat=device.last_heartbeat,
            current_load=device.current_load,
            active_tasks=device.active_tasks_json,
            pending_sync_count=device.pending_sync_count,
            owner_id=device.owner_id,
        )


# Singleton instance
_mesh_persistence: Optional[MeshPersistenceService] = None


def get_mesh_persistence() -> MeshPersistenceService:
    """Get the singleton MeshPersistenceService instance."""
    global _mesh_persistence
    if _mesh_persistence is None:
        _mesh_persistence = MeshPersistenceService()
    return _mesh_persistence
