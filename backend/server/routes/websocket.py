"""
WebSocket API Routes
HTTP endpoints for WebSocket management and metrics
"""
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status, Query
from typing import List, Optional
from pydantic import BaseModel
import uuid
import logging

from ..websocket.server import connection_manager
from ..websocket.publishers import publisher_manager
from ..services.metrics_aggregator import metrics_aggregator
from ..auth.dependencies import get_current_user
from ..auth.jwt_utils import verify_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ws", tags=["websocket"])


# Pydantic models
class SubscribeRequest(BaseModel):
    rooms: List[str]


class UnsubscribeRequest(BaseModel):
    rooms: List[str]


class StreamInfo(BaseModel):
    name: str
    description: str
    update_interval: float


class MetricsHistoryRequest(BaseModel):
    metric: str
    hours: int = 24


# WebSocket endpoint with authentication
@router.websocket("/connect")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None)
):
    """
    Main WebSocket endpoint for real-time updates

    Authentication via query parameter: ?token=<jwt_token>
    """
    connection_id = str(uuid.uuid4())
    user_id = None

    # Authenticate if token provided
    if token:
        try:
            payload = verify_token(token)
            user_id = payload.get("sub")
        except Exception as e:
            logger.warning(f"WebSocket authentication failed: {e}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    try:
        # Accept and register connection
        await connection_manager.connect(
            websocket,
            connection_id,
            user_id=user_id
        )

        # Handle incoming messages
        while True:
            try:
                message = await websocket.receive_json()
                await handle_websocket_message(connection_id, message)
            except WebSocketDisconnect:
                break

    except Exception as e:
        logger.error(f"WebSocket error for connection {connection_id}: {e}")
    finally:
        await connection_manager.disconnect(connection_id)


async def handle_websocket_message(connection_id: str, message: dict):
    """
    Handle incoming WebSocket messages from clients

    Supported message types:
    - subscribe: Subscribe to rooms
    - unsubscribe: Unsubscribe from rooms
    - ping: Heartbeat ping
    """
    msg_type = message.get("type")

    if msg_type == "subscribe":
        rooms = message.get("rooms", [])
        for room in rooms:
            await connection_manager.subscribe_to_room(connection_id, room)

    elif msg_type == "unsubscribe":
        rooms = message.get("rooms", [])
        for room in rooms:
            await connection_manager.unsubscribe_from_room(connection_id, room)

    elif msg_type == "ping":
        await connection_manager.handle_ping(connection_id)

    else:
        logger.warning(f"Unknown message type from {connection_id}: {msg_type}")


@router.post("/subscribe")
async def subscribe_to_streams(
    request: SubscribeRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Subscribe to data streams (HTTP endpoint for connection management)

    Note: Actual subscription happens via WebSocket after connection
    """
    return {
        "message": "Use WebSocket /api/ws/connect and send subscribe message",
        "available_rooms": [
            "nodes",
            "tasks",
            "metrics",
            "alerts",
            "resources",
            "topology"
        ],
        "example": {
            "type": "subscribe",
            "rooms": ["nodes", "metrics"]
        }
    }


@router.post("/unsubscribe")
async def unsubscribe_from_streams(
    request: UnsubscribeRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Unsubscribe from data streams
    """
    return {
        "message": "Use WebSocket and send unsubscribe message",
        "example": {
            "type": "unsubscribe",
            "rooms": ["nodes"]
        }
    }


@router.get("/streams", response_model=List[StreamInfo])
async def list_available_streams():
    """
    List all available WebSocket streams
    """
    return [
        StreamInfo(
            name="nodes",
            description="Node status updates (Betanet and P2P)",
            update_interval=5.0
        ),
        StreamInfo(
            name="tasks",
            description="Task progress updates from scheduler",
            update_interval=2.0
        ),
        StreamInfo(
            name="metrics",
            description="Performance metrics and health status",
            update_interval=10.0
        ),
        StreamInfo(
            name="alerts",
            description="Real-time alerts and notifications",
            update_interval=0.0  # Immediate
        ),
        StreamInfo(
            name="resources",
            description="Resource utilization (CPU, memory, storage)",
            update_interval=15.0
        ),
        StreamInfo(
            name="topology",
            description="Network topology changes",
            update_interval=5.0
        )
    ]


@router.get("/metrics/history")
async def get_metrics_history(
    metric: str = Query(..., description="Metric name (e.g., 'betanet.latency_ms')"),
    hours: int = Query(24, ge=1, le=168, description="Hours of history (1-168)"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get historical metrics data

    Available metrics:
    - betanet.active_nodes
    - betanet.latency_ms
    - betanet.connections
    - p2p.connected_peers
    - scheduler.total_jobs
    - scheduler.running_jobs
    - edge.total_devices
    - edge.avg_cpu_usage
    - edge.avg_memory_usage
    """
    data = metrics_aggregator.get_historical_data(metric, hours)

    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"No historical data found for metric: {metric}"
        )

    return {
        "metric": metric,
        "hours": hours,
        "data_points": len(data),
        "data": data
    }


@router.get("/metrics/statistics")
async def get_metrics_statistics(
    metric: str = Query(..., description="Metric name"),
    window: str = Query("5m", regex="^(1m|5m|1h)$", description="Time window"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get statistical analysis of a metric

    Windows: 1m, 5m, 1h
    """
    stats = metrics_aggregator.get_metric_statistics(metric, window)

    if "error" in stats:
        raise HTTPException(status_code=404, detail=stats["error"])

    return stats


@router.get("/metrics/summary")
async def get_all_metrics_summary(
    current_user: dict = Depends(get_current_user)
):
    """
    Get summary of all metrics across all time windows
    """
    return metrics_aggregator.get_all_metrics_summary()


@router.get("/stats")
async def get_websocket_stats(
    current_user: dict = Depends(get_current_user)
):
    """
    Get WebSocket connection statistics
    """
    stats = connection_manager.get_stats()

    return {
        **stats,
        "publishers_active": len(publisher_manager.publishers)
    }


@router.get("/connections/{connection_id}")
async def get_connection_info(
    connection_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get information about a specific WebSocket connection
    """
    info = connection_manager.get_connection_info(connection_id)

    if not info:
        raise HTTPException(
            status_code=404,
            detail=f"Connection not found: {connection_id}"
        )

    return info
