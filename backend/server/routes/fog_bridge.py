"""
Fog Bridge API Routes
Fog Compute Mesh Device Management

This module implements the API bridge for fog compute node coordination.
It provides endpoints for:
- Device registration and authentication
- Task distribution and monitoring
- Health monitoring
- Network topology queries
- Quota management

API Design:
- REST endpoints for CRUD operations
- WebSocket for real-time communication (see websocket routes)
- Rate limiting via middleware
- JWT-based device authentication
"""
from fastapi import APIRouter, HTTPException, Depends, Header, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Any
from datetime import datetime, UTC
import logging
import asyncio
import json
import os
from enum import Enum
from pathlib import Path

from pydantic import BaseModel

from ..schemas.fog_bridge import (
    DeviceRegisterRequest,
    DeviceRegisterResponse,
    DeviceInfo,
    DeviceStatus,
    DeviceType,
    HeartbeatRequest,
    HeartbeatResponse,
    HealthCheckResponse,
    FogTaskCreate,
    FogTaskResponse,
    TaskResultSubmit,
    DeviceQuota,
    QuotaUpdateRequest,
    NetworkTopologyResponse,
)
from ..services.device_auth import get_device_auth_service, DeviceAuthService
from ..services.health_checks import HealthCheckManager, HealthCheckConfig, HealthStatus
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/fog-bridge", tags=["fog-bridge"])
security = HTTPBearer(auto_error=False)

# Service startup time for health check
_service_start_time = datetime.now(UTC)


def _default_state_path() -> Path:
    return Path(os.getenv("FOG_BRIDGE_STATE_PATH", "data/fog_bridge_state.json"))


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


def _parse_datetime(value: Any) -> Any:
    if isinstance(value, datetime) or value is None:
        return value
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return value
    return value


def _hydrate_device(data: dict[str, Any]) -> dict[str, Any]:
    hydrated = dict(data)
    for key in ("registered_at", "last_heartbeat"):
        hydrated[key] = _parse_datetime(hydrated.get(key))
    return hydrated


def _hydrate_task(data: dict[str, Any]) -> dict[str, Any]:
    hydrated = dict(data)
    for key in ("created_at", "started_at", "completed_at"):
        hydrated[key] = _parse_datetime(hydrated.get(key))
    return hydrated


class FogBridgeStateStore:
    """File-backed state for fog bridge device registry, task queue, and quotas."""

    def __init__(self, state_path: Path | str | None = None):
        self.state_path = Path(state_path) if state_path is not None else _default_state_path()
        self.devices: dict[str, dict[str, Any]] = {}
        self.tasks: dict[str, dict[str, Any]] = {}
        self.quotas: dict[str, DeviceQuota] = {}
        self.load()

    def load(self) -> None:
        if not self.state_path.exists():
            self.devices = {}
            self.tasks = {}
            self.quotas = {}
            return

        raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.devices = {
            device_id: _hydrate_device(device)
            for device_id, device in raw.get("devices", {}).items()
        }
        self.tasks = {
            task_id: _hydrate_task(task)
            for task_id, task in raw.get("tasks", {}).items()
        }
        self.quotas = {
            device_id: DeviceQuota.model_validate(quota)
            for device_id, quota in raw.get("quotas", {}).items()
        }

    def save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "devices": _jsonable(self.devices),
            "tasks": _jsonable(self.tasks),
            "quotas": _jsonable(self.quotas),
        }
        tmp_path = self.state_path.with_suffix(f"{self.state_path.suffix}.tmp")
        tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(self.state_path)


_fog_bridge_store = FogBridgeStateStore()
_registered_devices: dict[str, dict[str, Any]] = _fog_bridge_store.devices
_task_queue: dict[str, dict[str, Any]] = _fog_bridge_store.tasks
_device_quotas: dict[str, DeviceQuota] = _fog_bridge_store.quotas


def _bind_fog_bridge_store(store: FogBridgeStateStore) -> None:
    global _fog_bridge_store, _registered_devices, _task_queue, _device_quotas
    _fog_bridge_store = store
    _registered_devices = store.devices
    _task_queue = store.tasks
    _device_quotas = store.quotas


def configure_fog_bridge_state_store(state_path: Path | str) -> FogBridgeStateStore:
    store = FogBridgeStateStore(state_path)
    _bind_fog_bridge_store(store)
    return store


def persist_fog_bridge_state() -> None:
    _fog_bridge_store.save()


def reload_fog_bridge_state() -> None:
    _fog_bridge_store.load()
    _bind_fog_bridge_store(_fog_bridge_store)


# === Dependencies ===

async def get_current_device(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    authorization: Optional[str] = Header(default=None)
) -> str:
    """
    Validate device authentication and return device ID

    Accepts token from either:
    - HTTPBearer (Authorization: Bearer <token>)
    - Raw Authorization header
    """
    token = None

    if credentials:
        token = credentials.credentials
    elif authorization and authorization.startswith("Bearer "):
        token = authorization[7:]

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Device authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )

    auth_service = get_device_auth_service()
    device_id = await auth_service.validate_access_token(token)

    if not device_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired device token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return device_id


async def get_optional_device(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[str]:
    """Get device ID if authenticated, None otherwise"""
    if not credentials:
        return None

    auth_service = get_device_auth_service()
    return await auth_service.validate_access_token(credentials.credentials)


# === Device Registration ===

@router.post("/devices/register", response_model=DeviceRegisterResponse)
async def register_device(request: DeviceRegisterRequest) -> DeviceRegisterResponse:
    """
    Register a new device with the fog compute network

    This endpoint:
    1. Creates a unique device ID
    2. Generates secure credentials (access + refresh tokens)
    3. Links device to owner if provided
    4. Returns WebSocket URL for real-time communication

    Rate limit: 10 requests/minute (auth category)
    """
    auth_service = get_device_auth_service()

    try:
        device_id, device_secret, access_token, refresh_token, token_expires_at = \
            await auth_service.register_device(
                device_name=request.device_name,
                device_type=request.device_type.value,
                capabilities=request.capabilities.model_dump(),
                owner_id=request.owner_id,
                region=request.region
            )

        # Store device info
        _registered_devices[device_id] = {
            "device_name": request.device_name,
            "device_type": request.device_type,
            "capabilities": request.capabilities.model_dump(),
            "region": request.region,
            "timezone": request.timezone,
            "owner_id": request.owner_id,
            "status": DeviceStatus.IDLE,
            "registered_at": datetime.now(UTC),
            "last_heartbeat": None,
            "current_task_id": None,
            "total_tasks_completed": 0,
            "uptime_percent": 100.0,
            "reputation_score": 1.0
        }

        # Initialize default quota
        _device_quotas[device_id] = DeviceQuota(
            device_id=device_id,
            quota_reset_at=datetime.now(UTC).replace(hour=0, minute=0, second=0) + \
                          __import__('datetime').timedelta(days=1)
        )
        persist_fog_bridge_state()

        # WebSocket URL
        ws_url = f"ws://{settings.API_HOST}:{settings.API_PORT}/api/fog-bridge/ws/{device_id}"

        logger.info(f"Device registered: {device_id} ({request.device_name})")

        return DeviceRegisterResponse(
            device_id=device_id,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
            websocket_url=ws_url
        )

    except Exception as e:
        logger.error(f"Device registration failed: {e}")
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


@router.post("/devices/authenticate")
async def authenticate_device(
    device_id: str,
    device_secret: str
) -> dict[str, Any]:
    """
    Authenticate a device and get new tokens

    Use this endpoint when access token expires and refresh token is invalid.
    Requires the original device_secret from registration.
    """
    auth_service = get_device_auth_service()

    result = await auth_service.authenticate_device(device_id, device_secret)

    if not result:
        raise HTTPException(
            status_code=401,
            detail="Invalid device credentials"
        )

    access_token, refresh_token, token_expires_at = result

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_expires_at": token_expires_at.isoformat(),
        "token_type": "bearer"
    }


@router.post("/devices/refresh")
async def refresh_token(refresh_token: str) -> dict[str, Any]:
    """
    Refresh access token using refresh token

    Use this endpoint when access token expires.
    """
    auth_service = get_device_auth_service()

    result = await auth_service.refresh_access_token(refresh_token)

    if not result:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired refresh token"
        )

    access_token, token_expires_at = result

    return {
        "access_token": access_token,
        "token_expires_at": token_expires_at.isoformat(),
        "token_type": "bearer"
    }


@router.get("/devices/me", response_model=DeviceInfo)
async def get_current_device_info(
    device_id: str = Depends(get_current_device)
) -> DeviceInfo:
    """Get information about the authenticated device"""
    device_data = _registered_devices.get(device_id)

    if not device_data:
        raise HTTPException(status_code=404, detail="Device not found")

    return DeviceInfo(
        device_id=device_id,
        **device_data
    )


@router.get("/devices", response_model=list[DeviceInfo])
async def list_devices(
    device_id: str = Depends(get_current_device),
    status: Optional[DeviceStatus] = None,
    device_type: Optional[DeviceType] = None,
    owner_id: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0)
) -> list[DeviceInfo]:
    """
    List registered devices with optional filters

    Requires device authentication.
    """
    devices = []

    for did, data in _registered_devices.items():
        # Apply filters
        if status and data.get("status") != status:
            continue
        if device_type and data.get("device_type") != device_type:
            continue
        if owner_id and data.get("owner_id") != owner_id:
            continue

        devices.append(DeviceInfo(device_id=did, **data))

    # Apply pagination
    return devices[offset:offset + limit]


@router.delete("/devices/{target_device_id}")
async def unregister_device(
    target_device_id: str,
    device_id: str = Depends(get_current_device)
) -> dict[str, str]:
    """
    Unregister a device from the fog network

    A device can only unregister itself or devices linked to the same owner.
    """
    # Check authorization
    if device_id != target_device_id:
        # Check if same owner
        requester_owner = _registered_devices.get(device_id, {}).get("owner_id")
        target_owner = _registered_devices.get(target_device_id, {}).get("owner_id")

        if not requester_owner or requester_owner != target_owner:
            raise HTTPException(status_code=403, detail="Not authorized to unregister this device")

    # Revoke device
    auth_service = get_device_auth_service()
    await auth_service.revoke_device(target_device_id)

    # Remove from registry
    if target_device_id in _registered_devices:
        del _registered_devices[target_device_id]
    if target_device_id in _device_quotas:
        del _device_quotas[target_device_id]
    persist_fog_bridge_state()

    logger.info(f"Device unregistered: {target_device_id}")

    return {"message": f"Device {target_device_id} unregistered successfully"}


# === Heartbeat & Health ===

@router.post("/heartbeat", response_model=HeartbeatResponse)
async def device_heartbeat(
    request: HeartbeatRequest,
    device_id: str = Depends(get_current_device)
) -> HeartbeatResponse:
    """
    Process device heartbeat and return any pending commands

    Devices should send heartbeats every 30 seconds.
    """
    if request.device_id != device_id:
        raise HTTPException(status_code=403, detail="Device ID mismatch")

    device_data = _registered_devices.get(device_id)
    if not device_data:
        raise HTTPException(status_code=404, detail="Device not found")

    # Update device state
    device_data["last_heartbeat"] = datetime.now(UTC)
    device_data["cpu_usage_percent"] = request.cpu_usage_percent
    device_data["memory_usage_percent"] = request.memory_usage_percent
    device_data["current_task_id"] = request.current_task_id

    # Update status based on task state
    if request.current_task_id:
        device_data["status"] = DeviceStatus.BUSY
    elif request.cpu_usage_percent < 10 and request.memory_usage_percent < 30:
        device_data["status"] = DeviceStatus.IDLE
    else:
        device_data["status"] = DeviceStatus.ONLINE
    persist_fog_bridge_state()

    # Check for pending commands (task assignments, etc.)
    commands = []

    # Check for assigned tasks
    for task_id, task_data in _task_queue.items():
        if task_data.get("assigned_device_id") == device_id and \
           task_data.get("status") == "assigned":
            commands.append({
                "type": "task_assigned",
                "task_id": task_id,
                "task_data": task_data
            })

    return HeartbeatResponse(
        acknowledged=True,
        server_time=datetime.now(UTC),
        next_heartbeat_seconds=30,
        commands=commands
    )


@router.get("/health", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    """
    Get fog bridge service health status

    Public endpoint - no authentication required.
    """
    uptime_seconds = (datetime.now(UTC) - _service_start_time).total_seconds()

    # Count connected devices (heartbeat within last 2 minutes)
    connected_devices = sum(
        1 for d in _registered_devices.values()
        if d.get("last_heartbeat") and
        (datetime.now(UTC) - d["last_heartbeat"]).total_seconds() < 120
    )

    # Count active tasks
    active_tasks = sum(
        1 for t in _task_queue.values()
        if t.get("status") in ("queued", "assigned", "running")
    )

    return HealthCheckResponse(
        status="healthy",
        version=settings.API_VERSION,
        uptime_seconds=uptime_seconds,
        connected_devices=connected_devices,
        active_tasks=active_tasks,
        services={
            "device_auth": {"status": "healthy"},
            "task_queue": {"status": "healthy", "pending": len(_task_queue)},
            "sync": {"status": "healthy"}
        }
    )


# === Task Distribution ===

@router.post("/tasks", response_model=FogTaskResponse)
async def create_task(
    request: FogTaskCreate,
    device_id: str = Depends(get_current_device)
) -> FogTaskResponse:
    """
    Create a new distributed task

    Tasks are routed to available devices based on:
    - Resource requirements
    - Target device/device type preferences
    - Device availability and load
    - Reputation score
    """
    from uuid import uuid4

    task_id = f"task-{uuid4().hex[:12]}"

    # Find suitable device
    assigned_device = None

    if request.target_device_id:
        # Route to specific device
        if request.target_device_id in _registered_devices:
            device_data = _registered_devices[request.target_device_id]
            if device_data.get("status") in (DeviceStatus.ONLINE, DeviceStatus.IDLE):
                assigned_device = request.target_device_id
    else:
        # Find best available device
        candidates = []
        for did, data in _registered_devices.items():
            # Check status
            if data.get("status") not in (DeviceStatus.ONLINE, DeviceStatus.IDLE):
                continue

            # Check device type filter
            if request.target_device_type and data.get("device_type") != request.target_device_type:
                continue

            # Check resource requirements
            if request.resource_requirements:
                caps = data.get("capabilities", {})
                if caps.get("cpu_cores", 0) < request.resource_requirements.cpu_cores:
                    continue
                if caps.get("memory_mb", 0) < request.resource_requirements.memory_mb:
                    continue
                if request.resource_requirements.gpu_available and not caps.get("gpu_available"):
                    continue

            # Check quota
            quota = _device_quotas.get(did)
            if quota and quota.tasks_today >= quota.daily_task_limit:
                continue

            candidates.append((did, data.get("reputation_score", 1.0)))

        # Select by reputation (highest first)
        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            assigned_device = candidates[0][0]

    # Create task record
    task_data = {
        "task_id": task_id,
        "task_type": request.task_type.value,
        "priority": request.priority.value,
        "payload": request.payload,
        "resource_requirements": request.resource_requirements.model_dump() if request.resource_requirements else None,
        "target_device_id": request.target_device_id,
        "target_device_type": request.target_device_type.value if request.target_device_type else None,
        "timeout_seconds": request.timeout_seconds,
        "retry_count": request.retry_count,
        "callback_url": request.callback_url,
        "status": "assigned" if assigned_device else "queued",
        "assigned_device_id": assigned_device,
        "created_at": datetime.now(UTC),
        "created_by_device": device_id,
        "started_at": None,
        "completed_at": None,
        "progress_percent": 0.0,
        "result": None,
        "error": None
    }

    _task_queue[task_id] = task_data

    # Update device quota
    if assigned_device:
        quota = _device_quotas.get(assigned_device)
        if quota:
            quota.tasks_today += 1
    persist_fog_bridge_state()

    logger.info(f"Task created: {task_id} -> {assigned_device or 'queued'}")

    return FogTaskResponse(
        task_id=task_id,
        status=task_data["status"],
        assigned_device_id=assigned_device,
        created_at=task_data["created_at"],
        progress_percent=0.0
    )


@router.get("/tasks/{task_id}", response_model=FogTaskResponse)
async def get_task(
    task_id: str,
    device_id: str = Depends(get_current_device)
) -> FogTaskResponse:
    """Get task status and details"""
    task_data = _task_queue.get(task_id)

    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")

    return FogTaskResponse(
        task_id=task_id,
        status=task_data["status"],
        assigned_device_id=task_data.get("assigned_device_id"),
        created_at=task_data["created_at"],
        started_at=task_data.get("started_at"),
        completed_at=task_data.get("completed_at"),
        progress_percent=task_data.get("progress_percent", 0.0),
        result=task_data.get("result"),
        error=task_data.get("error")
    )


@router.post("/tasks/{task_id}/result")
async def submit_task_result(
    task_id: str,
    request: TaskResultSubmit,
    device_id: str = Depends(get_current_device)
) -> dict[str, str]:
    """Submit task execution result"""
    task_data = _task_queue.get(task_id)

    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")

    if task_data.get("assigned_device_id") != device_id:
        raise HTTPException(status_code=403, detail="Not authorized to submit result for this task")

    # Update task
    task_data["status"] = "completed" if request.success else "failed"
    task_data["completed_at"] = datetime.now(UTC)
    task_data["result"] = request.result
    task_data["error"] = request.error
    task_data["execution_time_ms"] = request.execution_time_ms

    # Update device stats
    device_data = _registered_devices.get(device_id)
    if device_data:
        device_data["current_task_id"] = None
        if request.success:
            device_data["total_tasks_completed"] = device_data.get("total_tasks_completed", 0) + 1
    persist_fog_bridge_state()

    logger.info(f"Task {task_id} completed: {'success' if request.success else 'failed'}")

    return {"message": f"Task result submitted: {task_data['status']}"}


@router.delete("/tasks/{task_id}")
async def cancel_task(
    task_id: str,
    device_id: str = Depends(get_current_device)
) -> dict[str, str]:
    """Cancel a pending or running task"""
    task_data = _task_queue.get(task_id)

    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")

    if task_data.get("created_by_device") != device_id:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this task")

    if task_data["status"] in ("completed", "failed", "cancelled"):
        raise HTTPException(status_code=400, detail=f"Task already {task_data['status']}")

    task_data["status"] = "cancelled"
    task_data["completed_at"] = datetime.now(UTC)
    persist_fog_bridge_state()

    logger.info(f"Task cancelled: {task_id}")

    return {"message": f"Task {task_id} cancelled"}


# === Quota Management ===

@router.get("/quotas/me", response_model=DeviceQuota)
async def get_my_quota(
    device_id: str = Depends(get_current_device)
) -> DeviceQuota:
    """Get quota for the authenticated device"""
    quota = _device_quotas.get(device_id)

    if not quota:
        raise HTTPException(status_code=404, detail="Quota not found")

    return quota


@router.patch("/quotas/{target_device_id}")
async def update_quota(
    target_device_id: str,
    request: QuotaUpdateRequest,
    device_id: str = Depends(get_current_device)
) -> DeviceQuota:
    """
    Update device quota

    Only devices with the same owner can update each other's quotas.
    """
    # Check authorization
    requester_owner = _registered_devices.get(device_id, {}).get("owner_id")
    target_owner = _registered_devices.get(target_device_id, {}).get("owner_id")

    if not requester_owner or requester_owner != target_owner:
        raise HTTPException(status_code=403, detail="Not authorized to update this device's quota")

    quota = _device_quotas.get(target_device_id)
    if not quota:
        raise HTTPException(status_code=404, detail="Quota not found")

    # Apply updates
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(quota, key, value)
    persist_fog_bridge_state()

    return quota


# === Network Topology ===

@router.get("/topology", response_model=NetworkTopologyResponse)
async def get_network_topology(
    device_id: str = Depends(get_current_device)
) -> NetworkTopologyResponse:
    """
    Get current fog network topology snapshot

    Provides an overview of all connected devices and their capabilities.
    """
    # Count devices by type
    devices_by_type = {}
    devices_by_status = {}
    devices_by_region = {}
    total_cpu = 0
    available_cpu = 0
    total_memory = 0
    available_memory = 0

    for did, data in _registered_devices.items():
        # Count by type
        dtype = data.get("device_type", DeviceType.DESKTOP)
        if isinstance(dtype, DeviceType):
            dtype = dtype.value
        devices_by_type[dtype] = devices_by_type.get(dtype, 0) + 1

        # Count by status
        dstatus = data.get("status", DeviceStatus.OFFLINE)
        if isinstance(dstatus, DeviceStatus):
            dstatus = dstatus.value
        devices_by_status[dstatus] = devices_by_status.get(dstatus, 0) + 1

        # Count by region
        region = data.get("region", "unknown")
        devices_by_region[region] = devices_by_region.get(region, 0) + 1

        # Sum resources
        caps = data.get("capabilities", {})
        total_cpu += caps.get("cpu_cores", 0)
        total_memory += caps.get("memory_mb", 0)

        # Available resources (from idle/online devices)
        if dstatus in ("idle", "online"):
            cpu_usage = data.get("cpu_usage_percent", 0) / 100
            mem_usage = data.get("memory_usage_percent", 0) / 100
            available_cpu += int(caps.get("cpu_cores", 0) * (1 - cpu_usage))
            available_memory += int(caps.get("memory_mb", 0) * (1 - mem_usage))

    # Count tasks
    queued_tasks = sum(1 for t in _task_queue.values() if t.get("status") == "queued")
    running_tasks = sum(1 for t in _task_queue.values() if t.get("status") in ("assigned", "running"))

    # Count completed tasks in last 24h
    from datetime import timedelta
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    completed_24h = sum(
        1 for t in _task_queue.values()
        if t.get("status") == "completed" and
        t.get("completed_at") and t["completed_at"] > cutoff
    )

    return NetworkTopologyResponse(
        total_devices=len(_registered_devices),
        devices_by_type=devices_by_type,
        devices_by_status=devices_by_status,
        devices_by_region=devices_by_region,
        total_cpu_cores=total_cpu,
        available_cpu_cores=available_cpu,
        total_memory_mb=total_memory,
        available_memory_mb=available_memory,
        queued_tasks=queued_tasks,
        running_tasks=running_tasks,
        completed_tasks_24h=completed_24h,
        snapshot_time=datetime.now(UTC)
    )
