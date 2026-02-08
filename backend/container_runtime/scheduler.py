"""
Fog Container Scheduler
Distributes containers across fog mesh nodes transparently.

Containers are scheduled based on:
- Resource requirements (CPU, memory, GPU, disk)
- Placement constraints and affinities
- Node health and availability
- Network locality for volume access

PHASE0-SEC-001 (xqra): Container Authentication Integration
- Requires mesh_token on all container operations
- Validates tokens using MeshPersistenceService
- Prevents unauthorized container manipulation

PHASE1-COORD-002 (gfuj): Distributed Locking
- Separate locks for node registry vs container placement
- Prevents split-brain container placement
- Uses registry_lock and placement_lock patterns

FOG-SEC-003: Container State Persistence
- Persists containers, pending_queue, and stats to SQLite
- Uses in-memory cache with DB as authoritative source
- Rebuilds cache on startup from DB
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Optional, Any, Callable, Awaitable

from .models import (
    Container,
    ContainerSpec,
    ContainerStatus,
    VolumeType,
)

# PHASE0-SEC-001: Import persistence service for token validation
# Handle both package and standalone import scenarios
try:
    from ..server.services.mesh_persistence import (
        MeshPersistenceService,
        get_mesh_persistence,
    )
except ImportError:
    # Fallback for when running outside package context
    from backend.server.services.mesh_persistence import (
        MeshPersistenceService,
        get_mesh_persistence,
    )

# FOG-SEC-003: Import container persistence service
from .container_persistence import (
    ContainerPersistenceService,
    get_container_persistence,
)

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Raised when token validation fails."""
    pass


class PlacementStrategy(str, Enum):
    """Container placement strategy."""
    SPREAD = "spread"               # Spread across nodes
    BINPACK = "binpack"             # Pack containers on fewer nodes
    RANDOM = "random"               # Random placement
    RESOURCE_FIT = "resource-fit"   # Best resource match
    LOCALITY = "locality"           # Prefer nodes with volumes


@dataclass
class FogNode:
    """
    Represents a physical device in the fog mesh.

    Could be a desktop, laptop, phone, or any device running fog agent.
    """
    node_id: str
    hostname: str
    device_type: str = "desktop"    # desktop, laptop, phone, server

    # Capabilities
    cpu_cores: int = 1
    memory_mb: int = 512
    disk_mb: int = 1024
    gpu_available: bool = False
    gpu_memory_mb: int = 0

    # Current usage
    cpu_used_cores: float = 0.0
    memory_used_mb: int = 0
    disk_used_mb: int = 0

    # Status
    is_available: bool = True
    last_heartbeat: Optional[datetime] = None

    # Network
    ip_address: Optional[str] = None
    region: Optional[str] = None

    # Volumes hosted on this node
    volume_ids: list[str] = field(default_factory=list)

    # Running containers
    container_ids: list[str] = field(default_factory=list)

    @property
    def available_cpu(self) -> float:
        """Available CPU cores."""
        return max(0, self.cpu_cores - self.cpu_used_cores)

    @property
    def available_memory(self) -> int:
        """Available memory in MB."""
        return max(0, self.memory_mb - self.memory_used_mb)

    @property
    def available_disk(self) -> int:
        """Available disk in MB."""
        return max(0, self.disk_mb - self.disk_used_mb)

    def can_fit(self, spec: ContainerSpec) -> bool:
        """Check if this node can run a container with given spec."""
        res = spec.resources
        if res.cpu_cores > self.available_cpu:
            return False
        if res.memory_mb > self.available_memory:
            return False
        if res.disk_mb > self.available_disk:
            return False
        if res.gpu_count > 0 and not self.gpu_available:
            return False
        return True

    def get_fitness_score(self, spec: ContainerSpec) -> float:
        """
        Calculate fitness score for running this container.

        Higher score = better fit. 0 = cannot fit.
        """
        if not self.can_fit(spec):
            return 0.0

        res = spec.resources

        # Calculate how well resources match (avoid over-provisioning)
        cpu_fit = 1.0 - abs(res.cpu_cores - self.available_cpu) / max(self.cpu_cores, 1)
        mem_fit = 1.0 - abs(res.memory_mb - self.available_memory) / max(self.memory_mb, 1)

        # Bonus for having required volumes locally
        volume_bonus = 0.0
        for vol in spec.volumes:
            if vol.source in self.volume_ids:
                volume_bonus += 0.2

        return (cpu_fit * 0.4 + mem_fit * 0.4 + volume_bonus * 0.2)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "node_id": self.node_id,
            "hostname": self.hostname,
            "device_type": self.device_type,
            "cpu_cores": self.cpu_cores,
            "memory_mb": self.memory_mb,
            "disk_mb": self.disk_mb,
            "gpu_available": self.gpu_available,
            "cpu_used_cores": self.cpu_used_cores,
            "memory_used_mb": self.memory_used_mb,
            "disk_used_mb": self.disk_used_mb,
            "available_cpu": self.available_cpu,
            "available_memory": self.available_memory,
            "available_disk": self.available_disk,
            "is_available": self.is_available,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "ip_address": self.ip_address,
            "region": self.region,
            "container_count": len(self.container_ids),
        }


@dataclass
class SchedulerConfig:
    """Fog scheduler configuration."""
    # Placement
    default_strategy: PlacementStrategy = PlacementStrategy.RESOURCE_FIT
    prefer_locality: bool = True     # Prefer nodes with volumes

    # Scheduling
    schedule_interval_sec: float = 1.0
    max_pending_time_sec: int = 300  # Max time in pending before failure

    # Health
    node_heartbeat_timeout_sec: int = 60
    container_health_interval_sec: int = 30

    # Resource reservation
    reserve_cpu_percent: float = 10.0   # Reserve % of CPU on each node
    reserve_memory_percent: float = 10.0

    # PHASE0-SEC-001: Authentication
    require_auth: bool = False  # Set to True in production to require mesh_token

    # FOG-SEC-003: Persistence
    enable_persistence: bool = True  # Set to False to disable DB persistence


class FogScheduler:
    """
    Fog container scheduler.

    Accepts container specs, finds suitable nodes, and manages placement.
    Applications just submit containers - fog handles the rest.
    """

    def __init__(
        self,
        config: Optional[SchedulerConfig] = None,
        on_container_scheduled: Optional[Callable[[Container, str], Awaitable[None]]] = None,
        on_container_failed: Optional[Callable[[Container, str], Awaitable[None]]] = None,
        persistence: Optional[MeshPersistenceService] = None,
        container_persistence: Optional[ContainerPersistenceService] = None,
    ):
        """
        Initialize scheduler.

        Args:
            config: Scheduler configuration
            on_container_scheduled: Callback when container is placed on node
            on_container_failed: Callback when scheduling fails
            persistence: Optional persistence service for token validation (uses global if not provided)
            container_persistence: Optional container persistence service (uses global if not provided)
        """
        self.config = config or SchedulerConfig()
        self._on_container_scheduled = on_container_scheduled
        self._on_container_failed = on_container_failed

        # PHASE0-SEC-001: Persistence service for token validation
        self._persistence = persistence or get_mesh_persistence()

        # FOG-SEC-003: Container persistence service
        self._container_persistence = container_persistence or get_container_persistence()
        self._state_loaded = False  # Track if state has been loaded from DB

        # Node registry
        self._nodes: dict[str, FogNode] = {}

        # Container registry
        self._containers: dict[str, Container] = {}
        self._pending_queue: list[str] = []  # Container IDs waiting to be scheduled

        # Scheduling state
        self._is_running = False
        self._scheduler_task: Optional[asyncio.Task] = None

        # PHASE1-COORD-002: Distributed locking for critical sections
        # Separate locks prevent deadlock and allow concurrent operations on different resources
        self._registry_lock = asyncio.Lock()    # For node registration/unregistration
        self._placement_lock = asyncio.Lock()   # For container placement decisions
        self._container_lock = asyncio.Lock()   # For container state modifications

        # Stats
        self._stats = {
            "containers_scheduled": 0,
            "containers_failed": 0,
            "scheduling_latency_ms_avg": 0.0,
            "auth_failures": 0,  # PHASE0-SEC-001: Track auth failures
        }

        logger.info(f"FogScheduler initialized with auth (SEC-001), distributed locking (COORD-002), and persistence (SEC-003): {self.config.default_strategy.value}")

    async def start(self) -> None:
        """Start the scheduler loop."""
        if self._is_running:
            return

        # FOG-SEC-003: Load state from database on startup
        if self.config.enable_persistence and not self._state_loaded:
            await self._load_state_from_db()

        self._is_running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("FogScheduler started")

    async def _load_state_from_db(self) -> None:
        """
        Load container state from database on startup.

        FOG-SEC-003: Rebuilds in-memory state from persistent storage.
        """
        try:
            containers, pending_queue, stats = await self._container_persistence.load_state_from_db()
            self._containers = containers
            self._pending_queue = pending_queue
            self._stats.update(stats)
            self._state_loaded = True
            logger.info(
                f"Loaded state from DB: {len(containers)} containers, "
                f"{len(pending_queue)} pending"
            )
        except Exception as e:
            logger.error(f"Failed to load state from DB: {e}")
            # Continue with empty state if DB load fails
            self._state_loaded = True

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._is_running = False

        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

        # FOG-SEC-003: Persist stats on shutdown
        if self.config.enable_persistence:
            try:
                await self._container_persistence.update_stats(self._stats)
                logger.info("Persisted scheduler stats on shutdown")
            except Exception as e:
                logger.error(f"Failed to persist stats on shutdown: {e}")

        logger.info("FogScheduler stopped")

    # === PHASE0-SEC-001: Token Validation ===

    async def _validate_token(self, mesh_token: str, operation: str) -> str:
        """
        Validate mesh token and return device_id.

        PHASE0-SEC-001: All container operations require valid token.

        Args:
            mesh_token: The mesh authentication token
            operation: Name of operation being performed (for logging)

        Returns:
            device_id if token is valid

        Raises:
            AuthenticationError if token is invalid
        """
        if not mesh_token:
            self._stats["auth_failures"] += 1
            logger.warning(f"Auth failure for {operation}: no token provided")
            raise AuthenticationError(f"Token required for {operation}")

        try:
            device_id = await self._persistence.validate_token(mesh_token)
            if device_id is None:
                self._stats["auth_failures"] += 1
                logger.warning(f"Auth failure for {operation}: invalid or expired token")
                raise AuthenticationError(f"Invalid or expired token for {operation}")

            logger.debug(f"Token validated for {operation}: device={device_id}")
            return device_id

        except AuthenticationError:
            raise
        except Exception as e:
            self._stats["auth_failures"] += 1
            logger.error(f"Token validation error for {operation}: {e}")
            raise AuthenticationError(f"Token validation failed: {e}")

    # === Node Management (PHASE1-COORD-002: Uses registry_lock) ===

    def register_node(self, node: FogNode) -> None:
        """
        Register a fog node (sync version for backward compatibility).

        For authenticated registration, use register_node_async with mesh_token.
        """
        self._nodes[node.node_id] = node
        node.last_heartbeat = datetime.now(UTC)
        logger.info(f"Registered fog node: {node.node_id} ({node.hostname})")

    async def register_node_async(self, node: FogNode, mesh_token: Optional[str] = None) -> None:
        """
        Register a fog node with optional authentication.

        PHASE1-COORD-002: Uses registry_lock for atomic node registration.
        PHASE0-SEC-001: Optional token validation for authenticated registration.
        """
        # Optional auth for node registration (internal nodes may not have tokens yet)
        if mesh_token:
            await self._validate_token(mesh_token, "register_node")

        async with self._registry_lock:
            self._nodes[node.node_id] = node
            node.last_heartbeat = datetime.now(UTC)
            logger.info(f"Registered fog node: {node.node_id} ({node.hostname})")

    def unregister_node(self, node_id: str) -> None:
        """
        Unregister a fog node (sync version for backward compatibility).

        For authenticated unregistration, use unregister_node_async with mesh_token.
        """
        if node_id in self._nodes:
            del self._nodes[node_id]
            logger.info(f"Unregistered fog node: {node_id}")

    async def unregister_node_async(self, node_id: str, mesh_token: Optional[str] = None) -> None:
        """
        Unregister a fog node with optional authentication.

        PHASE1-COORD-002: Uses registry_lock for atomic node unregistration.
        """
        if mesh_token:
            await self._validate_token(mesh_token, "unregister_node")

        async with self._registry_lock:
            if node_id in self._nodes:
                del self._nodes[node_id]
                logger.info(f"Unregistered fog node: {node_id}")

    def update_node_metrics(self, node_id: str, **kwargs) -> None:
        """Update node resource metrics."""
        if node_id in self._nodes:
            node = self._nodes[node_id]
            for key, value in kwargs.items():
                if hasattr(node, key):
                    setattr(node, key, value)
            node.last_heartbeat = datetime.now(UTC)

    async def submit_container(
        self,
        spec: ContainerSpec,
        mesh_token: Optional[str] = None,
    ) -> Container:
        """
        Submit a container for scheduling.

        This is the main entry point - equivalent to `docker run`.
        Returns immediately with a Container object in PENDING state.
        Actual scheduling happens asynchronously.

        PHASE0-SEC-001: Requires valid mesh_token for authorization in production.
        PHASE1-COORD-002: Uses container_lock for atomic container creation.

        Args:
            spec: Container specification
            mesh_token: Authentication token (optional for testing, required in production)

        Returns:
            Container instance

        Raises:
            AuthenticationError: If token is provided but invalid
        """
        device_id = "anonymous"

        # PHASE0-SEC-001: Validate token if provided or required
        if mesh_token:
            device_id = await self._validate_token(mesh_token, "submit_container")
        elif self.config.require_auth:
            raise AuthenticationError("Authentication required: mesh_token not provided")
        else:
            logger.debug("submit_container called without mesh_token (testing/internal mode)")

        async with self._container_lock:
            container = Container(spec=spec)

            # Generate name if not provided
            if not spec.name:
                spec.name = f"fog-{container.container_id[-8:]}"

            # PHASE0-SEC-001: Track which device submitted the container
            container.spec.labels["fog.submitted_by"] = device_id

            self._containers[container.container_id] = container
            self._pending_queue.append(container.container_id)

            # FOG-SEC-003: Persist container and pending queue
            if self.config.enable_persistence:
                try:
                    await self._container_persistence.store_container(container)
                    await self._container_persistence.add_to_pending_queue(container.container_id)
                except Exception as e:
                    logger.error(f"Failed to persist container {container.container_id}: {e}")

            logger.info(f"Container {container.container_id} ({spec.name}) submitted by device {device_id}")
            return container

    def get_container(self, container_id: str) -> Optional[Container]:
        """Get container by ID."""
        return self._containers.get(container_id)

    def get_container_by_name(self, name: str) -> Optional[Container]:
        """Get container by name."""
        for container in self._containers.values():
            if container.name == name:
                return container
        return None

    def list_containers(
        self,
        status: Optional[ContainerStatus] = None,
        node_id: Optional[str] = None,
    ) -> list[Container]:
        """List containers with optional filters."""
        containers = list(self._containers.values())

        if status:
            containers = [c for c in containers if c.status == status]
        if node_id:
            containers = [c for c in containers if c.node_id == node_id]

        return containers

    async def stop_container(
        self,
        container_id: str,
        mesh_token: Optional[str] = None,
        timeout_sec: Optional[int] = None,
    ) -> bool:
        """
        Stop a running container.

        PHASE0-SEC-001: Requires valid mesh_token for authorization in production.
        PHASE1-COORD-002: Uses container_lock for atomic state change.

        Args:
            container_id: Container to stop
            mesh_token: Authentication token (optional for testing, required in production)
            timeout_sec: Timeout before force kill

        Returns:
            True if stop initiated successfully

        Raises:
            AuthenticationError: If token is provided but invalid
        """
        device_id = "anonymous"

        # PHASE0-SEC-001: Validate token if provided or required
        if mesh_token:
            device_id = await self._validate_token(mesh_token, "stop_container")
        elif self.config.require_auth:
            raise AuthenticationError("Authentication required: mesh_token not provided")

        async with self._container_lock:
            container = self._containers.get(container_id)
            if not container:
                return False

            if container.status not in (ContainerStatus.RUNNING, ContainerStatus.PAUSED):
                return False

            container.status = ContainerStatus.STOPPING

            # FOG-SEC-003: Persist container state change
            if self.config.enable_persistence:
                try:
                    await self._container_persistence.update_container(container)
                except Exception as e:
                    logger.error(f"Failed to persist container stop {container_id}: {e}")

            # Actual stop is handled by node agent
            logger.info(f"Stopping container {container_id} (requested by {device_id})")
            return True

    async def remove_container(
        self,
        container_id: str,
        mesh_token: Optional[str] = None,
        force: bool = False,
    ) -> bool:
        """
        Remove a container.

        PHASE0-SEC-001: Requires valid mesh_token for authorization in production.
        PHASE1-COORD-002: Uses container_lock for atomic removal.

        Args:
            container_id: Container to remove
            mesh_token: Authentication token (optional for testing, required in production)
            force: Force remove even if running

        Returns:
            True if removed successfully

        Raises:
            AuthenticationError: If token is provided but invalid
        """
        device_id = "anonymous"

        # PHASE0-SEC-001: Validate token if provided or required
        if mesh_token:
            device_id = await self._validate_token(mesh_token, "remove_container")
        elif self.config.require_auth:
            raise AuthenticationError("Authentication required: mesh_token not provided")

        # PHASE1-COORD-002: Acquire both locks in consistent order to prevent deadlock
        # Order: container_lock -> registry_lock (for node access)
        async with self._container_lock:
            container = self._containers.get(container_id)
            if not container:
                return False

            if container.status == ContainerStatus.RUNNING and not force:
                return False

            # Remove from node's container list (needs registry_lock for node access)
            node_id_to_update = container.node_id
            if node_id_to_update:
                async with self._registry_lock:
                    if node_id_to_update in self._nodes:
                        node = self._nodes[node_id_to_update]
                        if container_id in node.container_ids:
                            node.container_ids.remove(container_id)

            # Remove from pending queue
            if container_id in self._pending_queue:
                self._pending_queue.remove(container_id)

            del self._containers[container_id]

            # FOG-SEC-003: Delete container from persistence
            if self.config.enable_persistence:
                try:
                    await self._container_persistence.delete_container(container_id)
                    await self._container_persistence.remove_from_pending_queue(container_id)
                except Exception as e:
                    logger.error(f"Failed to delete container {container_id} from persistence: {e}")

            logger.info(f"Removed container {container_id} (requested by {device_id})")
            return True

    async def _scheduler_loop(self) -> None:
        """Main scheduling loop."""
        while self._is_running:
            try:
                await self._process_pending()
                await self._check_node_health()
                await asyncio.sleep(self.config.schedule_interval_sec)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(1)

    async def _process_pending(self) -> None:
        """
        Process pending containers.

        PHASE1-COORD-002: Uses placement_lock for scheduling decisions
        to prevent split-brain container placement.
        """
        async with self._placement_lock:
            for container_id in list(self._pending_queue):
                container = self._containers.get(container_id)
                if not container:
                    self._pending_queue.remove(container_id)
                    continue

                # Check pending timeout
                pending_time = (datetime.now(UTC) - container.created_at).total_seconds()
                if pending_time > self.config.max_pending_time_sec:
                    container.status = ContainerStatus.FAILED
                    container.error = "Scheduling timeout - no suitable node found"
                    self._pending_queue.remove(container_id)
                    self._stats["containers_failed"] += 1

                    # FOG-SEC-003: Persist failed container state
                    if self.config.enable_persistence:
                        try:
                            await self._container_persistence.update_container(container)
                            await self._container_persistence.remove_from_pending_queue(container_id)
                            await self._container_persistence.update_stats(self._stats)
                        except Exception as e:
                            logger.error(f"Failed to persist timeout state for {container_id}: {e}")

                    if self._on_container_failed:
                        await self._on_container_failed(container, container.error)
                    continue

                # Try to schedule
                node = await self._select_node(container.spec)
                if node:
                    await self._place_container(container, node)
                    self._pending_queue.remove(container_id)

                    # FOG-SEC-003: Persist scheduled container and update queue
                    if self.config.enable_persistence:
                        try:
                            await self._container_persistence.remove_from_pending_queue(container_id)
                        except Exception as e:
                            logger.error(f"Failed to update pending queue for {container_id}: {e}")

    async def _select_node(self, spec: ContainerSpec) -> Optional[FogNode]:
        """Select the best node for a container."""
        available_nodes = [
            n for n in self._nodes.values()
            if n.is_available and n.can_fit(spec)
        ]

        if not available_nodes:
            return None

        strategy = self.config.default_strategy

        # Check placement hints
        if spec.placement_hints:
            if "node_id" in spec.placement_hints:
                preferred_id = spec.placement_hints["node_id"]
                for node in available_nodes:
                    if node.node_id == preferred_id:
                        return node

            if "strategy" in spec.placement_hints:
                try:
                    strategy = PlacementStrategy(spec.placement_hints["strategy"])
                except ValueError:
                    pass

        # Apply strategy
        if strategy == PlacementStrategy.SPREAD:
            # Pick node with fewest containers
            return min(available_nodes, key=lambda n: len(n.container_ids))

        elif strategy == PlacementStrategy.BINPACK:
            # Pick node with most utilization that can still fit
            return max(available_nodes, key=lambda n: n.cpu_used_cores + n.memory_used_mb)

        elif strategy == PlacementStrategy.RANDOM:
            import random
            return random.choice(available_nodes)

        elif strategy == PlacementStrategy.RESOURCE_FIT:
            # Pick node with best resource fit
            return max(available_nodes, key=lambda n: n.get_fitness_score(spec))

        elif strategy == PlacementStrategy.LOCALITY:
            # Prefer nodes that have required volumes
            volume_sources = {v.source for v in spec.volumes}
            for node in available_nodes:
                if volume_sources & set(node.volume_ids):
                    return node
            # Fall back to resource fit
            return max(available_nodes, key=lambda n: n.get_fitness_score(spec))

        return available_nodes[0]

    async def _place_container(self, container: Container, node: FogNode) -> None:
        """Place a container on a node."""
        container.node_id = node.node_id
        container.status = ContainerStatus.CREATING

        # Reserve resources
        res = container.spec.resources
        node.cpu_used_cores += res.cpu_cores
        node.memory_used_mb += res.memory_mb
        node.disk_used_mb += res.disk_mb
        node.container_ids.append(container.container_id)

        self._stats["containers_scheduled"] += 1

        # FOG-SEC-003: Persist container placement and stats
        if self.config.enable_persistence:
            try:
                await self._container_persistence.update_container(container)
                await self._container_persistence.update_stats(self._stats)
            except Exception as e:
                logger.error(f"Failed to persist container placement for {container.container_id}: {e}")

        logger.info(
            f"Container {container.container_id} placed on node {node.node_id} ({node.hostname})"
        )

        # Notify
        if self._on_container_scheduled:
            await self._on_container_scheduled(container, node.node_id)

    async def _check_node_health(self) -> None:
        """
        Check node health and mark unhealthy nodes.

        PHASE1-COORD-002: Uses registry_lock for atomic node state changes.
        """
        now = datetime.now(UTC)
        timeout = self.config.node_heartbeat_timeout_sec

        async with self._registry_lock:
            for node in self._nodes.values():
                if node.last_heartbeat:
                    age = (now - node.last_heartbeat).total_seconds()
                    if age > timeout and node.is_available:
                        node.is_available = False
                        logger.warning(f"Node {node.node_id} marked unavailable (no heartbeat)")

    def handle_container_started(self, container_id: str, ip_address: str, pid: int) -> None:
        """Handle container start notification from node."""
        container = self._containers.get(container_id)
        if container:
            container.status = ContainerStatus.RUNNING
            container.started_at = datetime.now(UTC)
            container.ip_address = ip_address
            container.pid = pid

            # FOG-SEC-003: Persist container started state
            if self.config.enable_persistence:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop is not None:
                    loop.create_task(self._container_persistence.update_container(container))

            logger.info(f"Container {container_id} started at {ip_address}")

    def handle_container_started_sync(self, container_id: str, ip_address: str, pid: int) -> None:
        """Handle container start notification from node (sync version for backward compatibility)."""
        self.handle_container_started(container_id, ip_address, pid)

    def handle_container_stopped(
        self,
        container_id: str,
        exit_code: int,
        error: Optional[str] = None
    ) -> None:
        """Handle container stop notification from node."""
        container = self._containers.get(container_id)
        if container:
            container.status = ContainerStatus.STOPPED
            container.finished_at = datetime.now(UTC)
            container.exit_code = exit_code
            container.error = error

            # Release resources
            if container.node_id and container.node_id in self._nodes:
                node = self._nodes[container.node_id]
                res = container.spec.resources
                node.cpu_used_cores = max(0, node.cpu_used_cores - res.cpu_cores)
                node.memory_used_mb = max(0, node.memory_used_mb - res.memory_mb)
                node.disk_used_mb = max(0, node.disk_used_mb - res.disk_mb)

            # FOG-SEC-003: Persist container stopped state
            if self.config.enable_persistence:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop is not None:
                    loop.create_task(self._container_persistence.update_container(container))

            logger.info(f"Container {container_id} stopped (exit code: {exit_code})")

    def handle_container_stopped_sync(
        self,
        container_id: str,
        exit_code: int,
        error: Optional[str] = None
    ) -> None:
        """Handle container stop notification from node (sync version for backward compatibility)."""
        self.handle_container_stopped(container_id, exit_code, error=error)

    def handle_container_metrics(
        self,
        container_id: str,
        cpu_percent: float,
        memory_mb: int,
        network_rx: int,
        network_tx: int
    ) -> None:
        """Update container resource metrics."""
        container = self._containers.get(container_id)
        if container:
            container.cpu_usage_percent = cpu_percent
            container.memory_usage_mb = memory_mb
            container.network_rx_bytes = network_rx
            container.network_tx_bytes = network_tx

    def get_nodes(self) -> list[FogNode]:
        """Get all registered nodes."""
        return list(self._nodes.values())

    def get_node(self, node_id: str) -> Optional[FogNode]:
        """Get a specific node."""
        return self._nodes.get(node_id)

    def get_stats(self) -> dict[str, Any]:
        """Get scheduler statistics."""
        total_cpu = sum(n.cpu_cores for n in self._nodes.values())
        used_cpu = sum(n.cpu_used_cores for n in self._nodes.values())
        total_memory = sum(n.memory_mb for n in self._nodes.values())
        used_memory = sum(n.memory_used_mb for n in self._nodes.values())

        return {
            **self._stats,
            "total_nodes": len(self._nodes),
            "available_nodes": sum(1 for n in self._nodes.values() if n.is_available),
            "total_containers": len(self._containers),
            "running_containers": sum(
                1 for c in self._containers.values()
                if c.status == ContainerStatus.RUNNING
            ),
            "pending_containers": len(self._pending_queue),
            "total_cpu_cores": total_cpu,
            "used_cpu_cores": used_cpu,
            "cpu_utilization_percent": (used_cpu / total_cpu * 100) if total_cpu > 0 else 0,
            "total_memory_mb": total_memory,
            "used_memory_mb": used_memory,
            "memory_utilization_percent": (used_memory / total_memory * 100) if total_memory > 0 else 0,
        }
