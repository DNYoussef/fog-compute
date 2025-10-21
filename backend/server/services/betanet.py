"""
Betanet Privacy Network Service
Manages mixnode deployment and statistics
"""

import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import asyncio


@dataclass
class MixnodeInfo:
    """Information about a single mixnode"""
    id: str
    status: str  # active, deploying, stopped
    packets_processed: int
    uptime_seconds: int
    region: str = "us-east"
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BetanetStatus:
    """Overall Betanet network status"""
    status: str
    active_nodes: int
    connections: int
    avg_latency_ms: float
    packets_processed: int
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BetanetService:
    """Service for managing Betanet privacy network"""

    def __init__(self):
        self.mixnodes: Dict[str, MixnodeInfo] = {}
        self.total_packets_processed = 22274
        self._initialize_default_nodes()

    def _initialize_default_nodes(self):
        """Initialize with some default active nodes"""
        default_nodes = [
            MixnodeInfo(
                id=str(uuid.uuid4()),
                status="active",
                packets_processed=12453,
                uptime_seconds=86400,
                region="us-east",
                created_at=datetime.utcnow().isoformat(),
            ),
            MixnodeInfo(
                id=str(uuid.uuid4()),
                status="active",
                packets_processed=9821,
                uptime_seconds=72000,
                region="eu-west",
                created_at=datetime.utcnow().isoformat(),
            ),
        ]
        for node in default_nodes:
            self.mixnodes[node.id] = node

    async def get_status(self) -> BetanetStatus:
        """Get overall network status"""
        active_nodes = [n for n in self.mixnodes.values() if n.status == "active"]

        return BetanetStatus(
            status="operational",
            active_nodes=len(active_nodes),
            connections=len(active_nodes) * 3,  # Assume 3 connections per node
            avg_latency_ms=45.0,  # Mock value - would calculate from actual metrics
            packets_processed=self.total_packets_processed,
            timestamp=datetime.utcnow().isoformat(),
        )

    async def get_mixnodes(self) -> List[MixnodeInfo]:
        """Get all mixnodes"""
        return list(self.mixnodes.values())

    async def deploy_node(
        self,
        node_type: str = "mixnode",
        region: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Deploy a new mixnode

        Args:
            node_type: Type of node to deploy (currently only "mixnode")
            region: AWS region to deploy to (e.g., "us-east", "eu-west")

        Returns:
            Deployment result with node_id and status
        """
        node_id = str(uuid.uuid4())

        new_node = MixnodeInfo(
            id=node_id,
            status="deploying",
            packets_processed=0,
            uptime_seconds=0,
            region=region or "us-east",
            created_at=datetime.utcnow().isoformat(),
        )

        self.mixnodes[node_id] = new_node

        # Simulate async deployment
        asyncio.create_task(self._complete_deployment(node_id))

        return {
            "success": True,
            "node_id": node_id,
            "status": "deploying",
            "message": f"Deploying {node_type} in {new_node.region}",
        }

    async def _complete_deployment(self, node_id: str):
        """Simulate deployment completion after a delay"""
        await asyncio.sleep(5)  # Simulate 5 second deployment
        if node_id in self.mixnodes:
            self.mixnodes[node_id].status = "active"

    async def stop_node(self, node_id: str) -> Dict[str, Any]:
        """Stop a running mixnode"""
        if node_id not in self.mixnodes:
            return {"success": False, "error": "Node not found"}

        self.mixnodes[node_id].status = "stopped"
        return {"success": True, "node_id": node_id, "status": "stopped"}

    async def delete_node(self, node_id: str) -> Dict[str, Any]:
        """Delete a mixnode"""
        if node_id not in self.mixnodes:
            return {"success": False, "error": "Node not found"}

        del self.mixnodes[node_id]
        return {"success": True, "node_id": node_id}

    async def get_node(self, node_id: str) -> Optional[MixnodeInfo]:
        """Get a specific mixnode by ID"""
        return self.mixnodes.get(node_id)

    async def get_metrics(self) -> str:
        """Get Prometheus-style metrics"""
        active_nodes = [n for n in self.mixnodes.values() if n.status == "active"]

        metrics = f"""# HELP betanet_nodes_total Total number of betanet mixnodes
# TYPE betanet_nodes_total gauge
betanet_nodes_total {len(active_nodes)}
# HELP betanet_packets_processed_total Total packets processed
# TYPE betanet_packets_processed_total counter
betanet_packets_processed_total {self.total_packets_processed}
# HELP betanet_avg_latency_ms Average latency in milliseconds
# TYPE betanet_avg_latency_ms gauge
betanet_avg_latency_ms 45.0
"""
        return metrics

    async def update_node_stats(self, node_id: str, packets_delta: int = 0):
        """Update node statistics"""
        if node_id in self.mixnodes:
            self.mixnodes[node_id].packets_processed += packets_delta
            self.mixnodes[node_id].uptime_seconds += 1
            self.total_packets_processed += packets_delta


# Global singleton instance
betanet_service = BetanetService()
