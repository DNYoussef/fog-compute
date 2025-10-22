"""
Fog Coordinator Interface

Abstract base class defining the contract for fog network coordination.
Provides node management, task routing, and topology tracking for fog computing.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional
import asyncio


class NodeStatus(Enum):
    """Status of a fog node."""
    ACTIVE = "active"
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class NodeType(Enum):
    """Type of fog node."""
    EDGE_DEVICE = "edge_device"  # Mobile/IoT devices
    RELAY_NODE = "relay_node"    # Betanet relays
    MIXNODE = "mixnode"          # Betanet mixnodes
    COMPUTE_NODE = "compute_node"  # Dedicated compute
    GATEWAY = "gateway"          # Edge gateway


class RoutingStrategy(Enum):
    """Task routing strategy."""
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    AFFINITY_BASED = "affinity_based"
    PROXIMITY_BASED = "proximity_based"
    PRIVACY_AWARE = "privacy_aware"


@dataclass
class FogNode:
    """Represents a node in the fog network."""
    node_id: str
    node_type: NodeType
    status: NodeStatus = NodeStatus.ACTIVE

    # Capabilities
    cpu_cores: int = 1
    memory_mb: int = 512
    storage_mb: int = 1024
    gpu_available: bool = False

    # Location (optional)
    region: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Performance metrics
    cpu_usage_percent: float = 0.0
    memory_usage_percent: float = 0.0
    active_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0

    # Reputation
    reputation_score: float = 1.0  # 0.0 to 1.0
    uptime_percent: float = 100.0

    # Network
    ip_address: Optional[str] = None
    port: int = 8080
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(UTC))
    registered_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Privacy
    supports_onion_routing: bool = False
    circuit_participation_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert FogNode to dictionary for caching/serialization"""
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "status": self.status.value,
            "cpu_cores": self.cpu_cores,
            "memory_mb": self.memory_mb,
            "storage_mb": self.storage_mb,
            "gpu_available": self.gpu_available,
            "region": self.region,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "cpu_usage_percent": self.cpu_usage_percent,
            "memory_usage_percent": self.memory_usage_percent,
            "active_tasks": self.active_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "reputation_score": self.reputation_score,
            "uptime_percent": self.uptime_percent,
            "ip_address": self.ip_address,
            "port": self.port,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "registered_at": self.registered_at.isoformat() if self.registered_at else None,
            "supports_onion_routing": self.supports_onion_routing,
            "circuit_participation_count": self.circuit_participation_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FogNode":
        """Create FogNode from dictionary (for cache deserialization)"""
        # Parse enums
        node_type = NodeType(data["node_type"])
        status = NodeStatus(data.get("status", "active"))

        # Parse datetimes
        last_heartbeat = datetime.fromisoformat(data["last_heartbeat"]) if data.get("last_heartbeat") else datetime.now(UTC)
        registered_at = datetime.fromisoformat(data["registered_at"]) if data.get("registered_at") else datetime.now(UTC)

        return cls(
            node_id=data["node_id"],
            node_type=node_type,
            status=status,
            cpu_cores=data.get("cpu_cores", 1),
            memory_mb=data.get("memory_mb", 512),
            storage_mb=data.get("storage_mb", 1024),
            gpu_available=data.get("gpu_available", False),
            region=data.get("region"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            cpu_usage_percent=data.get("cpu_usage_percent", 0.0),
            memory_usage_percent=data.get("memory_usage_percent", 0.0),
            active_tasks=data.get("active_tasks", 0),
            completed_tasks=data.get("completed_tasks", 0),
            failed_tasks=data.get("failed_tasks", 0),
            reputation_score=data.get("reputation_score", 1.0),
            uptime_percent=data.get("uptime_percent", 100.0),
            ip_address=data.get("ip_address"),
            port=data.get("port", 8080),
            last_heartbeat=last_heartbeat,
            registered_at=registered_at,
            supports_onion_routing=data.get("supports_onion_routing", False),
            circuit_participation_count=data.get("circuit_participation_count", 0),
        )


@dataclass
class Task:
    """Represents a fog computing task."""
    task_id: str
    task_type: str
    priority: int = 5  # 1 (highest) to 10 (lowest)

    # Resource requirements
    cpu_required: int = 1
    memory_required: int = 256
    storage_required: int = 100
    gpu_required: bool = False

    # Privacy requirements
    privacy_level: str = "public"
    require_onion_circuit: bool = False

    # Task data
    task_data: dict[str, Any] = field(default_factory=dict)

    # Status tracking
    assigned_node: Optional[str] = None
    status: str = "pending"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class NetworkTopology:
    """Represents the fog network topology."""
    total_nodes: int = 0
    active_nodes: int = 0
    offline_nodes: int = 0

    # Node breakdown by type
    edge_devices: int = 0
    relay_nodes: int = 0
    mixnodes: int = 0
    compute_nodes: int = 0
    gateways: int = 0

    # Capacity
    total_cpu_cores: int = 0
    available_cpu_cores: int = 0
    total_memory_mb: int = 0
    available_memory_mb: int = 0

    # Tasks
    queued_tasks: int = 0
    running_tasks: int = 0
    completed_tasks: int = 0

    # Timestamp
    snapshot_time: datetime = field(default_factory=lambda: datetime.now(UTC))


class IFogCoordinator(ABC):
    """
    Abstract interface for fog network coordination.

    Responsibilities:
    - Node registry and health monitoring
    - Task routing and load balancing
    - Network topology tracking
    - Failover and recovery
    - Integration with privacy layer (onion routing)
    """

    @abstractmethod
    async def register_node(self, node: FogNode) -> bool:
        """
        Register a new fog node in the network.

        Args:
            node: FogNode instance with capabilities and metadata

        Returns:
            True if registration successful, False otherwise
        """
        pass

    @abstractmethod
    async def unregister_node(self, node_id: str) -> bool:
        """
        Remove a fog node from the network.

        Args:
            node_id: Unique identifier of the node

        Returns:
            True if unregistration successful, False otherwise
        """
        pass

    @abstractmethod
    async def update_node_status(self, node_id: str, status: NodeStatus) -> bool:
        """
        Update the status of a fog node.

        Args:
            node_id: Unique identifier of the node
            status: New NodeStatus

        Returns:
            True if update successful, False otherwise
        """
        pass

    @abstractmethod
    async def get_node(self, node_id: str) -> Optional[FogNode]:
        """
        Retrieve information about a specific node.

        Args:
            node_id: Unique identifier of the node

        Returns:
            FogNode instance if found, None otherwise
        """
        pass

    @abstractmethod
    async def list_nodes(
        self,
        status: Optional[NodeStatus] = None,
        node_type: Optional[NodeType] = None
    ) -> list[FogNode]:
        """
        List all nodes, optionally filtered by status and type.

        Args:
            status: Filter by NodeStatus (optional)
            node_type: Filter by NodeType (optional)

        Returns:
            List of FogNode instances
        """
        pass

    @abstractmethod
    async def route_task(
        self,
        task: Task,
        strategy: RoutingStrategy = RoutingStrategy.LEAST_LOADED
    ) -> Optional[FogNode]:
        """
        Select the best node for task execution.

        Args:
            task: Task to be routed
            strategy: Routing strategy to use

        Returns:
            Selected FogNode, or None if no suitable node available
        """
        pass

    @abstractmethod
    async def process_fog_request(
        self,
        request_type: str,
        request_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Process a generic fog network request.

        Args:
            request_type: Type of request (e.g., "compute_task", "query_status")
            request_data: Request payload

        Returns:
            Response dictionary with results
        """
        pass

    @abstractmethod
    async def get_topology(self) -> NetworkTopology:
        """
        Get current network topology snapshot.

        Returns:
            NetworkTopology instance with current state
        """
        pass

    @abstractmethod
    async def handle_node_failure(self, node_id: str) -> bool:
        """
        Handle a node failure event.

        Responsibilities:
        - Mark node as offline
        - Redistribute tasks from failed node
        - Update topology
        - Notify dependent services

        Args:
            node_id: ID of failed node

        Returns:
            True if failure handled successfully
        """
        pass

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """
        Perform coordinator health check.

        Returns:
            Health status dictionary
        """
        pass

    @abstractmethod
    async def start(self) -> None:
        """Start the coordinator and background tasks."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the coordinator gracefully."""
        pass
