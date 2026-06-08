"""
Device mesh schemas and enums.

Shared by mesh persistence, task security, and mesh coordination services.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class DeviceRole(str, Enum):
    """Role of a device in the mesh."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    WORKER = "worker"
    MOBILE = "mobile"
    EDGE = "edge"


class DeviceStatus(str, Enum):
    """Current liveness/availability status for a device."""

    ONLINE = "online"
    OFFLINE = "offline"
    IDLE = "idle"
    BUSY = "busy"
    DRAINING = "draining"
    MAINTENANCE = "maintenance"


class DeviceCapability(str, Enum):
    """Hardware/software capabilities advertised by a device."""

    CPU = "cpu"
    GPU = "gpu"
    TPU = "tpu"
    MEMORY = "memory"
    STORAGE = "storage"
    NETWORK = "network"


class DeviceProfile(BaseModel):
    """Hardware and software profile used for scheduling/security checks."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    hostname: str
    capabilities: list[DeviceCapability] = Field(default_factory=list)
    task_types: list[str] = Field(default_factory=list)

    cpu_cores: int = 1
    ram_gb: float = 1.0
    storage_gb: float = 10.0
    bandwidth_mbps: float = 0.0
    gpu_vram_gb: Optional[float] = None

    max_concurrent_tasks: int = 1
    device_id: Optional[str] = None


class LivenessState(BaseModel):
    """Per-device liveness and heartbeat quality details."""

    model_config = ConfigDict(extra="allow")

    device_id: str
    last_seen: datetime
    status: DeviceStatus
    is_healthy: bool
    consecutive_misses: int = 0
    consecutive_successes: int = 0
    avg_latency_ms: float = 0.0
    last_heartbeat_latency_ms: float = 0.0


class DeviceState(BaseModel):
    """Complete runtime state for a device."""

    model_config = ConfigDict(extra="allow")

    device_id: str
    device_name: str
    role: DeviceRole
    status: DeviceStatus
    zone: str = "default"
    profile: DeviceProfile
    liveness: LivenessState

    joined_at: datetime
    last_heartbeat: Optional[datetime] = None
    current_load: float = 0.0
    active_tasks: list[str] = Field(default_factory=list)
    pending_sync_count: int = 0
    owner_id: Optional[str] = None


class ZoneType(str, Enum):
    """Logical mesh zone type."""

    LOCAL = "local"
    REGIONAL = "regional"
    GLOBAL = "global"


class MeshJoinRequest(BaseModel):
    """Request to join the device mesh."""

    device_name: str = Field(min_length=1, max_length=100)
    profile: DeviceProfile
    preferred_role: DeviceRole = DeviceRole.WORKER
    preferred_zone: Optional[str] = None
    public_key: Optional[str] = None
    owner_id: Optional[str] = None


class MeshJoinResponse(BaseModel):
    """Response after joining the mesh."""

    device_id: str
    mesh_token: str
    assigned_role: DeviceRole
    assigned_zone: str
    primary_device_id: Optional[str] = None
    heartbeat_interval_sec: int = 30
    sync_interval_sec: int = 60
    websocket_url: str
    message: str = "Successfully joined the device mesh"


class HeartbeatRequest(BaseModel):
    """Periodic heartbeat from a mesh device."""

    device_id: str
    status: DeviceStatus = DeviceStatus.IDLE
    current_load: float = Field(default=0.0, ge=0.0, le=1.0)
    active_tasks: list[str] = Field(default_factory=list)
    pending_sync_count: int = Field(default=0, ge=0)
    metrics: dict[str, Any] = Field(default_factory=dict)


class HeartbeatResponse(BaseModel):
    """Response to a mesh heartbeat."""

    acknowledged: bool = True
    server_time: datetime
    next_heartbeat_sec: int = 30
    commands: list[dict[str, Any]] = Field(default_factory=list)
    primary_device_id: Optional[str] = None
    sync_required: bool = False
    sync_entities: list[str] = Field(default_factory=list)


class DeviceUpdateRequest(BaseModel):
    """Request to update mesh device properties."""

    device_name: Optional[str] = None
    preferred_role: Optional[DeviceRole] = None
    profile: Optional[DeviceProfile] = None
    max_concurrent_tasks: Optional[int] = Field(default=None, ge=1, le=100)


class MeshLeaveRequest(BaseModel):
    """Request to leave the mesh gracefully."""

    device_id: str
    reason: str = "shutdown"
    transfer_tasks_to: Optional[str] = None
    immediate: bool = False


class ZoneInfo(BaseModel):
    """Aggregated information about a mesh zone."""

    zone_id: str
    zone_type: ZoneType = ZoneType.LOCAL
    device_count: int
    healthy_count: int
    total_capacity: dict[str, float] = Field(default_factory=dict)
    available_capacity: dict[str, float] = Field(default_factory=dict)


class TopologySnapshot(BaseModel):
    """Snapshot of the mesh topology."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    total_devices: int
    healthy_devices: int
    online_devices: int
    offline_devices: int
    primary_device_id: Optional[str] = None
    secondary_device_ids: list[str] = Field(default_factory=list)
    devices: list[DeviceState] = Field(default_factory=list)
    zones: dict[str, ZoneInfo] = Field(default_factory=dict)
    total_capacity: dict[str, float] = Field(default_factory=dict)
    available_capacity: dict[str, float] = Field(default_factory=dict)
    pending_sync_total: int = 0
    mesh_health_score: float = Field(default=1.0, ge=0.0, le=1.0)


class EnrollmentCodeStatus(str, Enum):
    """Enrollment-code lifecycle state."""

    ACTIVE = "active"
    USED = "used"
    EXPIRED = "expired"
    REVOKED = "revoked"


class EnrollmentCodeCreateRequest(BaseModel):
    """Request payload for creating a one-time enrollment code."""

    intended_device_name: Optional[str] = None
    intended_role: DeviceRole = DeviceRole.WORKER
    expires_in_hours: float = Field(default=24.0, gt=0.0, le=168.0)


class EnrollmentCodeResponse(BaseModel):
    """Response payload describing an enrollment code."""

    id: str
    status: EnrollmentCodeStatus = EnrollmentCodeStatus.ACTIVE
    code: Optional[str] = None
    created_by_device_id: Optional[str] = None
    intended_device_name: Optional[str] = None
    intended_role: DeviceRole = DeviceRole.WORKER
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime
    used_at: Optional[datetime] = None
    used_by_device_id: Optional[str] = None


class EnrollmentRequest(BaseModel):
    """Request payload for joining mesh with an enrollment code."""

    device_name: str
    profile: DeviceProfile
    enrollment_code: str = Field(min_length=20)


class EnrollmentResponse(BaseModel):
    """Response payload for successful enrollment."""

    device_id: str
    mesh_token: str
    role: DeviceRole
    zone: str = "default"


class TokenRefreshRequest(BaseModel):
    """Request payload for token refresh."""

    refresh_token: str = Field(min_length=20)


class TokenRefreshResponse(BaseModel):
    """Response payload with rotated access/refresh tokens."""

    access_token: str
    access_token_expires_at: datetime
    refresh_token: str
    refresh_token_expires_at: datetime
    token_type: str = "Bearer"

