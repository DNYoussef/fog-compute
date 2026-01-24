"""
Fog Bridge Schemas
Pydantic models for Life OS Dashboard integration

This module defines the API contracts for:
- Device registration with Life OS Dashboard
- Task distribution protocol
- Health monitoring
- Real-time sync state
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any, Literal
from datetime import datetime
from enum import Enum
from uuid import UUID
import re


class DeviceType(str, Enum):
    """Type of fog compute device"""
    DESKTOP = "desktop"  # Primary workstation
    LAPTOP = "laptop"    # Portable compute
    MOBILE = "mobile"    # Phone/tablet (PWA)
    SERVER = "server"    # Cloud/dedicated server
    IOT = "iot"          # IoT device
    EDGE = "edge"        # Edge gateway


class DeviceStatus(str, Enum):
    """Device connection status"""
    ONLINE = "online"
    OFFLINE = "offline"
    IDLE = "idle"
    BUSY = "busy"
    MAINTENANCE = "maintenance"


class SyncStatus(str, Enum):
    """Synchronization status with Life OS"""
    SYNCED = "synced"
    SYNCING = "syncing"
    PENDING = "pending"
    CONFLICT = "conflict"
    ERROR = "error"


# === Device Registration ===

class DeviceCapabilities(BaseModel):
    """Hardware and software capabilities of a device"""
    cpu_cores: int = Field(default=1, ge=1)
    memory_mb: int = Field(default=512, ge=256)
    storage_mb: int = Field(default=1024, ge=100)
    gpu_available: bool = False
    gpu_name: Optional[str] = None
    network_bandwidth_mbps: Optional[float] = None
    supports_docker: bool = False
    supports_wasm: bool = False
    python_version: Optional[str] = None
    node_version: Optional[str] = None


class DeviceRegisterRequest(BaseModel):
    """Request to register a device with the fog network"""
    device_name: str = Field(..., min_length=1, max_length=100)
    device_type: DeviceType
    capabilities: DeviceCapabilities
    region: Optional[str] = None
    timezone: Optional[str] = None
    life_os_user_id: Optional[str] = None  # Link to Life OS user

    @field_validator('device_name')
    @classmethod
    def validate_device_name(cls, v: str) -> str:
        """Ensure device name is safe for use as identifier"""
        if not re.match(r'^[a-zA-Z0-9_\-\s]+$', v):
            raise ValueError('Device name must be alphanumeric with underscores, hyphens, or spaces')
        return v.strip()


class DeviceRegisterResponse(BaseModel):
    """Response after device registration"""
    device_id: str
    access_token: str
    refresh_token: str
    token_expires_at: datetime
    websocket_url: str
    message: str = "Device registered successfully"


class DeviceInfo(BaseModel):
    """Full device information"""
    device_id: str
    device_name: str
    device_type: DeviceType
    status: DeviceStatus
    capabilities: DeviceCapabilities
    region: Optional[str] = None
    timezone: Optional[str] = None
    life_os_user_id: Optional[str] = None
    registered_at: datetime
    last_heartbeat: Optional[datetime] = None
    current_task_id: Optional[str] = None
    total_tasks_completed: int = 0
    uptime_percent: float = 100.0
    reputation_score: float = 1.0

    class Config:
        from_attributes = True


# === Heartbeat & Health ===

class HeartbeatRequest(BaseModel):
    """Periodic heartbeat from device"""
    device_id: str
    cpu_usage_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    memory_usage_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    storage_usage_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    network_latency_ms: Optional[float] = None
    current_task_id: Optional[str] = None
    task_progress_percent: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    error_count: int = 0


class HeartbeatResponse(BaseModel):
    """Response to device heartbeat"""
    acknowledged: bool = True
    server_time: datetime
    next_heartbeat_seconds: int = 30
    commands: list[dict[str, Any]] = Field(default_factory=list)  # Remote commands


class HealthCheckResponse(BaseModel):
    """Health status of fog bridge service"""
    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    uptime_seconds: float
    connected_devices: int
    active_tasks: int
    life_os_connected: bool
    last_life_os_sync: Optional[datetime] = None
    services: dict[str, dict[str, Any]] = Field(default_factory=dict)


# === Task Distribution ===

class TaskPriority(str, Enum):
    """Task priority levels"""
    CRITICAL = "critical"  # P0 - Immediate
    HIGH = "high"          # P1 - Today
    NORMAL = "normal"      # P2 - This week
    LOW = "low"            # P3 - When possible
    BACKGROUND = "background"  # P4 - Idle time only


class TaskType(str, Enum):
    """Types of distributed tasks"""
    COMPUTE = "compute"        # CPU-intensive computation
    AI_INFERENCE = "ai_inference"  # AI model inference
    DATA_PROCESSING = "data_processing"  # Data transformation
    BUILD = "build"            # Code compilation/build
    TEST = "test"              # Test execution
    SYNC = "sync"              # Data synchronization
    PIPELINE = "pipeline"      # Pipeline step execution
    CUSTOM = "custom"          # User-defined task


class FogTaskCreate(BaseModel):
    """Create a new distributed task"""
    task_type: TaskType
    priority: TaskPriority = TaskPriority.NORMAL
    payload: dict[str, Any] = Field(default_factory=dict)
    resource_requirements: Optional[DeviceCapabilities] = None
    target_device_id: Optional[str] = None  # Route to specific device
    target_device_type: Optional[DeviceType] = None  # Route to device type
    timeout_seconds: int = Field(default=3600, ge=10, le=86400)
    retry_count: int = Field(default=3, ge=0, le=10)
    life_os_bead_id: Optional[str] = None  # Link to Beads task
    callback_url: Optional[str] = None


class FogTaskResponse(BaseModel):
    """Response for task operations"""
    task_id: str
    status: Literal["queued", "assigned", "running", "completed", "failed", "cancelled"]
    assigned_device_id: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress_percent: float = 0.0
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None


class TaskResultSubmit(BaseModel):
    """Submit task execution result"""
    task_id: str
    device_id: str
    success: bool
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: int
    resource_usage: Optional[dict[str, float]] = None


# === Life OS Sync ===

class SyncEntityType(str, Enum):
    """Types of entities to sync with Life OS"""
    BEAD = "bead"          # Task from Beads
    MEMORY = "memory"       # Memory MCP entry
    CALENDAR = "calendar"   # Calendar event
    PIPELINE = "pipeline"   # Pipeline definition


class SyncRequest(BaseModel):
    """Request to sync data with Life OS"""
    device_id: str
    entity_type: SyncEntityType
    entity_id: str
    operation: Literal["create", "update", "delete"]
    data: dict[str, Any]
    local_version: int = 1
    local_timestamp: datetime


class SyncResponse(BaseModel):
    """Response from sync operation"""
    entity_id: str
    status: SyncStatus
    server_version: int
    server_timestamp: datetime
    merged_data: Optional[dict[str, Any]] = None
    conflict_resolution: Optional[str] = None


class SyncBatchRequest(BaseModel):
    """Batch sync multiple entities"""
    device_id: str
    sync_items: list[SyncRequest] = Field(..., max_length=100)


class SyncBatchResponse(BaseModel):
    """Response for batch sync"""
    total: int
    synced: int
    failed: int
    conflicts: int
    results: list[SyncResponse]


# === Quota Management ===

class DeviceQuota(BaseModel):
    """Resource quota for a device"""
    device_id: str
    max_concurrent_tasks: int = 5
    max_cpu_percent: float = 80.0
    max_memory_percent: float = 80.0
    max_storage_mb: int = 10240
    max_bandwidth_mbps: float = 100.0
    daily_task_limit: int = 1000
    tasks_today: int = 0
    quota_reset_at: datetime


class QuotaUpdateRequest(BaseModel):
    """Update device quota"""
    max_concurrent_tasks: Optional[int] = Field(default=None, ge=1, le=100)
    max_cpu_percent: Optional[float] = Field(default=None, ge=10.0, le=100.0)
    max_memory_percent: Optional[float] = Field(default=None, ge=10.0, le=100.0)
    max_storage_mb: Optional[int] = Field(default=None, ge=100)
    max_bandwidth_mbps: Optional[float] = Field(default=None, ge=1.0)
    daily_task_limit: Optional[int] = Field(default=None, ge=10)


# === Network Topology ===

class NetworkTopologyResponse(BaseModel):
    """Current fog network topology"""
    total_devices: int
    devices_by_type: dict[str, int]
    devices_by_status: dict[str, int]
    devices_by_region: dict[str, int]
    total_cpu_cores: int
    available_cpu_cores: int
    total_memory_mb: int
    available_memory_mb: int
    queued_tasks: int
    running_tasks: int
    completed_tasks_24h: int
    life_os_sync_status: SyncStatus
    snapshot_time: datetime


# === WebSocket Messages ===

class WSMessageType(str, Enum):
    """WebSocket message types"""
    HEARTBEAT = "heartbeat"
    TASK_ASSIGNED = "task_assigned"
    TASK_CANCELLED = "task_cancelled"
    SYNC_UPDATE = "sync_update"
    COMMAND = "command"
    STATUS_UPDATE = "status_update"
    ERROR = "error"


class WSMessage(BaseModel):
    """WebSocket message structure"""
    type: WSMessageType
    device_id: str
    timestamp: datetime
    payload: dict[str, Any]
