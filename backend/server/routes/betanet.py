"""
Betanet API Routes
Handles Betanet privacy network status and operations
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import logging
import httpx

from ..services.enhanced_service_manager import enhanced_service_manager as service_manager
from ..constants import (
    HEALTH_CHECK_TIMEOUT,
    SHORT_REQUEST_TIMEOUT,
    LONG_REQUEST_TIMEOUT,
    MOCK_BANDWIDTH,
    MOCK_THROUGHPUT,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/betanet", tags=["betanet"])


class DeployNodeRequest(BaseModel):
    node_type: str = "mixnode"
    region: str = "us-east"


class NodeCreateRequest(BaseModel):
    """Request model for creating a new Betanet node"""
    node_type: str = Field(..., description="Node type: mixnode, gateway, or client")
    region: Optional[str] = Field(None, description="Deployment region (e.g., us-east, eu-west)")
    name: Optional[str] = Field(None, description="Custom node name")


class NodeUpdateRequest(BaseModel):
    """Request model for updating node configuration"""
    name: Optional[str] = None
    region: Optional[str] = None
    status: Optional[str] = None  # active, inactive, maintenance


class NodeResponse(BaseModel):
    """Response model for node information"""
    id: str
    node_type: str
    region: Optional[str]
    name: Optional[str]
    status: str
    packets_processed: int
    packets_forwarded: int
    packets_dropped: int
    avg_latency_ms: float
    created_at: str
    last_heartbeat: str


@router.get("/health")
async def check_betanet_health() -> Dict[str, Any]:
    """
    Health check endpoint that reports actual Betanet Rust server connectivity.

    Returns:
        Health status with connectivity information

    Status values:
        - healthy: Rust server is running and responding
        - degraded: Client initialized but server not reachable
        - unavailable: Client not initialized
    """
    betanet_client = service_manager.betanet_client

    if betanet_client is None:
        return {
            "status": "unavailable",
            "message": "Betanet client not initialized",
            "server_url": None,
            "server_reachable": False
        }

    try:
        async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT) as client:
            response = await client.get(f"{betanet_client.url}/status")

            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "message": "Betanet Rust server is running and responding",
                    "server_url": betanet_client.url,
                    "server_reachable": True
                }
            else:
                return {
                    "status": "degraded",
                    "message": f"Betanet server returned status {response.status_code}",
                    "server_url": betanet_client.url,
                    "server_reachable": True
                }

    except httpx.ConnectError:
        return {
            "status": "degraded",
            "message": "Betanet Rust server not running at localhost:9000",
            "server_url": betanet_client.url,
            "server_reachable": False
        }
    except httpx.TimeoutException:
        return {
            "status": "degraded",
            "message": "Betanet server request timed out",
            "server_url": betanet_client.url,
            "server_reachable": False
        }
    except Exception as e:
        return {
            "status": "degraded",
            "message": f"Health check failed: {str(e)}",
            "server_url": betanet_client.url,
            "server_reachable": False
        }


@router.get("/status")
async def get_betanet_status() -> Dict[str, Any]:
    """Get Betanet network status"""
    betanet = service_manager.get('betanet')

    if betanet is None:
        raise HTTPException(status_code=503, detail="Betanet service unavailable")

    try:
        status = await betanet.get_status()
        status_dict = status if isinstance(status, dict) else status.to_dict()

        return {
            "status": status_dict.get('status', 'unknown'),
            "nodes": {
                "total": status_dict.get('active_nodes', 0),
                "active": status_dict.get('active_nodes', 0),
                "inactive": 0
            },
            "network": {
                "latency": status_dict.get('avg_latency_ms', 0),
                "bandwidth": MOCK_BANDWIDTH,
                "throughput": MOCK_THROUGHPUT,
                "packetsProcessed": status_dict.get('packets_processed', 0)
            },
            "lastUpdated": status_dict.get('timestamp', None)
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
        result = await betanet.deploy_node(
            node_type=request.node_type,
            region=request.region
        )

        return {
            "success": result.get('success', False),
            "nodeId": result.get('node_id', None),
            "status": result.get('status', 'deploying')
        }
    except Exception as e:
        logger.error(f"Error deploying node: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Node Management CRUD Endpoints
# ============================================================================

@router.get("/nodes", response_model=List[NodeResponse])
async def list_nodes():
    """
    List all Betanet nodes with their current status.

    Returns:
        List of NodeResponse objects

    Raises:
        HTTPException 503: Betanet service unavailable
    """
    betanet_client = service_manager.betanet_client

    if betanet_client is None:
        raise HTTPException(
            status_code=503,
            detail="Betanet service unavailable - client not initialized"
        )

    try:
        async with httpx.AsyncClient(timeout=SHORT_REQUEST_TIMEOUT) as client:
            response = await client.get(f"{betanet_client.url}/nodes")

            if response.status_code != 200:
                raise HTTPException(
                    status_code=503,
                    detail="Betanet service returned error"
                )

            nodes_data = response.json()
            return nodes_data

    except httpx.ConnectError as e:
        logger.error(f"Failed to connect to Betanet server: {e}")
        raise HTTPException(
            status_code=503,
            detail="Betanet Rust server not running at localhost:9000"
        )
    except httpx.TimeoutException as e:
        logger.error(f"Betanet request timed out: {e}")
        raise HTTPException(
            status_code=503,
            detail="Betanet service request timed out"
        )
    except httpx.RequestError as e:
        logger.error(f"Failed to fetch nodes from Betanet: {e}")
        raise HTTPException(
            status_code=503,
            detail="Betanet service unavailable"
        )


@router.post("/nodes", response_model=NodeResponse, status_code=201)
async def create_node(request: NodeCreateRequest):
    """
    Deploy a new Betanet node.

    Args:
        request: NodeCreateRequest with node_type, region, name

    Returns:
        NodeResponse with created node details

    Raises:
        HTTPException 400: Invalid node type
        HTTPException 503: Betanet service unavailable
    """
    betanet_client = service_manager.betanet_client

    if betanet_client is None:
        raise HTTPException(
            status_code=503,
            detail="Betanet service unavailable - client not initialized"
        )

    # Validate node type
    valid_types = ["mixnode", "gateway", "client"]
    if request.node_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid node_type. Must be one of: {', '.join(valid_types)}"
        )

    try:
        # Call Betanet Rust service deploy endpoint
        async with httpx.AsyncClient(timeout=LONG_REQUEST_TIMEOUT) as client:
            response = await client.post(
                f"{betanet_client.url}/deploy",
                json={
                    "node_type": request.node_type,
                    "region": request.region,
                    "name": request.name
                }
            )

            if response.status_code != 200:
                error_detail = response.json().get("detail", "Deployment failed")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=error_detail
                )

            deploy_result = response.json()

            if not deploy_result.get("success"):
                raise HTTPException(
                    status_code=500,
                    detail=deploy_result.get("status", "Deployment failed")
                )

            # Fetch the newly created node details
            node_id = deploy_result.get("node_id")
            node_response = await client.get(f"{betanet_client.url}/nodes/{node_id}")

            return node_response.json()

    except httpx.ConnectError as e:
        logger.error(f"Failed to connect to Betanet server: {e}")
        raise HTTPException(
            status_code=503,
            detail="Betanet Rust server not running at localhost:9000"
        )
    except httpx.TimeoutException as e:
        logger.error(f"Betanet request timed out: {e}")
        raise HTTPException(
            status_code=503,
            detail="Betanet service request timed out"
        )
    except httpx.RequestError as e:
        logger.error(f"Failed to create node: {e}")
        raise HTTPException(
            status_code=503,
            detail="Betanet service unavailable"
        )


@router.get("/nodes/{node_id}", response_model=NodeResponse)
async def get_node(node_id: str):
    """
    Get detailed information about a specific Betanet node.

    Args:
        node_id: Node identifier

    Returns:
        NodeResponse with node details

    Raises:
        HTTPException 404: Node not found
        HTTPException 503: Betanet service unavailable
    """
    betanet_client = service_manager.betanet_client

    if betanet_client is None:
        raise HTTPException(
            status_code=503,
            detail="Betanet service unavailable - client not initialized"
        )

    try:
        async with httpx.AsyncClient(timeout=SHORT_REQUEST_TIMEOUT) as client:
            response = await client.get(f"{betanet_client.url}/nodes/{node_id}")

            if response.status_code == 404:
                raise HTTPException(
                    status_code=404,
                    detail=f"Node {node_id} not found"
                )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=503,
                    detail="Failed to fetch node details"
                )

            return response.json()

    except httpx.ConnectError as e:
        logger.error(f"Failed to connect to Betanet server: {e}")
        raise HTTPException(
            status_code=503,
            detail="Betanet Rust server not running at localhost:9000"
        )
    except httpx.TimeoutException as e:
        logger.error(f"Betanet request timed out: {e}")
        raise HTTPException(
            status_code=503,
            detail="Betanet service request timed out"
        )
    except httpx.RequestError as e:
        logger.error(f"Failed to fetch node {node_id}: {e}")
        raise HTTPException(
            status_code=503,
            detail="Betanet service unavailable"
        )


@router.put("/nodes/{node_id}", response_model=NodeResponse)
async def update_node(node_id: str, request: NodeUpdateRequest):
    """
    Update Betanet node configuration.

    Args:
        node_id: Node identifier
        request: NodeUpdateRequest with fields to update

    Returns:
        NodeResponse with updated node details

    Raises:
        HTTPException 404: Node not found
        HTTPException 503: Betanet service unavailable
    """
    betanet_client = service_manager.betanet_client

    if betanet_client is None:
        raise HTTPException(
            status_code=503,
            detail="Betanet service unavailable - client not initialized"
        )

    try:
        # Only send non-None fields
        update_data = request.model_dump(exclude_none=True)

        if not update_data:
            raise HTTPException(
                status_code=400,
                detail="No fields provided for update"
            )

        async with httpx.AsyncClient(timeout=SHORT_REQUEST_TIMEOUT) as client:
            response = await client.put(
                f"{betanet_client.url}/nodes/{node_id}",
                json=update_data
            )

            if response.status_code == 404:
                raise HTTPException(
                    status_code=404,
                    detail=f"Node {node_id} not found"
                )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=503,
                    detail="Failed to update node"
                )

            return response.json()

    except httpx.ConnectError as e:
        logger.error(f"Failed to connect to Betanet server: {e}")
        raise HTTPException(
            status_code=503,
            detail="Betanet Rust server not running at localhost:9000"
        )
    except httpx.TimeoutException as e:
        logger.error(f"Betanet request timed out: {e}")
        raise HTTPException(
            status_code=503,
            detail="Betanet service request timed out"
        )
    except httpx.RequestError as e:
        logger.error(f"Failed to update node {node_id}: {e}")
        raise HTTPException(
            status_code=503,
            detail="Betanet service unavailable"
        )


@router.delete("/nodes/{node_id}", status_code=204)
async def delete_node(node_id: str):
    """
    Delete/shutdown a Betanet node.

    Args:
        node_id: Node identifier

    Returns:
        204 No Content on success

    Raises:
        HTTPException 404: Node not found
        HTTPException 503: Betanet service unavailable
    """
    betanet_client = service_manager.betanet_client

    if betanet_client is None:
        raise HTTPException(
            status_code=503,
            detail="Betanet service unavailable - client not initialized"
        )

    try:
        async with httpx.AsyncClient(timeout=LONG_REQUEST_TIMEOUT) as client:
            response = await client.delete(f"{betanet_client.url}/nodes/{node_id}")

            if response.status_code == 404:
                raise HTTPException(
                    status_code=404,
                    detail=f"Node {node_id} not found"
                )

            if response.status_code not in [200, 204]:
                raise HTTPException(
                    status_code=503,
                    detail="Failed to delete node"
                )

            return None  # 204 No Content

    except httpx.ConnectError as e:
        logger.error(f"Failed to connect to Betanet server: {e}")
        raise HTTPException(
            status_code=503,
            detail="Betanet Rust server not running at localhost:9000"
        )
    except httpx.TimeoutException as e:
        logger.error(f"Betanet request timed out: {e}")
        raise HTTPException(
            status_code=503,
            detail="Betanet service request timed out"
        )
    except httpx.RequestError as e:
        logger.error(f"Failed to delete node {node_id}: {e}")
        raise HTTPException(
            status_code=503,
            detail="Betanet service unavailable"
        )
