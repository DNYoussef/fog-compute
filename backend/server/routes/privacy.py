"""
Privacy/VPN API Routes
Handles onion routing, circuit management, and VPN services
"""
from fastapi import APIRouter, HTTPException
from typing import Any, Dict
import logging

from ..services.enhanced_service_manager import enhanced_service_manager as service_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/privacy", tags=["privacy"])


@router.get("/stats")
async def get_privacy_stats() -> Dict[str, Any]:
    """Get privacy network statistics"""
    onion = service_manager.get('onion')
    vpn_coordinator = service_manager.get('vpn_coordinator')

    if onion is None:
        raise HTTPException(status_code=503, detail="Privacy service unavailable")

    try:
        # Get circuit stats
        circuits = onion.get_active_circuits() if hasattr(onion, 'get_active_circuits') else []

        hop_counts = []
        for circuit in circuits:
            hops = getattr(circuit, "hops", None)
            if isinstance(hops, list):
                hop_counts.append(len(hops))

        onion_layers = {
            "average": (sum(hop_counts) / len(hop_counts)) if hop_counts else None,
            "min": min(hop_counts) if hop_counts else None,
            "max": max(hop_counts) if hop_counts else None,
            "evidenceStatus": "measured_active_circuits" if hop_counts else "unavailable_no_active_circuits",
        }

        return {
            "activeCircuits": len(circuits),
            "totalBandwidth": sum(getattr(c, 'bandwidth', 0) for c in circuits),
            "avgLatency": sum(getattr(c, 'latency_ms', 0) for c in circuits) / len(circuits) if circuits else 0,
            "circuitHealth": sum(1 for c in circuits if getattr(c, 'health', 0) > 0.8) / len(circuits) if circuits else 1.0,
            "onionLayers": onion_layers,
            "hiddenServices": 0,
            "vpnConnections": 0,
            "claimStatus": {
                "onion_layers": onion_layers["evidenceStatus"],
                "vpn_connections": "unavailable_not_wired" if vpn_coordinator is None else "available",
            },
        }
    except Exception as e:
        logger.error(f"Error fetching privacy stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/circuits")
async def get_circuits() -> Dict[str, Any]:
    """Get all active onion routing circuits"""
    onion = service_manager.get('onion')

    if onion is None:
        raise HTTPException(status_code=503, detail="Privacy service unavailable")

    try:
        circuits = onion.get_active_circuits() if hasattr(onion, 'get_active_circuits') else []

        return {
            "circuits": [
                {
                    "id": getattr(c, 'circuit_id', str(i)),
                    "hops": getattr(c, 'hops', []),
                    "bandwidth": getattr(c, 'bandwidth', 0),
                    "latency": getattr(c, 'latency_ms', 0),
                    "health": getattr(c, 'health', 1.0),
                    "created": getattr(c, 'created_at', None)
                }
                for i, c in enumerate(circuits)
            ]
        }
    except Exception as e:
        logger.error(f"Error fetching circuits: {e}")
        raise HTTPException(status_code=500, detail=str(e))
