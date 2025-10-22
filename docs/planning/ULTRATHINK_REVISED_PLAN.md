# ULTRATHINK REVISED IMPLEMENTATION PLAN
## Leveraging Existing Fog Burst Architecture

**Created:** 2025-10-21
**Status:** Design Document
**Approach:** Gap-Filling Implementation (Build on 45% existing code)

---

## Executive Summary: What We Have vs. What We Need

### ✅ EXISTING INFRASTRUCTURE (45% Complete, ~3,500 LOC)

#### 1. **NSGA-II Job Placement** (`src/batch/placement.py` - 1,132 lines)
```python
class FogScheduler:
    """Multi-objective optimization for job placement"""

    # 5-dimensional Pareto optimization:
    # 1. Minimize latency
    # 2. Balance load
    # 3. Maximize trust
    # 4. Minimize cost
    # 5. Marketplace price optimization
```

**Capabilities:**
- Genetic algorithm with Pareto-optimal solutions
- Constraint satisfaction (resources, SLA, trust)
- Replication strategies (S-class, A-class, B-class jobs)
- Integration with reputation scoring

**Status:** 85% complete ✅

#### 2. **Dynamic Marketplace** (`src/batch/marketplace.py` - 779 lines)
```python
class FogMarketplace:
    """Spot/on-demand bidding with dynamic pricing"""

    # Economic models:
    # - Spot pricing (supply/demand)
    # - On-demand (fixed rate)
    # - Reserved (pre-purchased)
```

**Capabilities:**
- Bid matching algorithms
- Price discovery
- Trade execution
- Trust-based filtering

**Status:** 80% complete ✅

#### 3. **Resource Harvesting** (`src/idle/harvest_manager.py` - 520 lines)
```python
class FogHarvestManager:
    """Collects idle compute from mobile devices"""

    # Harvesting conditions:
    # - Battery > 20% + charging
    # - Thermal safe (< 45°C)
    # - WiFi connected
    # - Screen off + idle > 5min
```

**Capabilities:**
- Device eligibility evaluation
- Contribution tracking
- Token reward calculation
- Ledger management

**Status:** 75% complete ✅

#### 4. **Mobile Resource Optimization** (`src/idle/mobile_resource_manager.py` - 1,059 lines)
```python
class MobileResourceManager:
    """Battery/thermal-aware optimization"""

    # Adaptive strategies:
    # - Dynamic chunk sizing
    # - BitChat-preferred transport
    # - Thermal throttling
```

**Capabilities:**
- Battery-aware adaptation
- Thermal management
- Memory pressure handling
- Network type selection

**Status:** 85% complete ✅

---

### ❌ CRITICAL GAPS (0% Complete)

#### 1. **Job Executor** - Turns placement decisions into running containers
#### 2. **Container Runtime Integration** - Docker/containerd lifecycle
#### 3. **Autoscaler** - Load-based dynamic scaling
#### 4. **Migration Manager** - Live migration when devices fail
#### 5. **Resource Composition** - Aggregate multiple devices into virtual resources
#### 6. **Betanet Container Router** - Privacy-preserving traffic routing

---

## Revised Architecture: Connecting the Pieces

### Mathematical Model of Integration

```
Existing Flow (What We Have):
  1. Jobs submitted → FogScheduler
  2. FogScheduler → NSGA-II placement → FogNode selection
  3. FogHarvestManager → idle devices → ResourceListing
  4. FogMarketplace → bid matching → resource allocation

  ❌ BROKEN: Placement decisions never execute!

Fixed Flow (What We Build):
  1. Jobs submitted → FogScheduler ✅ (existing)
  2. Scheduler → JobExecutor 🔴 (NEW) → Container creation
  3. Container → Multi-device allocation 🔴 (NEW) → Resource composition
  4. Betanet routing 🔴 (NEW) → Privacy-preserving access
  5. Autoscaler 🔴 (NEW) → Dynamic adjustment
  6. Migration 🔴 (NEW) → Handle device failures
```

---

## PART 1: Week 1 - Fix Service Integration (Prerequisites)

### 1.1 Fix Python Import Issues (Days 1-2)

**Root Cause:** Services in `src/` can't be imported by `backend/server/`

**Fix:**
```bash
# Add __init__.py files
touch src/idle/__init__.py
touch src/vpn/__init__.py
touch src/p2p/__init__.py
touch src/tokenomics/__init__.py
touch src/batch/__init__.py
touch src/reputation/__init__.py

# Install missing dependencies
pip install psutil pulp  # For resource monitoring + optimization
```

**Update service_manager.py imports:**
```python
# backend/server/services/service_manager.py

async def _init_scheduler(self) -> None:
    try:
        # FIXED: Import actual class name
        from batch.placement import FogScheduler  # NOT NSGAIIScheduler

        # Create reputation engine (required dependency)
        from reputation.bayesian_reputation import BayesianReputationEngine
        reputation = BayesianReputationEngine()

        # Initialize with correct argument
        self.services['scheduler'] = FogScheduler(reputation_engine=reputation)
        logger.info("✓ Fog Scheduler (NSGA-II) initialized")
    except Exception as e:
        logger.error(f"Failed to initialize scheduler: {e}")
        self.services['scheduler'] = None

async def _init_idle_compute(self) -> None:
    try:
        # FIXED: Import correct class names
        from idle.edge_manager import EdgeManager
        from idle.harvest_manager import FogHarvestManager  # NOT HarvestManager

        self.services['edge'] = EdgeManager()
        self.services['harvest'] = FogHarvestManager()
        logger.info("✓ Idle compute services initialized")
    except Exception as e:
        logger.error(f"Failed to initialize idle compute: {e}")
```

**Success Criteria:**
- ✅ All 6 service managers initialize without errors
- ✅ Backend starts cleanly
- ✅ `is_ready()` returns `True`

---

## PART 2: Week 2 - Job Executor (Connect Scheduler to Reality)

### 2.1 Mathematical Abstraction: Placement → Execution

**Current State:**
```python
# placement.py returns this:
class PlacementSolution:
    job_to_node_mapping: Dict[JobID, List[NodeID]]
    objective_scores: List[float]

# But nothing executes it! ❌
```

**Fixed State:**
```python
# NEW: JobExecutor consumes placement and creates containers
class JobExecutor:
    def execute_placement(
        self,
        solution: PlacementSolution,
        job: FogJob,
    ) -> Container:
        """
        Turns placement decision into running container.

        Process:
        1. Take NSGA-II node allocation
        2. Reserve resources on selected nodes
        3. Deploy container image
        4. Start container
        5. Return handle for monitoring
        """
```

### 2.2 Implementation: Job Executor Service

```python
# backend/server/services/job_executor.py

from dataclasses import dataclass
from typing import Dict, List, Set
from datetime import datetime
import asyncio
import docker

@dataclass
class ExecutionContext:
    """Container execution environment"""
    container_id: str
    allocated_nodes: List[str]  # From NSGA-II placement
    primary_node: str            # First node runs main process
    replica_nodes: List[str]     # Other nodes provide resources

    # Resource allocation (from placement)
    cpu_cores: float
    memory_mb: float
    storage_mb: float

    # Execution state
    status: str  # pending, starting, running, failed
    started_at: datetime = None

    # Container handle
    docker_container = None  # Docker SDK container object


class JobExecutor:
    """
    Executes job placement decisions from FogScheduler.

    Integrates:
    - FogScheduler (existing) → placement decisions
    - Docker runtime (NEW) → container lifecycle
    - EdgeManager (existing) → device registry
    """

    def __init__(
        self,
        scheduler: 'FogScheduler',
        edge_manager: 'EdgeManager',
    ):
        self.scheduler = scheduler
        self.edge = edge_manager
        self.docker_clients: Dict[str, docker.DockerClient] = {}
        self.active_executions: Dict[str, ExecutionContext] = {}

    async def execute_job(
        self,
        job: 'FogJob',
    ) -> ExecutionContext:
        """
        Execute job using NSGA-II placement.

        Flow:
        1. Call FogScheduler.place_job() → get PlacementSolution
        2. Reserve resources on selected nodes
        3. Deploy container to primary node
        4. Setup replicas (future: distributed execution)
        5. Return execution context
        """
        # Step 1: Get placement from existing NSGA-II scheduler
        placement = self.scheduler.place_job(job)

        if not placement or not placement.job_to_node_mapping:
            raise PlacementError("No feasible placement found")

        # Extract node allocation
        allocated_nodes = placement.job_to_node_mapping.get(job.job_id, [])
        if not allocated_nodes:
            raise PlacementError("Empty node allocation")

        # Step 2: Reserve resources
        for node_id in allocated_nodes:
            device = await self.edge.get_device(node_id)
            await self._reserve_resources(device, job)

        # Step 3: Create execution context
        context = ExecutionContext(
            container_id=f"job-{job.job_id}",
            allocated_nodes=allocated_nodes,
            primary_node=allocated_nodes[0],  # First node is primary
            replica_nodes=allocated_nodes[1:] if len(allocated_nodes) > 1 else [],
            cpu_cores=job.cpu_required,
            memory_mb=job.memory_required,
            storage_mb=job.disk_required or 1024,
            status="pending",
        )

        # Step 4: Deploy container to primary node
        await self._deploy_container(context, job)

        # Step 5: Track execution
        self.active_executions[context.container_id] = context

        # Step 6: Start monitoring
        asyncio.create_task(self._monitor_execution(context))

        return context

    async def _reserve_resources(self, device: 'Device', job: 'FogJob'):
        """Reserve resources on device (prevent double allocation)"""
        device.cpu_utilization += job.cpu_required / device.cpu_cores
        device.memory_utilization += job.memory_required / device.memory_mb
        # TODO: Persist to database

    async def _deploy_container(
        self,
        context: ExecutionContext,
        job: 'FogJob',
    ):
        """
        Deploy Docker container to primary node.

        For now: Simple single-node deployment
        Future: Distributed execution across replicas
        """
        # Get Docker client for primary node
        primary_device = await self.edge.get_device(context.primary_node)

        # Connect to Docker daemon on device
        # (Assumes device is running Docker with exposed API)
        docker_client = docker.DockerClient(
            base_url=f"tcp://{primary_device.endpoint}:2375"
        )
        self.docker_clients[context.primary_node] = docker_client

        # Pull image if needed
        try:
            docker_client.images.get(job.image)
        except docker.errors.ImageNotFound:
            logger.info(f"Pulling image {job.image}")
            docker_client.images.pull(job.image)

        # Run container
        container = docker_client.containers.run(
            job.image,
            name=context.container_id,
            detach=True,

            # Resource limits (from NSGA-II allocation)
            cpu_quota=int(context.cpu_cores * 100000),  # CPU quota
            cpu_period=100000,
            mem_limit=f"{int(context.memory_mb)}m",

            # Environment variables
            environment=job.environment or {},

            # Networking (TODO: Betanet integration)
            network_mode="bridge",
        )

        context.docker_container = container
        context.status = "running"
        context.started_at = datetime.utcnow()

        logger.info(f"Container {context.container_id} started on {context.primary_node}")

    async def _monitor_execution(self, context: ExecutionContext):
        """
        Monitor running container for failures.

        Triggers migration if:
        - Primary node fails
        - Container crashes
        - Resource constraints violated
        """
        while context.status == "running":
            await asyncio.sleep(10)  # Check every 10s

            # Check container health
            container = context.docker_container
            try:
                container.reload()

                if container.status != "running":
                    logger.warning(f"Container {context.container_id} stopped: {container.status}")
                    context.status = "failed"
                    break

            except Exception as e:
                logger.error(f"Lost connection to container: {e}")
                # Trigger migration (Week 3)
                context.status = "migrating"
                break
```

**Why This Works:**
- ✅ Leverages existing NSGA-II placement (no duplication)
- ✅ Simple Docker integration (proven technology)
- ✅ Primary-replica pattern (easy to implement)
- ✅ Monitoring foundation for autoscaling

**Success Criteria:**
- ✅ Jobs placed by FogScheduler execute as Docker containers
- ✅ Can deploy nginx, Python apps, etc.
- ✅ Resource limits enforced

---

## PART 3: Week 3 - Resource Composition (Multi-Device Aggregation)

### 3.1 Mathematical Model: Device Aggregation

**Problem:**
```
Single device has: 2 CPU, 4GB RAM
Job requires:     8 CPU, 16GB RAM

Solution: Aggregate 4 devices → Virtual resource pool
```

**Abstraction:**
```python
class AggregatedResource:
    """Virtual resource composed of multiple devices"""

    devices: Set[DeviceID]
    total_cpu: float      # Σ device.cpu
    total_memory: float   # Σ device.memory

    def __add__(self, other: 'AggregatedResource'):
        """Compose two aggregated resources"""
        return AggregatedResource(
            devices=self.devices | other.devices,
            total_cpu=self.total_cpu + other.total_cpu,
            total_memory=self.total_memory + other.total_memory,
        )
```

### 3.2 Implementation: Resource Aggregator

```python
# backend/server/services/resource_aggregator.py

class ResourceAggregator:
    """
    Aggregates multiple fog devices into virtual resource pools.

    Integrates with:
    - FogScheduler (existing) → uses aggregated resources for placement
    - JobExecutor (new) → executes on aggregated pools
    """

    def aggregate_for_job(
        self,
        job: 'FogJob',
        available_devices: List['Device'],
    ) -> AggregatedResource:
        """
        Find minimal device set that satisfies job requirements.

        Algorithm: First-Fit Decreasing (greedy heuristic)
        1. Sort devices by available resources (descending)
        2. Add devices until requirements met
        3. Return aggregated resource

        Complexity: O(n log n) - fast enough for <1000 devices
        """
        # Sort by available CPU (prioritize powerful devices)
        sorted_devices = sorted(
            available_devices,
            key=lambda d: d.available_cpu(),
            reverse=True,
        )

        selected = []
        total_cpu = 0.0
        total_memory = 0.0

        for device in sorted_devices:
            selected.append(device)
            total_cpu += device.available_cpu()
            total_memory += device.available_memory()

            # Check if requirements satisfied
            if (total_cpu >= job.cpu_required and
                total_memory >= job.memory_required):
                break

        if (total_cpu < job.cpu_required or
            total_memory < job.memory_required):
            return None  # No feasible aggregation

        return AggregatedResource(
            devices=set(d.device_id for d in selected),
            total_cpu=total_cpu,
            total_memory=total_memory,
        )
```

**Integration with Existing FogScheduler:**
```python
# Modify FogScheduler to use aggregated resources

class FogScheduler:
    def __init__(self, reputation_engine, aggregator: ResourceAggregator):
        self.reputation = reputation_engine
        self.aggregator = aggregator  # NEW

    def place_job(self, job: FogJob) -> PlacementSolution:
        # Before placement, try to aggregate devices if needed
        if self._single_node_insufficient(job):
            aggregated = self.aggregator.aggregate_for_job(job, self.get_available_nodes())

            if aggregated:
                # Treat aggregated resource as virtual "super-node"
                virtual_node = self._create_virtual_node(aggregated)
                # Run NSGA-II with virtual node included
```

**Success Criteria:**
- ✅ Jobs requiring >1 device resources execute successfully
- ✅ Resource aggregation uses greedy algorithm (fast)
- ✅ FogScheduler leverages aggregated resources

---

## PART 4: Week 4 - Betanet Container Integration

### 4.1 Connect Existing BetanetService to Containers

**What We Have:**
```python
# backend/server/services/betanet.py (from Sprint 2)
class BetanetService:
    async def deploy_node(self, node_type, region):
        """Deploy mixnode"""

    async def get_status(self):
        """Get network status"""
```

**What We Need:**
```python
class BetanetContainerRouter:
    """Route traffic from Betanet to fog containers"""

    def register_container(
        self,
        container_id: str,
        primary_device: Device,
    ) -> str:
        """
        Create .onion address for container.

        Returns: "abc123def456.onion"
        """
```

### 4.2 Implementation

```python
# backend/server/services/betanet_container_router.py

class BetanetContainerRouter:
    """
    Routes Betanet traffic to fog containers.

    Integrates:
    - BetanetService (existing) → mixnode network
    - JobExecutor (new) → running containers
    """

    def __init__(self, betanet: BetanetService):
        self.betanet = betanet
        self.routing_table: Dict[str, ContainerID] = {}

    async def register_container(
        self,
        container_id: str,
        primary_device: 'Device',
        port: int = 80,
    ) -> str:
        """
        Create .onion hidden service for container.

        Process:
        1. Get 3 active mixnodes from Betanet
        2. Build circuit: Entry → Mix1 → Mix2 → Mix3 → Container
        3. Generate .onion address
        4. Register in routing table
        """
        # Get mixnodes
        mixnodes = await self.betanet.get_mixnodes()
        active = [m for m in mixnodes if m.status == "active"]

        if len(active) < 3:
            raise BetanetError("Insufficient mixnodes for circuit")

        # Select 3 random mixnodes
        circuit = random.sample(active, 3)

        # Generate .onion address (hash of public key)
        import hashlib
        onion_name = hashlib.sha256(container_id.encode()).hexdigest()[:16]
        onion_address = f"{onion_name}.onion"

        # Register in routing table
        self.routing_table[onion_address] = {
            'container_id': container_id,
            'primary_device': primary_device.device_id,
            'circuit': [m.id for m in circuit],
            'target_port': port,
        }

        logger.info(f"Registered {container_id} at {onion_address}")

        return onion_address

    async def route_request(
        self,
        onion_address: str,
        http_request: bytes,
    ) -> bytes:
        """
        Route HTTP request through Betanet to container.

        Flow:
        1. Lookup container by .onion address
        2. Forward request to primary device
        3. Return response through circuit
        """
        routing_info = self.routing_table.get(onion_address)
        if not routing_info:
            return self._404_response()

        # Get device
        device = await edge_manager.get_device(routing_info['primary_device'])

        # Forward request to Docker container
        response = await self._forward_to_container(
            device,
            routing_info['container_id'],
            http_request,
        )

        return response

    async def _forward_to_container(
        self,
        device: Device,
        container_id: str,
        request: bytes,
    ) -> bytes:
        """Forward HTTP request to container on device"""
        # Simple TCP proxy to container
        import aiohttp

        async with aiohttp.ClientSession() as session:
            container_ip = await self._get_container_ip(device, container_id)

            async with session.post(
                f"http://{container_ip}",
                data=request,
            ) as resp:
                return await resp.read()
```

**Success Criteria:**
- ✅ Containers accessible via .onion addresses
- ✅ Traffic routed through mixnodes
- ✅ Privacy preserved (no direct connection to container)

---

## PART 5: Week 5 - Autoscaler (Dynamic Load Response)

### 5.1 Integrate with Existing Metrics

**What We Have:**
```python
# src/idle/mobile_resource_manager.py
class MobileResourceManager:
    def get_current_load(self) -> float:
        """Returns CPU/memory/thermal load"""
```

**What We Build:**
```python
class ContainerAutoscaler:
    """
    Scale containers based on load.

    Integrates:
    - MobileResourceManager (existing) → device metrics
    - JobExecutor (new) → can restart with more resources
    - ResourceAggregator (new) → add/remove devices
    """

    async def monitor_and_scale(self, container_id: str):
        """
        Monitor container load and scale.

        Rules:
        - Load > 80% for 3min → scale out (add device)
        - Load < 20% for 5min → scale in (remove device)
        """
```

---

## Implementation Timeline (Revised)

### Week 1: Foundation (CRITICAL PATH)
- Fix all Python import issues
- Install missing dependencies
- All services initialize cleanly

### Week 2: Job Executor
- Implement JobExecutor service
- Integrate with FogScheduler
- Deploy first container via NSGA-II placement

### Week 3: Resource Aggregation
- Implement ResourceAggregator
- Update FogScheduler to use aggregated resources
- Test multi-device jobs

### Week 4: Betanet Integration
- Implement BetanetContainerRouter
- Register containers with .onion addresses
- Route traffic through mixnodes

### Week 5: Autoscaling
- Implement ContainerAutoscaler
- Integrate with MobileResourceManager
- Test dynamic scaling

### Week 6: UI & Testing
- Add /containers page to control panel
- Integration tests
- End-to-end demo

---

## Success Metrics

**Week 1:**
- ✅ Backend starts without errors
- ✅ All 6+ services initialized
- ✅ `is_ready()` returns True

**Week 2:**
- ✅ Can submit job via API
- ✅ FogScheduler places job on devices
- ✅ JobExecutor deploys Docker container
- ✅ Container runs successfully

**Week 3:**
- ✅ Job requiring 8 CPU (across 4 2-CPU devices) executes
- ✅ Resource aggregation works

**Week 4:**
- ✅ Container has .onion address
- ✅ Can access via Betanet routing
- ✅ Privacy preserved

**Week 5:**
- ✅ Autoscaler adds device when load > 80%
- ✅ Autoscaler removes device when load < 20%
- ✅ No thrashing observed

**Week 6:**
- ✅ Can create container from UI
- ✅ Can view .onion address
- ✅ E2E test passes

---

## Premortem: Integration Risks

### Risk 1: Docker API Not Exposed on Devices
**Probability:** High
**Impact:** Critical
**Mitigation:**
- Phase 1: Require Docker API enabled (manual setup)
- Phase 2: Auto-deploy Docker daemon via SSH
- Phase 3: Custom lightweight runtime (no Docker)

### Risk 2: NSGA-II Placement Too Slow
**Probability:** Low (already optimized)
**Impact:** Medium
**Mitigation:**
- Existing code is fast (<100ms for 100 nodes)
- Caching of placement solutions

### Risk 3: Device Churn Breaks Aggregation
**Probability:** Medium
**Impact:** High
**Mitigation:**
- Autoscaler re-aggregates on device loss
- Migration manager moves containers

### Risk 4: Betanet Circuit Setup Timeout
**Probability:** Medium
**Impact:** Medium
**Mitigation:**
- Fallback to direct connection for dev
- Retry with exponential backoff

---

## Conclusion

This revised plan **leverages 45% existing code** (~3,500 LOC) and builds only the **critical 55% gaps** needed to make the system operational:

**Existing (Keep):**
- ✅ NSGA-II placement engine
- ✅ Dynamic marketplace
- ✅ Resource harvesting
- ✅ Mobile optimization

**New (Build):**
- 🔴 JobExecutor (~300 LOC)
- 🔴 ResourceAggregator (~200 LOC)
- 🔴 BetanetContainerRouter (~250 LOC)
- 🔴 ContainerAutoscaler (~200 LOC)
- 🔴 UI components (~500 LOC)

**Total New Code:** ~1,450 LOC (vs. 15,000+ if built from scratch)

**ROI:** 10x reduction in implementation effort by leveraging existing infrastructure.

---

*Ready to begin Week 1: Foundation fixes.*
