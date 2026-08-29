"""
Device mesh API routes.

This route layer exposes the VIS-001 mesh surface on top of the current
persistence-backed mesh service and token store.
"""
from __future__ import annotations

from datetime import UTC, datetime
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..config import settings
from ..schemas.device_mesh import (
    DeviceRole,
    DeviceState,
    DeviceStatus,
    DeviceUpdateRequest,
    HeartbeatRequest,
    HeartbeatResponse,
    MeshJoinRequest,
    MeshJoinResponse,
    MeshLeaveRequest,
    TopologySnapshot,
    ZoneInfo,
    ZoneType,
)
from ..services.mesh_persistence import get_mesh_persistence
from ..services.mesh_service import get_mesh_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/mesh", tags=["mesh"])
security = HTTPBearer(auto_error=False)

_service_start_time = datetime.now(UTC)


async def get_current_mesh_device(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_mesh_token: Optional[str] = Header(default=None),
) -> str:
    token = credentials.credentials if credentials else x_mesh_token
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Mesh authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    device_id = await get_mesh_persistence().get_device_by_token(token)
    if not device_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired mesh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return device_id


def _zone_type(zone_id: str) -> ZoneType:
    return ZoneType.LOCAL if zone_id in {"default", "local"} else ZoneType.REGIONAL


def _capacity_for(device: DeviceState) -> dict[str, float]:
    return {
        "cpu_cores": float(device.profile.cpu_cores),
        "ram_gb": float(device.profile.ram_gb),
        "storage_gb": float(device.profile.storage_gb),
        "bandwidth_mbps": float(device.profile.bandwidth_mbps),
    }


def _add_capacity(target: dict[str, float], source: dict[str, float], factor: float = 1.0) -> None:
    for key, value in source.items():
        target[key] = target.get(key, 0.0) + value * factor


def _build_topology(devices: list[DeviceState]) -> TopologySnapshot:
    total_capacity: dict[str, float] = {}
    available_capacity: dict[str, float] = {}
    zone_devices: dict[str, list[DeviceState]] = {}

    for device in devices:
        capacity = _capacity_for(device)
        _add_capacity(total_capacity, capacity)
        if device.status in {DeviceStatus.ONLINE, DeviceStatus.IDLE} and device.liveness.is_healthy:
            available_factor = max(0.0, min(1.0, 1.0 - device.current_load))
            _add_capacity(available_capacity, capacity, available_factor)
        zone_devices.setdefault(device.zone, []).append(device)

    zones: dict[str, ZoneInfo] = {}
    for zone_id, zone_members in zone_devices.items():
        zone_total: dict[str, float] = {}
        zone_available: dict[str, float] = {}
        healthy_count = 0
        for member in zone_members:
            capacity = _capacity_for(member)
            _add_capacity(zone_total, capacity)
            if member.liveness.is_healthy:
                healthy_count += 1
            if member.status in {DeviceStatus.ONLINE, DeviceStatus.IDLE} and member.liveness.is_healthy:
                _add_capacity(zone_available, capacity, max(0.0, min(1.0, 1.0 - member.current_load)))
        zones[zone_id] = ZoneInfo(
            zone_id=zone_id,
            zone_type=_zone_type(zone_id),
            device_count=len(zone_members),
            healthy_count=healthy_count,
            total_capacity=zone_total,
            available_capacity=zone_available,
        )

    primary_device_id = next(
        (device.device_id for device in devices if device.role == DeviceRole.PRIMARY and device.status != DeviceStatus.OFFLINE),
        None,
    )
    secondary_device_ids = [
        device.device_id
        for device in devices
        if device.role == DeviceRole.SECONDARY and device.status != DeviceStatus.OFFLINE
    ]
    healthy_devices = sum(1 for device in devices if device.liveness.is_healthy)
    online_devices = sum(1 for device in devices if device.status in {DeviceStatus.ONLINE, DeviceStatus.IDLE, DeviceStatus.BUSY})
    offline_devices = sum(1 for device in devices if device.status == DeviceStatus.OFFLINE)

    return TopologySnapshot(
        timestamp=datetime.now(UTC),
        total_devices=len(devices),
        healthy_devices=healthy_devices,
        online_devices=online_devices,
        offline_devices=offline_devices,
        primary_device_id=primary_device_id,
        secondary_device_ids=secondary_device_ids,
        devices=devices,
        zones=zones,
        total_capacity=total_capacity,
        available_capacity=available_capacity,
        pending_sync_total=sum(device.pending_sync_count for device in devices),
        mesh_health_score=(healthy_devices / len(devices)) if devices else 1.0,
    )


async def _list_device_states(
    *,
    zone: Optional[str] = None,
    status: Optional[DeviceStatus] = None,
    role: Optional[DeviceRole] = None,
    include_offline: bool = True,
) -> list[DeviceState]:
    persistence = get_mesh_persistence()
    devices = await persistence.list_devices(
        zone=zone,
        status=status,
        role=role,
        include_offline=include_offline,
    )
    return [persistence.to_device_state(device) for device in devices]


@router.post("/join", response_model=MeshJoinResponse)
async def join_mesh(request: MeshJoinRequest) -> MeshJoinResponse:
    mesh_service = get_mesh_service()
    try:
        device_id, mesh_token, assigned_role, assigned_zone = await mesh_service.join_mesh(
            device_name=request.device_name,
            profile=request.profile,
            preferred_role=request.preferred_role,
            zone=request.preferred_zone or "default",
            public_key=request.public_key,
            owner_id=request.owner_id,
        )
    except Exception as exc:
        logger.exception("Mesh join failed")
        raise HTTPException(status_code=500, detail=f"Join failed: {exc}") from exc

    primary = await get_mesh_persistence().get_primary_device()
    return MeshJoinResponse(
        device_id=device_id,
        mesh_token=mesh_token,
        assigned_role=assigned_role,
        assigned_zone=assigned_zone,
        primary_device_id=primary.device_id if primary else None,
        heartbeat_interval_sec=mesh_service.heartbeat_interval_sec,
        sync_interval_sec=mesh_service.sync_interval_sec,
        websocket_url=settings.build_ws_url(f"/api/mesh/ws/{device_id}"),
    )


@router.post("/leave")
async def leave_mesh(
    request: MeshLeaveRequest,
    device_id: str = Depends(get_current_mesh_device),
) -> dict[str, str]:
    if request.device_id != device_id:
        raise HTTPException(status_code=403, detail="Can only leave as yourself")

    success = await get_mesh_persistence().remove_device(device_id, reason=request.reason)
    if not success:
        raise HTTPException(status_code=404, detail="Device not found in mesh")
    return {"message": f"Device {device_id} left the mesh"}


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def device_heartbeat(
    request: HeartbeatRequest,
    device_id: str = Depends(get_current_mesh_device),
) -> HeartbeatResponse:
    if request.device_id != device_id:
        raise HTTPException(status_code=403, detail="Device ID mismatch")

    mesh_service = get_mesh_service()
    acknowledged, commands, sync_required, next_heartbeat_sec = await mesh_service.process_heartbeat(
        device_id=device_id,
        status=request.status,
        current_load=request.current_load,
        active_tasks=request.active_tasks,
        pending_sync_count=request.pending_sync_count,
    )

    if not acknowledged:
        acknowledged = await get_mesh_persistence().update_device_heartbeat(
            device_id=device_id,
            status=request.status,
            current_load=request.current_load,
            active_tasks=request.active_tasks,
            pending_sync_count=request.pending_sync_count,
        )
    if not acknowledged:
        raise HTTPException(status_code=404, detail="Device not found in mesh")

    primary = await get_mesh_persistence().get_primary_device()
    return HeartbeatResponse(
        acknowledged=True,
        server_time=datetime.now(UTC),
        next_heartbeat_sec=next_heartbeat_sec,
        commands=commands,
        primary_device_id=primary.device_id if primary else None,
        sync_required=sync_required,
    )


@router.get("/devices", response_model=list[DeviceState])
async def list_devices(
    device_id: str = Depends(get_current_mesh_device),
    zone: Optional[str] = None,
    status: Optional[DeviceStatus] = None,
    role: Optional[DeviceRole] = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[DeviceState]:
    _ = device_id
    devices = await _list_device_states(zone=zone, status=status, role=role)
    return devices[offset : offset + limit]


@router.get("/devices/{target_device_id}", response_model=DeviceState)
async def get_device(
    target_device_id: str,
    device_id: str = Depends(get_current_mesh_device),
) -> DeviceState:
    _ = device_id
    device = await get_mesh_persistence().get_device_state(target_device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.patch("/devices/{target_device_id}", response_model=DeviceState)
async def update_device(
    target_device_id: str,
    request: DeviceUpdateRequest,
    device_id: str = Depends(get_current_mesh_device),
) -> DeviceState:
    if target_device_id != device_id:
        raise HTTPException(status_code=403, detail="Can only update your own device")

    updated = await get_mesh_persistence().update_device(
        device_id=target_device_id,
        device_name=request.device_name,
        role=request.preferred_role,
        profile=request.profile,
        max_concurrent_tasks=request.max_concurrent_tasks,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return get_mesh_persistence().to_device_state(updated)


@router.delete("/devices/{target_device_id}")
async def remove_device(
    target_device_id: str,
    device_id: str = Depends(get_current_mesh_device),
    reason: str = Query(default="removed"),
) -> dict[str, str]:
    persistence = get_mesh_persistence()
    if target_device_id != device_id:
        requester = await persistence.get_device_state(device_id)
        if requester is None or requester.role != DeviceRole.PRIMARY:
            raise HTTPException(status_code=403, detail="Only primary can remove other devices")

    success = await persistence.remove_device(target_device_id, reason=reason)
    if not success:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"message": f"Device {target_device_id} removed from mesh"}


@router.get("/topology", response_model=TopologySnapshot)
async def get_topology(device_id: str = Depends(get_current_mesh_device)) -> TopologySnapshot:
    _ = device_id
    return _build_topology(await _list_device_states())


@router.get("/zones", response_model=dict[str, ZoneInfo])
async def list_zones(device_id: str = Depends(get_current_mesh_device)) -> dict[str, ZoneInfo]:
    _ = device_id
    return (await get_topology(device_id)).zones


@router.get("/zones/{zone_id}", response_model=ZoneInfo)
async def get_zone(
    zone_id: str,
    device_id: str = Depends(get_current_mesh_device),
) -> ZoneInfo:
    topology = await get_topology(device_id)
    if zone_id not in topology.zones:
        raise HTTPException(status_code=404, detail="Zone not found")
    return topology.zones[zone_id]


@router.get("/health")
async def mesh_health() -> dict[str, Any]:
    topology = _build_topology(await _list_device_states())
    status = "healthy"
    if topology.mesh_health_score < 0.5:
        status = "unhealthy"
    elif topology.mesh_health_score < 0.8:
        status = "degraded"

    return {
        "status": status,
        "mesh_health_score": topology.mesh_health_score,
        "total_devices": topology.total_devices,
        "healthy_devices": topology.healthy_devices,
        "online_devices": topology.online_devices,
        "offline_devices": topology.offline_devices,
        "primary_device_id": topology.primary_device_id,
        "zones_count": len(topology.zones),
        "total_capacity": topology.total_capacity,
        "available_capacity": topology.available_capacity,
        "pending_sync_total": topology.pending_sync_total,
        "uptime_seconds": (datetime.now(UTC) - _service_start_time).total_seconds(),
        "version": settings.API_VERSION,
    }


@router.post("/discover")
async def discover_devices(
    device_id: str = Depends(get_current_mesh_device),
    zone: Optional[str] = None,
) -> dict[str, Any]:
    _ = device_id
    devices = await _list_device_states(zone=zone, include_offline=False)
    available = [device for device in devices if device.status in {DeviceStatus.ONLINE, DeviceStatus.IDLE}]
    return {
        "discovered_count": len(available),
        "devices": [
            {
                "device_id": device.device_id,
                "hostname": device.profile.hostname,
                "zone": device.zone,
                "capabilities": [capability.value for capability in device.profile.capabilities],
                "status": device.status.value,
            }
            for device in available
        ],
        "timestamp": datetime.now(UTC).isoformat(),
    }
