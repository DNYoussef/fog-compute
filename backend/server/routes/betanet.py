"""
Betanet API Routes (Option B: backend owns all API contracts)

SIN-003: Backend owns node CRUD, does not proxy to Rust /nodes.
SIN-006: Status response matches canonical betanet-status.schema.json.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import logging

from ..services.enhanced_service_manager import enhanced_service_manager as service_manager
from ..constants import HEALTH_CHECK_TIMEOUT
from ..middleware.api_key_auth import require_api_key
import httpx

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/betanet", tags=["betanet"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class DeployNodeRequest(BaseModel):
    node_type: str = "mixnode"
    region: str = "us-east"


class NodeCreateRequest(BaseModel):
    node_type: str = Field(..., description="Node type: mixnode, gateway, or client")
    region: Optional[str] = Field(None, description="Deployment region")
    name: Optional[str] = Field(None, description="Custom node name")


class NodeUpdateRequest(BaseModel):
    name: Optional[str] = None
    region: Optional[str] = None
    status: Optional[str] = None


class NodeResponse(BaseModel):
    id: str
    node_type: str
    region: Optional[str] = None
    name: Optional[str] = None
    status: str
    packets_processed: int
    packets_forwarded: int
    packets_dropped: int
    avg_latency_ms: float
    created_at: str
    last_heartbeat: str


# ---------------------------------------------------------------------------
# Helper to get the betanet service
# ---------------------------------------------------------------------------

def _get_service():
    """Return the BetanetService or raise 503."""
    svc = service_manager.get('betanet')
    if svc is None:
        raise HTTPException(status_code=503, detail="Betanet service unavailable")
    return svc


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@router.get("/health")
async def check_betanet_health() -> Dict[str, Any]:
    """Health check: reports Rust server connectivity."""
    betanet_client = getattr(service_manager, 'betanet_client', None)

    if betanet_client is None:
        return {
            "status": "unavailable",
            "message": "Betanet client not initialized",
            "server_url": None,
            "server_reachable": False,
        }

    try:
        async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT) as client:
            response = await client.get(f"{betanet_client.url}/status")
            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "message": "Betanet Rust server is running and responding",
                    "server_url": betanet_client.url,
                    "server_reachable": True,
                }
            return {
                "status": "degraded",
                "message": f"Betanet server returned status {response.status_code}",
                "server_url": betanet_client.url,
                "server_reachable": True,
            }
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        return {
            "status": "degraded",
            "message": str(e),
            "server_url": betanet_client.url,
            "server_reachable": False,
        }
    except Exception as e:
        return {
            "status": "degraded",
            "message": f"Health check failed: {e}",
            "server_url": betanet_client.url,
            "server_reachable": False,
        }


# ---------------------------------------------------------------------------
# Status (SIN-006: matches betanet-status.schema.json)
# ---------------------------------------------------------------------------

@router.get("/status")
async def get_betanet_status() -> Dict[str, Any]:
    """Get Betanet network status (conforms to betanet-status.schema.json)."""
    svc = _get_service()

    try:
        raw = await svc.get_status()
        # Adapt to canonical schema
        active = raw.get("active_nodes", 0)
        return {
            "status": raw.get("status", "degraded"),
            "nodes": {
                "total": active,
                "active": active,
                "inactive": 0,
            },
            "network": {
                "latency": raw.get("avg_latency_ms", 0),
                "bandwidth": raw.get("connections", 0),
                "throughput": raw.get("packets_processed", 0),
                "packetsProcessed": raw.get("packets_processed", 0),
            },
            "lastUpdated": raw.get("timestamp"),
        }
    except Exception as e:
        logger.error("Error fetching Betanet status: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Deploy (legacy)
# ---------------------------------------------------------------------------

@router.post("/deploy")
async def deploy_node(request: DeployNodeRequest, _auth: dict = Depends(require_api_key)) -> Dict[str, Any]:
    """Deploy a new Betanet node."""
    svc = _get_service()

    try:
        result = await svc.deploy_node(
            node_type=request.node_type,
            region=request.region,
        )
        return {
            "success": result.get("success", False),
            "nodeId": result.get("node_id"),
            "status": result.get("status", "deploying"),
        }
    except Exception as e:
        logger.error("Error deploying node: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Node CRUD (SIN-003: owned by backend, not proxied to Rust)
# ---------------------------------------------------------------------------

@router.get("/nodes", response_model=List[NodeResponse])
async def list_nodes():
    """List all Betanet nodes."""
    svc = _get_service()
    return await svc.list_nodes()


@router.post("/nodes", response_model=NodeResponse, status_code=201)
async def create_node(request: NodeCreateRequest, _auth: dict = Depends(require_api_key)):
    """Create a new Betanet node."""
    valid_types = ["mixnode", "gateway", "client"]
    if request.node_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid node_type. Must be one of: {', '.join(valid_types)}",
        )

    svc = _get_service()
    return await svc.create_node(
        node_type=request.node_type,
        region=request.region,
        name=request.name,
    )


@router.get("/nodes/{node_id}", response_model=NodeResponse)
async def get_node(node_id: str):
    """Get details of a specific node."""
    svc = _get_service()
    node = await svc.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    return node


@router.put("/nodes/{node_id}", response_model=NodeResponse)
async def update_node(node_id: str, request: NodeUpdateRequest, _auth: dict = Depends(require_api_key)):
    """Update a node's configuration."""
    updates = request.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    svc = _get_service()
    node = await svc.update_node(node_id, updates)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    return node


@router.delete("/nodes/{node_id}", status_code=204)
async def delete_node(node_id: str, _auth: dict = Depends(require_api_key)):
    """Delete a node."""
    svc = _get_service()
    deleted = await svc.delete_node(node_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    return None
