"""
Idle Compute API Routes
Handles mobile device harvesting, edge management, and resource monitoring
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import logging

from ..services.service_manager import service_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/idle-compute", tags=["idle-compute"])


class DeviceRegisterRequest(BaseModel):
    device_id: str
    device_type: str  # android, ios, desktop
    cpu_cores: int
    memory_mb: int
    battery_percent: float
    is_charging: bool


@router.get("/stats")
async def get_idle_compute_stats() -> Dict[str, Any]:
    """
    Get idle compute harvesting statistics

    Returns:
        - Total devices
        - Active harvesters
        - Resource metrics
        - Harvest efficiency
    """
    edge = service_manager.get('edge')
    harvest = service_manager.get('harvest')

    if edge is None:
        raise HTTPException(status_code=503, detail="Idle compute service unavailable")

    try:
        # Get statistics from services
        devices = edge.get_registered_devices() if hasattr(edge, 'get_registered_devices') else []
        harvest_stats = harvest.get_statistics() if harvest and hasattr(harvest, 'get_statistics') else {}

        # Calculate metrics
        total_devices = len(devices)
        active_devices = len([d for d in devices if getattr(d, 'status', None) == 'active'])
        harvesting = len([d for d in devices if getattr(d, 'status', None) == 'harvesting'])

        # Aggregate resources
        total_cpu = sum(getattr(d.capabilities, 'cpu_cores', 0) for d in devices)
        total_memory = sum(getattr(d.capabilities, 'memory_mb', 0) for d in devices)
        avg_battery = sum(getattr(d.capabilities, 'battery_percent', 0) for d in devices) / total_devices if total_devices > 0 else 0

        return {
            "totalDevices": total_devices,
            "activeDevices": active_devices,
            "harvestingDevices": harvesting,
            "idleDevices": total_devices - active_devices - harvesting,
            "totalResources": {
                "cpu": total_cpu,
                "memory": total_memory,
                "avgBattery": avg_battery
            },
            "harvestMetrics": {
                "tasksCompleted": harvest_stats.get('tasks_completed', 0),
                "totalComputeHours": harvest_stats.get('compute_hours', 0),
                "efficiency": harvest_stats.get('efficiency', 0)
            },
            "deviceTypes": {
                "android": len([d for d in devices if getattr(d, 'device_type', None) == 'android']),
                "ios": len([d for d in devices if getattr(d, 'device_type', None) == 'ios']),
                "desktop": len([d for d in devices if getattr(d, 'device_type', None) == 'desktop'])
            }
        }
    except Exception as e:
        logger.error(f"Error fetching idle compute stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/devices")
async def get_devices(
    status: Optional[str] = None,
    device_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get list of registered devices

    Args:
        status: Filter by status (active, idle, harvesting, offline)
        device_type: Filter by type (android, ios, desktop)

    Returns:
        List of devices with capabilities and status
    """
    edge = service_manager.get('edge')

    if edge is None:
        raise HTTPException(status_code=503, detail="Idle compute service unavailable")

    try:
        devices = edge.get_registered_devices() if hasattr(edge, 'get_registered_devices') else []

        # Apply filters
        if status:
            devices = [d for d in devices if getattr(d, 'status', None) == status]
        if device_type:
            devices = [d for d in devices if getattr(d, 'device_type', None) == device_type]

        # Format devices
        device_list = []
        for device in devices:
            caps = getattr(device, 'capabilities', None)
            device_list.append({
                "id": getattr(device, 'device_id', 'unknown'),
                "type": getattr(device, 'device_type', 'unknown'),
                "status": getattr(device, 'status', 'offline'),
                "battery": getattr(caps, 'battery_percent', 0) if caps else 0,
                "charging": getattr(caps, 'is_charging', False) if caps else False,
                "cpu": getattr(caps, 'cpu_cores', 0) if caps else 0,
                "memory": getattr(caps, 'memory_mb', 0) if caps else 0,
                "temperature": getattr(caps, 'cpu_temp_celsius', 0) if caps else None,
                "lastSeen": getattr(device, 'last_heartbeat', None),
                "tasksCompleted": getattr(device, 'tasks_completed', 0)
            })

        return {
            "devices": device_list,
            "total": len(device_list)
        }
    except Exception as e:
        logger.error(f"Error fetching devices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/devices")
async def register_device(request: DeviceRegisterRequest) -> Dict[str, Any]:
    """
    Register a new device for idle compute harvesting

    Args:
        Device information and capabilities

    Returns:
        Registration confirmation and device ID
    """
    edge = service_manager.get('edge')

    if edge is None:
        raise HTTPException(status_code=503, detail="Idle compute service unavailable")

    try:
        # Register device
        device_data = {
            'device_id': request.device_id,
            'device_type': request.device_type,
            'cpu_cores': request.cpu_cores,
            'memory_mb': request.memory_mb,
            'battery_percent': request.battery_percent,
            'is_charging': request.is_charging
        }

        if hasattr(edge, 'register_device'):
            result = edge.register_device(device_data)
        else:
            result = {"device_id": request.device_id}

        return {
            "success": True,
            "deviceId": request.device_id,
            "status": "registered"
        }
    except Exception as e:
        logger.error(f"Error registering device: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/devices/{device_id}")
async def get_device(device_id: str) -> Dict[str, Any]:
    """Get detailed information for a specific device"""
    edge = service_manager.get('edge')

    if edge is None:
        raise HTTPException(status_code=503, detail="Idle compute service unavailable")

    try:
        devices = edge.get_registered_devices() if hasattr(edge, 'get_registered_devices') else []
        device = next((d for d in devices if getattr(d, 'device_id', None) == device_id), None)

        if not device:
            raise HTTPException(status_code=404, detail=f"Device {device_id} not found")

        caps = getattr(device, 'capabilities', None)

        return {
            "id": device_id,
            "type": getattr(device, 'device_type', 'unknown'),
            "status": getattr(device, 'status', 'offline'),
            "capabilities": {
                "cpu": getattr(caps, 'cpu_cores', 0) if caps else 0,
                "memory": getattr(caps, 'memory_mb', 0) if caps else 0,
                "battery": getattr(caps, 'battery_percent', 0) if caps else 0,
                "charging": getattr(caps, 'is_charging', False) if caps else False,
                "temperature": getattr(caps, 'cpu_temp_celsius', None) if caps else None
            },
            "stats": {
                "tasksCompleted": getattr(device, 'tasks_completed', 0),
                "computeHours": getattr(device, 'compute_hours', 0),
                "uptime": getattr(device, 'uptime', 0)
            },
            "lastSeen": getattr(device, 'last_heartbeat', None)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching device {device_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/devices/{device_id}/heartbeat")
async def device_heartbeat(device_id: str, battery: float, is_charging: bool) -> Dict[str, Any]:
    """Update device heartbeat and status"""
    edge = service_manager.get('edge')

    if edge is None:
        raise HTTPException(status_code=503, detail="Idle compute service unavailable")

    try:
        if hasattr(edge, 'update_heartbeat'):
            edge.update_heartbeat(device_id, battery, is_charging)

        return {
            "success": True,
            "deviceId": device_id,
            "acknowledged": True
        }
    except Exception as e:
        logger.error(f"Error updating heartbeat for {device_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/devices/{device_id}")
async def unregister_device(device_id: str) -> Dict[str, Any]:
    """Unregister a device from idle compute"""
    edge = service_manager.get('edge')

    if edge is None:
        raise HTTPException(status_code=503, detail="Idle compute service unavailable")

    try:
        if hasattr(edge, 'unregister_device'):
            edge.unregister_device(device_id)

        return {
            "success": True,
            "deviceId": device_id,
            "status": "unregistered"
        }
    except Exception as e:
        logger.error(f"Error unregistering device {device_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
