"""
Betanet API Routes
Handles Betanet privacy network status and operations
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import logging

from ..services.service_manager import service_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/betanet", tags=["betanet"])


class DeployNodeRequest(BaseModel):
    node_type: str = "mixnode"
    region: str = "us-east"


@router.get("/status")
async def get_betanet_status() -> Dict[str, Any]:
    """Get Betanet network status"""
    betanet = service_manager.get('betanet')

    if betanet is None:
        raise HTTPException(status_code=503, detail="Betanet service unavailable")

    try:
        status = await betanet.get_status()

        return {
            "status": status.get('status', 'unknown'),
            "nodes": {
                "total": status.get('active_nodes', 0) + status.get('inactive_nodes', 0),
                "active": status.get('active_nodes', 0),
                "inactive": status.get('inactive_nodes', 0)
            },
            "network": {
                "latency": status.get('avg_latency_ms', 0),
                "bandwidth": status.get('bandwidth', 1024),
                "throughput": status.get('throughput', 850),
                "packetsProcessed": status.get('packets_processed', 0)
            },
            "lastUpdated": status.get('timestamp', None)
        }
    except Exception as e:
        logger.error(f"Error fetching Betanet status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deploy")
async def deploy_node(request: DeployNodeRequest) -> Dict[str, Any]:
    """Deploy a new Betanet node"""
    betanet = service_manager.get('betanet')

    if betanet is None:
        raise HTTPException(status_code=503, detail="Betanet service unavailable")

    try:
        result = await betanet.deploy_node({
            'node_type': request.node_type,
            'region': request.region
        })

        return {
            "success": result.get('success', False),
            "nodeId": result.get('node_id', None),
            "status": result.get('status', 'deploying')
        }
    except Exception as e:
        logger.error(f"Error deploying node: {e}")
        raise HTTPException(status_code=500, detail=str(e))
