"""
Distributed Volume Manager
Handles volume storage across fog mesh nodes.

Volumes appear as normal Docker volumes to containers,
but fog runtime handles replication and cross-node access transparently.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Optional, Any, Callable, Awaitable
from uuid import uuid4

from .models import Volume, VolumeType, VolumeMount

logger = logging.getLogger(__name__)


@dataclass
class VolumeConfig:
    """Volume manager configuration."""
    # Replication
    default_replication_factor: int = 2  # Number of replicas for distributed volumes
    sync_interval_sec: float = 5.0       # Sync interval for replicas

    # Storage
    default_size_mb: int = 1024          # Default volume size
    max_volume_size_mb: int = 102400     # Max 100GB per volume

    # Consistency
    default_consistency: str = "eventual"  # eventual or strong
    sync_timeout_sec: int = 30


@dataclass
class VolumeReplica:
    """Represents a volume replica on a node."""
    replica_id: str = field(default_factory=lambda: f"rep-{uuid4().hex[:8]}")
    volume_id: str = ""
    node_id: str = ""
    is_primary: bool = False

    # Sync state
    last_sync: Optional[datetime] = None
    sync_status: str = "pending"  # pending, syncing, synced, error
    sync_error: Optional[str] = None

    # Storage path on node
    local_path: Optional[str] = None
    used_mb: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "replica_id": self.replica_id,
            "volume_id": self.volume_id,
            "node_id": self.node_id,
            "is_primary": self.is_primary,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "sync_status": self.sync_status,
            "sync_error": self.sync_error,
            "local_path": self.local_path,
            "used_mb": self.used_mb,
        }


class DistributedVolumeManager:
    """
    Manages volumes across fog mesh.

    Features:
    - Local volumes (single node)
    - Distributed volumes (replicated across nodes)
    - Shared volumes (primary + network access)
    - Automatic replication and sync
    """

    def __init__(
        self,
        config: Optional[VolumeConfig] = None,
        on_volume_ready: Optional[Callable[[Volume], Awaitable[None]]] = None,
        on_sync_complete: Optional[Callable[[str, str], Awaitable[None]]] = None,
    ):
        """
        Initialize volume manager.

        Args:
            config: Volume configuration
            on_volume_ready: Callback when volume is ready for use
            on_sync_complete: Callback when replica sync completes (volume_id, node_id)
        """
        self.config = config or VolumeConfig()
        self._on_volume_ready = on_volume_ready
        self._on_sync_complete = on_sync_complete

        # Volume storage
        self._volumes: dict[str, Volume] = {}
        self._replicas: dict[str, list[VolumeReplica]] = {}  # volume_id -> replicas

        # Node storage capacity tracking
        self._node_storage: dict[str, dict[str, int]] = {}  # node_id -> {total_mb, used_mb}

        # Sync state
        self._is_running = False
        self._sync_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

        # Stats
        self._stats = {
            "volumes_created": 0,
            "volumes_deleted": 0,
            "total_replicas": 0,
            "sync_operations": 0,
            "sync_errors": 0,
        }

        logger.info("DistributedVolumeManager initialized")

    async def start(self) -> None:
        """Start the volume sync loop."""
        if self._is_running:
            return

        self._is_running = True
        self._sync_task = asyncio.create_task(self._sync_loop())
        logger.info("DistributedVolumeManager started")

    async def stop(self) -> None:
        """Stop the volume manager."""
        self._is_running = False

        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass

        logger.info("DistributedVolumeManager stopped")

    def register_node_storage(self, node_id: str, total_mb: int, used_mb: int = 0) -> None:
        """Register storage capacity for a node."""
        self._node_storage[node_id] = {
            "total_mb": total_mb,
            "used_mb": used_mb,
        }
        logger.debug(f"Registered storage for node {node_id}: {total_mb}MB total")

    def update_node_storage(self, node_id: str, used_mb: int) -> None:
        """Update node storage usage."""
        if node_id in self._node_storage:
            self._node_storage[node_id]["used_mb"] = used_mb

    async def create_volume(
        self,
        name: str,
        volume_type: VolumeType = VolumeType.LOCAL,
        size_mb: Optional[int] = None,
        replication_factor: Optional[int] = None,
        consistency_mode: Optional[str] = None,
        labels: Optional[dict[str, str]] = None,
        preferred_node_id: Optional[str] = None,
    ) -> Volume:
        """
        Create a new volume.

        Args:
            name: Volume name (must be unique)
            volume_type: Type of volume (local, distributed, shared)
            size_mb: Volume size in MB
            replication_factor: Number of replicas (for distributed)
            consistency_mode: eventual or strong
            labels: Volume labels/metadata
            preferred_node_id: Preferred primary node

        Returns:
            Created Volume
        """
        async with self._lock:
            # Check name uniqueness
            for vol in self._volumes.values():
                if vol.name == name:
                    raise ValueError(f"Volume with name '{name}' already exists")

            volume = Volume(
                name=name,
                volume_type=volume_type,
                size_mb=size_mb or self.config.default_size_mb,
                replication_factor=replication_factor or self.config.default_replication_factor,
                consistency_mode=consistency_mode or self.config.default_consistency,
                labels=labels or {},
            )

            # For local volumes, replication factor is always 1
            if volume_type == VolumeType.LOCAL:
                volume.replication_factor = 1

            self._volumes[volume.volume_id] = volume
            self._replicas[volume.volume_id] = []
            self._stats["volumes_created"] += 1

            logger.info(f"Created volume {volume.volume_id} ({name}): {volume_type.value}")

            # Create initial replica(s)
            await self._create_replicas(volume, preferred_node_id)

            return volume

    async def _create_replicas(
        self,
        volume: Volume,
        preferred_node_id: Optional[str] = None
    ) -> None:
        """Create volume replicas on appropriate nodes."""
        # Select nodes for replicas
        nodes = self._select_nodes_for_replicas(
            volume.size_mb,
            volume.replication_factor,
            preferred_node_id
        )

        if not nodes:
            volume.error = "No nodes available for volume storage"
            logger.warning(f"No nodes available for volume {volume.volume_id}")
            return

        # Create replicas
        for i, node_id in enumerate(nodes):
            replica = VolumeReplica(
                volume_id=volume.volume_id,
                node_id=node_id,
                is_primary=(i == 0),
            )
            self._replicas[volume.volume_id].append(replica)
            self._stats["total_replicas"] += 1

            if replica.is_primary:
                volume.primary_node_id = node_id
            else:
                volume.replica_node_ids.append(node_id)

            # Reserve storage on node
            if node_id in self._node_storage:
                self._node_storage[node_id]["used_mb"] += volume.size_mb

        volume.is_ready = True
        logger.info(
            f"Volume {volume.volume_id} ready with {len(nodes)} replica(s) "
            f"on nodes: {nodes}"
        )

        if self._on_volume_ready:
            await self._on_volume_ready(volume)

    def _select_nodes_for_replicas(
        self,
        size_mb: int,
        count: int,
        preferred_node_id: Optional[str] = None
    ) -> list[str]:
        """Select nodes for volume replicas."""
        selected: list[str] = []

        # Filter nodes with enough space
        available = [
            (node_id, storage)
            for node_id, storage in self._node_storage.items()
            if storage["total_mb"] - storage["used_mb"] >= size_mb
        ]

        if not available:
            return []

        # Sort by available space (most space first)
        available.sort(key=lambda x: x[1]["total_mb"] - x[1]["used_mb"], reverse=True)

        # Add preferred node first if it has space
        if preferred_node_id:
            for node_id, storage in available:
                if node_id == preferred_node_id:
                    selected.append(node_id)
                    available = [(n, s) for n, s in available if n != node_id]
                    break

        # Add remaining nodes
        for node_id, _ in available:
            if len(selected) >= count:
                break
            if node_id not in selected:
                selected.append(node_id)

        return selected

    def get_volume(self, volume_id: str) -> Optional[Volume]:
        """Get volume by ID."""
        return self._volumes.get(volume_id)

    def get_volume_by_name(self, name: str) -> Optional[Volume]:
        """Get volume by name."""
        for volume in self._volumes.values():
            if volume.name == name:
                return volume
        return None

    def list_volumes(
        self,
        volume_type: Optional[VolumeType] = None,
        node_id: Optional[str] = None,
    ) -> list[Volume]:
        """List volumes with optional filters."""
        volumes = list(self._volumes.values())

        if volume_type:
            volumes = [v for v in volumes if v.volume_type == volume_type]

        if node_id:
            volumes = [
                v for v in volumes
                if v.primary_node_id == node_id or node_id in v.replica_node_ids
            ]

        return volumes

    async def delete_volume(self, volume_id: str, force: bool = False) -> bool:
        """
        Delete a volume.

        Args:
            volume_id: Volume to delete
            force: Force delete even if in use

        Returns:
            True if deleted successfully
        """
        async with self._lock:
            volume = self._volumes.get(volume_id)
            if not volume:
                return False

            # Release storage on nodes
            for replica in self._replicas.get(volume_id, []):
                if replica.node_id in self._node_storage:
                    self._node_storage[replica.node_id]["used_mb"] -= volume.size_mb
                    self._node_storage[replica.node_id]["used_mb"] = max(
                        0, self._node_storage[replica.node_id]["used_mb"]
                    )

            # Clean up
            del self._volumes[volume_id]
            if volume_id in self._replicas:
                del self._replicas[volume_id]

            self._stats["volumes_deleted"] += 1
            logger.info(f"Deleted volume {volume_id}")
            return True

    async def resize_volume(self, volume_id: str, new_size_mb: int) -> bool:
        """Resize a volume."""
        async with self._lock:
            volume = self._volumes.get(volume_id)
            if not volume:
                return False

            if new_size_mb > self.config.max_volume_size_mb:
                return False

            # Check nodes have space for increase
            size_diff = new_size_mb - volume.size_mb
            if size_diff > 0:
                for replica in self._replicas.get(volume_id, []):
                    if replica.node_id in self._node_storage:
                        storage = self._node_storage[replica.node_id]
                        available = storage["total_mb"] - storage["used_mb"]
                        if available < size_diff:
                            return False

                # Reserve additional space
                for replica in self._replicas.get(volume_id, []):
                    if replica.node_id in self._node_storage:
                        self._node_storage[replica.node_id]["used_mb"] += size_diff

            elif size_diff < 0:
                # Release space
                for replica in self._replicas.get(volume_id, []):
                    if replica.node_id in self._node_storage:
                        self._node_storage[replica.node_id]["used_mb"] += size_diff

            volume.size_mb = new_size_mb
            logger.info(f"Resized volume {volume_id} to {new_size_mb}MB")
            return True

    def get_mount_path(self, volume_id: str, node_id: str) -> Optional[str]:
        """Get the local mount path for a volume on a specific node."""
        replicas = self._replicas.get(volume_id, [])
        for replica in replicas:
            if replica.node_id == node_id:
                return replica.local_path

        # Volume not on this node - need network mount
        return None

    def resolve_volume_mount(
        self,
        mount: VolumeMount,
        container_node_id: str
    ) -> dict[str, Any]:
        """
        Resolve a volume mount for a container.

        Returns mount configuration for the node agent to use.
        """
        volume = self.get_volume_by_name(mount.source)
        if not volume:
            # Might be a host path bind mount
            return {
                "type": "bind",
                "source": mount.source,
                "target": mount.target,
                "read_only": mount.read_only,
            }

        # Check if volume has replica on container's node
        local_path = self.get_mount_path(volume.volume_id, container_node_id)

        if local_path:
            # Volume is local to container's node
            return {
                "type": "volume",
                "volume_id": volume.volume_id,
                "source": local_path,
                "target": mount.target,
                "read_only": mount.read_only,
                "is_local": True,
            }
        else:
            # Need network mount from primary node
            return {
                "type": "volume",
                "volume_id": volume.volume_id,
                "source": volume.primary_node_id,
                "target": mount.target,
                "read_only": mount.read_only,
                "is_local": False,
                "network_mount": True,
                "primary_node": volume.primary_node_id,
            }

    async def _sync_loop(self) -> None:
        """Background loop for syncing distributed volumes."""
        while self._is_running:
            try:
                await self._sync_replicas()
                await asyncio.sleep(self.config.sync_interval_sec)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Sync loop error: {e}")
                await asyncio.sleep(1)

    async def _sync_replicas(self) -> None:
        """Sync all distributed volume replicas."""
        for volume_id, replicas in self._replicas.items():
            volume = self._volumes.get(volume_id)
            if not volume or volume.volume_type == VolumeType.LOCAL:
                continue

            # Find primary replica
            primary = next((r for r in replicas if r.is_primary), None)
            if not primary:
                continue

            # Sync each non-primary replica
            for replica in replicas:
                if replica.is_primary:
                    continue

                # Check if sync needed (based on last sync time)
                if replica.sync_status == "synced":
                    if replica.last_sync:
                        age = (datetime.now(UTC) - replica.last_sync).total_seconds()
                        if age < self.config.sync_interval_sec * 2:
                            continue

                # Mark as syncing
                replica.sync_status = "syncing"
                self._stats["sync_operations"] += 1

                # Actual sync would be done by node agents
                # Here we just track the state
                replica.last_sync = datetime.now(UTC)
                replica.sync_status = "synced"

                if self._on_sync_complete:
                    await self._on_sync_complete(volume_id, replica.node_id)

    def handle_replica_sync_complete(
        self,
        volume_id: str,
        node_id: str,
        used_mb: int
    ) -> None:
        """Handle sync completion notification from node."""
        replicas = self._replicas.get(volume_id, [])
        for replica in replicas:
            if replica.node_id == node_id:
                replica.sync_status = "synced"
                replica.last_sync = datetime.now(UTC)
                replica.used_mb = used_mb

                # Update volume usage
                volume = self._volumes.get(volume_id)
                if volume and replica.is_primary:
                    volume.used_mb = used_mb

                break

    def handle_replica_sync_error(
        self,
        volume_id: str,
        node_id: str,
        error: str
    ) -> None:
        """Handle sync error from node."""
        replicas = self._replicas.get(volume_id, [])
        for replica in replicas:
            if replica.node_id == node_id:
                replica.sync_status = "error"
                replica.sync_error = error
                self._stats["sync_errors"] += 1
                logger.error(f"Sync error for volume {volume_id} on node {node_id}: {error}")
                break

    def get_volume_replicas(self, volume_id: str) -> list[VolumeReplica]:
        """Get all replicas for a volume."""
        return self._replicas.get(volume_id, [])

    def get_stats(self) -> dict[str, Any]:
        """Get volume manager statistics."""
        total_storage = sum(s["total_mb"] for s in self._node_storage.values())
        used_storage = sum(s["used_mb"] for s in self._node_storage.values())

        return {
            **self._stats,
            "total_volumes": len(self._volumes),
            "local_volumes": sum(
                1 for v in self._volumes.values()
                if v.volume_type == VolumeType.LOCAL
            ),
            "distributed_volumes": sum(
                1 for v in self._volumes.values()
                if v.volume_type == VolumeType.DISTRIBUTED
            ),
            "shared_volumes": sum(
                1 for v in self._volumes.values()
                if v.volume_type == VolumeType.SHARED
            ),
            "nodes_with_storage": len(self._node_storage),
            "total_storage_mb": total_storage,
            "used_storage_mb": used_storage,
            "storage_utilization_percent": (
                used_storage / total_storage * 100 if total_storage > 0 else 0
            ),
        }
