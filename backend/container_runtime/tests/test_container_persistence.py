"""
Tests for FOG-SEC-003: Container State Persistence

Tests the ContainerPersistenceService and its integration with FogScheduler.
"""
import pytest
import asyncio
from datetime import datetime, timezone

from ..container_persistence import ContainerPersistenceService, get_container_persistence
from ..container_models import ContainerRecord, PendingQueueRecord, SchedulerStatsRecord
from ..models import (
    Container,
    ContainerSpec,
    ContainerStatus,
    ResourceLimits,
)
from ..scheduler import FogScheduler, SchedulerConfig, FogNode


class TestContainerPersistenceService:
    """Tests for ContainerPersistenceService."""

    @pytest.fixture
    def persistence_service(self):
        """Create a fresh persistence service instance."""
        return ContainerPersistenceService()

    @pytest.fixture
    def sample_container(self):
        """Create a sample container for testing."""
        spec = ContainerSpec(
            image="nginx:latest",
            name="test-nginx",
            resources=ResourceLimits(cpu_cores=1.0, memory_mb=512),
        )
        return Container(spec=spec)

    @pytest.mark.asyncio
    async def test_store_and_get_container(self, persistence_service, sample_container):
        """Test storing and retrieving a container."""
        # Store container
        await persistence_service.store_container(sample_container)

        # Retrieve container
        retrieved = await persistence_service.get_container(sample_container.container_id)

        assert retrieved is not None
        assert retrieved.container_id == sample_container.container_id
        assert retrieved.spec.image == "nginx:latest"
        assert retrieved.spec.name == "test-nginx"
        assert retrieved.status == ContainerStatus.PENDING

    @pytest.mark.asyncio
    async def test_update_container(self, persistence_service, sample_container):
        """Test updating a container."""
        # Store container
        await persistence_service.store_container(sample_container)

        # Update container
        sample_container.status = ContainerStatus.RUNNING
        sample_container.node_id = "node-1"
        sample_container.started_at = datetime.now(timezone.utc)

        result = await persistence_service.update_container(sample_container)
        assert result is True

        # Retrieve and verify
        retrieved = await persistence_service.get_container(sample_container.container_id)
        assert retrieved.status == ContainerStatus.RUNNING
        assert retrieved.node_id == "node-1"
        assert retrieved.started_at is not None

    @pytest.mark.asyncio
    async def test_delete_container(self, persistence_service, sample_container):
        """Test deleting a container."""
        # Store container
        await persistence_service.store_container(sample_container)

        # Delete container
        result = await persistence_service.delete_container(sample_container.container_id)
        assert result is True

        # Verify deleted
        retrieved = await persistence_service.get_container(sample_container.container_id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_pending_queue_operations(self, persistence_service, sample_container):
        """Test pending queue add/remove operations."""
        # Add to queue
        await persistence_service.add_to_pending_queue(sample_container.container_id)

        # Get queue
        queue = await persistence_service.get_pending_queue()
        assert sample_container.container_id in queue

        # Remove from queue
        result = await persistence_service.remove_from_pending_queue(sample_container.container_id)
        assert result is True

        # Verify removed
        queue = await persistence_service.get_pending_queue()
        assert sample_container.container_id not in queue

    @pytest.mark.asyncio
    async def test_stats_operations(self, persistence_service):
        """Test stats update and retrieval."""
        stats = {
            "containers_scheduled": 10,
            "containers_failed": 2,
            "scheduling_latency_ms_avg": 15.5,
            "auth_failures": 1,
        }

        # Update stats
        await persistence_service.update_stats(stats)

        # Retrieve stats
        retrieved = await persistence_service.get_stats()
        assert retrieved["containers_scheduled"] == 10
        assert retrieved["containers_failed"] == 2
        assert retrieved["scheduling_latency_ms_avg"] == 15.5
        assert retrieved["auth_failures"] == 1

    @pytest.mark.asyncio
    async def test_increment_stat(self, persistence_service):
        """Test incrementing a specific stat."""
        # Initialize stats
        stats = {
            "containers_scheduled": 5,
            "containers_failed": 0,
            "scheduling_latency_ms_avg": 0.0,
            "auth_failures": 0,
        }
        await persistence_service.update_stats(stats)

        # Increment
        await persistence_service.increment_stat("containers_scheduled", 1)

        # Verify
        retrieved = await persistence_service.get_stats()
        assert retrieved["containers_scheduled"] == 6

    @pytest.mark.asyncio
    async def test_load_state_from_db(self, persistence_service, sample_container):
        """Test loading full state from database."""
        # Store container and add to queue
        await persistence_service.store_container(sample_container)
        await persistence_service.add_to_pending_queue(sample_container.container_id)
        await persistence_service.update_stats({
            "containers_scheduled": 5,
            "containers_failed": 1,
            "scheduling_latency_ms_avg": 10.0,
            "auth_failures": 0,
        })

        # Create fresh instance and load state
        fresh_service = ContainerPersistenceService()
        containers, pending, stats = await fresh_service.load_state_from_db()

        assert sample_container.container_id in containers
        assert sample_container.container_id in pending
        assert stats["containers_scheduled"] == 5


class TestFogSchedulerPersistence:
    """Tests for FogScheduler with persistence enabled."""

    @pytest.fixture
    def scheduler_config(self):
        """Create scheduler config with persistence enabled."""
        return SchedulerConfig(
            enable_persistence=True,
            require_auth=False,
        )

    @pytest.fixture
    def sample_node(self):
        """Create a sample fog node."""
        return FogNode(
            node_id="node-1",
            hostname="test-node",
            cpu_cores=4,
            memory_mb=4096,
            disk_mb=10240,
        )

    @pytest.mark.asyncio
    async def test_scheduler_start_loads_state(self, scheduler_config):
        """Test that scheduler loads state from DB on start."""
        scheduler = FogScheduler(config=scheduler_config)
        await scheduler.start()

        assert scheduler._state_loaded is True

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_submit_container_persists(self, scheduler_config):
        """Test that submit_container persists to database."""
        scheduler = FogScheduler(config=scheduler_config)
        await scheduler.start()

        spec = ContainerSpec(image="nginx:latest", name="test-nginx")
        container = await scheduler.submit_container(spec)

        # Verify in cache
        assert container.container_id in scheduler._containers
        assert container.container_id in scheduler._pending_queue

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_scheduler_stop_persists_stats(self, scheduler_config):
        """Test that scheduler persists stats on stop."""
        scheduler = FogScheduler(config=scheduler_config)
        await scheduler.start()

        # Modify stats
        scheduler._stats["containers_scheduled"] = 100

        await scheduler.stop()

        # Verify stats were persisted
        persistence = get_container_persistence()
        stats = await persistence.get_stats()
        assert stats["containers_scheduled"] == 100


class TestContainerModels:
    """Tests for SQLAlchemy container models."""

    def test_container_record_to_dict(self):
        """Test ContainerRecord.to_dict() method."""
        record = ContainerRecord(
            container_id="fog-abc123",
            spec_json={"image": "nginx:latest"},
            status="running",
        )
        result = record.to_dict()

        assert result["container_id"] == "fog-abc123"
        assert result["spec"]["image"] == "nginx:latest"
        assert result["status"] == "running"

    def test_pending_queue_record_to_dict(self):
        """Test PendingQueueRecord.to_dict() method."""
        record = PendingQueueRecord(
            container_id="fog-abc123",
            position=1,
        )
        result = record.to_dict()

        assert result["container_id"] == "fog-abc123"
        assert result["position"] == 1

    def test_scheduler_stats_record_to_dict(self):
        """Test SchedulerStatsRecord.to_dict() method."""
        record = SchedulerStatsRecord(
            containers_scheduled=10,
            containers_failed=2,
            scheduling_latency_ms_avg=15.5,
            auth_failures=1,
        )
        result = record.to_dict()

        assert result["containers_scheduled"] == 10
        assert result["containers_failed"] == 2
        assert result["scheduling_latency_ms_avg"] == 15.5
        assert result["auth_failures"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
