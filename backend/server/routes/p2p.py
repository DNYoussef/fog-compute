"""
P2P API Routes
Handles unified P2P system (BitChat BLE + Betanet HTX + Mesh)
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging

from ..services.enhanced_service_manager import enhanced_service_manager as service_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/p2p", tags=["p2p"])


@router.get("/stats")
async def get_p2p_stats() -> Dict[str, Any]:
    """Get P2P network statistics"""
    p2p = service_manager.get('p2p')

    if p2p is None:
        raise HTTPException(status_code=503, detail="P2P service unavailable")

    try:
        health = p2p.get_health() if hasattr(p2p, 'get_health') else {}

        return {
            "connectedPeers": health.get('connected_peers', 0),
            "messagesSent": health.get('messages_sent', 0),
            "messagesReceived": health.get('messages_received', 0),
            "protocols": {
                "ble": health.get('ble_connections', 0),
                "htx": health.get('htx_connections', 0),
                "mesh": health.get('mesh_connections', 0)
            },
            "networkHealth": health.get('network_health', 1.0)
        }
    except Exception as e:
        logger.error(f"Error fetching P2P stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
