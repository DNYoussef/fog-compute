# Fog Container Runtime Architecture

## Vision: Transparent Distribution

The core insight of Fogburst is that **applications should not need fog-specific code**. Life OS (or any containerized application) runs as a standard Docker container. The fog runtime handles all distribution, replication, and cross-device routing **transparently**.

```
+----------------------------------------------------------+
|                    STANDARD CONTAINER                      |
|  +----------------------------------------------------+  |
|  |               Life OS Application                   |  |
|  |  - No fog awareness                                 |  |
|  |  - Uses standard DNS (db.fog.local:5432)           |  |
|  |  - Mounts normal volumes (/data)                   |  |
|  |  - Standard environment variables                   |  |
|  +----------------------------------------------------+  |
+----------------------------------------------------------+
                            |
                            v
+----------------------------------------------------------+
|                 FOG CONTAINER RUNTIME                      |
|  +----------------+  +----------------+  +--------------+  |
|  | Scheduler      |  | Storage        |  | Network      |  |
|  | - Placement    |  | - Replication  |  | - Overlay    |  |
|  | - Resources    |  | - Consistency  |  | - DNS        |  |
|  | - Failover     |  | - Sync         |  | - Routing    |  |
|  +----------------+  +----------------+  +--------------+  |
+----------------------------------------------------------+
                            |
                            v
+----------------------------------------------------------+
|                    FOG MESH (6+ DEVICES)                   |
|  [Desktop]  [Laptop]  [Server]  [Phone]  [Tablet]  [RPi]  |
+----------------------------------------------------------+
```

## Three Core Components

### 1. Fog Scheduler (`scheduler.py`)

Handles container placement across fog nodes:

**Placement Strategies:**
- `RESOURCE_FIT` (default): Best match between container requirements and node capacity
- `SPREAD`: Distribute containers evenly across all nodes
- `BINPACK`: Pack containers on fewer nodes (power efficiency)
- `LOCALITY`: Prefer nodes that have required volumes locally
- `RANDOM`: Random placement

**Resource Tracking:**
```python
class FogNode:
    cpu_cores: int         # Available CPU
    memory_mb: int         # Available memory
    disk_mb: int           # Available disk
    gpu_available: bool    # GPU capability
    device_type: str       # desktop/laptop/phone/rpi
```

**Scheduling Flow:**
1. Container spec submitted (standard Docker format)
2. Scheduler finds nodes that can fit resource requirements
3. Applies placement strategy to select best node
4. Reserves resources and places container
5. Node agent pulls image and starts container

### 2. Distributed Volume Manager (`storage.py`)

Handles persistent storage across the mesh:

**Volume Types:**
- `LOCAL`: Single-node storage (default)
- `DISTRIBUTED`: Replicated across multiple nodes
- `SHARED`: Primary + network mount access

**Replication:**
```python
volume = await volume_manager.create_volume(
    name="postgres-data",
    volume_type=VolumeType.DISTRIBUTED,
    replication_factor=2,  # Primary + 1 replica
    consistency_mode="strong",  # or "eventual"
)
```

**Automatic Placement:**
- Volumes placed on nodes with most available space
- Replicas spread across different physical devices
- Automatic sync between replicas (eventual or strong consistency)

**Container Access:**
- If container is on same node as volume: direct local access
- If container is on different node: transparent network mount

### 3. Fog Network Manager (`network.py`)

Handles container networking across devices:

**Overlay Network:**
- Single flat network spanning all fog nodes
- Containers get IPs in the overlay subnet (10.200.x.x)
- Cross-device traffic tunneled through fog mesh

**DNS-Based Service Discovery:**
```python
# Container "db" on network "myapp" gets DNS:
# db.myapp.fog.local -> 10.200.1.5

# Life OS connects using standard DNS:
DATABASE_URL="postgresql://db.myapp.fog.local:5432/lifeos"
```

**Port Mapping:**
- Container ports mapped to host ports (30000-32767 range)
- Accessible from any device in the mesh
- Automatic port allocation avoids conflicts

**Routing:**
```python
# Get routing info for container-to-container communication
routing = network_manager.get_routing_info("life-os", "10.200.1.5")
# Returns: {
#   "target_node_id": "node-phone",
#   "target_node_ip": "192.168.1.13",
#   "same_node": False  # Needs mesh routing
# }
```

## Example: Deploying Life OS

```python
# 1. Create volumes (distributed for redundancy)
await volume_manager.create_volume(
    name="life-os-data",
    volume_type=VolumeType.DISTRIBUTED,
    replication_factor=2,
)

# 2. Deploy containers (standard Docker specs!)
db_spec = ContainerSpec(
    image="postgres:15",
    name="db",
    resources=ResourceLimits(cpu_cores=1.0, memory_mb=2048),
    volumes=[VolumeMount(source="postgres-data", target="/var/lib/postgresql/data")],
)

life_os_spec = ContainerSpec(
    image="life-os:latest",
    name="life-os",
    environment={
        # Standard DNS names - no fog awareness!
        "DATABASE_URL": "postgresql://db.fog.local:5432/lifeos",
    },
    resources=ResourceLimits(cpu_cores=2.0, memory_mb=4096),
)

# 3. Submit to fog scheduler
await scheduler.submit_container(db_spec)
await scheduler.submit_container(life_os_spec)

# Fog handles:
# - Placing containers on suitable devices
# - Setting up overlay networking
# - Creating DNS records
# - Routing cross-device traffic
```

## Family Device Example

```
FOG MESH: David's Family Network
================================

Desktop (Main) - 8 CPU, 32GB RAM
  Running: life-os (main application)

Laptop (Work) - 4 CPU, 16GB RAM
  Running: db (PostgreSQL)

Media Server - 4 CPU, 8GB RAM, 2TB disk
  Volumes: life-os-data (primary), postgres-data (primary)

Phone - 2 CPU, 4GB RAM
  Running: cache (Redis)

Tablet - 2 CPU, 4GB RAM
  Running: vectordb (ChromaDB)

Raspberry Pi - 1 CPU, 1GB RAM
  Running: sensor-collector


Cross-Device Communication:
- life-os on Desktop -> db on Laptop (mesh routed)
- life-os on Desktop -> cache on Phone (mesh routed)
- All volumes synced across Desktop and Media Server
```

## Key Benefits

1. **No Application Changes**: Life OS runs as-is, no fog SDK needed
2. **Automatic Failover**: If a device goes offline, containers can be rescheduled
3. **Data Redundancy**: Distributed volumes replicated across devices
4. **Resource Pooling**: Combine resources from all family devices
5. **Transparent Networking**: Containers communicate via DNS as if on same host

## Implementation Status

| Component | Status | Files |
|-----------|--------|-------|
| Models | Complete | `container_runtime/models.py` |
| Scheduler | Complete | `container_runtime/scheduler.py` |
| Storage | Complete | `container_runtime/storage.py` |
| Network | Complete | `container_runtime/network.py` |
| Node Agent | TODO | Runs on each device |
| Docker API | TODO | REST API compatibility |
| CLI | TODO | `fog run`, `fog ps`, etc. |

## Next Steps

1. **Node Agent**: Implement agent that runs on each family device
2. **Docker API Shim**: Accept standard `docker run` commands
3. **Compose Support**: Parse docker-compose.yml files
4. **Web Dashboard**: Visualize mesh status and containers
5. **Mobile App**: Control fog mesh from phone
