# Container Runtime Security & Architecture Audit

## Executive Summary

This audit compares the new `container_runtime` module against the existing fog-compute architecture to identify security risks, bugs, integration gaps, and architectural misalignments.

**Verdict**: The container runtime layer is a solid foundation but requires significant security hardening and integration work before production deployment.

| Category | Status | Critical Issues |
|----------|--------|-----------------|
| Security | HIGH RISK | No authentication, no encryption, no distributed locking |
| Architecture | GAPS | Doesn't integrate with MeshService, BatteryValidator |
| Coding Quality | MEDIUM | Race conditions, unwaited coroutines |
| Multi-Burst Support | PARTIAL | Scheduler supports it, but coordinator bottleneck risk |
| Mobile Throttling | MISSING | No integration with existing BatteryValidator |

---

## 1. Security Risks

### 1.1 CRITICAL: No Authentication in Container Runtime

**Issue**: `container_runtime/scheduler.py` accepts container submissions without authentication.

**Existing Pattern**: `mesh_service.py` (PHASE0-SEC-001) implements:
- Token-based authentication with hash storage (line 330-356)
- Token validation via `validate_token()` (line 577-588)
- 7-day token expiry with revocation support

**Risk**: Any node can submit containers to the scheduler without verification.

**Recommendation**: Integrate with MeshPersistenceService for token validation:
```python
# scheduler.py should add:
async def submit_container(self, spec: ContainerSpec, mesh_token: str) -> Container:
    device_id = await self._persistence.validate_token(mesh_token)
    if not device_id:
        raise AuthenticationError("Invalid mesh token")
    # ... rest of submission logic
```

### 1.2 CRITICAL: No Distributed Locking in Container Runtime

**Issue**: `scheduler.py` uses a single `asyncio.Lock()` which only works within one process.

**Existing Pattern**: `mesh_service.py` (PHASE1-COORD-002) implements:
- `_registry_lock` for device join/leave operations (line 143)
- `_role_lock` for role transitions and elections (line 144)
- Careful lock ordering to prevent deadlocks (lines 457-474)

**Risk**: Multiple coordinator instances can cause split-brain container placement.

**Recommendation**: Add distributed locking:
```python
# Use the same pattern from mesh_service.py
self._scheduler_lock = asyncio.Lock()  # Per-instance
# Plus: Integrate with coordination layer for cross-instance locking
```

### 1.3 HIGH: No Persistence for Container State

**Issue**: `scheduler.py` stores all state in memory dicts (`_nodes`, `_containers`).

**Existing Pattern**: `mesh_service.py` (PHASE0-SEC-001) uses SQLite persistence:
- `MeshPersistenceService` for durable storage (line 122)
- In-memory cache with DB as authoritative source (line 126)
- Cache rebuild on startup (lines 148-201)

**Risk**: Server restart loses all container state.

**Recommendation**: Add SQLite persistence for containers and placements.

### 1.4 HIGH: No Volume Encryption

**Issue**: `storage.py` replicates volumes without encryption.

**Risk**: Volume data exposed during network transfer and at rest.

**Recommendation**: Add encryption layer for distributed volumes:
- At-rest encryption with device-specific keys
- In-transit encryption via TLS or mesh network encryption

### 1.5 MEDIUM: No Node Trust Scoring

**Issue**: `scheduler.py` trusts all registered nodes equally.

**Existing Pattern**: `battery_validator.py` (PHASE4-PWA-003) implements:
- Trust scoring per device (lines 75-89)
- Trust decay on anomalies (line 139)
- Trust recovery on valid reports (line 140)

**Recommendation**: Add trust scoring to FogNode:
```python
@dataclass
class FogNode:
    # ... existing fields
    trust_score: float = 1.0
    anomaly_count: int = 0
```

---

## 2. Architecture Integration Gaps

### 2.1 CRITICAL: Separate Device Registries

**Problem**: Container runtime uses `FogNode` while mesh service uses `MeshDevice`.

| container_runtime/scheduler.py | server/services/mesh_service.py |
|-------------------------------|--------------------------------|
| `FogNode` dataclass | `MeshDevice` dataclass |
| `_nodes: dict[str, FogNode]` | `_devices_cache: dict[str, MeshDevice]` |
| No persistence | SQLite persistence |
| No roles | Roles: PRIMARY, SECONDARY, WORKER, MOBILE, EDGE |

**Impact**: Two separate sources of truth for the same physical devices.

**Recommendation**: Unify into single device registry:
```python
# Option A: FogNode extends MeshDevice capabilities
# Option B: Container runtime queries MeshService for device info
# Option C: Shared device model in common module
```

### 2.2 CRITICAL: No Integration with BatteryValidator

**Problem**: Container scheduler doesn't check mobile device battery status.

**Existing Throttles** (battery_validator.py):
- Max charge rate: 3%/min (line 131)
- Max discharge rate: 5%/min (line 132)
- Physics-based anomaly detection (lines 252-303)
- Rate limiting: 1 hour after 3 anomalies (lines 137-138)
- Trust scoring with decay/recovery (lines 139-140)

**Impact**: Containers can be scheduled on battery-limited mobile devices.

**Recommendation**: Add battery check to scheduling:
```python
async def _select_node(self, spec: ContainerSpec) -> Optional[FogNode]:
    available_nodes = []
    for node in self._nodes.values():
        if node.device_type in ("phone", "tablet"):
            # Check battery validator
            if battery_validator.is_device_rate_limited(node.node_id):
                continue
            if battery_validator.get_device_trust_score(node.node_id) < 0.5:
                continue
        if node.is_available and node.can_fit(spec):
            available_nodes.append(node)
```

### 2.3 HIGH: Device Roles Not Considered

**Problem**: Container scheduler ignores device roles from mesh_service.

**Mesh Service Roles** (DeviceRole enum):
- `PRIMARY`: Main coordinator
- `SECONDARY`: Backup coordinator
- `WORKER`: Standard compute node
- `MOBILE`: Mobile device (limited)
- `EDGE`: Edge device (limited)

**Impact**: Heavy containers could be scheduled on coordinator or limited devices.

**Recommendation**: Add role-based placement constraints:
```python
# Don't schedule heavy workloads on PRIMARY/SECONDARY (they coordinate)
# Limit resources on MOBILE/EDGE devices
if node.device_type in ("mobile", "edge"):
    max_cpu = min(spec.resources.cpu_cores, node.cpu_cores * 0.5)
```

### 2.4 MEDIUM: Heartbeat Systems Not Unified

**Problem**: Both systems have separate heartbeat mechanisms.

| container_runtime/scheduler.py | mesh_service.py |
|-------------------------------|-----------------|
| `node_heartbeat_timeout_sec: 60` | `heartbeat_timeout_sec: 90` |
| Simple last_heartbeat check | Monotonic clock (PHASE1-COORD-003) |
| No jitter | Jitter buffer to prevent thundering herd |

**Recommendation**: Use mesh_service heartbeat as single source of truth.

---

## 3. Multiple Simultaneous Fog Bursts

### 3.1 Current Support

The container scheduler DOES support multiple simultaneous fog bursts:
- `_pending_queue` handles multiple container submissions (line 200)
- `_process_pending()` schedules all pending containers (lines 385-409)
- Each container gets independent placement decision

### 3.2 Bottleneck Risks

| Risk | Location | Impact |
|------|----------|--------|
| Single scheduler instance | `FogScheduler` | All scheduling goes through one coordinator |
| Single lock | `_lock = asyncio.Lock()` | Serializes all operations |
| No sharding | `_select_node()` | Evaluates all nodes for every container |

### 3.3 Scalability Recommendations

1. **Distribute Scheduling**: Allow multiple scheduler instances with coordination
2. **Node Sharding**: Partition nodes by zone for parallel scheduling
3. **Async Placement**: Don't hold lock during node selection

```python
# Current (holds lock during selection):
async def _process_pending(self) -> None:
    async with self._lock:  # PROBLEM: Blocks everything
        for container_id in list(self._pending_queue):
            node = await self._select_node(container.spec)

# Recommended (release lock during selection):
async def _process_pending(self) -> None:
    async with self._lock:
        pending = list(self._pending_queue)
    # No lock held during node selection
    for container_id in pending:
        node = await self._select_node(container.spec)
        async with self._lock:  # Brief lock for placement
            await self._place_container(container, node)
```

---

## 4. Coding Issues

### 4.1 BUG: Unwaited Coroutine in __init__

**Location**: `network.py:209`
```python
def __init__(self, config: Optional[NetworkConfig] = None):
    # ...
    asyncio.create_task(self._create_default_network())  # Not awaited!
```

**Risk**: If accessed before network creation completes, `get_default_network()` returns None.

**Fix**: Either await in async context or make network creation explicit:
```python
async def initialize(self) -> None:
    await self._create_default_network()
```

### 4.2 BUG: Race Condition in IP Allocation

**Location**: `network.py:431-453`
```python
def _allocate_ip(self, network_id: str) -> Optional[str]:
    # No lock around IP allocation!
    next_offset = self._next_ip.get(network_id, 2)
    # ...
    self._ip_allocations[network_id][ip] = ""  # Race condition
```

**Risk**: Concurrent calls can allocate same IP to different containers.

**Fix**: Must be called within `_lock` context (currently is, but method doesn't enforce it).

### 4.3 MEDIUM: No Cleanup on Scheduler Stop

**Location**: `scheduler.py:225-236`
```python
async def stop(self) -> None:
    self._is_running = False
    # No cleanup of running containers!
```

**Risk**: Running containers orphaned on shutdown.

**Recommendation**: Add graceful shutdown:
```python
async def stop(self, timeout_sec: int = 30) -> None:
    self._is_running = False
    # Stop accepting new containers
    # Wait for pending to complete or timeout
    # Notify node agents to handle containers
```

### 4.4 MEDIUM: Missing Error Handling in Volume Sync

**Location**: `storage.py:461-495`
```python
async def _sync_replicas(self) -> None:
    # Actual sync would be done by node agents
    # Here we just track the state
    replica.last_sync = datetime.now(UTC)
    replica.sync_status = "synced"  # Always succeeds - unrealistic
```

**Issue**: Sync always succeeds, no actual data transfer or error handling.

---

## 5. Integration Recommendations

### 5.1 Phase 1: Security Hardening (Required Before Production)

1. **Add Authentication**
   - Integrate with MeshPersistenceService for token validation
   - Require mesh_token on all container operations

2. **Add Distributed Locking**
   - Use coordination layer for cross-instance locking
   - Follow mesh_service.py patterns (registry_lock, role_lock)

3. **Add Persistence**
   - SQLite backend for container state
   - In-memory cache with DB as source of truth

### 5.2 Phase 2: Architecture Unification

1. **Unify Device Registry**
   - Either merge FogNode and MeshDevice
   - Or have container runtime query MeshService

2. **Integrate Battery Throttling**
   - Check BatteryValidator before scheduling on mobile devices
   - Respect rate limits and trust scores

3. **Unify Heartbeat Systems**
   - Use MeshService heartbeat as single source
   - Container runtime subscribes to device status changes

### 5.3 Phase 3: Multi-Burst Optimization

1. **Sharded Scheduling**
   - Partition nodes by zone
   - Parallel scheduling per zone

2. **Lock Optimization**
   - Hold locks only for state mutations
   - Release during node selection

3. **Event-Driven Updates**
   - Node agents push status changes
   - Scheduler reacts to events vs polling

---

## 6. Conclusion

The container runtime provides a clean abstraction for transparent container distribution, but it was developed in isolation from the existing fog-compute security and coordination infrastructure. Before production use:

**MUST DO**:
- [ ] Add authentication (integrate with MeshPersistenceService)
- [ ] Add distributed locking (follow mesh_service.py patterns)
- [ ] Add persistence (SQLite backend)
- [ ] Integrate with BatteryValidator for mobile throttling

**SHOULD DO**:
- [ ] Unify device registries (FogNode + MeshDevice)
- [ ] Add node trust scoring
- [ ] Fix unwaited coroutine bug
- [ ] Add graceful shutdown

**NICE TO HAVE**:
- [ ] Volume encryption
- [ ] Sharded scheduling for scale
- [ ] Event-driven architecture

---

*Audit conducted: 2026-01-24*
*Files reviewed: scheduler.py, storage.py, network.py, mesh_service.py, battery_validator.py*
