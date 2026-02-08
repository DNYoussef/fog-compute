"""
Fog Container Runtime
Transparent container orchestration across fog mesh nodes.

Provides Docker-compatible API for running containers without fog awareness.
Applications deploy as standard containers - fog handles distribution transparently.

FOG-SEC-003: Container State Persistence
- Persists containers, pending_queue, and stats to SQLite
- Uses in-memory cache with DB as authoritative source
- Rebuilds cache on startup from DB
"""
from .models import (
    Container,
    ContainerSpec,
    ContainerStatus,
    Volume,
    VolumeMount,
    PortMapping,
    NetworkConfig,
    ResourceLimits,
)
from .scheduler import FogScheduler, SchedulerConfig, PlacementStrategy, AuthenticationError, FogNode
from .storage import DistributedVolumeManager, VolumeType
from .network import FogNetworkManager, NetworkMode
from .container_persistence import ContainerPersistenceService, get_container_persistence
from .container_models import ContainerRecord, PendingQueueRecord, SchedulerStatsRecord

__all__ = [
    # Models
    "Container",
    "ContainerSpec",
    "ContainerStatus",
    "Volume",
    "VolumeMount",
    "PortMapping",
    "NetworkConfig",
    "ResourceLimits",
    # Scheduler
    "FogScheduler",
    "FogNode",
    "SchedulerConfig",
    "PlacementStrategy",
    "AuthenticationError",
    # Storage
    "DistributedVolumeManager",
    "VolumeType",
    # Network
    "FogNetworkManager",
    "NetworkMode",
    # Persistence (FOG-SEC-003)
    "ContainerPersistenceService",
    "get_container_persistence",
    "ContainerRecord",
    "PendingQueueRecord",
    "SchedulerStatsRecord",
]

__version__ = "0.1.0"
