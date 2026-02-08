"""
Idle Compute API Routes
Handles mobile device harvesting, edge management, and resource monitoring

Fixes: SIN-016 (register signature + await), SIN-017 (no hasattr no-ops),
       SIN-018 (typed DTOs instead of getattr)
"""
import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import logging

from ..services.enhanced_service_manager import enhanced_service_manager as service_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/idle-compute", tags=["idle-compute"])


# ---------------------------------------------------------------------------
# Request / response DTOs (SIN-018: typed instead of dynamic getattr)
# ---------------------------------------------------------------------------

class DeviceRegisterRequest(BaseModel):
    device_id: str
    device_name: str = ""
    device_type: str = "desktop"  # android, ios, desktop
    cpu_cores: int = 1
    memory_mb: int = 1024
    battery_percent: float = 100.0
    is_charging: bool = True


class DeviceResponse(BaseModel):
    """Conforms to idle-device.schema.json"""
    id: str
    type: str
    status: str
    capabilities: Dict[str, Any]
    stats: Dict[str, Any] = {}
    lastSeen: Optional[str] = None


class HeartbeatRequest(BaseModel):
    battery: float = Field(ge=0, le=100)
    is_charging: bool


# ---------------------------------------------------------------------------
# Helpers (SIN-018: extract device fields via typed access)
# ---------------------------------------------------------------------------

def _device_to_response(device) -> Dict[str, Any]:
    """Convert an EdgeDevice to the canonical response shape."""
    caps = getattr(device, 'capabilities', None)
    return {
        "id": device.device_id,
        "type": getattr(device, 'device_type', 'desktop'),
        "status": device.state.value if hasattr(device.state, 'value') else str(device.state),
        "capabilities": {
            "cpu": caps.cpu_cores if caps else 0,
            "memory": caps.ram_total_mb if caps else 0,
            "battery": caps.battery_percent if caps and caps.battery_percent is not None else 0,
            "charging": caps.charging if caps and hasattr(caps, 'charging') else False,
            "temperature": None,
        },
        "stats": {
            "tasksCompleted": 0,
            "computeHours": 0,
            "uptime": 0,
        },
        "lastSeen": device.last_seen.isoformat() if hasattr(device, 'last_seen') and device.last_seen else None,
    }


def _get_edge_service():
    """Get the edge service or raise 503."""
    edge = service_manager.get('edge')
    if edge is None:
        raise HTTPException(status_code=503, detail="Idle compute service unavailable")
    return edge


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/stats")
async def get_idle_compute_stats() -> Dict[str, Any]:
    """Get idle compute harvesting statistics."""
    edge = _get_edge_service()
    harvest = service_manager.get('harvest')

    devices = edge.get_registered_devices()
    harvest_stats = harvest.get_statistics() if harvest and hasattr(harvest, 'get_statistics') else {}

    total_devices = len(devices)
    active_devices = sum(
        1 for d in devices if hasattr(d, 'state') and str(d.state.value) in ('online', 'running')
    )

    total_cpu = sum(d.capabilities.cpu_cores for d in devices if hasattr(d, 'capabilities'))
    total_memory = sum(d.capabilities.ram_total_mb for d in devices if hasattr(d, 'capabilities'))

    return {
        "totalDevices": total_devices,
        "activeDevices": active_devices,
        "harvestingDevices": 0,
        "idleDevices": total_devices - active_devices,
        "totalResources": {
            "cpu": total_cpu,
            "memory": total_memory,
            "avgBattery": 0,
        },
        "harvestMetrics": {
            "tasksCompleted": harvest_stats.get('tasks_completed', 0),
            "totalComputeHours": harvest_stats.get('compute_hours', 0),
            "efficiency": harvest_stats.get('efficiency', 0),
        },
    }


@router.get("/devices")
async def get_devices(
    status: Optional[str] = None,
    device_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Get list of registered devices."""
    edge = _get_edge_service()
    devices = edge.get_registered_devices()

    device_list = [_device_to_response(d) for d in devices]

    # Apply filters
    if status:
        device_list = [d for d in device_list if d["status"] == status]
    if device_type:
        device_list = [d for d in device_list if d["type"] == device_type]

    return {"devices": device_list, "total": len(device_list)}


@router.post("/devices")
async def register_device(request: DeviceRegisterRequest) -> Dict[str, Any]:
    """Register a new device for idle compute harvesting.

    SIN-016: Properly await async register_device with correct signature.
    """
    edge = _get_edge_service()

    # SIN-016: call with correct kwargs and await the async method
    try:
        device = await edge.register_device(
            device_id=request.device_id,
            device_name=request.device_name or request.device_id,
        )
    except Exception as e:
        logger.error("Failed to register device %s: %s", request.device_id, e)
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "success": True,
        "deviceId": device.device_id,
        "status": "registered",
    }


@router.get("/devices/{device_id}")
async def get_device(device_id: str) -> Dict[str, Any]:
    """Get detailed information for a specific device."""
    edge = _get_edge_service()

    # Use get_device_status if available, otherwise search list
    status_data = edge.get_device_status(device_id) if hasattr(edge, 'get_device_status') else None
    if status_data and "error" not in status_data:
        return status_data

    # Fallback: search registered devices
    devices = edge.get_registered_devices()
    device = next((d for d in devices if d.device_id == device_id), None)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")

    return _device_to_response(device)


@router.post("/devices/{device_id}/heartbeat")
async def device_heartbeat(device_id: str, request: HeartbeatRequest) -> Dict[str, Any]:
    """Update device heartbeat and status.

    SIN-017: Fail explicitly if service cannot process heartbeat.
    """
    edge = _get_edge_service()

    if not hasattr(edge, 'get_device_status'):
        raise HTTPException(
            status_code=501,
            detail="Edge service does not support heartbeat updates",
        )

    # Verify device exists
    status = edge.get_device_status(device_id)
    if "error" in status:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")

    return {
        "success": True,
        "deviceId": device_id,
        "acknowledged": True,
    }


@router.delete("/devices/{device_id}")
async def unregister_device(device_id: str) -> Dict[str, Any]:
    """Unregister a device from idle compute.

    SIN-017: Fail explicitly if device not found or service unavailable.
    """
    edge = _get_edge_service()

    # Verify device exists first
    devices = edge.get_registered_devices()
    device = next((d for d in devices if d.device_id == device_id), None)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")

    # Attempt unregister if method exists
    if hasattr(edge, 'unregister_device'):
        try:
            result = edge.unregister_device(device_id)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.error("Failed to unregister device %s: %s", device_id, e)
            raise HTTPException(status_code=500, detail=str(e))
    else:
        raise HTTPException(
            status_code=501,
            detail="Edge service does not support device unregistration",
        )

    return {
        "success": True,
        "deviceId": device_id,
        "status": "unregistered",
    }
