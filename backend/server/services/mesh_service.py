"""
Mesh coordination service.

Maintains in-memory device state with heartbeat jitter and persistence hooks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import logging
import random
import time
from typing import Optional
import uuid

from ..schemas.device_mesh import (
    DeviceProfile,
    DeviceRole,
    DeviceStatus,
    LivenessState,
)
from .mesh_persistence import generate_token, get_mesh_persistence

logger = logging.getLogger(__name__)


@dataclass
class MeshDevice:
    """Runtime representation of a device in mesh memory cache."""

    device_id: str
    device_name: str
    role: DeviceRole
    status: DeviceStatus
    zone: str
    profile: DeviceProfile
    mesh_token: str
    joined_at: datetime
    last_heartbeat: datetime
    last_heartbeat_monotonic: Optional[float] = None

    current_load: float = 0.0
    active_tasks: list[str] = field(default_factory=list)
    pending_sync_count: int = 0
    consecutive_missed_heartbeats: int = 0
    consecutive_successful_heartbeats: int = 0
    avg_latency_ms: float = 0.0
    last_heartbeat_latency_ms: float = 0.0


class MeshService:
    """
    Mesh orchestration service with heartbeat jitter and health checks.

    The service keeps an in-memory cache for fast coordination and mirrors key
    state to MeshPersistenceService when available.
    """

    def __init__(
        self,
        heartbeat_timeout_sec: int = 90,
        heartbeat_interval_sec: int = 30,
        sync_interval_sec: int = 60,
        max_missed_heartbeats: int = 3,
        heartbeat_jitter_ratio: float = 0.2,
        persistence=None,
    ):
        self.heartbeat_timeout_sec = max(1, int(heartbeat_timeout_sec))
        self.heartbeat_interval_sec = max(1, int(heartbeat_interval_sec))
        self.sync_interval_sec = max(1, int(sync_interval_sec))
        self.max_missed_heartbeats = max(1, int(max_missed_heartbeats))
        self.heartbeat_jitter_ratio = min(0.5, max(0.0, float(heartbeat_jitter_ratio)))

        # PHASE1-COORD-003: use 2.0x multiplier for missed-heartbeat threshold.
        self._heartbeat_miss_multiplier = 2.0

        self._persistence = persistence or get_mesh_persistence()
        self._devices_cache: dict[str, MeshDevice] = {}
        self._cache_initialized = False
        self._primary_device_id: Optional[str] = None

    def _calculate_next_heartbeat_interval(self) -> int:
        """Return next heartbeat interval with bounded jitter."""
        base = self.heartbeat_interval_sec
        if self.heartbeat_jitter_ratio <= 0.0:
            return base

        jitter_range = int(base * self.heartbeat_jitter_ratio)
        if jitter_range <= 0:
            return max(1, base)

        offset = random.randint(-jitter_range, jitter_range)
        return max(1, base + offset)

    def _elapsed_since_last_heartbeat(self, device: MeshDevice) -> float:
        """Get elapsed seconds since heartbeat, preferring monotonic time."""
        if device.last_heartbeat_monotonic is not None:
            return max(0.0, time.monotonic() - device.last_heartbeat_monotonic)

        return max(0.0, (datetime.now(UTC) - device.last_heartbeat).total_seconds())

    def _get_device_liveness(self, device: MeshDevice) -> LivenessState:
        """Build liveness view from current cached device state."""
        elapsed = self._elapsed_since_last_heartbeat(device)
        is_healthy = elapsed <= self.heartbeat_timeout_sec

        return LivenessState(
            device_id=device.device_id,
            last_seen=device.last_heartbeat,
            status=device.status,
            is_healthy=is_healthy,
            consecutive_misses=device.consecutive_missed_heartbeats,
            consecutive_successes=device.consecutive_successful_heartbeats,
            avg_latency_ms=device.avg_latency_ms,
            last_heartbeat_latency_ms=device.last_heartbeat_latency_ms,
        )

    async def _check_device_health(self) -> None:
        """Mark devices with stale heartbeats as missed/offline."""
        miss_threshold = self.heartbeat_interval_sec * self._heartbeat_miss_multiplier

        for device in self._devices_cache.values():
            elapsed = self._elapsed_since_last_heartbeat(device)
            if elapsed <= miss_threshold:
                continue

            device.consecutive_missed_heartbeats += 1
            device.consecutive_successful_heartbeats = 0

            if device.consecutive_missed_heartbeats >= self.max_missed_heartbeats:
                device.status = DeviceStatus.OFFLINE

            try:
                if self._persistence is not None:
                    await self._persistence.mark_device_missed_heartbeat(device.device_id)
            except Exception as exc:
                logger.debug(
                    "Failed to persist missed heartbeat for %s: %s",
                    device.device_id,
                    exc,
                )

    def _select_role(self, preferred_role: Optional[DeviceRole]) -> DeviceRole:
        """Select the effective role for a joining device."""
        if preferred_role == DeviceRole.PRIMARY and self._primary_device_id is None:
            return DeviceRole.PRIMARY

        if self._primary_device_id is None:
            return DeviceRole.PRIMARY

        if preferred_role is not None and preferred_role != DeviceRole.PRIMARY:
            return preferred_role

        return DeviceRole.WORKER

    @staticmethod
    def _generate_device_id(role: DeviceRole) -> str:
        """Generate deterministic role-prefixed mesh device IDs."""
        prefix_map = {
            DeviceRole.PRIMARY: "mesh-pri",
            DeviceRole.SECONDARY: "mesh-sec",
            DeviceRole.WORKER: "mesh-wor",
            DeviceRole.MOBILE: "mesh-mob",
            DeviceRole.EDGE: "mesh-edg",
        }
        prefix = prefix_map.get(role, "mesh-dev")
        return f"{prefix}-{uuid.uuid4().hex[:8]}"

    async def join_mesh(
        self,
        device_name: str,
        profile: DeviceProfile,
        preferred_role: Optional[DeviceRole] = None,
        zone: str = "default",
    ) -> tuple[str, str, DeviceRole, str]:
        """Register a device in mesh and return auth token material."""
        role = self._select_role(preferred_role)
        device_id = profile.device_id or self._generate_device_id(role)
        profile.device_id = device_id

        mesh_token, token_hash = generate_token()
        now = datetime.now(UTC)

        device = MeshDevice(
            device_id=device_id,
            device_name=device_name,
            role=role,
            status=DeviceStatus.ONLINE,
            zone=zone,
            profile=profile,
            mesh_token=mesh_token,
            joined_at=now,
            last_heartbeat=now,
            last_heartbeat_monotonic=time.monotonic(),
        )
        self._devices_cache[device_id] = device
        self._cache_initialized = True

        if role == DeviceRole.PRIMARY:
            self._primary_device_id = device_id

        try:
            if self._persistence is not None:
                await self._persistence.store_device(
                    device_id=device_id,
                    device_name=device_name,
                    profile=profile,
                    role=role,
                    zone=zone,
                )
                await self._persistence.store_token(
                    device_id=device_id,
                    token_hash=token_hash,
                    token_type="mesh_auth",
                )
        except Exception as exc:
            logger.debug("Failed to persist mesh join for %s: %s", device_id, exc)

        return device_id, mesh_token, role, zone

    async def process_heartbeat(
        self,
        device_id: str,
        status: DeviceStatus,
        current_load: float,
        active_tasks: list[str],
    ) -> tuple[bool, list[dict[str, str]], bool, int]:
        """
        Process heartbeat and return coordination response tuple.

        Returns:
            (acknowledged, commands, sync_required, next_heartbeat_sec)
        """
        device = self._devices_cache.get(device_id)
        if device is None:
            return False, [], False, self.heartbeat_interval_sec

        now = datetime.now(UTC)
        monotonic_now = time.monotonic()
        elapsed = max(0.0, monotonic_now - (device.last_heartbeat_monotonic or monotonic_now))
        latency_ms = elapsed * 1000.0

        device.status = status
        device.current_load = current_load
        device.active_tasks = list(active_tasks)
        device.last_heartbeat = now
        device.last_heartbeat_monotonic = monotonic_now
        device.pending_sync_count = 0
        device.consecutive_missed_heartbeats = 0
        device.consecutive_successful_heartbeats += 1
        device.last_heartbeat_latency_ms = latency_ms

        alpha = 0.2
        device.avg_latency_ms = alpha * latency_ms + (1 - alpha) * device.avg_latency_ms

        acknowledged = True
        try:
            if self._persistence is not None:
                acknowledged = bool(
                    await self._persistence.update_device_heartbeat(
                        device_id=device_id,
                        status=status,
                        current_load=current_load,
                        active_tasks=list(active_tasks),
                        pending_sync_count=device.pending_sync_count,
                        latency_ms=latency_ms,
                    )
                )
        except Exception as exc:
            logger.debug("Failed to persist heartbeat for %s: %s", device_id, exc)
            acknowledged = False

        next_heartbeat_sec = (
            self._calculate_next_heartbeat_interval()
            if acknowledged
            else self.heartbeat_interval_sec
        )
        return acknowledged, [], False, next_heartbeat_sec

