"""
Container Runtime Models
Data structures for fog container orchestration.

Designed to be Docker-compatible while enabling transparent fog distribution.
"""
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Optional, Any
from uuid import uuid4


class ContainerStatus(str, Enum):
    """Container lifecycle status."""
    PENDING = "pending"         # Waiting to be scheduled
    PULLING = "pulling"         # Pulling image
    CREATING = "creating"       # Creating container
    RUNNING = "running"         # Running
    PAUSED = "paused"           # Paused
    STOPPING = "stopping"       # Stopping
    STOPPED = "stopped"         # Stopped
    FAILED = "failed"           # Failed to start/run
    REMOVING = "removing"       # Being removed


class RestartPolicy(str, Enum):
    """Container restart policy."""
    NO = "no"                   # Never restart
    ON_FAILURE = "on-failure"   # Restart on failure
    ALWAYS = "always"           # Always restart
    UNLESS_STOPPED = "unless-stopped"


class VolumeType(str, Enum):
    """Volume storage type."""
    LOCAL = "local"             # Node-local storage
    DISTRIBUTED = "distributed" # Replicated across fog mesh
    SHARED = "shared"           # Single source, network mounted


class NetworkMode(str, Enum):
    """Container network mode."""
    BRIDGE = "bridge"           # Isolated bridge network
    HOST = "host"               # Host networking
    FOG_MESH = "fog-mesh"       # Fog mesh overlay network
    NONE = "none"               # No networking


@dataclass
class ResourceLimits:
    """
    Container resource constraints.

    Fog scheduler uses these for placement decisions.
    """
    cpu_cores: float = 1.0          # CPU cores (can be fractional)
    memory_mb: int = 512            # Memory in MB
    memory_swap_mb: int = 0         # Swap limit (0 = same as memory)
    gpu_count: int = 0              # GPU devices needed
    disk_mb: int = 1024             # Disk space in MB

    # Network limits
    bandwidth_mbps: Optional[int] = None  # Network bandwidth limit

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "cpu_cores": self.cpu_cores,
            "memory_mb": self.memory_mb,
            "memory_swap_mb": self.memory_swap_mb,
            "gpu_count": self.gpu_count,
            "disk_mb": self.disk_mb,
            "bandwidth_mbps": self.bandwidth_mbps,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResourceLimits":
        """Create from dictionary."""
        return cls(
            cpu_cores=data.get("cpu_cores", 1.0),
            memory_mb=data.get("memory_mb", 512),
            memory_swap_mb=data.get("memory_swap_mb", 0),
            gpu_count=data.get("gpu_count", 0),
            disk_mb=data.get("disk_mb", 1024),
            bandwidth_mbps=data.get("bandwidth_mbps"),
        )


@dataclass
class PortMapping:
    """
    Container port mapping.

    In fog mesh, ports are automatically routed through overlay network.
    """
    container_port: int
    host_port: Optional[int] = None  # None = auto-assign
    protocol: str = "tcp"            # tcp or udp

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "container_port": self.container_port,
            "host_port": self.host_port,
            "protocol": self.protocol,
        }


@dataclass
class VolumeMount:
    """
    Volume mount specification.

    Fog runtime translates these to appropriate storage backend.
    """
    source: str                      # Volume name or host path
    target: str                      # Mount path in container
    read_only: bool = False
    volume_type: VolumeType = VolumeType.LOCAL

    # Distributed volume options
    replication_factor: int = 1      # For distributed volumes
    consistency: str = "eventual"    # eventual or strong

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source": self.source,
            "target": self.target,
            "read_only": self.read_only,
            "volume_type": self.volume_type.value,
            "replication_factor": self.replication_factor,
            "consistency": self.consistency,
        }


@dataclass
class NetworkConfig:
    """
    Container network configuration.

    Fog mesh provides transparent cross-device connectivity.
    """
    mode: NetworkMode = NetworkMode.FOG_MESH
    network_name: Optional[str] = None  # Custom network name

    # DNS configuration
    dns_servers: list[str] = field(default_factory=list)
    dns_search: list[str] = field(default_factory=list)

    # Service discovery
    hostname: Optional[str] = None
    domain_name: Optional[str] = None
    aliases: list[str] = field(default_factory=list)

    # Fog mesh specific
    expose_to_mesh: bool = True      # Accessible from other fog nodes
    mesh_dns_name: Optional[str] = None  # DNS name in fog mesh

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "mode": self.mode.value,
            "network_name": self.network_name,
            "dns_servers": self.dns_servers,
            "dns_search": self.dns_search,
            "hostname": self.hostname,
            "domain_name": self.domain_name,
            "aliases": self.aliases,
            "expose_to_mesh": self.expose_to_mesh,
            "mesh_dns_name": self.mesh_dns_name,
        }


@dataclass
class HealthCheck:
    """Container health check configuration."""
    command: list[str]               # Health check command
    interval_sec: int = 30           # Check interval
    timeout_sec: int = 30            # Check timeout
    retries: int = 3                 # Failures before unhealthy
    start_period_sec: int = 0        # Grace period on start

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "command": self.command,
            "interval_sec": self.interval_sec,
            "timeout_sec": self.timeout_sec,
            "retries": self.retries,
            "start_period_sec": self.start_period_sec,
        }


@dataclass
class ContainerSpec:
    """
    Container specification - what the user wants to run.

    Docker-compatible spec that fog runtime translates to
    distributed execution across fog mesh.
    """
    image: str                       # Container image (e.g., "postgres:15")
    name: Optional[str] = None       # Container name (auto-generated if None)

    # Command
    command: Optional[list[str]] = None    # Override CMD
    entrypoint: Optional[list[str]] = None # Override ENTRYPOINT

    # Environment
    environment: dict[str, str] = field(default_factory=dict)
    env_file: Optional[str] = None   # Path to env file

    # Resources
    resources: ResourceLimits = field(default_factory=ResourceLimits)

    # Storage
    volumes: list[VolumeMount] = field(default_factory=list)
    working_dir: Optional[str] = None

    # Network
    network: NetworkConfig = field(default_factory=NetworkConfig)
    ports: list[PortMapping] = field(default_factory=list)

    # Health
    health_check: Optional[HealthCheck] = None

    # Lifecycle
    restart_policy: RestartPolicy = RestartPolicy.NO
    stop_timeout_sec: int = 10

    # Labels and annotations
    labels: dict[str, str] = field(default_factory=dict)

    # Fog-specific hints (optional - for advanced users)
    placement_hints: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "image": self.image,
            "name": self.name,
            "command": self.command,
            "entrypoint": self.entrypoint,
            "environment": self.environment,
            "env_file": self.env_file,
            "resources": self.resources.to_dict(),
            "volumes": [v.to_dict() for v in self.volumes],
            "working_dir": self.working_dir,
            "network": self.network.to_dict(),
            "ports": [p.to_dict() for p in self.ports],
            "health_check": self.health_check.to_dict() if self.health_check else None,
            "restart_policy": self.restart_policy.value,
            "stop_timeout_sec": self.stop_timeout_sec,
            "labels": self.labels,
            "placement_hints": self.placement_hints,
        }


@dataclass
class Volume:
    """
    Fog volume - distributed or local storage.

    Volumes appear as normal Docker volumes to containers,
    but fog runtime handles replication and distribution.
    """
    volume_id: str = field(default_factory=lambda: f"vol-{uuid4().hex[:12]}")
    name: str = ""
    volume_type: VolumeType = VolumeType.LOCAL

    # Size
    size_mb: int = 1024              # Volume size
    used_mb: int = 0                 # Current usage

    # Distribution (for distributed/shared types)
    replication_factor: int = 1      # Number of replicas
    primary_node_id: Optional[str] = None    # Primary storage node
    replica_node_ids: list[str] = field(default_factory=list)

    # Consistency
    consistency_mode: str = "eventual"  # eventual or strong

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    labels: dict[str, str] = field(default_factory=dict)

    # Status
    is_ready: bool = False
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "volume_id": self.volume_id,
            "name": self.name,
            "volume_type": self.volume_type.value,
            "size_mb": self.size_mb,
            "used_mb": self.used_mb,
            "replication_factor": self.replication_factor,
            "primary_node_id": self.primary_node_id,
            "replica_node_ids": self.replica_node_ids,
            "consistency_mode": self.consistency_mode,
            "created_at": self.created_at.isoformat(),
            "labels": self.labels,
            "is_ready": self.is_ready,
            "error": self.error,
        }


@dataclass
class Container:
    """
    Running container instance.

    Represents a container running somewhere in the fog mesh.
    The application doesn't know or care which physical node hosts it.
    """
    container_id: str = field(default_factory=lambda: f"fog-{uuid4().hex[:12]}")
    spec: ContainerSpec = field(default_factory=ContainerSpec)

    # Status
    status: ContainerStatus = ContainerStatus.PENDING
    exit_code: Optional[int] = None
    error: Optional[str] = None

    # Placement (internal - fog runtime manages this)
    node_id: Optional[str] = None    # Physical fog node hosting container

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    # Runtime info
    pid: Optional[int] = None        # Process ID on node
    ip_address: Optional[str] = None # Container IP in fog mesh

    # Health
    health_status: str = "unknown"   # healthy, unhealthy, unknown
    last_health_check: Optional[datetime] = None
    health_check_failures: int = 0

    # Resource usage
    cpu_usage_percent: float = 0.0
    memory_usage_mb: int = 0
    network_rx_bytes: int = 0
    network_tx_bytes: int = 0

    # Restart tracking
    restart_count: int = 0

    @property
    def name(self) -> str:
        """Get container name."""
        return self.spec.name or self.container_id

    @property
    def is_running(self) -> bool:
        """Check if container is running."""
        return self.status == ContainerStatus.RUNNING

    @property
    def uptime_seconds(self) -> Optional[float]:
        """Get container uptime in seconds."""
        if not self.started_at:
            return None
        end_time = self.finished_at or datetime.now(UTC)
        return (end_time - self.started_at).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "container_id": self.container_id,
            "name": self.name,
            "spec": self.spec.to_dict(),
            "status": self.status.value,
            "exit_code": self.exit_code,
            "error": self.error,
            "node_id": self.node_id,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "pid": self.pid,
            "ip_address": self.ip_address,
            "health_status": self.health_status,
            "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None,
            "health_check_failures": self.health_check_failures,
            "cpu_usage_percent": self.cpu_usage_percent,
            "memory_usage_mb": self.memory_usage_mb,
            "network_rx_bytes": self.network_rx_bytes,
            "network_tx_bytes": self.network_tx_bytes,
            "restart_count": self.restart_count,
            "uptime_seconds": self.uptime_seconds,
        }


@dataclass
class ContainerLogs:
    """Container log output."""
    container_id: str
    stdout: str = ""
    stderr: str = ""
    timestamps: bool = False
    since: Optional[datetime] = None
    until: Optional[datetime] = None
    tail: int = 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "container_id": self.container_id,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timestamps": self.timestamps,
            "since": self.since.isoformat() if self.since else None,
            "until": self.until.isoformat() if self.until else None,
            "tail": self.tail,
        }
