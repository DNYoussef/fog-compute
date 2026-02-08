"""
Betanet Privacy Network Service (Option B: backend owns API contracts)

SIN-003: Backend owns node CRUD. Rust provides transport/metrics only.
SIN-004: Canonical node schema defined here, adapter maps Rust data.

The service maintains an in-memory node registry and syncs metrics
from the Rust Betanet server when available.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from ..constants import CONNECTIONS_PER_NODE, DEPLOYMENT_DELAY_SECONDS

logger = logging.getLogger(__name__)


@dataclass
class BetanetNode:
    """Canonical node representation (matches betanet-node.schema.json)."""

    id: str
    node_type: str  # mixnode, gateway, client
    status: str  # active, inactive, maintenance, deploying
    region: Optional[str] = None
    name: Optional[str] = None
    packets_processed: int = 0
    packets_forwarded: int = 0
    packets_dropped: int = 0
    avg_latency_ms: float = 0.0
    created_at: str = ""
    last_heartbeat: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "node_type": self.node_type,
            "region": self.region,
            "name": self.name,
            "status": self.status,
            "packets_processed": self.packets_processed,
            "packets_forwarded": self.packets_forwarded,
            "packets_dropped": self.packets_dropped,
            "avg_latency_ms": self.avg_latency_ms,
            "created_at": self.created_at,
            "last_heartbeat": self.last_heartbeat,
        }


class BetanetService:
    """Service for managing Betanet privacy network.

    Option B architecture: this service owns all node state.
    It optionally delegates deploy and metrics to the Rust server
    via BetanetClient, but the canonical node registry lives here.
    """

    def __init__(self, client=None):
        """Initialize with optional BetanetClient for Rust communication."""
        self.client = client
        self._nodes: Dict[str, BetanetNode] = {}

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    async def get_status(self) -> Dict[str, Any]:
        """Get overall network status.

        Tries Rust server first for live metrics, falls back to local state.
        """
        if self.client:
            try:
                rust_status = await self.client.get_status()
                if rust_status.get("status") != "mock":
                    return rust_status
            except Exception as e:
                logger.warning("Rust status unavailable, using local: %s", e)

        active = [n for n in self._nodes.values() if n.status == "active"]
        total_packets = sum(n.packets_processed for n in self._nodes.values())
        avg_lat = (
            sum(n.avg_latency_ms for n in active) / len(active) if active else 0.0
        )
        return {
            "status": "healthy" if active else "degraded",
            "active_nodes": len(active),
            "connections": len(active) * CONNECTIONS_PER_NODE,
            "avg_latency_ms": avg_lat,
            "packets_processed": total_packets,
            "timestamp": self._now_iso(),
        }

    # ------------------------------------------------------------------
    # Node CRUD (SIN-003: backend owns this)
    # ------------------------------------------------------------------

    async def list_nodes(self) -> List[Dict[str, Any]]:
        """List all registered nodes."""
        return [n.to_dict() for n in self._nodes.values()]

    async def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        node = self._nodes.get(node_id)
        return node.to_dict() if node else None

    async def create_node(
        self,
        node_type: str,
        region: Optional[str] = None,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new node. Optionally delegates deploy to Rust."""
        node_id = str(uuid.uuid4())
        now = self._now_iso()

        node = BetanetNode(
            id=node_id,
            node_type=node_type,
            status="deploying",
            region=region,
            name=name,
            created_at=now,
            last_heartbeat=now,
        )
        self._nodes[node_id] = node

        # Try Rust deploy if client available
        if self.client:
            try:
                result = await self.client.deploy_node(
                    node_type=node_type, region=region, name=name
                )
                if result.get("success"):
                    node.status = "active"
                    node.last_heartbeat = self._now_iso()
            except Exception as e:
                logger.warning("Rust deploy failed, node stays deploying: %s", e)

        return node.to_dict()

    async def update_node(
        self, node_id: str, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        node = self._nodes.get(node_id)
        if not node:
            return None

        for key in ("name", "region", "status"):
            if key in updates and updates[key] is not None:
                setattr(node, key, updates[key])

        node.last_heartbeat = self._now_iso()
        return node.to_dict()

    async def delete_node(self, node_id: str) -> bool:
        if node_id not in self._nodes:
            return False
        del self._nodes[node_id]
        return True

    # ------------------------------------------------------------------
    # Deploy (legacy compat - route calls this)
    # ------------------------------------------------------------------

    async def deploy_node(
        self, node_type: str = "mixnode", region: Optional[str] = None
    ) -> Dict[str, Any]:
        """Legacy deploy interface used by /deploy route."""
        node_dict = await self.create_node(node_type=node_type, region=region)
        return {
            "success": True,
            "node_id": node_dict["id"],
            "status": node_dict["status"],
        }

    # ------------------------------------------------------------------
    # Metrics (SIN-005: parse Prometheus text from Rust)
    # ------------------------------------------------------------------

    async def get_metrics(self) -> Dict[str, float]:
        """Get metrics. Delegates to Rust if available."""
        if self.client:
            try:
                return await self.client.get_metrics()
            except Exception as e:
                logger.warning("Rust metrics unavailable: %s", e)
        return {}

    # ------------------------------------------------------------------
    # Sync from Rust (SIN-004: adapter maps Rust schema to canonical)
    # ------------------------------------------------------------------

    async def sync_from_rust(self) -> int:
        """Pull mixnode data from Rust and merge into local registry.

        SIN-004: Adapts Rust MixnodeInfoResponse fields to our canonical
        BetanetNode schema.
        """
        if not self.client:
            return 0

        try:
            rust_nodes = await self.client.get_mixnodes()
        except Exception as e:
            logger.warning("Failed to sync from Rust: %s", e)
            return 0

        now = self._now_iso()
        synced = 0
        for rn in rust_nodes:
            node_id = rn.get("id", "")
            if not node_id:
                continue

            if node_id in self._nodes:
                # Update metrics from Rust
                node = self._nodes[node_id]
                node.packets_processed = rn.get("packets_processed", 0)
                node.packets_forwarded = rn.get("packets_forwarded", 0)
                node.packets_dropped = rn.get("packets_dropped", 0)
                node.avg_latency_ms = rn.get("avg_latency_ms", 0.0)
                node.status = rn.get("status", node.status)
                node.last_heartbeat = now
            else:
                # New node from Rust - add to our registry
                self._nodes[node_id] = BetanetNode(
                    id=node_id,
                    node_type="mixnode",
                    status=rn.get("status", "active"),
                    packets_processed=rn.get("packets_processed", 0),
                    packets_forwarded=rn.get("packets_forwarded", 0),
                    packets_dropped=rn.get("packets_dropped", 0),
                    avg_latency_ms=rn.get("avg_latency_ms", 0.0),
                    created_at=now,
                    last_heartbeat=now,
                )
            synced += 1

        return synced
