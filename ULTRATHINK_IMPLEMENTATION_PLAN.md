# ULTRATHINK Implementation Plan: Fog Compute → Dynamic Betanet Containers

**Status:** Design Document
**Created:** 2025-10-21
**Objective:** Transform idle fog compute into dynamically-sized privacy-preserving containers hosting websites/apps on Betanet

---

## Executive Summary

This plan implements a **mathematical abstraction hierarchy** where each layer enables the next, building toward a system that:

1. **Harvests** idle compute from mobile/edge devices
2. **Aggregates** distributed resources into virtual containers
3. **Deploys** websites/applications onto these containers
4. **Routes** traffic through Betanet privacy network
5. **Dynamically scales** based on available fog compute

**Core Innovation:** Treating fog compute as a **fungible resource pool** that can be composed into arbitrary-sized containers, hosted on a privacy-preserving network.

---

## Part 0: Fundamental Mathematical Abstractions

### 0.1 Resource Abstraction: The Compute Primitive

**Mathematical Model:**
```
Resource ≡ (CPU, Memory, Storage, Network) ∈ ℝ⁴₊

Device_i = {r_i(t) | r_i: T → ℝ⁴₊}
  where r_i(t) = available resources at time t

FogPool(t) = Σᵢ r_i(t) × availability_i(t)
  where availability_i ∈ [0,1] (battery, charging, idle state)
```

**Abstraction Layer:**
```python
class ComputePrimitive:
    """Fundamental unit of fog compute"""
    cpu_cores: float        # Fractional cores available
    memory_mb: float        # Available RAM
    storage_mb: float       # Available disk
    bandwidth_mbps: float   # Network capacity
    availability: float     # 0-1 probability of staying online

    def __add__(self, other):
        """Resources are composable via addition"""
        return ComputePrimitive(
            cpu_cores=self.cpu_cores + other.cpu_cores,
            memory_mb=self.memory_mb + other.memory_mb,
            # ... combine all dimensions
        )
```

**Why This Enables Next Step:** Treating resources as composable primitives allows us to build containers as **sums of fog devices**.

---

### 0.2 Container Abstraction: The Execution Environment

**Mathematical Model:**
```
Container_j ≡ {
    requirements: R_j ∈ ℝ⁴₊,
    allocation: A_j ⊆ {Device₁, Device₂, ...},
    state: S_j ∈ {Pending, Running, Migrating, Stopped}
}

Feasibility: Σ_{i ∈ A_j} r_i(t) ≥ R_j  ∀t ∈ [t_start, t_end]
```

**Abstraction Layer:**
```python
class FogContainer:
    """Virtual container composed of distributed fog resources"""
    requirements: ComputePrimitive  # What it needs
    allocation: Set[DeviceID]       # Which devices provide it
    workload: ContainerImage        # What it runs (website, app, etc)

    def is_feasible(self, fog_pool: FogPool) -> bool:
        """Can the fog pool satisfy requirements?"""
        return fog_pool.available_resources() >= self.requirements

    def allocate(self, devices: Set[Device]) -> Allocation:
        """Bin-packing problem: assign devices to container"""
        # This is the SCHEDULER's job - NP-hard optimization
```

**Why This Enables Next Step:** Containers as abstract requirements allow us to separate **what we want to run** from **how resources are allocated**.

---

### 0.3 Betanet Routing Abstraction: The Privacy Layer

**Mathematical Model:**
```
Traffic Flow:
  User → Betanet Entry → Mixnode₁ → ... → Mixnode_n → Container

Privacy Guarantee:
  P(Observer links User to Container) ≤ 1/n^k
    where n = number of mixnodes
          k = mixing rounds
```

**Abstraction Layer:**
```python
class BetanetRoute:
    """Privacy-preserving path to container"""
    entry_node: MixnodeID
    circuit: List[MixnodeID]  # Onion-routed path
    exit_node: MixnodeID
    target_container: ContainerID

    def encrypt_layer(self, payload: bytes, hop: int) -> bytes:
        """Onion encryption: each layer peeled by one mixnode"""
        # Sphinx packet format

    def route_traffic(self, request: HTTPRequest) -> HTTPResponse:
        """User → Betanet → Container → Betanet → User"""
```

**Why This Enables Next Step:** Separating routing from compute allows containers to be **location-agnostic** and **privacy-preserving**.

---

### 0.4 Dynamic Scaling Abstraction: The Adaptation Layer

**Mathematical Model:**
```
Scaling Function:
  Scale(C_j, t) = argmin_{A'_j} Cost(A'_j)
  subject to:
    Σ_{i ∈ A'_j} r_i(t) ≥ R_j(t)
    |A'_j Δ A_j| ≤ k  (minimize churn)

  where R_j(t) adapts to load:
    R_j(t) = R_base + α × traffic(t)
```

**Abstraction Layer:**
```python
class DynamicScaler:
    """Adapts container allocation based on load and availability"""

    def scale_out(self, container: FogContainer, additional: ComputePrimitive):
        """Add devices when load increases"""

    def scale_in(self, container: FogContainer, reduce: ComputePrimitive):
        """Remove devices when load decreases or devices go offline"""

    def migrate(self, container: FogContainer, from_device: DeviceID, to_device: DeviceID):
        """Live migration when device battery low or going offline"""
```

**Why This Enables Next Step:** Dynamic scaling ensures containers remain **resilient** despite fog compute churn.

---

## Part 1: Root Cause Analysis & Quick Wins (Week 1)

### 1.1 Service Integration Fixes

**Root Cause Summary:**
- 7 distinct architectural violations
- Missing `__init__.py` files (Python package infrastructure)
- Incorrect relative imports (assumes wrong directory structure)
- Class name mismatches (importing wrong names)
- Missing dependencies (psutil)
- Invalid constructor arguments (config objects not created)

**Quick Win Strategy:** Fix in dependency order

**Day 1-2: Foundation Layer**
```bash
# Fix 1: Add __init__.py to make packages importable
touch src/idle/__init__.py
touch src/vpn/__init__.py
touch src/p2p/__init__.py
touch src/tokenomics/__init__.py

# Fix 2: Install missing dependencies
pip install psutil
```

**Premortem:**
- ❌ **Risk:** Other missing __init__.py files in subdirectories
- ✅ **Mitigation:** Run `find src/ -type d -exec test -f {}/__init__.py \; -print` to find all
- ❌ **Risk:** Version conflicts with psutil
- ✅ **Mitigation:** Pin version in requirements.txt

**Day 3-4: Import Path Corrections**

Fix relative imports by creating index files:

```python
# src/vpn/__init__.py
from .onion_routing import OnionRouter, OnionCircuit
from .onion_circuit_service import OnionCircuitService
from .fog_onion_coordinator import FogOnionCoordinator
from .hidden_services import HiddenServiceManager

__all__ = [
    'OnionRouter', 'OnionCircuit',
    'OnionCircuitService', 'FogOnionCoordinator',
    'HiddenServiceManager'
]
```

Then update service_manager.py imports:
```python
# Before (BROKEN):
from vpn.onion_circuit_service import OnionCircuitService

# After (FIXED):
from ..vpn import OnionCircuitService
```

**Premortem:**
- ❌ **Risk:** Circular import dependencies
- ✅ **Mitigation:** Use lazy imports or dependency injection
- ❌ **Risk:** Imports still fail due to sys.path issues
- ✅ **Mitigation:** Add PYTHONPATH=/app to all Docker containers

**Day 5-7: Constructor Argument Fixes**

Create config objects before instantiation:

```python
# backend/server/services/service_manager.py

async def _init_tokenomics(self) -> None:
    try:
        from tokenomics.unified_dao_tokenomics_system import UnifiedDAOTokenomicsSystem
        from tokenomics.config import TokenomicsConfig  # NEW

        config = TokenomicsConfig(
            total_supply=1_000_000_000,
            staking_enabled=True,
            dao_threshold=0.1,
        )

        self.services['dao'] = UnifiedDAOTokenomicsSystem(config)  # NOW WORKS
        logger.info("✓ Tokenomics DAO system initialized")
    except Exception as e:
        logger.error(f"Failed to initialize tokenomics: {e}")
        self.services['dao'] = None
```

**Premortem:**
- ❌ **Risk:** Don't know what config parameters are required
- ✅ **Mitigation:** Read class __init__ docstrings and type hints
- ❌ **Risk:** Config objects have their own dependencies
- ✅ **Mitigation:** Create config factory functions

---

## Part 2: Fog-to-Container Pipeline (Weeks 2-3)

### 2.1 Mathematical Foundation: Resource Pooling

**Core Abstraction:**
```
Problem: Given N fog devices with varying resources, compose them into M containers

Formal Definition:
  Devices: D = {d₁, d₂, ..., d_N}
  Resources: r(d_i) ∈ ℝ⁴₊  (CPU, RAM, disk, network)
  Containers: C = {c₁, c₂, ..., c_M}
  Requirements: req(c_j) ∈ ℝ⁴₊

  Allocation: α: C → 2^D (maps containers to device sets)

  Constraints:
    1. Feasibility: Σ_{d ∈ α(c_j)} r(d) ≥ req(c_j)  ∀c_j
    2. No oversubscription: |{c | d ∈ α(c)}| ≤ 1  ∀d
    3. Minimize fragmentation: min Σ_d (r(d) - used(d))²
```

**Implementation Abstraction:**

```python
# backend/server/services/fog_container_orchestrator.py

from dataclasses import dataclass
from typing import Set, Dict, Optional
import pulp  # Linear programming solver

@dataclass
class ResourceVector:
    """4-dimensional resource vector"""
    cpu_cores: float
    memory_mb: float
    storage_mb: float
    bandwidth_mbps: float

    def __ge__(self, other: 'ResourceVector') -> bool:
        """Component-wise comparison"""
        return (
            self.cpu_cores >= other.cpu_cores and
            self.memory_mb >= other.memory_mb and
            self.storage_mb >= other.storage_mb and
            self.bandwidth_mbps >= other.bandwidth_mbps
        )

    def __add__(self, other: 'ResourceVector') -> 'ResourceVector':
        """Resource composition"""
        return ResourceVector(
            cpu_cores=self.cpu_cores + other.cpu_cores,
            memory_mb=self.memory_mb + other.memory_mb,
            storage_mb=self.storage_mb + other.storage_mb,
            bandwidth_mbps=self.bandwidth_mbps + other.bandwidth_mbps,
        )


class FogContainerOrchestrator:
    """
    Orchestrates allocation of fog devices to containers.

    Mathematical abstraction:
    - Input: Set of devices D with resources r(d)
    - Output: Allocation α: Container → DeviceSet
    - Objective: Minimize fragmentation while satisfying requirements
    """

    def __init__(self, device_registry: 'DeviceRegistry'):
        self.device_registry = device_registry
        self.allocations: Dict[ContainerID, Set[DeviceID]] = {}

    def allocate_container(
        self,
        requirements: ResourceVector,
        affinity: Optional[Set[DeviceID]] = None
    ) -> Optional[Set[DeviceID]]:
        """
        Bin-packing allocation with integer linear programming.

        Mathematical formulation:
          Variables: x_id ∈ {0, 1} (device d allocated to container c)

          Minimize: Σ_d w_d × x_d  (minimize cost)

          Subject to:
            Σ_d x_d × r_d ≥ req  (meet requirements)
            x_d ∈ {0, 1}         (binary allocation)

        where w_d = cost of using device d (battery, reliability)
        """
        available_devices = self.device_registry.get_available()

        # Integer linear programming formulation
        prob = pulp.LpProblem("FogAllocation", pulp.LpMinimize)

        # Binary variables: x[d] = 1 if device d is allocated
        x = pulp.LpVariable.dicts("device", available_devices, cat='Binary')

        # Objective: minimize weighted cost
        prob += pulp.lpSum([
            self._cost(d) * x[d] for d in available_devices
        ])

        # Constraints: meet resource requirements
        for resource in ['cpu', 'memory', 'storage', 'bandwidth']:
            prob += pulp.lpSum([
                getattr(d.resources, resource) * x[d]
                for d in available_devices
            ]) >= getattr(requirements, resource)

        # Solve
        prob.solve(pulp.PULP_CBC_CMD(msg=0))

        if pulp.LpStatus[prob.status] == 'Optimal':
            allocated = {d for d in available_devices if x[d].varValue == 1}
            return allocated
        else:
            return None  # No feasible allocation

    def _cost(self, device: 'Device') -> float:
        """Cost function for device allocation"""
        return (
            1.0 / device.battery_percent +        # Prefer devices with high battery
            1.0 / device.reliability_score +      # Prefer reliable devices
            (0 if device.is_charging else 10)     # Strong preference for charging
        )
```

**Why This Abstraction Works:**
1. **Mathematical Foundation:** ILP ensures optimal allocation
2. **Composability:** ResourceVector supports addition (fog aggregation)
3. **Extensibility:** Cost function can incorporate any device metric
4. **Testability:** Can unit test with mock devices

**Premortem:**
- ❌ **Risk:** ILP solver too slow for real-time allocation
- ✅ **Mitigation:** Use greedy heuristic (First-Fit Decreasing) for <100 devices, ILP for offline optimization
- ❌ **Risk:** Device availability changes during allocation
- ✅ **Mitigation:** Two-phase commit: reserve → allocate → confirm
- ❌ **Risk:** Requirements may be infeasible (asking for 100GB RAM from phones)
- ✅ **Mitigation:** Return None and suggest reduced requirements

---

### 2.2 Container Image Abstraction

**Mathematical Model:**
```
Container Image ≡ (Filesystem, Entrypoint, Config)

Filesystem: F = {files, directories} (immutable layer)
Entrypoint: cmd: Args → Process
Config: environment variables, ports, volumes
```

**Implementation:**

```python
# backend/server/models/container.py

from enum import Enum
from sqlalchemy import Column, String, JSON, DateTime, Float
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

class ContainerStatus(str, Enum):
    PENDING = "pending"
    ALLOCATING = "allocating"
    STARTING = "starting"
    RUNNING = "running"
    MIGRATING = "migrating"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class FogContainerModel(Base):
    """
    Database model for fog containers.

    Represents a virtual container composed of distributed fog resources.
    """
    __tablename__ = 'fog_containers'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    image = Column(String(255), nullable=False)  # Docker image or custom format
    status = Column(String(50), default=ContainerStatus.PENDING)

    # Resource requirements
    cpu_cores = Column(Float, nullable=False)
    memory_mb = Column(Float, nullable=False)
    storage_mb = Column(Float, nullable=False)
    bandwidth_mbps = Column(Float, nullable=False)

    # Allocation (which devices are running this container)
    allocated_devices = Column(JSON, default=list)  # List of device IDs

    # Betanet routing
    betanet_entry_node = Column(String(255), nullable=True)
    betanet_circuit = Column(JSON, nullable=True)  # List of mixnode IDs
    betanet_onion_address = Column(String(255), nullable=True)  # .onion address

    # Configuration
    environment = Column(JSON, default=dict)
    ports = Column(JSON, default=list)
    volumes = Column(JSON, default=list)

    # Lifecycle
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    stopped_at = Column(DateTime, nullable=True)

    # Metrics
    cpu_usage_percent = Column(Float, default=0.0)
    memory_usage_mb = Column(Float, default=0.0)
    network_rx_mbps = Column(Float, default=0.0)
    network_tx_mbps = Column(Float, default=0.0)

    def to_dict(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'image': self.image,
            'status': self.status,
            'requirements': {
                'cpu_cores': self.cpu_cores,
                'memory_mb': self.memory_mb,
                'storage_mb': self.storage_mb,
                'bandwidth_mbps': self.bandwidth_mbps,
            },
            'allocated_devices': self.allocated_devices,
            'betanet': {
                'entry_node': self.betanet_entry_node,
                'onion_address': self.betanet_onion_address,
            },
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
        }
```

**Why This Abstraction:**
- **Database-backed:** Persistent state survives restarts
- **Status FSM:** Clear state transitions (Pending → Allocating → Running → ...)
- **Betanet Integration:** Onion address stored for privacy routing
- **Metrics Tracking:** Real-time resource usage

---

### 2.3 Container Lifecycle Manager

**State Machine:**
```
States: {Pending, Allocating, Starting, Running, Migrating, Stopping, Stopped, Failed}

Transitions:
  Pending → Allocating: allocate_resources()
  Allocating → Starting: resources confirmed
  Starting → Running: entrypoint started
  Running → Migrating: device going offline
  Migrating → Running: migration complete
  Running → Stopping: user requested stop
  Stopping → Stopped: cleanup complete
  * → Failed: error occurred
```

**Implementation:**

```python
# backend/server/services/container_lifecycle.py

class ContainerLifecycleManager:
    """
    Manages container state machine and lifecycle.

    Orchestrates:
    1. Resource allocation (via FogContainerOrchestrator)
    2. Image deployment (to allocated devices)
    3. Betanet routing setup
    4. Container startup
    5. Health monitoring
    6. Migration (when devices go offline)
    7. Shutdown
    """

    def __init__(
        self,
        orchestrator: FogContainerOrchestrator,
        betanet_service: BetanetService,
        device_registry: DeviceRegistry,
    ):
        self.orchestrator = orchestrator
        self.betanet = betanet_service
        self.devices = device_registry

    async def create_container(
        self,
        name: str,
        image: str,
        requirements: ResourceVector,
        environment: Dict[str, str] = None,
    ) -> FogContainerModel:
        """
        Create and start a fog container.

        Process:
        1. Create database record (status=PENDING)
        2. Allocate devices (status=ALLOCATING)
        3. Deploy image to devices
        4. Setup Betanet routing (create .onion address)
        5. Start container (status=STARTING → RUNNING)
        6. Begin health monitoring
        """
        # Step 1: Create DB record
        container = FogContainerModel(
            name=name,
            image=image,
            cpu_cores=requirements.cpu_cores,
            memory_mb=requirements.memory_mb,
            storage_mb=requirements.storage_mb,
            bandwidth_mbps=requirements.bandwidth_mbps,
            environment=environment or {},
            status=ContainerStatus.PENDING,
        )
        db.add(container)
        await db.commit()

        try:
            # Step 2: Allocate devices
            container.status = ContainerStatus.ALLOCATING
            await db.commit()

            allocated_devices = self.orchestrator.allocate_container(requirements)
            if not allocated_devices:
                raise AllocationError("No feasible device allocation found")

            container.allocated_devices = [str(d.id) for d in allocated_devices]
            await db.commit()

            # Step 3: Deploy image to devices
            await self._deploy_image(container, allocated_devices, image)

            # Step 4: Setup Betanet routing
            container.status = ContainerStatus.STARTING
            await db.commit()

            onion_address = await self._setup_betanet_routing(container)
            container.betanet_onion_address = onion_address

            # Step 5: Start container
            await self._start_container(container, allocated_devices)

            container.status = ContainerStatus.RUNNING
            container.started_at = datetime.utcnow()
            await db.commit()

            # Step 6: Begin health monitoring
            asyncio.create_task(self._monitor_health(container))

            return container

        except Exception as e:
            container.status = ContainerStatus.FAILED
            await db.commit()
            raise

    async def _deploy_image(
        self,
        container: FogContainerModel,
        devices: Set[Device],
        image: str,
    ):
        """
        Deploy container image to allocated devices.

        For now: Simple Docker pull on each device
        Future: Custom image format, content-addressed storage
        """
        for device in devices:
            await device.rpc_client.execute(f"docker pull {image}")

    async def _setup_betanet_routing(self, container: FogContainerModel) -> str:
        """
        Setup Betanet onion routing to container.

        Process:
        1. Choose entry mixnode
        2. Build circuit (chain of mixnodes)
        3. Register hidden service
        4. Return .onion address
        """
        # Choose 3 mixnodes for circuit
        mixnodes = await self.betanet.get_mixnodes()
        circuit = random.sample([m for m in mixnodes if m.status == "active"], 3)

        # Create hidden service descriptor
        onion_address = await self.betanet.create_hidden_service(
            container_id=str(container.id),
            circuit=[m.id for m in circuit],
            target_port=container.ports[0] if container.ports else 80,
        )

        # Store circuit for later use
        container.betanet_entry_node = circuit[0].id
        container.betanet_circuit = [m.id for m in circuit]

        return onion_address

    async def _start_container(
        self,
        container: FogContainerModel,
        devices: Set[Device],
    ):
        """
        Start container on allocated devices.

        Challenge: Container is distributed across multiple devices
        Solution: Primary-replica pattern
        - One device is primary (runs main process)
        - Other devices provide resources (CPU offload, storage, etc.)
        """
        # Choose primary device (highest resources)
        primary = max(devices, key=lambda d: d.resources.cpu_cores)
        replicas = devices - {primary}

        # Start on primary
        await primary.rpc_client.execute(
            f"docker run -d "
            f"--name {container.name} "
            f"--cpus {container.cpu_cores} "
            f"--memory {container.memory_mb}m "
            f"{' '.join(f'-e {k}={v}' for k, v in container.environment.items())} "
            f"{container.image}"
        )

        # Replicas provide additional resources (future: distributed execution)

    async def _monitor_health(self, container: FogContainerModel):
        """
        Monitor container health and handle failures.

        Checks:
        1. Device availability (battery, connectivity)
        2. Container process health
        3. Resource usage

        Actions:
        - Migrate if device going offline
        - Scale if load increases
        - Alert if failing
        """
        while container.status == ContainerStatus.RUNNING:
            await asyncio.sleep(30)  # Check every 30s

            # Check device availability
            for device_id in container.allocated_devices:
                device = await self.devices.get(device_id)
                if device.battery_percent < 20 and not device.is_charging:
                    # Trigger migration
                    await self._migrate_from_device(container, device)

            # Update metrics
            await self._update_metrics(container)
```

**Premortem:**
- ❌ **Risk:** Image deployment fails on some devices
- ✅ **Mitigation:** Retry with exponential backoff, mark device as unhealthy
- ❌ **Risk:** Betanet circuit setup times out
- ✅ **Mitigation:** Fallback to direct connection for dev, queue for retry
- ❌ **Risk:** Primary device goes offline mid-execution
- ✅ **Mitigation:** Promote replica to primary (requires state replication - Phase 2)

---

## Part 3: Betanet Integration (Week 4)

### 3.1 Mathematical Model: Onion Routing to Containers

**Routing Abstraction:**
```
HTTP Request Flow:
  User → Entry Node → Mix₁ → Mix₂ → Mix₃ → Container

Encryption Layers:
  E_k3(E_k2(E_k1(request, next=Mix₁), next=Mix₂), next=Mix₃)

Each mixnode peels one layer:
  Mix₁ decrypts → sees next=Mix₂
  Mix₂ decrypts → sees next=Mix₃
  Mix₃ decrypts → sees next=Container

No single node knows full path.
```

**Implementation:**

```python
# backend/server/services/betanet_router.py

class BetanetRouter:
    """
    Routes traffic from Betanet to fog containers.

    Abstraction: Maps .onion addresses → Container IDs → Devices
    """

    def __init__(self, betanet_service: BetanetService):
        self.betanet = betanet_service
        self.routing_table: Dict[str, ContainerID] = {}

    def register_container(self, onion_address: str, container_id: str):
        """Map .onion address to container"""
        self.routing_table[onion_address] = container_id

    async def route_request(
        self,
        onion_address: str,
        request: HTTPRequest,
    ) -> HTTPResponse:
        """
        Route incoming request to container.

        Process:
        1. Lookup container by .onion address
        2. Find primary device
        3. Forward request
        4. Return response through circuit
        """
        container_id = self.routing_table.get(onion_address)
        if not container_id:
            return HTTPResponse(status=404, body="Container not found")

        container = await db.query(FogContainerModel).get(container_id)
        if not container or container.status != ContainerStatus.RUNNING:
            return HTTPResponse(status=503, body="Container not available")

        # Find primary device
        primary_device_id = container.allocated_devices[0]  # First is primary
        device = await device_registry.get(primary_device_id)

        # Forward request to container
        response = await device.rpc_client.http_request(
            container_name=container.name,
            request=request,
        )

        return response
```

**Why This Works:**
- Betanet circuit setup already done in lifecycle manager
- Router is stateless (just a lookup table)
- Can scale horizontally (multiple routers share table via Redis)

---

### 3.2 Hidden Service Descriptor

**Protocol:**
```
Hidden Service Descriptor:
  - Onion Address: hash(public_key)
  - Introduction Points: List of mixnodes
  - Rendezvous Protocol: How to establish circuit
```

**Implementation:**

```python
class HiddenServiceDescriptor:
    """
    Betanet hidden service (similar to Tor hidden service).

    Allows users to access container via .onion address without
    knowing which devices are hosting it.
    """

    def __init__(
        self,
        container_id: str,
        introduction_points: List[MixnodeID],
        public_key: bytes,
    ):
        self.container_id = container_id
        self.introduction_points = introduction_points
        self.public_key = public_key
        self.onion_address = self._compute_onion_address()

    def _compute_onion_address(self) -> str:
        """
        Compute .onion address from public key.

        Format: base32(hash(public_key))[:16].onion
        """
        import hashlib
        import base64

        hash_digest = hashlib.sha256(self.public_key).digest()
        onion_name = base64.b32encode(hash_digest)[:16].decode().lower()
        return f"{onion_name}.onion"

    async def publish_to_dht(self):
        """
        Publish descriptor to Betanet DHT.

        Users lookup .onion address → get descriptor → establish circuit
        """
        await betanet_dht.put(
            key=self.onion_address,
            value=self.to_dict(),
        )
```

---

## Part 4: Dynamic Scaling (Week 5)

### 4.1 Mathematical Model: Load-Based Scaling

**Scaling Function:**
```
Define:
  Load(t) = (CPU_usage, Memory_usage, Network_usage)
  Threshold_high = (0.8, 0.8, 0.8)
  Threshold_low = (0.2, 0.2, 0.2)

Scale Out Trigger:
  Load(t) > Threshold_high for T_consecutive seconds

Scale In Trigger:
  Load(t) < Threshold_low for T_consecutive seconds

Scaling Amount:
  ΔR = α × (Load(t) - Threshold) × Current_R
  where α = scaling factor (e.g., 0.5 = 50% increase)
```

**Implementation:**

```python
# backend/server/services/autoscaler.py

class ContainerAutoscaler:
    """
    Automatically scales containers based on load.

    Monitors:
    - CPU usage
    - Memory usage
    - Network usage
    - Request latency

    Actions:
    - Scale out: Add more devices
    - Scale in: Remove devices
    - Migrate: Move to different devices
    """

    def __init__(
        self,
        orchestrator: FogContainerOrchestrator,
        lifecycle: ContainerLifecycleManager,
    ):
        self.orchestrator = orchestrator
        self.lifecycle = lifecycle

        # Thresholds
        self.scale_out_threshold = 0.8  # 80% utilization
        self.scale_in_threshold = 0.2   # 20% utilization
        self.consecutive_checks = 3     # Must exceed threshold 3 times

        # History
        self.load_history: Dict[ContainerID, List[float]] = {}

    async def monitor_and_scale(self, container: FogContainerModel):
        """
        Main scaling loop.

        Runs continuously while container is active.
        """
        while container.status == ContainerStatus.RUNNING:
            await asyncio.sleep(10)  # Check every 10 seconds

            # Get current load
            load = await self._get_load(container)

            # Record history
            if container.id not in self.load_history:
                self.load_history[container.id] = []
            self.load_history[container.id].append(load)

            # Keep last N measurements
            if len(self.load_history[container.id]) > 10:
                self.load_history[container.id].pop(0)

            # Check for scaling conditions
            recent_loads = self.load_history[container.id][-self.consecutive_checks:]

            if len(recent_loads) >= self.consecutive_checks:
                avg_load = sum(recent_loads) / len(recent_loads)

                if avg_load > self.scale_out_threshold:
                    await self._scale_out(container)
                elif avg_load < self.scale_in_threshold:
                    await self._scale_in(container)

    async def _get_load(self, container: FogContainerModel) -> float:
        """
        Calculate composite load metric.

        Load = max(CPU_usage, Memory_usage, Network_usage)
        Using max ensures we scale if ANY resource is saturated.
        """
        return max(
            container.cpu_usage_percent / 100.0,
            container.memory_usage_mb / container.memory_mb,
            (container.network_rx_mbps + container.network_tx_mbps) / container.bandwidth_mbps,
        )

    async def _scale_out(self, container: FogContainerModel):
        """
        Add more devices to container.

        Process:
        1. Calculate additional resources needed
        2. Allocate new devices
        3. Migrate partial workload to new devices
        4. Update container allocation
        """
        logger.info(f"Scaling out container {container.name}")

        # Need 50% more resources
        additional = ResourceVector(
            cpu_cores=container.cpu_cores * 0.5,
            memory_mb=container.memory_mb * 0.5,
            storage_mb=0,  # Don't need more storage
            bandwidth_mbps=container.bandwidth_mbps * 0.5,
        )

        # Allocate new devices
        new_devices = self.orchestrator.allocate_container(additional)
        if not new_devices:
            logger.warning("No available devices for scale out")
            return

        # Add to allocation
        container.allocated_devices.extend([str(d.id) for d in new_devices])
        container.cpu_cores += additional.cpu_cores
        container.memory_mb += additional.memory_mb
        container.bandwidth_mbps += additional.bandwidth_mbps

        await db.commit()

        # TODO: Migrate workload to new devices
        # For now: Just having more resources reduces load on primary

    async def _scale_in(self, container: FogContainerModel):
        """
        Remove excess devices from container.

        Process:
        1. Identify least utilized devices
        2. Migrate workload away
        3. Deallocate devices
        4. Update container allocation
        """
        logger.info(f"Scaling in container {container.name}")

        if len(container.allocated_devices) <= 1:
            # Can't scale below 1 device
            return

        # Remove last device (simplest heuristic)
        removed_device_id = container.allocated_devices.pop()

        # TODO: Migrate workload from removed device

        await db.commit()

        # Mark device as available again
        device = await device_registry.get(removed_device_id)
        await device_registry.mark_available(device)
```

**Premortem:**
- ❌ **Risk:** Thrashing (scale out → scale in → scale out repeatedly)
- ✅ **Mitigation:** Hysteresis - different thresholds for scale out (80%) vs scale in (20%)
- ❌ **Risk:** Scale out when no devices available
- ✅ **Mitigation:** Log warning, alert operator, queue scale request
- ❌ **Risk:** Scale in removes device mid-request
- ✅ **Mitigation:** Graceful drain - wait for active requests to complete

---

## Part 5: Web UI for Container Management (Week 6)

### 5.1 Frontend: Container Dashboard

**Page Structure:**
```
/containers
├── List View
│   ├── Container cards with status
│   ├── Create new container button
│   └── Filters (running, stopped, all)
├── Create Container Form
│   ├── Image selection
│   ├── Resource sliders
│   └── Environment variables
└── Container Detail View
    ├── Status and metrics
    ├── Allocated devices
    ├── Betanet .onion address
    ├── Logs viewer
    └── Actions (stop, restart, delete)
```

**Implementation:**

```typescript
// apps/control-panel/app/containers/page.tsx

'use client'

import { useState, useEffect } from 'react'
import { ContainerCard } from '@/components/ContainerCard'
import { CreateContainerForm } from '@/components/CreateContainerForm'

interface Container {
  id: string
  name: string
  image: string
  status: 'pending' | 'running' | 'stopped' | 'failed'
  requirements: {
    cpu_cores: number
    memory_mb: number
    storage_mb: number
    bandwidth_mbps: number
  }
  betanet: {
    onion_address?: string
  }
  allocated_devices: string[]
  created_at: string
}

export default function ContainersPage() {
  const [containers, setContainers] = useState<Container[]>([])
  const [showCreateForm, setShowCreateForm] = useState(false)

  useEffect(() => {
    fetchContainers()
    const interval = setInterval(fetchContainers, 5000) // Refresh every 5s
    return () => clearInterval(interval)
  }, [])

  async function fetchContainers() {
    const res = await fetch('/api/containers')
    const data = await res.json()
    setContainers(data.containers)
  }

  async function createContainer(formData: any) {
    const res = await fetch('/api/containers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData),
    })

    if (res.ok) {
      setShowCreateForm(false)
      fetchContainers()
    }
  }

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold">Fog Containers</h1>
        <button
          onClick={() => setShowCreateForm(true)}
          className="bg-blue-600 px-4 py-2 rounded hover:bg-blue-700"
        >
          + Create Container
        </button>
      </div>

      {showCreateForm && (
        <CreateContainerForm
          onCreate={createContainer}
          onCancel={() => setShowCreateForm(false)}
        />
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {containers.map(container => (
          <ContainerCard key={container.id} container={container} />
        ))}
      </div>

      {containers.length === 0 && !showCreateForm && (
        <div className="text-center py-16 text-gray-500">
          No containers yet. Create one to get started!
        </div>
      )}
    </div>
  )
}
```

**Container Card Component:**

```typescript
// apps/control-panel/components/ContainerCard.tsx

interface ContainerCardProps {
  container: Container
}

export function ContainerCard({ container }: ContainerCardProps) {
  const statusColors = {
    pending: 'bg-yellow-500',
    running: 'bg-green-500',
    stopped: 'bg-gray-500',
    failed: 'bg-red-500',
  }

  return (
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
      {/* Header */}
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-xl font-bold">{container.name}</h3>
          <p className="text-sm text-gray-400">{container.image}</p>
        </div>
        <span className={`px-2 py-1 rounded text-xs ${statusColors[container.status]}`}>
          {container.status}
        </span>
      </div>

      {/* Resources */}
      <div className="mb-4 text-sm">
        <div className="flex justify-between mb-1">
          <span className="text-gray-400">CPU:</span>
          <span>{container.requirements.cpu_cores} cores</span>
        </div>
        <div className="flex justify-between mb-1">
          <span className="text-gray-400">Memory:</span>
          <span>{(container.requirements.memory_mb / 1024).toFixed(1)} GB</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-400">Devices:</span>
          <span>{container.allocated_devices.length}</span>
        </div>
      </div>

      {/* Betanet Address */}
      {container.betanet.onion_address && (
        <div className="mb-4 p-3 bg-gray-900 rounded">
          <div className="text-xs text-gray-400 mb-1">Onion Address:</div>
          <div className="text-xs font-mono break-all">
            {container.betanet.onion_address}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2">
        <button className="flex-1 bg-blue-600 px-3 py-2 rounded text-sm hover:bg-blue-700">
          View Details
        </button>
        <button className="px-3 py-2 rounded text-sm bg-gray-700 hover:bg-gray-600">
          Stop
        </button>
      </div>
    </div>
  )
}
```

---

## Part 6: Testing & Validation (Week 7)

### 6.1 Integration Tests

```python
# backend/tests/integration/test_container_lifecycle.py

import pytest
from backend.server.services.container_lifecycle import ContainerLifecycleManager
from backend.server.services.fog_container_orchestrator import FogContainerOrchestrator

@pytest.mark.asyncio
async def test_create_container_end_to_end():
    """
    Test complete container creation flow:
    1. Create container request
    2. Allocate devices
    3. Deploy image
    4. Setup Betanet routing
    5. Start container
    6. Verify running
    """
    # Setup
    orchestrator = FogContainerOrchestrator(device_registry)
    lifecycle = ContainerLifecycleManager(orchestrator, betanet_service, device_registry)

    # Mock devices available
    for i in range(5):
        device_registry.register(MockDevice(
            id=f"device-{i}",
            cpu_cores=2.0,
            memory_mb=4096,
            battery_percent=80,
            is_charging=True,
        ))

    # Create container
    container = await lifecycle.create_container(
        name="test-website",
        image="nginx:latest",
        requirements=ResourceVector(
            cpu_cores=1.0,
            memory_mb=512,
            storage_mb=1024,
            bandwidth_mbps=10,
        ),
    )

    # Verify
    assert container.status == "running"
    assert len(container.allocated_devices) >= 1
    assert container.betanet_onion_address is not None
    assert container.betanet_onion_address.endswith(".onion")

    # Cleanup
    await lifecycle.stop_container(container.id)
```

---

## Part 7: Production Deployment (Week 8)

### 7.1 Update Docker Compose

```yaml
# docker-compose.yml

services:
  # ... existing services ...

  # Container orchestrator
  orchestrator:
    build:
      context: .
      dockerfile: backend/Dockerfile
    environment:
      - PYTHONPATH=/app
      - DATABASE_URL=${DATABASE_URL}
    command: python -m backend.server.services.container_orchestrator
    depends_on:
      - postgres
      - redis
    networks:
      - fog-network

  # Autoscaler
  autoscaler:
    build:
      context: .
      dockerfile: backend/Dockerfile
    environment:
      - PYTHONPATH=/app
      - DATABASE_URL=${DATABASE_URL}
    command: python -m backend.server.services.autoscaler
    depends_on:
      - postgres
      - redis
    networks:
      - fog-network
```

---

## Implementation Priority Matrix

### Critical Path (Must Do First)

```
Week 1: Foundation
├── Fix Python imports (ALL services must load)
├── Add missing __init__.py files
└── Install dependencies (psutil, etc.)

Week 2-3: Core Abstractions
├── ResourceVector class
├── FogContainerOrchestrator
├── FogContainerModel (database)
└── ContainerLifecycleManager

Week 4: Betanet Integration
├── BetanetRouter
├── HiddenServiceDescriptor
└── Circuit setup

Week 5: Dynamic Scaling
├── ContainerAutoscaler
└── Load monitoring

Week 6: UI
├── /containers page
├── Create container form
└── Container detail view

Week 7: Testing
└── Integration tests

Week 8: Production
└── Deploy
```

### Why This Order?

1. **Foundation → Abstractions:** Can't build orchestrator if services don't import
2. **Orchestrator → Lifecycle:** Lifecycle depends on orchestrator
3. **Lifecycle → Betanet:** Must have running containers before routing
4. **Betanet → Scaling:** Scaling needs stable routing
5. **Scaling → UI:** UI consumes backend APIs
6. **UI → Testing:** Test complete user flow
7. **Testing → Production:** Deploy with confidence

---

## Success Metrics

### Week 1 (Foundation)
- ✅ All 6 service managers initialize without errors
- ✅ `is_ready()` returns `True`
- ✅ Backend starts without import errors

### Week 3 (Core)
- ✅ Can allocate devices to virtual containers
- ✅ Container state machine works (Pending → Running)
- ✅ Database persists container state

### Week 4 (Betanet)
- ✅ .onion address generated for each container
- ✅ Traffic routes through Betanet to container
- ✅ Privacy guarantee maintained

### Week 5 (Scaling)
- ✅ Autoscaler triggers on load
- ✅ Devices added/removed dynamically
- ✅ No thrashing observed

### Week 6 (UI)
- ✅ Can create container from UI
- ✅ See container status in real-time
- ✅ Copy .onion address with one click

### Week 7 (Testing)
- ✅ 80%+ test coverage
- ✅ E2E test passes
- ✅ No critical bugs

### Week 8 (Production)
- ✅ Docker Compose deploys cleanly
- ✅ Monitoring dashboards show metrics
- ✅ Can host demo website on fog compute

---

## Final Premortem: What Could Go Wrong?

### Category 1: Technical Risks

**Risk:** ILP solver too slow for real-time allocation
**Probability:** Medium
**Impact:** High
**Mitigation:** Fallback to greedy First-Fit Decreasing algorithm

**Risk:** Devices churn too fast (30s average uptime)
**Probability:** Low (most phones idle for >1hr)
**Impact:** Critical
**Mitigation:** Require minimum 5min commitment, penalize early exit

**Risk:** Container image too large to deploy on phones
**Probability:** High (Docker images are GB-sized)
**Impact:** High
**Mitigation:** Custom lightweight image format, content-addressed chunks

**Risk:** Betanet circuit setup fails frequently
**Probability:** Medium
**Impact:** High
**Mitigation:** Retry with backoff, fallback to direct (non-private) connection

### Category 2: Architectural Risks

**Risk:** Primary-replica model doesn't scale
**Probability:** Medium
**Impact:** Medium
**Mitigation:** Move to distributed execution model (Phase 2)

**Risk:** Database becomes bottleneck
**Probability:** Medium
**Impact:** Medium
**Mitigation:** Read replicas, caching layer (Redis)

### Category 3: Operational Risks

**Risk:** No way to debug failed containers
**Probability:** High
**Impact:** High
**Mitigation:** Centralized logging, log aggregation via Loki

**Risk:** Billing/accounting for resource usage not implemented
**Probability:** High (out of scope)
**Impact:** Low (for MVP)
**Mitigation:** Phase 2 feature

---

## Conclusion

This ULTRATHINK plan provides:

1. **Mathematical Foundation** - Every abstraction grounded in formal models
2. **Dependency-Ordered Implementation** - Each piece enables the next
3. **Premortem Analysis** - Risks identified and mitigated upfront
4. **Clear Success Metrics** - Know when each phase is complete
5. **Production-Ready Design** - Not just prototypes, but deployable code

**The Core Insight:**

Fog compute + Dynamic containers + Betanet privacy = **Decentralized, privacy-preserving web hosting powered by idle phones**

This is fundamentally new infrastructure that enables websites to run on distributed devices, routed through privacy networks, scaled dynamically based on load - all without revealing the hosting devices or user locations.

---

*Ready to begin implementation. Start with Week 1: Foundation fixes.*
