"""
Tests for Fog Container Runtime
Comprehensive test coverage for container scheduling, storage, and networking.
"""
import asyncio
import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock

# Import container runtime components
from container_runtime.models import (
    Container,
    ContainerSpec,
    ContainerStatus,
    Volume,
    VolumeMount,
    VolumeType,
    PortMapping,
    NetworkConfig,
    NetworkMode,
    ResourceLimits,
    HealthCheck,
    RestartPolicy,
    ContainerLogs,
)
from container_runtime.scheduler import (
    FogScheduler,
    SchedulerConfig,
    FogNode,
    PlacementStrategy,
)
from container_runtime.storage import (
    DistributedVolumeManager,
    VolumeConfig,
    VolumeReplica,
)
from container_runtime.network import (
    FogNetworkManager,
    NetworkConfig as NetConfig,
    FogNetwork,
    NetworkEndpoint,
    PortAllocation,
    DNSRecord,
)


# ============================================================================
# Model Tests
# ============================================================================

class TestResourceLimits:
    """Tests for ResourceLimits model."""

    def test_default_values(self):
        """Test default resource limits."""
        limits = ResourceLimits()
        assert limits.cpu_cores == 1.0
        assert limits.memory_mb == 512
        assert limits.gpu_count == 0
        assert limits.disk_mb == 1024

    def test_custom_values(self):
        """Test custom resource limits."""
        limits = ResourceLimits(
            cpu_cores=4.0,
            memory_mb=8192,
            gpu_count=2,
            disk_mb=102400,
            bandwidth_mbps=100,
        )
        assert limits.cpu_cores == 4.0
        assert limits.memory_mb == 8192
        assert limits.gpu_count == 2
        assert limits.bandwidth_mbps == 100

    def test_to_dict(self):
        """Test serialization."""
        limits = ResourceLimits(cpu_cores=2.0, memory_mb=1024)
        data = limits.to_dict()
        assert data["cpu_cores"] == 2.0
        assert data["memory_mb"] == 1024

    def test_from_dict(self):
        """Test deserialization."""
        data = {"cpu_cores": 4.0, "memory_mb": 4096}
        limits = ResourceLimits.from_dict(data)
        assert limits.cpu_cores == 4.0
        assert limits.memory_mb == 4096


class TestPortMapping:
    """Tests for PortMapping model."""

    def test_basic_mapping(self):
        """Test basic port mapping."""
        mapping = PortMapping(container_port=80)
        assert mapping.container_port == 80
        assert mapping.host_port is None
        assert mapping.protocol == "tcp"

    def test_explicit_host_port(self):
        """Test explicit host port mapping."""
        mapping = PortMapping(container_port=80, host_port=8080)
        assert mapping.host_port == 8080

    def test_udp_protocol(self):
        """Test UDP port mapping."""
        mapping = PortMapping(container_port=53, protocol="udp")
        assert mapping.protocol == "udp"


class TestVolumeMount:
    """Tests for VolumeMount model."""

    def test_basic_mount(self):
        """Test basic volume mount."""
        mount = VolumeMount(source="data-vol", target="/data")
        assert mount.source == "data-vol"
        assert mount.target == "/data"
        assert mount.read_only is False
        assert mount.volume_type == VolumeType.LOCAL

    def test_distributed_mount(self):
        """Test distributed volume mount."""
        mount = VolumeMount(
            source="shared-data",
            target="/shared",
            volume_type=VolumeType.DISTRIBUTED,
            replication_factor=3,
            consistency="strong",
        )
        assert mount.volume_type == VolumeType.DISTRIBUTED
        assert mount.replication_factor == 3
        assert mount.consistency == "strong"


class TestNetworkConfig:
    """Tests for NetworkConfig model."""

    def test_default_config(self):
        """Test default network configuration."""
        config = NetworkConfig()
        assert config.mode == NetworkMode.FOG_MESH
        assert config.expose_to_mesh is True

    def test_custom_config(self):
        """Test custom network configuration."""
        config = NetworkConfig(
            mode=NetworkMode.BRIDGE,
            hostname="mycontainer",
            aliases=["web", "frontend"],
        )
        assert config.mode == NetworkMode.BRIDGE
        assert config.hostname == "mycontainer"
        assert "web" in config.aliases


class TestHealthCheck:
    """Tests for HealthCheck model."""

    def test_basic_health_check(self):
        """Test basic health check."""
        hc = HealthCheck(command=["curl", "-f", "http://localhost/health"])
        assert hc.interval_sec == 30
        assert hc.timeout_sec == 30
        assert hc.retries == 3

    def test_custom_health_check(self):
        """Test custom health check."""
        hc = HealthCheck(
            command=["pg_isready"],
            interval_sec=10,
            timeout_sec=5,
            retries=5,
            start_period_sec=30,
        )
        assert hc.interval_sec == 10
        assert hc.start_period_sec == 30


class TestContainerSpec:
    """Tests for ContainerSpec model."""

    def test_minimal_spec(self):
        """Test minimal container spec."""
        spec = ContainerSpec(image="postgres:15")
        assert spec.image == "postgres:15"
        assert spec.name is None
        assert spec.restart_policy == RestartPolicy.NO

    def test_full_spec(self):
        """Test full container spec."""
        spec = ContainerSpec(
            image="my-app:latest",
            name="my-app-container",
            command=["python", "main.py"],
            environment={"DEBUG": "true"},
            resources=ResourceLimits(cpu_cores=2.0, memory_mb=2048),
            volumes=[VolumeMount(source="data", target="/data")],
            ports=[PortMapping(container_port=8080, host_port=80)],
            restart_policy=RestartPolicy.ALWAYS,
            labels={"app": "myapp"},
        )
        assert spec.name == "my-app-container"
        assert spec.command == ["python", "main.py"]
        assert spec.environment["DEBUG"] == "true"
        assert len(spec.volumes) == 1
        assert len(spec.ports) == 1

    def test_to_dict(self):
        """Test spec serialization."""
        spec = ContainerSpec(image="nginx", name="web")
        data = spec.to_dict()
        assert data["image"] == "nginx"
        assert data["name"] == "web"


class TestContainer:
    """Tests for Container model."""

    def test_container_creation(self):
        """Test container creation."""
        spec = ContainerSpec(image="redis:7")
        container = Container(spec=spec)
        assert container.container_id.startswith("fog-")
        assert container.status == ContainerStatus.PENDING
        assert container.node_id is None

    def test_container_name_from_spec(self):
        """Test container name from spec."""
        spec = ContainerSpec(image="redis:7", name="cache")
        container = Container(spec=spec)
        assert container.name == "cache"

    def test_container_name_fallback(self):
        """Test container name fallback to ID."""
        spec = ContainerSpec(image="redis:7")
        container = Container(spec=spec)
        assert container.name == container.container_id

    def test_is_running(self):
        """Test is_running property."""
        container = Container(spec=ContainerSpec(image="test"))
        assert container.is_running is False
        container.status = ContainerStatus.RUNNING
        assert container.is_running is True

    def test_uptime(self):
        """Test uptime calculation."""
        container = Container(spec=ContainerSpec(image="test"))
        assert container.uptime_seconds is None

        container.started_at = datetime.now(UTC)
        assert container.uptime_seconds is not None
        assert container.uptime_seconds >= 0


class TestVolume:
    """Tests for Volume model."""

    def test_volume_creation(self):
        """Test volume creation."""
        volume = Volume(name="data-vol", size_mb=1024)
        assert volume.volume_id.startswith("vol-")
        assert volume.name == "data-vol"
        assert volume.is_ready is False

    def test_distributed_volume(self):
        """Test distributed volume."""
        volume = Volume(
            name="shared-data",
            volume_type=VolumeType.DISTRIBUTED,
            replication_factor=3,
            consistency_mode="strong",
        )
        assert volume.volume_type == VolumeType.DISTRIBUTED
        assert volume.replication_factor == 3


# ============================================================================
# Scheduler Tests
# ============================================================================

class TestFogNode:
    """Tests for FogNode model."""

    def test_basic_node(self):
        """Test basic node creation."""
        node = FogNode(
            node_id="node-1",
            hostname="desktop-1",
            cpu_cores=8,
            memory_mb=16384,
        )
        assert node.node_id == "node-1"
        assert node.available_cpu == 8
        assert node.available_memory == 16384

    def test_node_with_usage(self):
        """Test node with resource usage."""
        node = FogNode(
            node_id="node-1",
            hostname="laptop-1",
            cpu_cores=4,
            memory_mb=8192,
            cpu_used_cores=2.5,
            memory_used_mb=4096,
        )
        assert node.available_cpu == 1.5
        assert node.available_memory == 4096

    def test_can_fit_success(self):
        """Test can_fit returns true for fitting container."""
        node = FogNode(node_id="n1", hostname="h1", cpu_cores=4, memory_mb=4096)
        spec = ContainerSpec(
            image="test",
            resources=ResourceLimits(cpu_cores=2.0, memory_mb=2048),
        )
        assert node.can_fit(spec) is True

    def test_can_fit_cpu_failure(self):
        """Test can_fit returns false for CPU constraint."""
        node = FogNode(node_id="n1", hostname="h1", cpu_cores=2, memory_mb=4096)
        spec = ContainerSpec(
            image="test",
            resources=ResourceLimits(cpu_cores=4.0, memory_mb=1024),
        )
        assert node.can_fit(spec) is False

    def test_can_fit_memory_failure(self):
        """Test can_fit returns false for memory constraint."""
        node = FogNode(node_id="n1", hostname="h1", cpu_cores=8, memory_mb=2048)
        spec = ContainerSpec(
            image="test",
            resources=ResourceLimits(cpu_cores=1.0, memory_mb=4096),
        )
        assert node.can_fit(spec) is False

    def test_can_fit_gpu_failure(self):
        """Test can_fit returns false for GPU constraint."""
        node = FogNode(node_id="n1", hostname="h1", cpu_cores=8, memory_mb=8192, gpu_available=False)
        spec = ContainerSpec(
            image="test",
            resources=ResourceLimits(gpu_count=1),
        )
        assert node.can_fit(spec) is False

    def test_fitness_score(self):
        """Test fitness score calculation."""
        node = FogNode(node_id="n1", hostname="h1", cpu_cores=4, memory_mb=4096)
        spec = ContainerSpec(
            image="test",
            resources=ResourceLimits(cpu_cores=2.0, memory_mb=2048),
        )
        score = node.get_fitness_score(spec)
        assert 0 < score <= 1.0


class TestFogScheduler:
    """Tests for FogScheduler."""

    @pytest.fixture
    def scheduler(self):
        """Create a scheduler instance."""
        return FogScheduler()

    @pytest.fixture
    def scheduler_with_nodes(self, scheduler):
        """Create a scheduler with registered nodes."""
        scheduler.register_node(FogNode(
            node_id="node-1",
            hostname="desktop-1",
            cpu_cores=8,
            memory_mb=16384,
            disk_mb=102400,
        ))
        scheduler.register_node(FogNode(
            node_id="node-2",
            hostname="laptop-1",
            cpu_cores=4,
            memory_mb=8192,
            disk_mb=51200,
        ))
        return scheduler

    def test_scheduler_creation(self, scheduler):
        """Test scheduler creation."""
        assert scheduler.config.default_strategy == PlacementStrategy.RESOURCE_FIT
        assert scheduler._is_running is False

    @pytest.mark.asyncio
    async def test_start_stop(self, scheduler):
        """Test scheduler start and stop."""
        await scheduler.start()
        assert scheduler._is_running is True

        await scheduler.stop()
        assert scheduler._is_running is False

    def test_register_node(self, scheduler):
        """Test node registration."""
        node = FogNode(node_id="test-node", hostname="test-host")
        scheduler.register_node(node)
        assert "test-node" in scheduler._nodes
        assert scheduler._nodes["test-node"].last_heartbeat is not None

    def test_unregister_node(self, scheduler_with_nodes):
        """Test node unregistration."""
        scheduler_with_nodes.unregister_node("node-1")
        assert "node-1" not in scheduler_with_nodes._nodes
        assert "node-2" in scheduler_with_nodes._nodes

    def test_update_node_metrics(self, scheduler_with_nodes):
        """Test node metrics update."""
        scheduler_with_nodes.update_node_metrics(
            "node-1",
            cpu_used_cores=4.0,
            memory_used_mb=8192,
        )
        node = scheduler_with_nodes._nodes["node-1"]
        assert node.cpu_used_cores == 4.0
        assert node.memory_used_mb == 8192

    @pytest.mark.asyncio
    async def test_submit_container(self, scheduler_with_nodes):
        """Test container submission."""
        spec = ContainerSpec(image="nginx", name="web")
        container = await scheduler_with_nodes.submit_container(spec)

        assert container.container_id in scheduler_with_nodes._containers
        assert container.status == ContainerStatus.PENDING
        assert container.container_id in scheduler_with_nodes._pending_queue

    @pytest.mark.asyncio
    async def test_container_scheduling(self, scheduler_with_nodes):
        """Test container gets scheduled to a node."""
        await scheduler_with_nodes.start()

        spec = ContainerSpec(
            image="nginx",
            resources=ResourceLimits(cpu_cores=1.0, memory_mb=512),
        )
        container = await scheduler_with_nodes.submit_container(spec)

        # Wait for scheduling
        await asyncio.sleep(0.1)
        await scheduler_with_nodes._process_pending()

        assert container.node_id is not None
        assert container.status == ContainerStatus.CREATING

        await scheduler_with_nodes.stop()

    @pytest.mark.asyncio
    async def test_placement_spread_strategy(self, scheduler_with_nodes):
        """Test spread placement strategy."""
        scheduler_with_nodes.config.default_strategy = PlacementStrategy.SPREAD

        spec1 = ContainerSpec(image="app1", resources=ResourceLimits(cpu_cores=1.0))
        spec2 = ContainerSpec(image="app2", resources=ResourceLimits(cpu_cores=1.0))

        container1 = await scheduler_with_nodes.submit_container(spec1)
        await scheduler_with_nodes._process_pending()

        container2 = await scheduler_with_nodes.submit_container(spec2)
        await scheduler_with_nodes._process_pending()

        # Should be placed on different nodes
        assert container1.node_id != container2.node_id

    @pytest.mark.asyncio
    async def test_placement_binpack_strategy(self, scheduler_with_nodes):
        """Test binpack placement strategy."""
        scheduler_with_nodes.config.default_strategy = PlacementStrategy.BINPACK

        # Add some load to node-1
        scheduler_with_nodes._nodes["node-1"].cpu_used_cores = 2.0

        spec = ContainerSpec(image="app", resources=ResourceLimits(cpu_cores=1.0))
        container = await scheduler_with_nodes.submit_container(spec)
        await scheduler_with_nodes._process_pending()

        # Should prefer the more loaded node
        assert container.node_id == "node-1"

    @pytest.mark.asyncio
    async def test_no_available_nodes(self, scheduler):
        """Test scheduling when no nodes available."""
        spec = ContainerSpec(
            image="big-app",
            resources=ResourceLimits(cpu_cores=100.0),  # Impossible requirement
        )
        container = await scheduler.submit_container(spec)
        await scheduler._process_pending()

        # Should still be pending (no node can fit)
        assert container.status == ContainerStatus.PENDING

    @pytest.mark.asyncio
    async def test_stop_container(self, scheduler_with_nodes):
        """Test stopping a container."""
        spec = ContainerSpec(image="nginx")
        container = await scheduler_with_nodes.submit_container(spec)
        await scheduler_with_nodes._process_pending()

        # Simulate running state
        container.status = ContainerStatus.RUNNING

        result = await scheduler_with_nodes.stop_container(container.container_id)
        assert result is True
        assert container.status == ContainerStatus.STOPPING

    @pytest.mark.asyncio
    async def test_remove_container(self, scheduler_with_nodes):
        """Test removing a container."""
        spec = ContainerSpec(image="nginx")
        container = await scheduler_with_nodes.submit_container(spec)
        container.status = ContainerStatus.STOPPED

        result = await scheduler_with_nodes.remove_container(container.container_id)
        assert result is True
        assert container.container_id not in scheduler_with_nodes._containers

    def test_handle_container_started(self, scheduler_with_nodes):
        """Test handling container start notification."""
        container = Container(spec=ContainerSpec(image="test"))
        scheduler_with_nodes._containers[container.container_id] = container

        scheduler_with_nodes.handle_container_started(
            container.container_id,
            ip_address="10.200.0.5",
            pid=12345,
        )

        assert container.status == ContainerStatus.RUNNING
        assert container.ip_address == "10.200.0.5"
        assert container.pid == 12345

    def test_handle_container_stopped(self, scheduler_with_nodes):
        """Test handling container stop notification."""
        spec = ContainerSpec(image="test", resources=ResourceLimits(cpu_cores=2.0))
        container = Container(spec=spec)
        container.node_id = "node-1"
        container.status = ContainerStatus.RUNNING
        scheduler_with_nodes._containers[container.container_id] = container
        scheduler_with_nodes._nodes["node-1"].cpu_used_cores = 2.0

        scheduler_with_nodes.handle_container_stopped(
            container.container_id,
            exit_code=0,
        )

        assert container.status == ContainerStatus.STOPPED
        assert container.exit_code == 0
        assert scheduler_with_nodes._nodes["node-1"].cpu_used_cores == 0

    def test_get_stats(self, scheduler_with_nodes):
        """Test getting scheduler stats."""
        stats = scheduler_with_nodes.get_stats()
        assert stats["total_nodes"] == 2
        assert stats["available_nodes"] == 2
        assert "cpu_utilization_percent" in stats


# ============================================================================
# Storage Tests
# ============================================================================

class TestDistributedVolumeManager:
    """Tests for DistributedVolumeManager."""

    @pytest.fixture
    def volume_manager(self):
        """Create a volume manager instance."""
        return DistributedVolumeManager()

    @pytest.fixture
    def volume_manager_with_nodes(self, volume_manager):
        """Create a volume manager with registered nodes."""
        volume_manager.register_node_storage("node-1", total_mb=102400, used_mb=0)
        volume_manager.register_node_storage("node-2", total_mb=51200, used_mb=0)
        volume_manager.register_node_storage("node-3", total_mb=51200, used_mb=0)
        return volume_manager

    def test_manager_creation(self, volume_manager):
        """Test volume manager creation."""
        assert volume_manager.config.default_replication_factor == 2
        assert volume_manager._is_running is False

    def test_register_node_storage(self, volume_manager):
        """Test node storage registration."""
        volume_manager.register_node_storage("test-node", total_mb=10240)
        assert "test-node" in volume_manager._node_storage
        assert volume_manager._node_storage["test-node"]["total_mb"] == 10240

    @pytest.mark.asyncio
    async def test_create_local_volume(self, volume_manager_with_nodes):
        """Test creating a local volume."""
        volume = await volume_manager_with_nodes.create_volume(
            name="local-data",
            volume_type=VolumeType.LOCAL,
            size_mb=1024,
        )

        assert volume.name == "local-data"
        assert volume.volume_type == VolumeType.LOCAL
        assert volume.replication_factor == 1
        assert volume.is_ready is True

    @pytest.mark.asyncio
    async def test_create_distributed_volume(self, volume_manager_with_nodes):
        """Test creating a distributed volume."""
        volume = await volume_manager_with_nodes.create_volume(
            name="shared-data",
            volume_type=VolumeType.DISTRIBUTED,
            size_mb=2048,
            replication_factor=2,
        )

        assert volume.name == "shared-data"
        assert volume.volume_type == VolumeType.DISTRIBUTED
        assert volume.replication_factor == 2
        assert volume.is_ready is True
        assert len(volume.replica_node_ids) == 1  # Primary + 1 replica

    @pytest.mark.asyncio
    async def test_create_volume_unique_name(self, volume_manager_with_nodes):
        """Test volume name uniqueness."""
        await volume_manager_with_nodes.create_volume(name="my-vol")

        with pytest.raises(ValueError, match="already exists"):
            await volume_manager_with_nodes.create_volume(name="my-vol")

    @pytest.mark.asyncio
    async def test_get_volume(self, volume_manager_with_nodes):
        """Test getting a volume."""
        created = await volume_manager_with_nodes.create_volume(name="test-vol")

        found = volume_manager_with_nodes.get_volume(created.volume_id)
        assert found == created

        by_name = volume_manager_with_nodes.get_volume_by_name("test-vol")
        assert by_name == created

    @pytest.mark.asyncio
    async def test_list_volumes(self, volume_manager_with_nodes):
        """Test listing volumes."""
        await volume_manager_with_nodes.create_volume(name="vol1", volume_type=VolumeType.LOCAL)
        await volume_manager_with_nodes.create_volume(name="vol2", volume_type=VolumeType.DISTRIBUTED)

        all_volumes = volume_manager_with_nodes.list_volumes()
        assert len(all_volumes) == 2

        local_only = volume_manager_with_nodes.list_volumes(volume_type=VolumeType.LOCAL)
        assert len(local_only) == 1

    @pytest.mark.asyncio
    async def test_delete_volume(self, volume_manager_with_nodes):
        """Test deleting a volume."""
        volume = await volume_manager_with_nodes.create_volume(name="to-delete")

        result = await volume_manager_with_nodes.delete_volume(volume.volume_id)
        assert result is True
        assert volume_manager_with_nodes.get_volume(volume.volume_id) is None

    @pytest.mark.asyncio
    async def test_resize_volume(self, volume_manager_with_nodes):
        """Test resizing a volume."""
        volume = await volume_manager_with_nodes.create_volume(name="resizable", size_mb=1024)

        result = await volume_manager_with_nodes.resize_volume(volume.volume_id, 2048)
        assert result is True
        assert volume.size_mb == 2048

    @pytest.mark.asyncio
    async def test_resolve_volume_mount_local(self, volume_manager_with_nodes):
        """Test resolving a volume mount to local path."""
        volume = await volume_manager_with_nodes.create_volume(
            name="app-data",
            preferred_node_id="node-1",
        )

        mount = VolumeMount(source="app-data", target="/data")

        # Set local path for the replica
        replicas = volume_manager_with_nodes.get_volume_replicas(volume.volume_id)
        for replica in replicas:
            if replica.node_id == "node-1":
                replica.local_path = "/var/fog/volumes/app-data"

        result = volume_manager_with_nodes.resolve_volume_mount(mount, "node-1")
        assert result["type"] == "volume"
        assert result["is_local"] is True

    def test_get_stats(self, volume_manager_with_nodes):
        """Test getting volume manager stats."""
        stats = volume_manager_with_nodes.get_stats()
        assert stats["nodes_with_storage"] == 3
        assert stats["total_storage_mb"] > 0


# ============================================================================
# Network Tests
# ============================================================================

class TestFogNetworkManager:
    """Tests for FogNetworkManager."""

    @pytest.fixture
    def network_manager(self):
        """Create a network manager instance."""
        return FogNetworkManager()

    @pytest.fixture
    def network_manager_with_nodes(self, network_manager):
        """Create a network manager with registered nodes."""
        network_manager.register_node("node-1", "192.168.1.10")
        network_manager.register_node("node-2", "192.168.1.11")
        return network_manager

    def test_manager_creation(self, network_manager):
        """Test network manager creation."""
        assert network_manager.config.overlay_subnet == "10.200.0.0/16"

    def test_register_node(self, network_manager):
        """Test node registration."""
        network_manager.register_node("test-node", "10.0.0.1")
        assert "test-node" in network_manager._node_ips
        assert network_manager._node_ips["test-node"] == "10.0.0.1"

    @pytest.mark.asyncio
    async def test_create_network(self, network_manager):
        """Test network creation."""
        network = await network_manager.create_network(
            name="my-network",
            subnet="10.100.0.0/24",
        )

        assert network.name == "my-network"
        assert network.subnet == "10.100.0.0/24"
        assert network.gateway == "10.100.0.1"
        assert network.dns_enabled is True

    @pytest.mark.asyncio
    async def test_create_network_unique_name(self, network_manager):
        """Test network name uniqueness."""
        await network_manager.create_network(name="test-net")

        with pytest.raises(ValueError, match="already exists"):
            await network_manager.create_network(name="test-net")

    @pytest.mark.asyncio
    async def test_get_network(self, network_manager):
        """Test getting a network."""
        created = await network_manager.create_network(name="find-me")

        found = network_manager.get_network(created.network_id)
        assert found == created

        by_name = network_manager.get_network_by_name("find-me")
        assert by_name == created

    @pytest.mark.asyncio
    async def test_delete_network(self, network_manager):
        """Test deleting a network."""
        network = await network_manager.create_network(name="to-delete")

        result = await network_manager.delete_network(network.network_id)
        assert result is True
        assert network_manager.get_network(network.network_id) is None

    @pytest.mark.asyncio
    async def test_connect_container(self, network_manager_with_nodes):
        """Test connecting a container to a network."""
        network = await network_manager_with_nodes.create_network(name="app-net")

        endpoint = await network_manager_with_nodes.connect_container(
            container_id="container-1",
            container_name="web",
            node_id="node-1",
            network_id=network.network_id,
        )

        assert endpoint.container_id == "container-1"
        assert endpoint.ip_address is not None
        assert endpoint.mac_address.startswith("02:46:6f:67")  # "Fog" prefix
        assert "web" in endpoint.dns_names

    @pytest.mark.asyncio
    async def test_connect_container_with_aliases(self, network_manager_with_nodes):
        """Test connecting with DNS aliases."""
        network = await network_manager_with_nodes.create_network(name="app-net")

        endpoint = await network_manager_with_nodes.connect_container(
            container_id="container-1",
            container_name="web",
            node_id="node-1",
            network_id=network.network_id,
            aliases=["frontend", "ui"],
        )

        assert "web" in endpoint.dns_names
        assert "frontend" in endpoint.dns_names
        assert "ui" in endpoint.dns_names

    @pytest.mark.asyncio
    async def test_disconnect_container(self, network_manager_with_nodes):
        """Test disconnecting a container."""
        network = await network_manager_with_nodes.create_network(name="app-net")

        await network_manager_with_nodes.connect_container(
            container_id="container-1",
            container_name="web",
            node_id="node-1",
            network_id=network.network_id,
        )

        result = await network_manager_with_nodes.disconnect_container("container-1")
        assert result is True
        assert network_manager_with_nodes.get_container_ip("container-1") is None

    @pytest.mark.asyncio
    async def test_allocate_host_port(self, network_manager_with_nodes):
        """Test host port allocation."""
        mapping = PortMapping(container_port=80)

        port = await network_manager_with_nodes.allocate_host_port(
            mapping,
            container_id="container-1",
            node_id="node-1",
        )

        assert port >= network_manager_with_nodes.config.host_port_range_start
        assert port <= network_manager_with_nodes.config.host_port_range_end

    @pytest.mark.asyncio
    async def test_allocate_specific_host_port(self, network_manager_with_nodes):
        """Test specific host port allocation."""
        mapping = PortMapping(container_port=80, host_port=8080)

        port = await network_manager_with_nodes.allocate_host_port(
            mapping,
            container_id="container-1",
            node_id="node-1",
        )

        assert port == 8080

    @pytest.mark.asyncio
    async def test_port_conflict(self, network_manager_with_nodes):
        """Test port conflict detection."""
        mapping1 = PortMapping(container_port=80, host_port=8080)
        mapping2 = PortMapping(container_port=80, host_port=8080)

        await network_manager_with_nodes.allocate_host_port(mapping1, "c1", "node-1")

        with pytest.raises(ValueError, match="already in use"):
            await network_manager_with_nodes.allocate_host_port(mapping2, "c2", "node-1")

    @pytest.mark.asyncio
    async def test_dns_resolution(self, network_manager_with_nodes):
        """Test DNS name resolution."""
        network = await network_manager_with_nodes.create_network(name="app-net")

        await network_manager_with_nodes.connect_container(
            container_id="container-1",
            container_name="db",
            node_id="node-1",
            network_id=network.network_id,
        )

        ip = network_manager_with_nodes.resolve_dns(f"db.{network.dns_domain}")
        assert ip is not None
        assert ip.startswith("10.")

    @pytest.mark.asyncio
    async def test_get_routing_info(self, network_manager_with_nodes):
        """Test getting routing info."""
        network = await network_manager_with_nodes.create_network(name="app-net")

        await network_manager_with_nodes.connect_container(
            container_id="web",
            container_name="web",
            node_id="node-1",
            network_id=network.network_id,
        )

        ep2 = await network_manager_with_nodes.connect_container(
            container_id="db",
            container_name="db",
            node_id="node-2",
            network_id=network.network_id,
        )

        routing = network_manager_with_nodes.get_routing_info("web", ep2.ip_address)
        assert routing is not None
        assert routing["target_node_id"] == "node-2"
        assert routing["same_node"] is False

    def test_get_stats(self, network_manager_with_nodes):
        """Test getting network manager stats."""
        stats = network_manager_with_nodes.get_stats()
        assert stats["registered_nodes"] == 2


# ============================================================================
# Integration Tests
# ============================================================================

class TestContainerRuntimeIntegration:
    """Integration tests for the full container runtime."""

    @pytest.fixture
    def runtime_components(self):
        """Create all runtime components."""
        scheduler = FogScheduler()
        volume_manager = DistributedVolumeManager()
        network_manager = FogNetworkManager()

        # Register nodes
        for i in range(1, 4):
            node = FogNode(
                node_id=f"node-{i}",
                hostname=f"fog-device-{i}",
                cpu_cores=4,
                memory_mb=8192,
                disk_mb=102400,
            )
            scheduler.register_node(node)
            volume_manager.register_node_storage(f"node-{i}", 102400, 0)
            network_manager.register_node(f"node-{i}", f"192.168.1.{10 + i}")

        return scheduler, volume_manager, network_manager

    @pytest.mark.asyncio
    async def test_deploy_container_with_volume(self, runtime_components):
        """Test deploying a container with a volume."""
        scheduler, volume_manager, network_manager = runtime_components

        # Create a volume
        volume = await volume_manager.create_volume(
            name="postgres-data",
            volume_type=VolumeType.DISTRIBUTED,
            size_mb=5120,
        )

        # Create container spec with volume mount
        spec = ContainerSpec(
            image="postgres:15",
            name="database",
            environment={"POSTGRES_PASSWORD": "secret"},
            resources=ResourceLimits(cpu_cores=2.0, memory_mb=2048),
            volumes=[VolumeMount(
                source="postgres-data",
                target="/var/lib/postgresql/data",
                volume_type=VolumeType.DISTRIBUTED,
            )],
            ports=[PortMapping(container_port=5432)],
        )

        # Submit container
        container = await scheduler.submit_container(spec)
        await scheduler._process_pending()

        # Verify scheduling
        assert container.node_id is not None
        assert container.status == ContainerStatus.CREATING

        # Verify volume exists
        assert volume_manager.get_volume_by_name("postgres-data") is not None

    @pytest.mark.asyncio
    async def test_deploy_multi_container_app(self, runtime_components):
        """Test deploying a multi-container application."""
        scheduler, volume_manager, network_manager = runtime_components

        # Create app network
        network = await network_manager.create_network(name="myapp")

        # Deploy database
        db_spec = ContainerSpec(
            image="postgres:15",
            name="db",
            resources=ResourceLimits(cpu_cores=1.0, memory_mb=1024),
        )
        db_container = await scheduler.submit_container(db_spec)
        await scheduler._process_pending()

        # Deploy web server
        web_spec = ContainerSpec(
            image="nginx",
            name="web",
            resources=ResourceLimits(cpu_cores=0.5, memory_mb=256),
            ports=[PortMapping(container_port=80)],
        )
        web_container = await scheduler.submit_container(web_spec)
        await scheduler._process_pending()

        # Both should be scheduled
        assert db_container.node_id is not None
        assert web_container.node_id is not None

        # Connect to network
        await network_manager.connect_container(
            db_container.container_id,
            "db",
            db_container.node_id,
            network.network_id,
        )
        await network_manager.connect_container(
            web_container.container_id,
            "web",
            web_container.node_id,
            network.network_id,
        )

        # Verify network connectivity
        db_ip = network_manager.get_container_ip(db_container.container_id)
        web_ip = network_manager.get_container_ip(web_container.container_id)
        assert db_ip is not None
        assert web_ip is not None

    @pytest.mark.asyncio
    async def test_container_lifecycle(self, runtime_components):
        """Test full container lifecycle."""
        scheduler, volume_manager, network_manager = runtime_components

        # Create and schedule container
        spec = ContainerSpec(image="redis", name="cache")
        container = await scheduler.submit_container(spec)
        await scheduler._process_pending()

        assert container.status == ContainerStatus.CREATING

        # Simulate container start
        scheduler.handle_container_started(
            container.container_id,
            ip_address="10.200.0.5",
            pid=12345,
        )
        assert container.status == ContainerStatus.RUNNING

        # Update metrics
        scheduler.handle_container_metrics(
            container.container_id,
            cpu_percent=25.5,
            memory_mb=128,
            network_rx=1024,
            network_tx=512,
        )
        assert container.cpu_usage_percent == 25.5

        # Stop container
        scheduler.handle_container_stopped(
            container.container_id,
            exit_code=0,
        )
        assert container.status == ContainerStatus.STOPPED
        assert container.exit_code == 0

        # Remove container
        result = await scheduler.remove_container(container.container_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_resource_scheduling_limits(self, runtime_components):
        """Test that resource limits are respected."""
        scheduler, volume_manager, network_manager = runtime_components

        # Use up most resources on all nodes
        for node_id, node in scheduler._nodes.items():
            node.cpu_used_cores = node.cpu_cores - 0.5
            node.memory_used_mb = node.memory_mb - 256

        # Try to schedule a big container
        big_spec = ContainerSpec(
            image="big-app",
            resources=ResourceLimits(cpu_cores=4.0, memory_mb=4096),
        )
        container = await scheduler.submit_container(big_spec)
        await scheduler._process_pending()

        # Should remain pending (no node can fit)
        assert container.status == ContainerStatus.PENDING
        assert container.node_id is None


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
