"""
Container State Persistence Service
Database operations for container runtime state persistence.

FOG-SEC-003: Container State Persistence
- Persists containers, pending_queue, and stats to SQLite
- Uses in-memory cache with DB as authoritative source
- Rebuilds cache on startup from DB
- Follows MeshPersistenceService async patterns
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional, Any
import logging

from sqlalchemy import select, update, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

# Handle both package and standalone import scenarios
try:
    from ..server.database import AsyncSessionLocal
except ImportError:
    from backend.server.database import AsyncSessionLocal

from .models import (
    Container,
    ContainerSpec,
    ContainerStatus,
    ResourceLimits,
    VolumeMount,
    VolumeType,
    PortMapping,
    NetworkConfig,
    NetworkMode,
    HealthCheck,
    RestartPolicy,
)
from .container_models import (
    ContainerRecord,
    PendingQueueRecord,
    SchedulerStatsRecord,
)

logger = logging.getLogger(__name__)


class ContainerPersistenceService:
    """
    Async persistence service for container runtime state.

    FOG-SEC-003: Provides atomic database operations with proper error handling.
    Uses in-memory cache with DB as authoritative source.
    """

    def __init__(self):
        """Initialize persistence service with empty cache."""
        # In-memory cache (mirrors DB state)
        self._containers_cache: dict[str, Container] = {}
        self._pending_queue_cache: list[str] = []
        self._stats_cache: dict[str, Any] = {
            "containers_scheduled": 0,
            "containers_failed": 0,
            "scheduling_latency_ms_avg": 0.0,
            "auth_failures": 0,
        }
        self._cache_loaded = False

    # === Cache Rebuild (Startup) ===

    async def load_state_from_db(self) -> tuple[dict[str, Container], list[str], dict[str, Any]]:
        """
        Load all container state from database on startup.

        FOG-SEC-003: Rebuilds in-memory cache from DB (authoritative source).

        Returns:
            Tuple of (containers dict, pending_queue list, stats dict)
        """
        async with AsyncSessionLocal() as session:
            # Load containers
            containers: dict[str, Container] = {}
            result = await session.execute(select(ContainerRecord))
            for record in result.scalars().all():
                container = self._record_to_container(record)
                containers[record.container_id] = container

            # Load pending queue (ordered by position)
            pending_queue: list[str] = []
            result = await session.execute(
                select(PendingQueueRecord).order_by(PendingQueueRecord.position)
            )
            for record in result.scalars().all():
                pending_queue.append(record.container_id)

            # Load stats
            stats: dict[str, Any] = {
                "containers_scheduled": 0,
                "containers_failed": 0,
                "scheduling_latency_ms_avg": 0.0,
                "auth_failures": 0,
            }
            result = await session.execute(select(SchedulerStatsRecord))
            stats_record = result.scalar_one_or_none()
            if stats_record:
                stats = {
                    "containers_scheduled": stats_record.containers_scheduled,
                    "containers_failed": stats_record.containers_failed,
                    "scheduling_latency_ms_avg": stats_record.scheduling_latency_ms_avg,
                    "auth_failures": stats_record.auth_failures,
                }

            # Update cache
            self._containers_cache = containers
            self._pending_queue_cache = pending_queue
            self._stats_cache = stats
            self._cache_loaded = True

            logger.info(
                f"Loaded container state from DB: {len(containers)} containers, "
                f"{len(pending_queue)} pending, stats={stats}"
            )

            return containers, pending_queue, stats

    # === Container Operations ===

    async def store_container(self, container: Container) -> ContainerRecord:
        """
        Store a new container in the database.

        FOG-SEC-003: Persists container with all spec details as JSON.

        Args:
            container: Container instance to store

        Returns:
            The created ContainerRecord
        """
        async with AsyncSessionLocal() as session:
            record = ContainerRecord(
                container_id=container.container_id,
                spec_json=container.spec.to_dict(),
                status=container.status.value,
                exit_code=container.exit_code,
                error=container.error,
                node_id=container.node_id,
                created_at=container.created_at,
                started_at=container.started_at,
                finished_at=container.finished_at,
                pid=container.pid,
                ip_address=container.ip_address,
                health_status=container.health_status,
                last_health_check=container.last_health_check,
                health_check_failures=container.health_check_failures,
                cpu_usage_percent=container.cpu_usage_percent,
                memory_usage_mb=container.memory_usage_mb,
                network_rx_bytes=container.network_rx_bytes,
                network_tx_bytes=container.network_tx_bytes,
                restart_count=container.restart_count,
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)

            # Update cache
            self._containers_cache[container.container_id] = container

            logger.info(f"Stored container {container.container_id} to DB")
            return record

    async def update_container(self, container: Container) -> bool:
        """
        Update an existing container in the database.

        FOG-SEC-003: Updates container state atomically.

        Args:
            container: Container instance with updated state

        Returns:
            True if container was updated, False if not found
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                update(ContainerRecord)
                .where(ContainerRecord.container_id == container.container_id)
                .values(
                    spec_json=container.spec.to_dict(),
                    status=container.status.value,
                    exit_code=container.exit_code,
                    error=container.error,
                    node_id=container.node_id,
                    started_at=container.started_at,
                    finished_at=container.finished_at,
                    pid=container.pid,
                    ip_address=container.ip_address,
                    health_status=container.health_status,
                    last_health_check=container.last_health_check,
                    health_check_failures=container.health_check_failures,
                    cpu_usage_percent=container.cpu_usage_percent,
                    memory_usage_mb=container.memory_usage_mb,
                    network_rx_bytes=container.network_rx_bytes,
                    network_tx_bytes=container.network_tx_bytes,
                    restart_count=container.restart_count,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()

            if result.rowcount > 0:
                # Update cache
                self._containers_cache[container.container_id] = container
                logger.debug(f"Updated container {container.container_id} in DB")
                return True
            return False

    async def delete_container(self, container_id: str) -> bool:
        """
        Delete a container from the database.

        FOG-SEC-003: Removes container record atomically.

        Args:
            container_id: ID of container to delete

        Returns:
            True if container was deleted, False if not found
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                delete(ContainerRecord).where(ContainerRecord.container_id == container_id)
            )
            await session.commit()

            if result.rowcount > 0:
                # Update cache
                self._containers_cache.pop(container_id, None)
                logger.info(f"Deleted container {container_id} from DB")
                return True
            return False

    async def get_container(self, container_id: str) -> Optional[Container]:
        """
        Get a container by ID (from cache or DB).

        FOG-SEC-003: Prefers cache, falls back to DB.

        Args:
            container_id: Container ID to look up

        Returns:
            Container instance or None if not found
        """
        # Try cache first
        if container_id in self._containers_cache:
            return self._containers_cache[container_id]

        # Fall back to DB
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ContainerRecord).where(ContainerRecord.container_id == container_id)
            )
            record = result.scalar_one_or_none()

            if record:
                container = self._record_to_container(record)
                # Update cache
                self._containers_cache[container_id] = container
                return container
            return None

    async def list_containers(
        self,
        status: Optional[ContainerStatus] = None,
        node_id: Optional[str] = None,
    ) -> list[Container]:
        """
        List containers with optional filters.

        FOG-SEC-003: Queries DB with filters.

        Args:
            status: Filter by status (optional)
            node_id: Filter by node ID (optional)

        Returns:
            List of matching Container instances
        """
        async with AsyncSessionLocal() as session:
            query = select(ContainerRecord)

            conditions = []
            if status is not None:
                conditions.append(ContainerRecord.status == status.value)
            if node_id is not None:
                conditions.append(ContainerRecord.node_id == node_id)

            if conditions:
                query = query.where(and_(*conditions))

            result = await session.execute(query)
            containers = []
            for record in result.scalars().all():
                container = self._record_to_container(record)
                containers.append(container)
                # Update cache
                self._containers_cache[record.container_id] = container

            return containers

    # === Pending Queue Operations ===

    async def add_to_pending_queue(self, container_id: str) -> bool:
        """
        Add a container to the pending queue.

        FOG-SEC-003: Persists queue position for ordering.

        Args:
            container_id: Container ID to add

        Returns:
            True if added successfully
        """
        async with AsyncSessionLocal() as session:
            # Get current max position
            result = await session.execute(
                select(PendingQueueRecord.position).order_by(PendingQueueRecord.position.desc()).limit(1)
            )
            max_pos = result.scalar_one_or_none() or 0

            record = PendingQueueRecord(
                container_id=container_id,
                position=max_pos + 1,
            )
            session.add(record)
            await session.commit()

            # Update cache
            if container_id not in self._pending_queue_cache:
                self._pending_queue_cache.append(container_id)

            logger.debug(f"Added container {container_id} to pending queue at position {max_pos + 1}")
            return True

    async def remove_from_pending_queue(self, container_id: str) -> bool:
        """
        Remove a container from the pending queue.

        FOG-SEC-003: Removes from persistent queue.

        Args:
            container_id: Container ID to remove

        Returns:
            True if removed, False if not found
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                delete(PendingQueueRecord).where(PendingQueueRecord.container_id == container_id)
            )
            await session.commit()

            if result.rowcount > 0:
                # Update cache
                if container_id in self._pending_queue_cache:
                    self._pending_queue_cache.remove(container_id)
                logger.debug(f"Removed container {container_id} from pending queue")
                return True
            return False

    async def get_pending_queue(self) -> list[str]:
        """
        Get the current pending queue (from cache or DB).

        FOG-SEC-003: Returns ordered list of pending container IDs.

        Returns:
            List of container IDs in queue order
        """
        if self._cache_loaded:
            return list(self._pending_queue_cache)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(PendingQueueRecord).order_by(PendingQueueRecord.position)
            )
            queue = [record.container_id for record in result.scalars().all()]
            self._pending_queue_cache = queue
            return queue

    # === Stats Operations ===

    async def update_stats(self, stats: dict[str, Any]) -> bool:
        """
        Update scheduler statistics in the database.

        FOG-SEC-003: Persists stats for recovery.

        Args:
            stats: Statistics dictionary

        Returns:
            True if updated successfully
        """
        async with AsyncSessionLocal() as session:
            # Try to update existing record
            result = await session.execute(
                update(SchedulerStatsRecord)
                .where(SchedulerStatsRecord.id == 1)
                .values(
                    containers_scheduled=stats.get("containers_scheduled", 0),
                    containers_failed=stats.get("containers_failed", 0),
                    scheduling_latency_ms_avg=stats.get("scheduling_latency_ms_avg", 0.0),
                    auth_failures=stats.get("auth_failures", 0),
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()

            if result.rowcount == 0:
                # Insert new record
                record = SchedulerStatsRecord(
                    id=1,
                    containers_scheduled=stats.get("containers_scheduled", 0),
                    containers_failed=stats.get("containers_failed", 0),
                    scheduling_latency_ms_avg=stats.get("scheduling_latency_ms_avg", 0.0),
                    auth_failures=stats.get("auth_failures", 0),
                )
                session.add(record)
                await session.commit()

            # Update cache
            self._stats_cache = stats.copy()
            logger.debug(f"Updated scheduler stats in DB: {stats}")
            return True

    async def get_stats(self) -> dict[str, Any]:
        """
        Get scheduler statistics (from cache or DB).

        FOG-SEC-003: Returns persisted stats.

        Returns:
            Statistics dictionary
        """
        if self._cache_loaded:
            return self._stats_cache.copy()

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(SchedulerStatsRecord))
            record = result.scalar_one_or_none()

            if record:
                stats = {
                    "containers_scheduled": record.containers_scheduled,
                    "containers_failed": record.containers_failed,
                    "scheduling_latency_ms_avg": record.scheduling_latency_ms_avg,
                    "auth_failures": record.auth_failures,
                }
                self._stats_cache = stats
                return stats

            return self._stats_cache.copy()

    async def increment_stat(self, stat_name: str, increment: int = 1) -> bool:
        """
        Increment a specific statistic.

        FOG-SEC-003: Atomic increment of stat value.

        Args:
            stat_name: Name of stat to increment
            increment: Amount to increment by

        Returns:
            True if updated successfully
        """
        if stat_name not in self._stats_cache:
            return False

        self._stats_cache[stat_name] = self._stats_cache.get(stat_name, 0) + increment
        return await self.update_stats(self._stats_cache)

    # === Helper Methods ===

    def _record_to_container(self, record: ContainerRecord) -> Container:
        """
        Convert database record to Container instance.

        FOG-SEC-003: Deserializes spec JSON back to dataclass.

        Args:
            record: ContainerRecord from database

        Returns:
            Container instance
        """
        spec_dict = record.spec_json

        # Rebuild ContainerSpec from JSON
        resources = ResourceLimits.from_dict(spec_dict.get("resources", {}))

        volumes = []
        for v in spec_dict.get("volumes", []):
            volumes.append(VolumeMount(
                source=v["source"],
                target=v["target"],
                read_only=v.get("read_only", False),
                volume_type=VolumeType(v.get("volume_type", "local")),
                replication_factor=v.get("replication_factor", 1),
                consistency=v.get("consistency", "eventual"),
            ))

        ports = []
        for p in spec_dict.get("ports", []):
            ports.append(PortMapping(
                container_port=p["container_port"],
                host_port=p.get("host_port"),
                protocol=p.get("protocol", "tcp"),
            ))

        network_dict = spec_dict.get("network", {})
        network = NetworkConfig(
            mode=NetworkMode(network_dict.get("mode", "fog-mesh")),
            network_name=network_dict.get("network_name"),
            dns_servers=network_dict.get("dns_servers", []),
            dns_search=network_dict.get("dns_search", []),
            hostname=network_dict.get("hostname"),
            domain_name=network_dict.get("domain_name"),
            aliases=network_dict.get("aliases", []),
            expose_to_mesh=network_dict.get("expose_to_mesh", True),
            mesh_dns_name=network_dict.get("mesh_dns_name"),
        )

        health_check = None
        hc_dict = spec_dict.get("health_check")
        if hc_dict:
            health_check = HealthCheck(
                command=hc_dict["command"],
                interval_sec=hc_dict.get("interval_sec", 30),
                timeout_sec=hc_dict.get("timeout_sec", 30),
                retries=hc_dict.get("retries", 3),
                start_period_sec=hc_dict.get("start_period_sec", 0),
            )

        spec = ContainerSpec(
            image=spec_dict["image"],
            name=spec_dict.get("name"),
            command=spec_dict.get("command"),
            entrypoint=spec_dict.get("entrypoint"),
            environment=spec_dict.get("environment", {}),
            env_file=spec_dict.get("env_file"),
            resources=resources,
            volumes=volumes,
            working_dir=spec_dict.get("working_dir"),
            network=network,
            ports=ports,
            health_check=health_check,
            restart_policy=RestartPolicy(spec_dict.get("restart_policy", "no")),
            stop_timeout_sec=spec_dict.get("stop_timeout_sec", 10),
            labels=spec_dict.get("labels", {}),
            placement_hints=spec_dict.get("placement_hints", {}),
        )

        container = Container(
            container_id=record.container_id,
            spec=spec,
            status=ContainerStatus(record.status),
            exit_code=record.exit_code,
            error=record.error,
            node_id=record.node_id,
            created_at=record.created_at,
            started_at=record.started_at,
            finished_at=record.finished_at,
            pid=record.pid,
            ip_address=record.ip_address,
            health_status=record.health_status,
            last_health_check=record.last_health_check,
            health_check_failures=record.health_check_failures,
            cpu_usage_percent=record.cpu_usage_percent,
            memory_usage_mb=record.memory_usage_mb,
            network_rx_bytes=record.network_rx_bytes,
            network_tx_bytes=record.network_tx_bytes,
            restart_count=record.restart_count,
        )

        return container


# Singleton instance
_container_persistence: Optional[ContainerPersistenceService] = None


def get_container_persistence() -> ContainerPersistenceService:
    """Get the singleton ContainerPersistenceService instance."""
    global _container_persistence
    if _container_persistence is None:
        _container_persistence = ContainerPersistenceService()
    return _container_persistence
