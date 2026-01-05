"""
Integration tests for container orchestration.
Verifies Docker client lifecycle, mock fallback, scheduler transitions, and load balancer integration.
"""
import importlib
import importlib.util
from pathlib import Path
import sys
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
try:
    import pytest_asyncio
except ModuleNotFoundError:
    pytest_asyncio = SimpleNamespace(fixture=pytest.fixture)

from server.models.deployment import DeploymentReplica, ReplicaStatus
from server.services import docker_client as docker_module
from server.services import scheduler as scheduler_module
from server.services.docker_client import ContainerConfig, DockerClient, DockerClientError


class FakeContainer:
    """Simple fake container with lifecycle flags."""

    def __init__(self, name: str):
        self.name = name
        self.id = f"real-{uuid.uuid4().hex[:12]}"
        self.started = False
        self.stopped = False
        self.deleted = False

    async def start(self):
        self.started = True

    async def stop(self, t: int = 10):
        self.stopped = True

    async def delete(self, force: bool = False):
        self.deleted = True

    async def show(self):
        return {
            "Name": self.name,
            "Config": {"Image": "nginx:latest"},
            "State": {
                "Status": "running" if self.started and not self.deleted else "created",
                "StartedAt": "2024-01-01T00:00:00Z" if self.started else "",
                "FinishedAt": "2024-01-01T00:10:00Z" if self.stopped else "",
                "ExitCode": 0,
            },
            "Created": "2024-01-01T00:00:00Z",
            "NetworkSettings": {"Ports": {}},
        }


class FakeContainerManager:
    """Fake container manager replicating a subset of aiodocker API."""

    def __init__(self):
        self.containers = {}

    async def create(self, config, name):
        container = FakeContainer(name)
        self.containers[container.id] = container
        return container

    async def get(self, container_id: str):
        if container_id not in self.containers:
            raise RuntimeError("container not found")
        return self.containers[container_id]


class FakeDocker:
    """Fake aiodocker client returning fake containers."""

    def __init__(self):
        self.containers = FakeContainerManager()
        self.closed = False

    async def version(self):
        return {"Version": "test"}

    async def close(self):
        self.closed = True


class FailingDocker(FakeDocker):
    """Fake client that simulates daemon unavailability."""

    async def version(self):
        raise RuntimeError("docker unavailable")


@pytest.fixture
def mock_mode_client(monkeypatch):
    """Fresh DockerClient in mock mode with clean state."""
    monkeypatch.setattr(docker_module, "DOCKER_ENABLED", False)
    client = DockerClient()
    client._mock_containers.clear()
    return client


def _patch_aiodocker(monkeypatch, docker_impl):
    """Insert a fake aiodocker module with the provided Docker implementation."""
    fake_module = SimpleNamespace(Docker=docker_impl)
    monkeypatch.setitem(sys.modules, "aiodocker", fake_module)


@pytest.fixture
def deployment_routes(monkeypatch):
    """
    Import deployment routes with a stubbed database module to avoid runtime database dependencies.
    """
    dummy_database = SimpleNamespace(
        get_db=AsyncMock(),
        get_db_context=AsyncMock(),
    )
    monkeypatch.setitem(sys.modules, "server.database", dummy_database)
    module_name = "server.routes.deployment"
    module_path = Path(__file__).resolve().parents[1] / "server" / "routes" / "deployment.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    deployment_module = importlib.util.module_from_spec(spec)
    deployment_module.__package__ = "server.routes"
    sys.modules[module_name] = deployment_module
    assert spec and spec.loader
    spec.loader.exec_module(deployment_module)
    return deployment_module


@pytest.mark.asyncio
async def test_mock_container_lifecycle(mock_mode_client):
    """Ensure mock lifecycle covers create -> start -> stop -> remove."""
    config = ContainerConfig(
        image="nginx:latest",
        name="mock-container",
        cpu_limit=0.5,
        memory_limit=128,
    )

    container_id = await mock_mode_client.create_container(config)
    assert container_id in mock_mode_client._mock_containers
    assert mock_mode_client._mock_containers[container_id].status == "created"

    started = await mock_mode_client.start_container(container_id)
    assert started is True
    assert mock_mode_client._mock_containers[container_id].status == "running"

    stopped = await mock_mode_client.stop_container(container_id)
    assert stopped is True
    assert mock_mode_client._mock_containers[container_id].status == "exited"

    removed = await mock_mode_client.remove_container(container_id)
    assert removed is True
    assert container_id not in mock_mode_client._mock_containers

    # Error handling: non-existent container returns False
    assert await mock_mode_client.start_container(container_id) is False
    assert await mock_mode_client.stop_container(container_id) is False
    assert await mock_mode_client.remove_container(container_id) is False


@pytest.mark.asyncio
async def test_real_docker_path_with_mocked_aiodocker(monkeypatch):
    """Verify Docker-backed lifecycle using mocked aiodocker implementation."""
    _patch_aiodocker(monkeypatch, FakeDocker)
    monkeypatch.setattr(docker_module, "DOCKER_ENABLED", True)

    client = DockerClient()
    connected = await client.connect()
    assert connected is True
    assert client.is_connected

    config = ContainerConfig(
        image="nginx:latest",
        name="real-container",
        cpu_limit=1.0,
        memory_limit=256,
    )

    container_id = await client.create_container(config)
    assert container_id in client._client.containers.containers

    assert await client.start_container(container_id) is True
    assert client._client.containers.containers[container_id].started is True

    assert await client.stop_container(container_id) is True
    assert client._client.containers.containers[container_id].stopped is True

    assert await client.remove_container(container_id) is True
    assert client._client.containers.containers[container_id].deleted is True


@pytest.mark.asyncio
async def test_fallback_when_docker_unavailable(monkeypatch):
    """Ensure client falls back to mock mode when Docker daemon cannot be reached."""
    _patch_aiodocker(monkeypatch, FailingDocker)
    monkeypatch.setattr(docker_module, "DOCKER_ENABLED", True)

    client = DockerClient()
    connected = await client.connect()
    assert connected is False
    assert client.is_connected is False

    config = ContainerConfig(
        image="nginx:latest",
        name="fallback-container",
        cpu_limit=1.0,
        memory_limit=256,
    )

    container_id = await client.create_container(config)
    assert container_id.startswith("mock-")

    assert await client.start_container(container_id) is True
    assert await client.stop_container(container_id) is True
    assert await client.remove_container(container_id) is True


@pytest.mark.asyncio
async def test_scheduler_transitions_replicas_with_docker_client(monkeypatch):
    """Scheduler should mark replicas running and assign container IDs when orchestration succeeds."""
    class SuccessfulClient:
        def __init__(self):
            self.created_configs = []
            self.started_containers = []

        async def create_container(self, config):
            self.created_configs.append(config)
            return f"real-{config.name}"

        async def start_container(self, container_id: str):
            self.started_containers.append(container_id)
            return True

    successful_client = SuccessfulClient()
    monkeypatch.setattr(
        scheduler_module,
        "get_docker_client",
        AsyncMock(return_value=successful_client),
    )

    replica = DeploymentReplica(
        id=uuid.uuid4(),
        deployment_id=uuid.uuid4(),
        node_id=uuid.uuid4(),
        status=ReplicaStatus.PENDING,
    )

    await scheduler_module.scheduler._transition_replicas_to_running(
        AsyncMock(), [replica], container_image="demo:latest", cpu_cores=0.5, memory_mb=64
    )

    assert replica.status == ReplicaStatus.RUNNING
    assert replica.container_id.startswith("real-")
    assert successful_client.created_configs
    assert successful_client.started_containers == [replica.container_id]


@pytest.mark.asyncio
async def test_scheduler_stub_container_on_unexpected_error(monkeypatch):
    """Scheduler should fall back to stub containers when orchestration raises unexpected errors."""
    class UnexpectedErrorClient:
        async def create_container(self, config):
            raise RuntimeError("network partition")

        async def start_container(self, container_id: str):
            return True

    monkeypatch.setattr(
        scheduler_module,
        "get_docker_client",
        AsyncMock(return_value=UnexpectedErrorClient()),
    )

    replica = DeploymentReplica(
        id=uuid.uuid4(),
        deployment_id=uuid.uuid4(),
        node_id=uuid.uuid4(),
        status=ReplicaStatus.PENDING,
    )

    await scheduler_module.scheduler._transition_replicas_to_running(
        AsyncMock(), [replica], container_image="demo:latest", cpu_cores=0.5, memory_mb=64
    )

    assert replica.status == ReplicaStatus.RUNNING
    assert replica.container_id.startswith("mock-container-")


@pytest.mark.asyncio
async def test_scheduler_marks_failure_on_docker_client_error(monkeypatch):
    """DockerClientError should mark the replica as failed during scaling transitions."""
    class ErroringClient:
        async def create_container(self, config):
            raise DockerClientError("permission denied")

        async def start_container(self, container_id: str):
            return True

    monkeypatch.setattr(
        scheduler_module,
        "get_docker_client",
        AsyncMock(return_value=ErroringClient()),
    )

    replica = DeploymentReplica(
        id=uuid.uuid4(),
        deployment_id=uuid.uuid4(),
        node_id=uuid.uuid4(),
        status=ReplicaStatus.PENDING,
    )

    await scheduler_module.scheduler._transition_replicas_to_running(
        AsyncMock(), [replica], container_image="demo:latest", cpu_cores=0.5, memory_mb=64
    )

    assert replica.status == ReplicaStatus.FAILED
    assert replica.container_id is None


@pytest.mark.asyncio
async def test_load_balancer_update_respects_environment(monkeypatch, deployment_routes):
    """Load balancer updates should be no-ops when disabled and succeed when enabled."""
    # Disabled path
    monkeypatch.setenv("LOAD_BALANCER_ENABLED", "false")
    disabled_result = await deployment_routes._update_load_balancer_routes(
        deployment_id="deploy-123",
        action="add",
        endpoints=["localhost:8080"],
    )
    assert disabled_result is True

    # Enabled path with mocked HTTP client
    monkeypatch.setenv("LOAD_BALANCER_ENABLED", "true")
    monkeypatch.setenv("LOAD_BALANCER_TYPE", "nginx")
    monkeypatch.setenv("LOAD_BALANCER_API_URL", "http://lb.example/api")

    # Mock httpx.AsyncClient to avoid real network calls
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = AsyncMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.delete = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: mock_client)

    enabled_result = await deployment_routes._update_load_balancer_routes(
        deployment_id="deploy-123",
        action="add",
        endpoints=["localhost:8080", "localhost:8081"],
    )
    assert enabled_result is True

    remove_result = await deployment_routes._update_load_balancer_routes(
        deployment_id="deploy-123",
        action="remove",
    )
    assert remove_result is True
