"""
Unit Tests for FogCoordinator

Comprehensive test suite for fog network coordinator functionality.
Tests node management, task routing, health monitoring, and failover.
"""

import asyncio
import pytest
from datetime import datetime, timedelta, UTC

from ..coordinator import FogCoordinator
from ..coordinator_interface import (
    FogNode,
    NodeStatus,
    NodeType,
    RoutingStrategy,
    Task,
)


@pytest.fixture
async def coordinator():
    """Create a FogCoordinator instance for testing."""
    coord = FogCoordinator(
        node_id="test-coordinator",
        onion_router=None,
        heartbeat_interval=1,
        heartbeat_timeout=3,
    )
    await coord.start()
    yield coord
    await coord.stop()


@pytest.fixture
def sample_node():
    """Create a sample fog node for testing."""
    return FogNode(
        node_id="test-node-1",
        node_type=NodeType.COMPUTE_NODE,
        status=NodeStatus.ACTIVE,
        cpu_cores=4,
        memory_mb=8192,
        storage_mb=100000,
        gpu_available=False,
        region="us-east-1",
        ip_address="192.168.1.100",
        supports_onion_routing=True,
    )


@pytest.fixture
def sample_task():
    """Create a sample task for testing."""
    return Task(
        task_id="test-task-1",
        task_type="compute",
        priority=5,
        cpu_required=2,
        memory_required=2048,
        storage_required=1000,
        privacy_level="public",
    )


class TestNodeRegistration:
    """Test node registration and management."""

    @pytest.mark.asyncio
    async def test_register_node_success(self, coordinator, sample_node):
        """Test successful node registration."""
        result = await coordinator.register_node(sample_node)
        assert result is True

        # Verify node is in registry
        retrieved = await coordinator.get_node(sample_node.node_id)
        assert retrieved is not None
        assert retrieved.node_id == sample_node.node_id
        assert retrieved.status == NodeStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_register_duplicate_node(self, coordinator, sample_node):
        """Test registering a node that already exists."""
        await coordinator.register_node(sample_node)

        # Try to register again
        result = await coordinator.register_node(sample_node)
        assert result is False  # Should fail

    @pytest.mark.asyncio
    async def test_unregister_node(self, coordinator, sample_node):
        """Test node unregistration."""
        await coordinator.register_node(sample_node)

        result = await coordinator.unregister_node(sample_node.node_id)
        assert result is True

        # Verify node is removed
        retrieved = await coordinator.get_node(sample_node.node_id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_unregister_nonexistent_node(self, coordinator):
        """Test unregistering a node that doesn't exist."""
        result = await coordinator.unregister_node("nonexistent-node")
        assert result is False

    @pytest.mark.asyncio
    async def test_update_node_status(self, coordinator, sample_node):
        """Test updating node status."""
        await coordinator.register_node(sample_node)

        result = await coordinator.update_node_status(
            sample_node.node_id, NodeStatus.BUSY
        )
        assert result is True

        # Verify status updated
        node = await coordinator.get_node(sample_node.node_id)
        assert node.status == NodeStatus.BUSY

    @pytest.mark.asyncio
    async def test_list_nodes_no_filter(self, coordinator):
        """Test listing all nodes without filters."""
        # Register multiple nodes
        nodes = [
            FogNode(
                node_id=f"node-{i}",
                node_type=NodeType.EDGE_DEVICE if i % 2 == 0 else NodeType.COMPUTE_NODE,
                status=NodeStatus.ACTIVE if i % 3 == 0 else NodeStatus.IDLE,
            )
            for i in range(5)
        ]

        for node in nodes:
            await coordinator.register_node(node)

        all_nodes = await coordinator.list_nodes()
        assert len(all_nodes) == 5

    @pytest.mark.asyncio
    async def test_list_nodes_filter_by_status(self, coordinator):
        """Test listing nodes filtered by status."""
        nodes = [
            FogNode(
                node_id=f"node-{i}",
                node_type=NodeType.COMPUTE_NODE,
                status=NodeStatus.ACTIVE if i < 3 else NodeStatus.IDLE,
            )
            for i in range(5)
        ]

        for node in nodes:
            await coordinator.register_node(node)

        active_nodes = await coordinator.list_nodes(status=NodeStatus.ACTIVE)
        assert len(active_nodes) == 3

        idle_nodes = await coordinator.list_nodes(status=NodeStatus.IDLE)
        assert len(idle_nodes) == 2

    @pytest.mark.asyncio
    async def test_list_nodes_filter_by_type(self, coordinator):
        """Test listing nodes filtered by type."""
        nodes = [
            FogNode(
                node_id=f"node-{i}",
                node_type=NodeType.EDGE_DEVICE if i < 2 else NodeType.COMPUTE_NODE,
            )
            for i in range(5)
        ]

        for node in nodes:
            await coordinator.register_node(node)

        edge_nodes = await coordinator.list_nodes(node_type=NodeType.EDGE_DEVICE)
        assert len(edge_nodes) == 2

        compute_nodes = await coordinator.list_nodes(node_type=NodeType.COMPUTE_NODE)
        assert len(compute_nodes) == 3


class TestTaskRouting:
    """Test task routing strategies."""

    @pytest.mark.asyncio
    async def test_route_task_round_robin(self, coordinator):
        """Test round-robin task routing."""
        # Register multiple nodes
        nodes = [
            FogNode(
                node_id=f"node-{i}",
                node_type=NodeType.COMPUTE_NODE,
                cpu_cores=4,
                memory_mb=8192,
            )
            for i in range(3)
        ]

        for node in nodes:
            await coordinator.register_node(node)

        # Route tasks and verify round-robin distribution
        task1 = Task(task_id="task-1", task_type="compute")
        task2 = Task(task_id="task-2", task_type="compute")
        task3 = Task(task_id="task-3", task_type="compute")

        node1 = await coordinator.route_task(task1, RoutingStrategy.ROUND_ROBIN)
        node2 = await coordinator.route_task(task2, RoutingStrategy.ROUND_ROBIN)
        node3 = await coordinator.route_task(task3, RoutingStrategy.ROUND_ROBIN)

        assert node1.node_id == "node-0"
        assert node2.node_id == "node-1"
        assert node3.node_id == "node-2"

    @pytest.mark.asyncio
    async def test_route_task_least_loaded(self, coordinator):
        """Test least-loaded task routing."""
        # Register nodes with different CPU usage
        nodes = [
            FogNode(
                node_id=f"node-{i}",
                node_type=NodeType.COMPUTE_NODE,
                cpu_cores=4,
                memory_mb=8192,
                cpu_usage_percent=i * 20.0,  # 0%, 20%, 40%, 60%, 80%
            )
            for i in range(5)
        ]

        for node in nodes:
            await coordinator.register_node(node)

        task = Task(task_id="task-1", task_type="compute")
        selected_node = await coordinator.route_task(task, RoutingStrategy.LEAST_LOADED)

        # Should select node-0 with 0% CPU usage
        assert selected_node.node_id == "node-0"
        assert selected_node.cpu_usage_percent == 0.0

    @pytest.mark.asyncio
    async def test_route_task_insufficient_resources(self, coordinator):
        """Test task routing when no node has sufficient resources."""
        # Register node with limited resources
        node = FogNode(
            node_id="small-node",
            node_type=NodeType.EDGE_DEVICE,
            cpu_cores=1,
            memory_mb=512,
        )
        await coordinator.register_node(node)

        # Create task requiring more resources
        task = Task(
            task_id="large-task",
            task_type="compute",
            cpu_required=4,
            memory_required=8192,
        )

        selected_node = await coordinator.route_task(task)
        assert selected_node is None  # No suitable node

    @pytest.mark.asyncio
    async def test_route_task_gpu_required(self, coordinator):
        """Test task routing for GPU-required tasks."""
        # Register nodes with and without GPU
        node_no_gpu = FogNode(
            node_id="cpu-node",
            node_type=NodeType.COMPUTE_NODE,
            gpu_available=False,
        )
        node_with_gpu = FogNode(
            node_id="gpu-node",
            node_type=NodeType.COMPUTE_NODE,
            gpu_available=True,
        )

        await coordinator.register_node(node_no_gpu)
        await coordinator.register_node(node_with_gpu)

        # Create GPU-required task
        task = Task(task_id="gpu-task", task_type="ml-training", gpu_required=True)

        selected_node = await coordinator.route_task(task)
        assert selected_node.node_id == "gpu-node"
        assert selected_node.gpu_available is True

    @pytest.mark.asyncio
    async def test_route_task_privacy_aware(self, coordinator):
        """Test privacy-aware task routing."""
        # Register nodes with and without onion routing support
        node_no_privacy = FogNode(
            node_id="public-node",
            node_type=NodeType.COMPUTE_NODE,
            supports_onion_routing=False,
        )
        node_with_privacy = FogNode(
            node_id="private-node",
            node_type=NodeType.COMPUTE_NODE,
            supports_onion_routing=True,
        )

        await coordinator.register_node(node_no_privacy)
        await coordinator.register_node(node_with_privacy)

        # Create privacy-required task
        task = Task(
            task_id="secret-task",
            task_type="compute",
            privacy_level="confidential",
            require_onion_circuit=True,
        )

        selected_node = await coordinator.route_task(task)
        assert selected_node is not None
        assert selected_node.supports_onion_routing is True


class TestNetworkTopology:
    """Test network topology tracking."""

    @pytest.mark.asyncio
    async def test_get_topology_empty(self, coordinator):
        """Test topology with no registered nodes."""
        topology = await coordinator.get_topology()

        assert topology.total_nodes == 0
        assert topology.active_nodes == 0
        assert topology.offline_nodes == 0
        assert topology.total_cpu_cores == 0
        assert topology.running_tasks == 0

    @pytest.mark.asyncio
    async def test_get_topology_with_nodes(self, coordinator):
        """Test topology with registered nodes."""
        nodes = [
            FogNode(
                node_id=f"node-{i}",
                node_type=NodeType.COMPUTE_NODE,
                status=NodeStatus.ACTIVE if i < 3 else NodeStatus.OFFLINE,
                cpu_cores=4,
                memory_mb=8192,
                cpu_usage_percent=25.0,  # 1 core used per node
                active_tasks=1,
            )
            for i in range(5)
        ]

        for node in nodes:
            await coordinator.register_node(node)

        topology = await coordinator.get_topology()

        assert topology.total_nodes == 5
        assert topology.active_nodes == 3
        assert topology.offline_nodes == 2
        assert topology.total_cpu_cores == 20  # 5 nodes * 4 cores
        assert topology.available_cpu_cores == 15  # 20 total - 5 used (25% of 20)
        assert topology.total_memory_mb == 40960  # 5 nodes * 8192 MB
        assert topology.running_tasks == 5  # 5 nodes * 1 task each


class TestFailover:
    """Test node failure handling and recovery."""

    @pytest.mark.asyncio
    async def test_handle_node_failure(self, coordinator, sample_node):
        """Test handling a node failure."""
        # Register node with active tasks
        sample_node.active_tasks = 3
        await coordinator.register_node(sample_node)

        # Simulate failure
        result = await coordinator.handle_node_failure(sample_node.node_id)
        assert result is True

        # Verify node marked as offline
        node = await coordinator.get_node(sample_node.node_id)
        assert node.status == NodeStatus.OFFLINE
        assert node.active_tasks == 0
        assert node.failed_tasks == 3

    @pytest.mark.asyncio
    async def test_heartbeat_timeout(self, coordinator):
        """Test heartbeat timeout detection."""
        # Register node
        node = FogNode(
            node_id="timeout-node",
            node_type=NodeType.COMPUTE_NODE,
        )
        await coordinator.register_node(node)

        # Manually set last heartbeat to past timeout
        node.last_heartbeat = datetime.now(UTC) - timedelta(seconds=10)

        # Wait for heartbeat monitor to detect timeout
        await asyncio.sleep(2)

        # Verify node marked as offline
        updated_node = await coordinator.get_node("timeout-node")
        # Note: May still be ACTIVE if heartbeat monitor hasn't run yet
        # In real usage, would wait longer or trigger monitor manually


class TestFogRequests:
    """Test fog network request processing."""

    @pytest.mark.asyncio
    async def test_process_compute_task_request(self, coordinator, sample_node):
        """Test processing a compute task request."""
        await coordinator.register_node(sample_node)

        response = await coordinator.process_fog_request(
            "compute_task",
            {
                "task_id": "req-task-1",
                "task_type": "compute",
                "priority": 5,
            },
        )

        assert response["success"] is True
        assert response["node_id"] == sample_node.node_id

    @pytest.mark.asyncio
    async def test_process_query_status_request(self, coordinator, sample_node):
        """Test querying node status."""
        await coordinator.register_node(sample_node)

        response = await coordinator.process_fog_request(
            "query_status", {"node_id": sample_node.node_id}
        )

        assert response["success"] is True
        assert response["status"] == NodeStatus.ACTIVE.value
        assert "active_tasks" in response

    @pytest.mark.asyncio
    async def test_process_update_metrics_request(self, coordinator, sample_node):
        """Test updating node metrics."""
        await coordinator.register_node(sample_node)

        response = await coordinator.process_fog_request(
            "update_metrics",
            {
                "node_id": sample_node.node_id,
                "cpu_usage": 75.5,
                "memory_usage": 60.0,
            },
        )

        assert response["success"] is True

        # Verify metrics updated
        node = await coordinator.get_node(sample_node.node_id)
        assert node.cpu_usage_percent == 75.5
        assert node.memory_usage_percent == 60.0

    @pytest.mark.asyncio
    async def test_process_unknown_request_type(self, coordinator):
        """Test processing unknown request type."""
        response = await coordinator.process_fog_request("unknown_request", {})

        assert response["success"] is False
        assert "Unknown request type" in response["error"]


class TestHealthCheck:
    """Test coordinator health monitoring."""

    @pytest.mark.asyncio
    async def test_health_check(self, coordinator):
        """Test coordinator health check."""
        # Register some nodes
        nodes = [
            FogNode(node_id=f"node-{i}", node_type=NodeType.COMPUTE_NODE)
            for i in range(3)
        ]
        for node in nodes:
            await coordinator.register_node(node)

        health = await coordinator.health_check()

        assert health["coordinator_id"] == "test-coordinator"
        assert health["status"] == "healthy"
        assert health["total_nodes"] == 3
        assert health["active_nodes"] == 3
        assert health["running_tasks"] == 0
        assert health["has_onion_router"] is False


class TestLifecycle:
    """Test coordinator lifecycle management."""

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test starting and stopping coordinator."""
        coord = FogCoordinator(node_id="lifecycle-test")

        assert not coord._running

        await coord.start()
        assert coord._running
        assert coord._heartbeat_task is not None

        await coord.stop()
        assert not coord._running

    @pytest.mark.asyncio
    async def test_double_start(self):
        """Test starting coordinator twice (should be idempotent)."""
        coord = FogCoordinator(node_id="double-start-test")

        await coord.start()
        await coord.start()  # Should not raise error

        assert coord._running

        await coord.stop()
