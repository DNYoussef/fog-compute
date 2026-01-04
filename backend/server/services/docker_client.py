"""
Docker Client Service
Async wrapper for Docker container orchestration using aiodocker.
Provides create, start, stop, remove operations with fallback support.
"""
import asyncio
import logging
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Feature flag for Docker integration (graceful fallback when Docker unavailable)
DOCKER_ENABLED = os.environ.get("DOCKER_ENABLED", "false").lower() == "true"


@dataclass
class ContainerConfig:
    """Configuration for container creation"""
    image: str
    name: str
    cpu_limit: float  # CPU cores (e.g., 2.0)
    memory_limit: int  # Memory in MB
    env: Optional[Dict[str, str]] = None
    ports: Optional[Dict[str, int]] = None  # container_port: host_port
    volumes: Optional[Dict[str, str]] = None  # host_path: container_path
    network: Optional[str] = None
    labels: Optional[Dict[str, str]] = None


@dataclass
class ContainerInfo:
    """Container status information"""
    container_id: str
    name: str
    status: str  # running, stopped, created, exited
    image: str
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    exit_code: Optional[int] = None
    ports: Optional[Dict[str, Any]] = None


class DockerClientError(Exception):
    """Custom exception for Docker client errors"""
    pass


class DockerClient:
    """
    Async Docker client wrapper using aiodocker.
    Provides graceful fallback when Docker daemon is unavailable.
    """

    def __init__(self):
        self._client = None
        self._connected = False
        self._mock_containers: Dict[str, ContainerInfo] = {}

    async def connect(self) -> bool:
        """
        Connect to Docker daemon.
        Returns True if connected, False if using mock mode.
        """
        if not DOCKER_ENABLED:
            logger.info("Docker integration disabled (DOCKER_ENABLED=false). Using mock mode.")
            return False

        try:
            import aiodocker
            self._client = aiodocker.Docker()
            # Test connection
            await self._client.version()
            self._connected = True
            logger.info("Connected to Docker daemon")
            return True
        except ImportError:
            logger.warning("aiodocker not installed. Using mock mode.")
            return False
        except Exception as e:
            logger.warning(f"Cannot connect to Docker daemon: {e}. Using mock mode.")
            self._client = None
            self._connected = False
            return False

    async def disconnect(self):
        """Disconnect from Docker daemon"""
        if self._client:
            await self._client.close()
            self._client = None
            self._connected = False
            logger.info("Disconnected from Docker daemon")

    @property
    def is_connected(self) -> bool:
        """Check if connected to Docker daemon"""
        return self._connected and self._client is not None

    async def create_container(self, config: ContainerConfig) -> str:
        """
        Create a new container from config.

        Args:
            config: ContainerConfig with image, resources, etc.

        Returns:
            Container ID (real or mock)
        """
        if not self.is_connected:
            return await self._mock_create_container(config)

        try:
            # Build Docker API config
            container_config = {
                "Image": config.image,
                "HostConfig": {
                    "NanoCpus": int(config.cpu_limit * 1e9),  # Convert cores to nanocores
                    "Memory": config.memory_limit * 1024 * 1024,  # Convert MB to bytes
                },
            }

            if config.env:
                container_config["Env"] = [f"{k}={v}" for k, v in config.env.items()]

            if config.ports:
                container_config["ExposedPorts"] = {
                    f"{port}/tcp": {} for port in config.ports.keys()
                }
                container_config["HostConfig"]["PortBindings"] = {
                    f"{port}/tcp": [{"HostPort": str(host_port)}]
                    for port, host_port in config.ports.items()
                }

            if config.labels:
                container_config["Labels"] = config.labels

            if config.network:
                container_config["HostConfig"]["NetworkMode"] = config.network

            # Create container
            container = await self._client.containers.create(
                config=container_config,
                name=config.name
            )

            container_id = container.id
            logger.info(f"Created container {container_id} ({config.name}) from {config.image}")
            return container_id

        except Exception as e:
            logger.error(f"Failed to create container: {e}")
            raise DockerClientError(f"Container creation failed: {e}")

    async def start_container(self, container_id: str) -> bool:
        """
        Start a container.

        Args:
            container_id: Docker container ID

        Returns:
            True if started successfully
        """
        if not self.is_connected:
            return await self._mock_start_container(container_id)

        try:
            container = await self._client.containers.get(container_id)
            await container.start()
            logger.info(f"Started container {container_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to start container {container_id}: {e}")
            raise DockerClientError(f"Container start failed: {e}")

    async def stop_container(self, container_id: str, timeout: int = 10) -> bool:
        """
        Stop a running container.

        Args:
            container_id: Docker container ID
            timeout: Seconds to wait before killing

        Returns:
            True if stopped successfully
        """
        if not self.is_connected:
            return await self._mock_stop_container(container_id)

        try:
            container = await self._client.containers.get(container_id)
            await container.stop(t=timeout)
            logger.info(f"Stopped container {container_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to stop container {container_id}: {e}")
            raise DockerClientError(f"Container stop failed: {e}")

    async def remove_container(self, container_id: str, force: bool = False) -> bool:
        """
        Remove a container.

        Args:
            container_id: Docker container ID
            force: Force remove even if running

        Returns:
            True if removed successfully
        """
        if not self.is_connected:
            return await self._mock_remove_container(container_id)

        try:
            container = await self._client.containers.get(container_id)
            await container.delete(force=force)
            logger.info(f"Removed container {container_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove container {container_id}: {e}")
            raise DockerClientError(f"Container removal failed: {e}")

    async def get_container_info(self, container_id: str) -> Optional[ContainerInfo]:
        """
        Get container status information.

        Args:
            container_id: Docker container ID

        Returns:
            ContainerInfo or None if not found
        """
        if not self.is_connected:
            return self._mock_containers.get(container_id)

        try:
            container = await self._client.containers.get(container_id)
            info = await container.show()

            state = info.get("State", {})

            return ContainerInfo(
                container_id=container_id,
                name=info.get("Name", "").lstrip("/"),
                status=state.get("Status", "unknown"),
                image=info.get("Config", {}).get("Image", ""),
                created_at=datetime.fromisoformat(
                    info.get("Created", "").replace("Z", "+00:00")
                ),
                started_at=datetime.fromisoformat(
                    state.get("StartedAt", "").replace("Z", "+00:00")
                ) if state.get("StartedAt") else None,
                finished_at=datetime.fromisoformat(
                    state.get("FinishedAt", "").replace("Z", "+00:00")
                ) if state.get("FinishedAt") else None,
                exit_code=state.get("ExitCode"),
                ports=info.get("NetworkSettings", {}).get("Ports")
            )
        except Exception as e:
            logger.warning(f"Failed to get container info for {container_id}: {e}")
            return None

    async def list_containers(
        self,
        all_containers: bool = False,
        filters: Optional[Dict[str, str]] = None
    ) -> List[ContainerInfo]:
        """
        List containers.

        Args:
            all_containers: Include stopped containers
            filters: Filter by labels, status, etc.

        Returns:
            List of ContainerInfo
        """
        if not self.is_connected:
            return list(self._mock_containers.values())

        try:
            containers = await self._client.containers.list(
                all=all_containers,
                filters=filters
            )

            result = []
            for container in containers:
                info = await container.show()
                state = info.get("State", {})

                result.append(ContainerInfo(
                    container_id=container.id,
                    name=info.get("Name", "").lstrip("/"),
                    status=state.get("Status", "unknown"),
                    image=info.get("Config", {}).get("Image", ""),
                    created_at=datetime.fromisoformat(
                        info.get("Created", "").replace("Z", "+00:00")
                    ),
                ))

            return result
        except Exception as e:
            logger.error(f"Failed to list containers: {e}")
            return []

    # =========================================================================
    # Mock implementations for development/testing without Docker
    # =========================================================================

    async def _mock_create_container(self, config: ContainerConfig) -> str:
        """Create mock container for testing"""
        import uuid
        container_id = f"mock-{uuid.uuid4().hex[:12]}"

        self._mock_containers[container_id] = ContainerInfo(
            container_id=container_id,
            name=config.name,
            status="created",
            image=config.image,
            created_at=datetime.now(timezone.utc)
        )

        logger.info(f"[MOCK] Created container {container_id} ({config.name})")
        return container_id

    async def _mock_start_container(self, container_id: str) -> bool:
        """Start mock container"""
        if container_id in self._mock_containers:
            self._mock_containers[container_id].status = "running"
            self._mock_containers[container_id].started_at = datetime.now(timezone.utc)
            logger.info(f"[MOCK] Started container {container_id}")
            return True

        # Handle stub containers from scheduler
        if container_id.startswith("stub-container-"):
            logger.info(f"[MOCK] Started stub container {container_id}")
            return True

        logger.warning(f"[MOCK] Container {container_id} not found")
        return False

    async def _mock_stop_container(self, container_id: str) -> bool:
        """Stop mock container"""
        if container_id in self._mock_containers:
            self._mock_containers[container_id].status = "exited"
            self._mock_containers[container_id].finished_at = datetime.now(timezone.utc)
            self._mock_containers[container_id].exit_code = 0
            logger.info(f"[MOCK] Stopped container {container_id}")
            return True

        # Handle stub containers
        if container_id.startswith("stub-container-"):
            logger.info(f"[MOCK] Stopped stub container {container_id}")
            return True

        logger.warning(f"[MOCK] Container {container_id} not found")
        return False

    async def _mock_remove_container(self, container_id: str) -> bool:
        """Remove mock container"""
        if container_id in self._mock_containers:
            del self._mock_containers[container_id]
            logger.info(f"[MOCK] Removed container {container_id}")
            return True

        # Handle stub containers
        if container_id.startswith("stub-container-"):
            logger.info(f"[MOCK] Removed stub container {container_id}")
            return True

        logger.warning(f"[MOCK] Container {container_id} not found")
        return False


# Global singleton instance
docker_client = DockerClient()


async def get_docker_client() -> DockerClient:
    """
    Get Docker client instance.
    Ensures connection is attempted on first use.
    """
    if not docker_client._connected and docker_client._client is None:
        await docker_client.connect()
    return docker_client
