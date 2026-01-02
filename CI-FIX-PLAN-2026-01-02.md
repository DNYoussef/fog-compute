# Fog Compute CI/CD E2E Test Fix Plan

**Date**: 2026-01-02
**Status**: Ready for Implementation

---

## Root Cause Analysis

### What's Working
- `axe-playwright` dependency: INSTALLED
- `playwright.merge.config.ts`: EXISTS
- Redis provisioning in CI: WORKING
- PostgreSQL provisioning: WORKING
- Node.js unit tests: PASSING
- Rust tests: PASSING
- Python tests (local): 60/60 PASSING

### What's Failing
E2E tests fail with:
- HTTP 500 errors on `/nodes` and `/` endpoints
- Service heartbeat timeouts for: betanet, bitchat, dao, edge, fog_coordinator, harvest, onion, p2p, scheduler, vpn_coordinator

### Root Cause (updated after code review)
- The `enhanced_service_manager.initialize()` pipeline has **no per-service timeouts**. Any slow start (database pool warming, tokenomics init, or future external calls) can block the Playwright webServer `/health` wait, producing global timeouts.
- CI currently tries to initialize **external-facing services** (`p2p`, `betanet`, `bitchat`, `vpn_coordinator`, `onion`) even though the code already provides stubs for missing transports. These services are not needed for the UI/auth flows exercised in CI and can still regress startup if future implementations add I/O.
- The `/health` endpoint reports "healthy" when initialization short-circuits (states are set to `RUNNING` even if instances are `None` and health monitors never start). That yields false positives and hides degraded CI startups.
- New CI knobs (e.g., `SKIP_EXTERNAL_SERVICES`, `P2P_TIMEOUT`, `SERVICE_INIT_TIMEOUT`) must be propagated both to GitHub Actions **and** to the Playwright `webServer` env. The previous plan only updated the workflow, so the backend process launched by Playwright would still ignore the flags.

**Playwright webServer config waits for `/health` to return before running tests. Without timeouts and accurate readiness, a single slow init blocks all shards.**

---

## Implementation Plan

### Phase 1: Add CI-Aware Service Initialization (CRITICAL)

**File**: `backend/server/services/enhanced_service_manager.py`

**Change**: Add CI detection and skip non-essential service initialization in CI mode.

```python
# In initialize() method, add CI detection:
import os

async def initialize(self) -> None:
    """Initialize all services in dependency order"""
    is_ci = os.getenv('CI') == 'true'
    skip_external = os.getenv('SKIP_EXTERNAL_SERVICES', '').lower() == 'true' or is_ci
    init_timeout = int(os.getenv('SERVICE_INIT_TIMEOUT', '30'))

    # Only services required by E2E flows should run in CI
    # External-facing services (networking, mixnets) are skipped to avoid startup stalls
    skip_services = {'p2p', 'betanet', 'bitchat', 'vpn_coordinator', 'onion'} if skip_external else set()

    # ... rest of initialization
    for service_name in startup_order:
        if service_name in skip_services:
            logger.info(f"  Skipping {service_name} (non-essential in CI)")
            self.services[service_name].status = ServiceStatus.STOPPED
            self.services[service_name].is_critical = False
            continue

        # Apply per-service timeout so no single service can block startup
        try:
            await asyncio.wait_for(self._initialize_service(service_name), timeout=init_timeout)
        except asyncio.TimeoutError:
            logger.error(f"Service {service_name} initialization timed out after {init_timeout}s")
            state = self.services[service_name]
            state.status = ServiceStatus.FAILED
            state.last_error = f"timeout {init_timeout}s"
            if state.is_critical:
                raise
        # ... existing initialization logic
```

### Phase 2: Add Initialization Timeouts

**File**: `backend/server/services/enhanced_service_manager.py`

**Change**: Wrap P2P and external service initialization with timeouts.

```python
async def _init_p2p(self) -> None:
    """Initialize unified P2P system with timeout"""
    try:
        from p2p.unified_p2p_system import UnifiedDecentralizedSystem

        # Add timeout to prevent CI hanging
        p2p_system = UnifiedDecentralizedSystem(...)

        try:
            started = await asyncio.wait_for(
                p2p_system.start(),
                timeout=int(os.getenv('P2P_TIMEOUT', '30'))  # 30 second timeout (configurable)
            )
        except asyncio.TimeoutError:
            logger.warning("P2P system start timed out (30s)")
            started = False

        if not started:
            logger.warning("P2P system failed to start, continuing with limited functionality")

        self.services['p2p'].instance = p2p_system

    except Exception as e:
        logger.error(f"Failed to initialize P2P: {e}")
        self.services['p2p'].instance = None
        self.services['p2p'].is_critical = False  # Mark non-critical
```

### Phase 3: Update Health Endpoint for Graceful Degradation

**File**: `backend/server/main.py`

**Change**: The `/health` endpoint should return 200 even when optional services fail, but expose readiness that respects initialization failures and skipped services.

```python
@app.get("/health")
async def health_check():
    """System health check - returns healthy if core services work"""
    service_health = enhanced_service_manager.get_health()

    readiness = enhanced_service_manager.get_readiness_summary()
    is_ready = readiness["ready"]

    return {
        "status": "healthy" if is_ready else "degraded",
        "readiness": readiness,
        "services": service_health,
        "version": settings.API_VERSION
    }
```

### Phase 4: Add CI-Specific Environment Variables

**File**: `.github/workflows/e2e-tests.yml`

**Change**: Ensure CI environment variable is set consistently **and propagated to the Playwright-launched backend**.

```yaml
- name: Run E2E tests
  run: npx playwright test ...
  env:
    CI: true
    SKIP_EXTERNAL_SERVICES: true  # New flag
    SERVICE_INIT_TIMEOUT: 20      # Per-service guardrail to unblock /health waits
    P2P_TIMEOUT: 5                # Reduce timeout in CI
    BETANET_URL: ""              # Disable betanet
```

Also add the same env flags to `playwright.config.ts` `webServer.env` so the backend sees them when Playwright spawns uvicorn locally.

---

## Files to Modify

| File | Change |
|------|--------|
| `backend/server/services/enhanced_service_manager.py` | Add CI detection, timeouts |
| `backend/server/main.py` | Update health endpoint |
| `.github/workflows/e2e-tests.yml` | Add environment variables |

---

## Execution Order

1. **Step 1**: Modify `enhanced_service_manager.py` - Add CI detection and skip non-essential services
2. **Step 2**: Add timeouts to `_init_p2p()` and other external service initializers
3. **Step 3**: Update `/health` endpoint for graceful degradation
4. **Step 4**: Update CI workflow with new env vars
5. **Step 5**: Commit, push, and verify CI passes

---

## Expected Results After Fix

| Workflow | Expected Status |
|----------|-----------------|
| Node.js Tests | PASS (already passing) |
| Rust Tests | PASS (already passing) |
| E2E Tests (Ubuntu) | PASS |
| E2E Tests (Windows) | PASS |
| Mobile Tests | PASS |
| Cross-browser Tests | PASS |
| Report Merge | PASS |

---

## Verification Steps

1. Push changes to a feature branch
2. Open PR to trigger CI
3. Monitor E2E workflow
4. Verify all shards pass (Ubuntu + Windows x chromium/firefox/webkit x 4 shards)
5. Merge to main if all green

---

## Rollback Plan

If changes break local development:
1. Revert commits
2. Keep CI detection logic but default to full initialization
3. Only skip services explicitly when `SKIP_EXTERNAL_SERVICES=true`
