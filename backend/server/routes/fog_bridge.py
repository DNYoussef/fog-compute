"""
Fog task control-plane routes.

This request path owns worker registration, explicit leasing, lease renewal,
task completion, and topology/health reads from persistent state.
"""
from __future__ import annotations

from datetime import UTC, datetime
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..config import settings
from ..models.control_plane import ControlPlaneTaskState, ControlPlaneWorker
from ..schemas.fog_bridge import (
    DeviceInfo,
    DeviceQuota,
    DeviceRegisterRequest,
    DeviceRegisterResponse,
    DeviceStatus,
    DeviceType,
    FogTaskCreate,
    FogTaskResponse,
    HealthCheckResponse,
    HeartbeatRequest,
    HeartbeatResponse,
    NetworkTopologyResponse,
    QuotaUpdateRequest,
    ReadinessCheckResponse,
    TaskLeaseRenewRequest,
    TaskLeaseRequest,
    TaskResultSubmit,
    TaskStartRequest,
)
from ..services.fog_task_control_plane import (
    ControlPlaneConflictError,
    ControlPlaneNotFoundError,
    ControlPlaneSchemaError,
    fog_task_control_plane,
)
from ..services.device_auth import get_device_auth_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/fog-bridge", tags=["fog-task-control-plane"])
security = HTTPBearer(auto_error=False)

_service_start_time = datetime.now(UTC)


async def get_current_device(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    authorization: Optional[str] = Header(default=None),
) -> str:
    """Validate device authentication and return device ID."""
    token = None
    if credentials:
        token = credentials.credentials
    elif authorization and authorization.startswith("Bearer "):
        token = authorization[7:]

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Device authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    auth_service = get_device_auth_service()
    device_id = await auth_service.validate_access_token(token)
    if not device_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired device token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return device_id


def _raise_control_plane_error(exc: Exception) -> None:
    if isinstance(exc, ControlPlaneSchemaError):
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if isinstance(exc, ControlPlaneNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, ControlPlaneConflictError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _require_control_plane_ready() -> None:
    try:
        await fog_task_control_plane.ensure_ready()
    except Exception as exc:
        _raise_control_plane_error(exc)


def _worker_to_device_info(worker: ControlPlaneWorker, active_leases) -> DeviceInfo:
    active_task_ids = [lease.task_id for lease in active_leases]
    active_attempt_ids = [lease.attempt_id for lease in active_leases]
    active_lease_ids = [lease.lease_id for lease in active_leases]
    return DeviceInfo(
        device_id=worker.worker_id,
        device_name=worker.device_name,
        device_type=DeviceType(worker.device_type),
        status=DeviceStatus(worker.status),
        capabilities=worker.capabilities_json or {},
        region=worker.region,
        timezone=worker.timezone,
        owner_id=worker.owner_id,
        registered_at=worker.registered_at,
        last_heartbeat=worker.last_heartbeat_at,
        current_task_id=active_task_ids[0] if len(active_task_ids) == 1 else None,
        active_task_count=len(active_task_ids),
        active_task_ids=active_task_ids,
        active_attempt_ids=active_attempt_ids,
        active_lease_ids=active_lease_ids,
        total_tasks_completed=worker.total_tasks_completed,
        uptime_percent=100.0,
        reputation_score=worker.reputation_score,
    )


def _task_to_response(task, *, attempt_id: Optional[str] = None, lease_id: Optional[str] = None) -> FogTaskResponse:
    worker_id = task.worker_id
    return FogTaskResponse(
        task_id=task.task_id,
        status=ControlPlaneTaskState(task.status),
        worker_id=worker_id,
        assigned_device_id=worker_id,
        attempt_id=attempt_id or task.current_attempt_id,
        lease_id=lease_id or task.current_lease_id,
        assigned_at=task.assigned_at,
        lease_expires_at=task.lease_expires_at,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        progress_percent=task.progress_percent,
        result=task.result_json,
        error=task.error,
        idempotency_key=task.idempotency_key,
    )


def _quota_from_worker(worker: ControlPlaneWorker) -> DeviceQuota:
    return DeviceQuota(
        device_id=worker.worker_id,
        max_concurrent_tasks=worker.max_concurrent_tasks,
        daily_task_limit=worker.daily_task_limit,
        tasks_today=worker.tasks_today,
        quota_reset_at=worker.quota_reset_at,
    )


@router.post("/devices/register", response_model=DeviceRegisterResponse)
async def register_device(request: DeviceRegisterRequest) -> DeviceRegisterResponse:
    auth_service = get_device_auth_service()

    try:
        await _require_control_plane_ready()
        device_id, _device_secret, access_token, refresh_token, token_expires_at = await auth_service.register_device(
            device_name=request.device_name,
            device_type=request.device_type.value,
            capabilities=request.capabilities.model_dump(),
            owner_id=request.owner_id,
            region=request.region,
        )
        await fog_task_control_plane.register_worker(
            worker_id=device_id,
            device_name=request.device_name,
            device_type=request.device_type.value,
            capabilities=request.capabilities.model_dump(),
            region=request.region,
            timezone=request.timezone,
            owner_id=request.owner_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Device registration failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Registration failed: {exc}") from exc

    ws_url = settings.build_ws_url(f"/api/fog-bridge/ws/{device_id}")
    return DeviceRegisterResponse(
        device_id=device_id,
        access_token=access_token,
        refresh_token=refresh_token,
        token_expires_at=token_expires_at,
        websocket_url=ws_url,
    )


@router.post("/devices/authenticate")
async def authenticate_device(device_id: str, device_secret: str) -> dict[str, Any]:
    auth_service = get_device_auth_service()
    result = await auth_service.authenticate_device(device_id, device_secret)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid device credentials")

    access_token, refresh_token, token_expires_at = result
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_expires_at": token_expires_at.isoformat(),
        "token_type": "bearer",
    }


@router.post("/devices/refresh")
async def refresh_token(refresh_token: str) -> dict[str, Any]:
    auth_service = get_device_auth_service()
    result = await auth_service.refresh_access_token(refresh_token)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    access_token, token_expires_at = result
    return {
        "access_token": access_token,
        "token_expires_at": token_expires_at.isoformat(),
        "token_type": "bearer",
    }


@router.get("/devices/me", response_model=DeviceInfo)
async def get_current_device_info(device_id: str = Depends(get_current_device)) -> DeviceInfo:
    await _require_control_plane_ready()
    worker = await fog_task_control_plane.get_worker(device_id)
    if worker is None:
        raise HTTPException(status_code=404, detail="Device not found")
    active_leases = await fog_task_control_plane.get_worker_active_leases(device_id)
    return _worker_to_device_info(worker, active_leases)


@router.get("/devices", response_model=list[DeviceInfo])
async def list_devices(
    device_id: str = Depends(get_current_device),
    status: Optional[DeviceStatus] = None,
    device_type: Optional[DeviceType] = None,
    owner_id: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[DeviceInfo]:
    _ = device_id
    await _require_control_plane_ready()
    workers = await fog_task_control_plane.list_workers(
        status=status.value if status else None,
        device_type=device_type.value if device_type else None,
        owner_id=owner_id,
        limit=limit,
        offset=offset,
    )
    active_leases = await fog_task_control_plane.list_worker_active_leases([worker.worker_id for worker in workers])
    return [_worker_to_device_info(worker, active_leases.get(worker.worker_id, [])) for worker in workers]


@router.delete("/devices/{target_device_id}")
async def unregister_device(
    target_device_id: str,
    device_id: str = Depends(get_current_device),
) -> dict[str, str]:
    await _require_control_plane_ready()
    requester = await fog_task_control_plane.get_worker(device_id)
    target = await fog_task_control_plane.get_worker(target_device_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Device not found")
    if requester is None:
        raise HTTPException(status_code=404, detail="Requesting device not found")
    if device_id != target_device_id and requester.owner_id != target.owner_id:
        raise HTTPException(status_code=403, detail="Not authorized to unregister this device")

    auth_service = get_device_auth_service()
    await auth_service.revoke_device(target_device_id)
    await fog_task_control_plane.unregister_worker(target_device_id)
    return {"message": f"Device {target_device_id} unregistered successfully"}


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def device_heartbeat(
    request: HeartbeatRequest,
    device_id: str = Depends(get_current_device),
) -> HeartbeatResponse:
    if request.device_id != device_id:
        raise HTTPException(status_code=403, detail="Device ID mismatch")
    await _require_control_plane_ready()

    try:
        await fog_task_control_plane.update_worker_heartbeat(
            device_id,
            cpu_usage_percent=request.cpu_usage_percent,
            memory_usage_percent=request.memory_usage_percent,
            storage_usage_percent=request.storage_usage_percent,
            network_latency_ms=request.network_latency_ms,
            error_count=request.error_count,
        )
    except Exception as exc:
        _raise_control_plane_error(exc)

    return HeartbeatResponse(
        acknowledged=True,
        server_time=datetime.now(UTC),
        next_heartbeat_seconds=30,
        commands=[],
    )


@router.get("/health", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    uptime_seconds = (datetime.now(UTC) - _service_start_time).total_seconds()
    snapshot = await fog_task_control_plane.get_health_snapshot()
    return HealthCheckResponse(
        status=snapshot["status"],
        version=settings.API_VERSION,
        uptime_seconds=uptime_seconds,
        connected_devices=snapshot["workers"],
        active_tasks=snapshot["active_tasks"],
        services=snapshot["services"],
    )


@router.get("/ready", response_model=ReadinessCheckResponse)
async def readiness_check() -> ReadinessCheckResponse:
    snapshot = await fog_task_control_plane.get_readiness_snapshot(force_refresh=True)
    return ReadinessCheckResponse(**snapshot)


@router.post("/tasks", response_model=FogTaskResponse)
async def create_task(
    request: FogTaskCreate,
    device_id: str = Depends(get_current_device),
) -> FogTaskResponse:
    await _require_control_plane_ready()
    try:
        task = await fog_task_control_plane.create_task(
            task_type=request.task_type.value,
            priority=request.priority.name,
            payload=request.payload,
            resource_requirements=request.resource_requirements.model_dump() if request.resource_requirements else None,
            target_worker_id=request.target_device_id,
            target_device_type=request.target_device_type.value if request.target_device_type else None,
            timeout_seconds=request.timeout_seconds,
            max_retries=request.retry_count,
            callback_url=request.callback_url,
            created_by_worker_id=device_id,
            idempotency_key=request.idempotency_key,
        )
    except Exception as exc:
        _raise_control_plane_error(exc)
    return _task_to_response(task)


@router.post("/tasks/lease", response_model=Optional[FogTaskResponse])
async def lease_task(
    request: TaskLeaseRequest,
    device_id: str = Depends(get_current_device),
) -> Optional[FogTaskResponse]:
    await _require_control_plane_ready()
    try:
        grant = await fog_task_control_plane.lease_task(
            device_id,
            preferred_task_id=request.preferred_task_id,
            lease_ttl_seconds=request.lease_ttl_seconds,
        )
    except Exception as exc:
        _raise_control_plane_error(exc)
    if grant is None:
        return None
    return _task_to_response(grant.task, attempt_id=grant.attempt.attempt_id, lease_id=grant.lease.lease_id)


@router.post("/tasks/{task_id}/start", response_model=FogTaskResponse)
async def start_task(
    task_id: str,
    request: TaskStartRequest,
    device_id: str = Depends(get_current_device),
) -> FogTaskResponse:
    await _require_control_plane_ready()
    try:
        task = await fog_task_control_plane.start_task(
            task_id,
            worker_id=device_id,
            attempt_id=request.attempt_id,
            lease_id=request.lease_id,
        )
    except Exception as exc:
        _raise_control_plane_error(exc)
    return _task_to_response(task, attempt_id=request.attempt_id, lease_id=request.lease_id)


@router.post("/tasks/{task_id}/lease/renew", response_model=FogTaskResponse)
async def renew_task_lease(
    task_id: str,
    request: TaskLeaseRenewRequest,
    device_id: str = Depends(get_current_device),
) -> FogTaskResponse:
    await _require_control_plane_ready()
    try:
        task = await fog_task_control_plane.renew_lease(
            task_id,
            worker_id=device_id,
            attempt_id=request.attempt_id,
            lease_id=request.lease_id,
            lease_ttl_seconds=request.lease_ttl_seconds,
        )
    except Exception as exc:
        _raise_control_plane_error(exc)
    return _task_to_response(task, attempt_id=request.attempt_id, lease_id=request.lease_id)


@router.get("/tasks/{task_id}", response_model=FogTaskResponse)
async def get_task(
    task_id: str,
    device_id: str = Depends(get_current_device),
) -> FogTaskResponse:
    _ = device_id
    await _require_control_plane_ready()
    task = await fog_task_control_plane.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return _task_to_response(task)


@router.post("/tasks/{task_id}/result", response_model=FogTaskResponse)
async def submit_task_result(
    task_id: str,
    request: TaskResultSubmit,
    device_id: str = Depends(get_current_device),
) -> FogTaskResponse:
    if request.task_id != task_id:
        raise HTTPException(status_code=400, detail="Task ID mismatch")
    if request.device_id != device_id:
        raise HTTPException(status_code=403, detail="Device ID mismatch")
    await _require_control_plane_ready()

    try:
        task, _idempotent = await fog_task_control_plane.complete_task(
            task_id,
            worker_id=device_id,
            attempt_id=request.attempt_id,
            lease_id=request.lease_id,
            success=request.success,
            result=request.result,
            error=request.error,
            execution_time_ms=request.execution_time_ms,
        )
    except Exception as exc:
        _raise_control_plane_error(exc)
    return _task_to_response(task, attempt_id=request.attempt_id, lease_id=request.lease_id)


@router.delete("/tasks/{task_id}", response_model=FogTaskResponse)
async def cancel_task(
    task_id: str,
    device_id: str = Depends(get_current_device),
) -> FogTaskResponse:
    await _require_control_plane_ready()
    task = await fog_task_control_plane.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.created_by_worker_id != device_id:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this task")
    task = await fog_task_control_plane.cancel_task(task_id)
    return _task_to_response(task)


@router.get("/quotas/me", response_model=DeviceQuota)
async def get_my_quota(device_id: str = Depends(get_current_device)) -> DeviceQuota:
    await _require_control_plane_ready()
    worker = await fog_task_control_plane.get_worker(device_id)
    if worker is None:
        raise HTTPException(status_code=404, detail="Quota not found")
    return _quota_from_worker(worker)


@router.get("/metrics")
async def get_control_plane_metrics() -> dict[str, Any]:
    return await fog_task_control_plane.get_metrics()


@router.patch("/quotas/{target_device_id}", response_model=DeviceQuota)
async def update_quota(
    target_device_id: str,
    request: QuotaUpdateRequest,
    device_id: str = Depends(get_current_device),
) -> DeviceQuota:
    await _require_control_plane_ready()
    requester = await fog_task_control_plane.get_worker(device_id)
    target = await fog_task_control_plane.get_worker(target_device_id)
    if requester is None or target is None:
        raise HTTPException(status_code=404, detail="Device not found")
    if not requester.owner_id or requester.owner_id != target.owner_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this device's quota")
    unsupported = [
        field_name
        for field_name in ("max_cpu_percent", "max_memory_percent", "max_storage_mb", "max_bandwidth_mbps")
        if getattr(request, field_name) is not None
    ]
    if unsupported:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported durable quota fields: {unsupported}",
        )

    updated = await fog_task_control_plane.update_worker_quota(
        target_device_id,
        max_concurrent_tasks=request.max_concurrent_tasks,
        daily_task_limit=request.daily_task_limit,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Quota not found")
    return _quota_from_worker(updated)


@router.get("/topology", response_model=NetworkTopologyResponse)
async def get_network_topology(device_id: str = Depends(get_current_device)) -> NetworkTopologyResponse:
    _ = device_id
    await _require_control_plane_ready()
    snapshot = await fog_task_control_plane.get_topology_snapshot()
    return NetworkTopologyResponse(**snapshot)
