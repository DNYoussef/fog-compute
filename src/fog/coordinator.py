"""
Fog Coordinator Implementation

Concrete implementation of the fog network coordinator.
Manages node registry, task routing, health monitoring, and failover.
"""

import asyncio
import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from .coordinator_interface import (
    FogNode,
    IFogCoordinator,
    NetworkTopology,
    NodeStatus,
    NodeType,
    RoutingStrategy,
    Task,
)

logger = logging.getLogger(__name__)


class FogCoordinator(IFogCoordinator):
    """
    Fog network coordinator implementation.

    Provides:
    - Dynamic node registry with health tracking
    - Intelligent task routing (round-robin, least-loaded, affinity-based)
    - Network topology monitoring
    - Graceful failover and recovery
    - Integration with onion router for privacy-aware routing
    """

    def __init__(
        self,
        node_id: str,
        onion_router: Optional[Any] = None,
        heartbeat_interval: int = 30,
        heartbeat_timeout: int = 90,
    ):
        """
        Initialize fog coordinator.

        Args:
            node_id: Unique ID for this coordinator instance
            onion_router: Optional OnionRouter instance for privacy features
            heartbeat_interval: Interval (seconds) for node heartbeat checks
            heartbeat_timeout: Timeout (seconds) before marking node offline
        """
        self.node_id = node_id
        self.onion_router = onion_router
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_timeout = heartbeat_timeout

        # Node registry
        self._nodes: dict[str, FogNode] = {}
        self._node_lock = asyncio.Lock()

        # Task routing state
        self._round_robin_index = 0
        self._task_assignments: dict[str, str] = {}  # task_id -> node_id

        # Topology tracking
        self._topology_snapshots: list[NetworkTopology] = []
        self._max_snapshots = 100

        # Background tasks
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False

        logger.info(f"FogCoordinator initialized: {node_id}")

    async def register_node(self, node: FogNode) -> bool:
        """Register a new fog node."""
        async with self._node_lock:
            if node.node_id in self._nodes:
                logger.warning(f"Node {node.node_id} already registered")
                return False

            # Update registration time
            node.registered_at = datetime.now(UTC)
            node.last_heartbeat = datetime.now(UTC)
            node.status = NodeStatus.ACTIVE

            self._nodes[node.node_id] = node
            logger.info(
                f"Registered node: {node.node_id} "
                f"(type={node.node_type.value}, region={node.region})"
            )
            return True

    async def unregister_node(self, node_id: str) -> bool:
        """Unregister a fog node."""
        async with self._node_lock:
            if node_id not in self._nodes:
                logger.warning(f"Node {node_id} not found for unregistration")
                return False

            node = self._nodes.pop(node_id)
            logger.info(f"Unregistered node: {node_id} (type={node.node_type.value})")

            # Handle any active tasks on this node
            await self.handle_node_failure(node_id)
            return True

    async def update_node_status(self, node_id: str, status: NodeStatus) -> bool:
        """Update node status."""
        async with self._node_lock:
            if node_id not in self._nodes:
                logger.warning(f"Node {node_id} not found for status update")
                return False

            node = self._nodes[node_id]
            old_status = node.status
            node.status = status
            node.last_heartbeat = datetime.now(UTC)

            logger.info(f"Node {node_id} status: {old_status.value} → {status.value}")
            return True

    async def get_node(self, node_id: str) -> Optional[FogNode]:
        """Get node by ID."""
        async with self._node_lock:
            return self._nodes.get(node_id)

    async def list_nodes(
        self,
        status: Optional[NodeStatus] = None,
        node_type: Optional[NodeType] = None,
    ) -> list[FogNode]:
        """List nodes with optional filtering."""
        async with self._node_lock:
            nodes = list(self._nodes.values())

            if status:
                nodes = [n for n in nodes if n.status == status]
            if node_type:
                nodes = [n for n in nodes if n.node_type == node_type]

            return nodes

    async def route_task(
        self,
        task: Task,
        strategy: RoutingStrategy = RoutingStrategy.LEAST_LOADED,
    ) -> Optional[FogNode]:
        """
        Route task to best available node.

        Strategies:
        - ROUND_ROBIN: Distribute evenly across nodes
        - LEAST_LOADED: Select node with lowest CPU usage
        - AFFINITY_BASED: Prefer nodes with matching capabilities
        - PROXIMITY_BASED: Select nearest node (by region)
        - PRIVACY_AWARE: Prefer nodes supporting onion routing
        """
        async with self._node_lock:
            # Get eligible nodes (active + idle)
            eligible = [
                n
                for n in self._nodes.values()
                if n.status in (NodeStatus.ACTIVE, NodeStatus.IDLE)
                and n.cpu_cores >= task.cpu_required
                and n.memory_mb >= task.memory_required
                and (not task.gpu_required or n.gpu_available)
            ]

            if not eligible:
                logger.warning(f"No eligible nodes for task {task.task_id}")
                return None

            # Privacy filtering
            if task.require_onion_circuit:
                eligible = [n for n in eligible if n.supports_onion_routing]
                if not eligible:
                    logger.warning(
                        f"No privacy-capable nodes for task {task.task_id}"
                    )
                    return None

            # Apply routing strategy
            selected_node = None

            if strategy == RoutingStrategy.ROUND_ROBIN:
                selected_node = self._route_round_robin(eligible)
            elif strategy == RoutingStrategy.LEAST_LOADED:
                selected_node = self._route_least_loaded(eligible)
            elif strategy == RoutingStrategy.AFFINITY_BASED:
                selected_node = self._route_affinity_based(eligible, task)
            elif strategy == RoutingStrategy.PROXIMITY_BASED:
                selected_node = self._route_proximity_based(eligible, task)
            elif strategy == RoutingStrategy.PRIVACY_AWARE:
                selected_node = self._route_privacy_aware(eligible, task)
            else:
                selected_node = eligible[0]  # Fallback

            if selected_node:
                # Update task assignment
                task.assigned_node = selected_node.node_id
                self._task_assignments[task.task_id] = selected_node.node_id

                # Update node state
                selected_node.active_tasks += 1
                selected_node.status = NodeStatus.BUSY

                logger.info(
                    f"Routed task {task.task_id} to node {selected_node.node_id} "
                    f"(strategy={strategy.value})"
                )

            return selected_node

    def _route_round_robin(self, nodes: list[FogNode]) -> FogNode:
        """Round-robin routing."""
        node = nodes[self._round_robin_index % len(nodes)]
        self._round_robin_index += 1
        return node

    def _route_least_loaded(self, nodes: list[FogNode]) -> FogNode:
        """Select node with lowest CPU usage."""
        return min(nodes, key=lambda n: n.cpu_usage_percent)

    def _route_affinity_based(self, nodes: list[FogNode], task: Task) -> FogNode:
        """Select node with best matching capabilities."""
        # Prefer nodes with exact resource match
        scored = [
            (
                n,
                abs(n.cpu_cores - task.cpu_required)
                + abs(n.memory_mb - task.memory_required),
            )
            for n in nodes
        ]
        return min(scored, key=lambda x: x[1])[0]

    def _route_proximity_based(self, nodes: list[FogNode], task: Task) -> FogNode:
        """Select nearest node (placeholder - would use geolocation)."""
        # For now, prefer nodes in same region if task has region preference
        task_region = task.task_data.get("preferred_region")
        if task_region:
            regional = [n for n in nodes if n.region == task_region]
            if regional:
                return regional[0]
        return nodes[0]

    def _route_privacy_aware(self, nodes: list[FogNode], task: Task) -> FogNode:
        """Select node with best privacy support."""
        # Prefer nodes with high circuit participation
        return max(nodes, key=lambda n: n.circuit_participation_count)

    async def process_fog_request(
        self, request_type: str, request_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Process generic fog network request.

        Supported request types:
        - compute_task: Execute computation
        - query_status: Get task/node status
        - update_metrics: Update node metrics
        """
        try:
            if request_type == "compute_task":
                task_id = request_data.get("task_id")
                task_data = request_data.get("task_data", {})

                # Create task
                task = Task(
                    task_id=task_id,
                    task_type=request_data.get("task_type", "generic"),
                    task_data=task_data,
                    priority=request_data.get("priority", 5),
                )

                # Route task
                node = await self.route_task(task)
                if node:
                    return {"success": True, "node_id": node.node_id}
                else:
                    return {"success": False, "error": "No suitable node available"}

            elif request_type == "query_status":
                node_id = request_data.get("node_id")
                if node_id:
                    node = await self.get_node(node_id)
                    if node:
                        return {
                            "success": True,
                            "status": node.status.value,
                            "active_tasks": node.active_tasks,
                        }
                return {"success": False, "error": "Node not found"}

            elif request_type == "update_metrics":
                node_id = request_data.get("node_id")
                if node_id:
                    async with self._node_lock:
                        if node_id in self._nodes:
                            node = self._nodes[node_id]
                            node.cpu_usage_percent = request_data.get(
                                "cpu_usage", node.cpu_usage_percent
                            )
                            node.memory_usage_percent = request_data.get(
                                "memory_usage", node.memory_usage_percent
                            )
                            node.last_heartbeat = datetime.now(UTC)
                            return {"success": True}
                return {"success": False, "error": "Node not found"}

            else:
                return {"success": False, "error": f"Unknown request type: {request_type}"}

        except Exception as e:
            logger.error(f"Error processing fog request: {e}")
            return {"success": False, "error": str(e)}

    async def get_topology(self) -> NetworkTopology:
        """Get network topology snapshot."""
        async with self._node_lock:
            nodes = list(self._nodes.values())

            # Count nodes by status
            active = sum(1 for n in nodes if n.status == NodeStatus.ACTIVE)
            offline = sum(1 for n in nodes if n.status == NodeStatus.OFFLINE)

            # Count by type
            type_counts = defaultdict(int)
            for node in nodes:
                type_counts[node.node_type] += 1

            # Calculate capacity
            total_cpu = sum(n.cpu_cores for n in nodes)
            used_cpu = sum(
                int(n.cpu_cores * n.cpu_usage_percent / 100) for n in nodes
            )
            total_memory = sum(n.memory_mb for n in nodes)
            used_memory = sum(
                int(n.memory_mb * n.memory_usage_percent / 100) for n in nodes
            )

            # Task stats
            running_tasks = sum(n.active_tasks for n in nodes)

            topology = NetworkTopology(
                total_nodes=len(nodes),
                active_nodes=active,
                offline_nodes=offline,
                edge_devices=type_counts[NodeType.EDGE_DEVICE],
                relay_nodes=type_counts[NodeType.RELAY_NODE],
                mixnodes=type_counts[NodeType.MIXNODE],
                compute_nodes=type_counts[NodeType.COMPUTE_NODE],
                gateways=type_counts[NodeType.GATEWAY],
                total_cpu_cores=total_cpu,
                available_cpu_cores=total_cpu - used_cpu,
                total_memory_mb=total_memory,
                available_memory_mb=total_memory - used_memory,
                running_tasks=running_tasks,
                snapshot_time=datetime.now(UTC),
            )

            # Store snapshot (limited history)
            self._topology_snapshots.append(topology)
            if len(self._topology_snapshots) > self._max_snapshots:
                self._topology_snapshots.pop(0)

            return topology

    async def handle_node_failure(self, node_id: str) -> bool:
        """Handle node failure and task redistribution."""
        try:
            async with self._node_lock:
                if node_id not in self._nodes:
                    return False

                node = self._nodes[node_id]
                node.status = NodeStatus.OFFLINE
                node.failed_tasks += node.active_tasks

                logger.warning(
                    f"Node {node_id} failed with {node.active_tasks} active tasks"
                )

                # In a real system, would redistribute tasks
                # For now, just mark them as failed
                node.active_tasks = 0

                return True

        except Exception as e:
            logger.error(f"Error handling node failure: {e}")
            return False

    async def health_check(self) -> dict[str, Any]:
        """Perform coordinator health check."""
        topology = await self.get_topology()

        return {
            "coordinator_id": self.node_id,
            "status": "healthy" if self._running else "stopped",
            "total_nodes": topology.total_nodes,
            "active_nodes": topology.active_nodes,
            "running_tasks": topology.running_tasks,
            "has_onion_router": self.onion_router is not None,
            "uptime_seconds": (
                (datetime.now(UTC) - self._topology_snapshots[0].snapshot_time).total_seconds()
                if self._topology_snapshots
                else 0
            ),
        }

    async def _heartbeat_monitor(self):
        """Background task to monitor node heartbeats."""
        while self._running:
            try:
                async with self._node_lock:
                    now = datetime.now(UTC)
                    timeout = timedelta(seconds=self.heartbeat_timeout)

                    for node_id, node in list(self._nodes.items()):
                        if node.status == NodeStatus.OFFLINE:
                            continue

                        time_since_heartbeat = now - node.last_heartbeat
                        if time_since_heartbeat > timeout:
                            logger.warning(
                                f"Node {node_id} heartbeat timeout "
                                f"({time_since_heartbeat.total_seconds()}s)"
                            )
                            await self.handle_node_failure(node_id)

                await asyncio.sleep(self.heartbeat_interval)

            except Exception as e:
                logger.error(f"Error in heartbeat monitor: {e}")
                await asyncio.sleep(5)

    async def start(self):
        """Start coordinator and background tasks."""
        if self._running:
            logger.warning("Coordinator already running")
            return

        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_monitor())
        logger.info(f"FogCoordinator {self.node_id} started")

    async def stop(self):
        """Stop coordinator gracefully."""
        if not self._running:
            return

        self._running = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        logger.info(f"FogCoordinator {self.node_id} stopped")
