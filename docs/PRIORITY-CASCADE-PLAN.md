# FOG Compute Priority Cascade Plan
## Dependency-Based Execution Order

**Generated**: 2025-11-25
**Based On**: MECE Issue Synthesis from Claude Code, Codex, and Gemini

---

## Dependency Graph Overview

```
WAVE 0: Unblocking (Parallel)
    |
    +---> INF-01: Delete nul file
    +---> SVC-07: Fix Python imports
    |
    v
WAVE 1: Critical Security (Sequential)
    |
    +---> SEC-01/02/09: Auth token fixes
    +---> SEC-03: CSRF protection
    +---> CFG-05: Remove exposed Docker secrets
    |
    v
WAVE 2: Service Connectivity (Parallel Groups)
    |
    +---> [Group A] Backend Services
    |     +---> SVC-01: Betanet server
    |     +---> SVC-04: Tokenomics init
    |     +---> SVC-05: FogOnion imports
    |
    +---> [Group B] P2P/Transport
    |     +---> SVC-02: P2P startup
    |     +---> SVC-08: Transport modules
    |     +---> SVC-03: Idle compute methods
    |
    v
WAVE 3: Mock Replacement (Sequential)
    |
    +---> MOCK-01: Betanet real data
    +---> MOCK-02: Deployment API
    +---> MOCK-08: WebSocket publishers
    +---> MOCK-03/04/05: Dashboard/Benchmarks/UI
    |
    v
WAVE 4: Frontend Alignment (Parallel)
    |
    +---> UI-01/02/06: API contract fixes
    +---> UI-08: BitChat real API calls
    +---> UI-03/04: UX improvements
    |
    v
WAVE 5: Stabilization (Parallel)
    |
    +---> ERR-01: Rust unwrap() elimination
    +---> ERR-02/03/04: Python error handling
    +---> CFG-01/02/03: Config externalization
    |
    v
WAVE 6: Testing Infrastructure
    |
    +---> TST-01/02: Fix placeholder tests
    +---> TST-03/04/05/06: Add missing test types
    +---> INF-02: Re-enable CI benchmarks
    |
    v
WAVE 7: Technical Debt Cleanup
    |
    +---> DEBT-01/05: Convert TODOs to issues
    +---> DEBT-02/03/04: Dead code removal
    +---> UI-05/07: Debug logs, type safety
```

---

## WAVE 0: UNBLOCKING FOUNDATION
**Time Estimate**: 2-4 hours
**Dependencies**: None (START HERE)
**Can Block**: Everything else

### Tasks (Execute in Parallel)

| ID | Task | Effort | Command/Location |
|----|------|--------|------------------|
| INF-01 | Delete Windows `nul` file | 5 min | `rm fog-compute/nul` |
| SVC-07 | Fix Python import paths | 2h | Add `conftest.py` with `sys.path` setup |

### Success Criteria
- [ ] `rg` and `grep` work without "os error 1"
- [ ] `pytest backend/tests/` runs without ModuleNotFoundError
- [ ] All Windows CI agents can clone/build

### Why First?
- INF-01 blocks ALL tooling on Windows (ripgrep, git operations)
- SVC-07 blocks ALL Python test execution
- Cannot validate ANY fixes until these pass

---

## WAVE 1: CRITICAL SECURITY
**Time Estimate**: 16-24 hours
**Dependencies**: Wave 0 complete
**Can Block**: Production deployment

### Tasks (Execute Sequentially)

| Priority | ID | Task | Effort | Location |
|----------|-----|------|--------|----------|
| 1.1 | SEC-01 | Replace predictable auth tokens with JWT/HMAC | 4h | `onion_circuit_service.py:342-346` |
| 1.2 | SEC-09 | Fix VPN coordinator auth tokens | 2h | `fog_onion_coordinator.py:238,314,365` |
| 1.3 | SEC-02 | Move hardcoded secrets to env vars | 4h | `backend/server/main.py` |
| 1.4 | CFG-05 | Update Docker compose for external secrets | 2h | `docker-compose.yml` |
| 1.5 | SEC-03 | Implement CSRF protection | 4h | Backend routes |
| 1.6 | SEC-04 | Add BitChat E2E encryption | 8h | BitChat service layer |

### Success Criteria
- [ ] No predictable token patterns in codebase
- [ ] `grep -r "auth_.*_token" src/` returns 0 hardcoded patterns
- [ ] All secrets loaded from environment
- [ ] CSRF tokens on all state-changing endpoints
- [ ] Security scan (`bandit -r src/`) passes

### Why Second?
- Security vulnerabilities are CRITICAL severity
- Must fix before any external exposure
- Auth bypass = complete system compromise

---

## WAVE 2: SERVICE CONNECTIVITY
**Time Estimate**: 16-24 hours
**Dependencies**: Wave 1 complete (secure services before connecting them)

### Group A: Backend Services (Parallel)

| ID | Task | Effort | Blocks |
|----|------|--------|--------|
| SVC-01 | Implement/containerize Betanet control plane (port 9000) | 8h | MOCK-01 |
| SVC-04 | Await tokenomics `initialize()` in service manager | 2h | Tokenomics API |
| SVC-05 | Fix FogOnionCoordinator undefined NymMixnetClient | 4h | VPN services |
| SVC-06 | Wire BetanetClient into service manager | 2h | Real metrics |

### Group B: P2P/Transport (Parallel with Group A)

| ID | Task | Effort | Blocks |
|----|------|--------|--------|
| SVC-02 | Add async start() to P2P and call in service manager | 4h | P2P status |
| SVC-08 | Create transport modules or fix imports | 4h | P2P connectivity |
| SVC-03 | Implement EdgeManager.get_registered_devices() | 2h | Idle compute API |

### Success Criteria
- [ ] `curl localhost:9000/health` returns 200
- [ ] P2P service reports `TRANSPORTS_AVAILABLE = True`
- [ ] `/api/idle-compute/stats` returns without AttributeError
- [ ] Tokenomics `dao.initialized == True` at startup
- [ ] VPN coordinator imports without NameError

### Why Third?
- Cannot replace mocks until real services exist
- Services are foundation for all API endpoints
- Frontend can't show real data without backend connectivity

---

## WAVE 3: MOCK REPLACEMENT
**Time Estimate**: 24-32 hours
**Dependencies**: Wave 2 complete (real services must exist)

### Tasks (Sequential - Each validates previous)

| Order | ID | Task | Effort | Validates |
|-------|-----|------|--------|-----------|
| 3.1 | MOCK-01 | Replace Betanet mock with Rust daemon wrapper | 8h | SVC-01, SVC-06 |
| 3.2 | MOCK-02 | Implement real deployment scheduling | 8h | Database schema |
| 3.3 | MOCK-08 | Implement WebSocket publishers | 4h | Real-time feeds |
| 3.4 | MOCK-04 | Return all dashboard data sections | 4h | UI completeness |
| 3.5 | MOCK-03 | Connect benchmarks to real metrics | 4h | Performance data |
| 3.6 | MOCK-05 | Remove UI mock fallbacks | 4h | Forces real APIs |

### Success Criteria
- [ ] `/api/betanet/status` returns data from Rust daemon
- [ ] Deployment CRUD persists to database
- [ ] WebSocket `/ws/metrics` streams real data
- [ ] Dashboard shows all 5 data sections
- [ ] UI shows error states when backend unavailable (no silent fallback)

### Why Fourth?
- Mocks hide integration bugs
- Real data reveals contract mismatches
- Must complete before testing can validate

---

## WAVE 4: FRONTEND ALIGNMENT
**Time Estimate**: 16-20 hours
**Dependencies**: Wave 3 complete (backend must send real data)

### Tasks (Parallel)

| ID | Task | Effort | Location |
|----|------|--------|----------|
| UI-01 | Fix WebSocket URL to `/ws/metrics` | 1h | `ThroughputChart.tsx:23` |
| UI-02 | Handle non-200 responses in NodeListTable | 2h | `NodeListTable.tsx` |
| UI-06 | Align SystemMetrics with actual API schema | 4h | `SystemMetrics.tsx` |
| UI-08 | Wire BitChat UI to real `/api/bitchat/*` | 4h | `BitChatWrapper.tsx` |
| UI-03 | Replace page reload with state reset on WS reconnect | 2h | `WebSocketStatus.tsx` |
| UI-04 | Fix encoding corruption in UI strings | 2h | Multiple components |

### Success Criteria
- [ ] WebSocket chart connects to correct endpoint
- [ ] API errors shown in UI (not silent failures)
- [ ] All UI fields match backend response schema
- [ ] BitChat calls real backend endpoints
- [ ] No page reloads on WebSocket reconnect
- [ ] No corrupted glyphs in UI or logs

### Why Fifth?
- Frontend must align with backend after mock removal
- User-facing issues now become visible
- Can only verify with real backend data

---

## WAVE 5: STABILIZATION
**Time Estimate**: 32-40 hours
**Dependencies**: Wave 4 complete (system functional enough to stabilize)

### Error Handling (Parallel)

| ID | Task | Effort | Language |
|----|------|--------|----------|
| ERR-01 | Replace 80+ unwrap() with Result handling | 12h | Rust |
| ERR-02 | Convert return None to explicit exceptions | 8h | Python |
| ERR-03 | Remove empty pass statements | 2h | Python |
| ERR-04 | Add specific exception types | 4h | Python |
| ERR-05 | Document error handling standards | 2h | All |

### Configuration Externalization (Parallel)

| ID | Task | Effort | Scope |
|----|------|--------|-------|
| CFG-01 | Extract 50+ hardcoded addresses | 8h | Python/Rust |
| CFG-02 | Externalize port configurations | 2h | All |
| CFG-03 | Create named constants for magic numbers | 4h | Business logic |
| CFG-04 | Create centralized config module | 4h | All |

### Success Criteria
- [ ] `grep -r "\.unwrap()" src/betanet/ | wc -l` returns 0 in production paths
- [ ] No `return None` in error paths
- [ ] All addresses loaded from config/env
- [ ] Magic numbers have named constants

### Why Sixth?
- System must be functional before stabilizing
- Error handling prevents silent failures
- Config externalization enables deployment flexibility

---

## WAVE 6: TESTING INFRASTRUCTURE
**Time Estimate**: 40-48 hours
**Dependencies**: Wave 5 complete (stable system to test)

### Tasks (Sequential then Parallel)

| Phase | ID | Task | Effort |
|-------|-----|------|--------|
| 6.1 | TST-01 | Convert TODO test placeholders to real tests | 8h |
| 6.2 | TST-02 | Fix mock tests to have actual assertions | 4h |
| 6.3 | TST-03 | Add cross-component integration tests | 12h |
| 6.4 | TST-04 | Implement load tests (1000+ WS connections) | 8h |
| 6.5 | TST-05 | Add performance benchmarks (25k pps) | 8h |
| 6.6 | TST-06 | Add security penetration tests | 8h |
| 6.7 | INF-02 | Re-enable CI performance benchmarks | 4h |

### Success Criteria
- [ ] 0 TODO comments in test files
- [ ] All tests have at least one assertion
- [ ] Integration tests cover all service boundaries
- [ ] Load test passes with 1000 concurrent WS clients
- [ ] Pipeline benchmark verifies 25k pps claim
- [ ] CI pipeline includes re-enabled benchmarks

### Why Seventh?
- Cannot test unstable system
- Tests validate all previous waves
- Performance benchmarks prove claims

---

## WAVE 7: TECHNICAL DEBT CLEANUP
**Time Estimate**: 24-32 hours
**Dependencies**: Wave 6 complete (tests catch regressions during cleanup)

### Tasks (Parallel)

| ID | Task | Effort | Scope |
|----|------|--------|-------|
| DEBT-01 | Convert all TODOs to GitHub Issues | 4h | All 47+ TODOs |
| DEBT-05 | Update future-dated comments | 1h | Week 7 references |
| DEBT-02 | Remove dead code (allow(dead_code)) | 4h | Rust |
| DEBT-03 | Eliminate duplicate code patterns | 8h | All |
| DEBT-04 | Refactor long functions (<50 lines) | 8h | Async handlers |
| UI-05 | Remove console.log from production | 2h | TypeScript |
| UI-07 | Replace `any` types with proper types | 4h | TypeScript |
| INF-03 | Standardize logging (println -> tracing) | 2h | Rust |
| INF-04 | Remove unused modules | 2h | Dead code |
| DEBT-06 | Update dependencies | 4h | All package managers |

### Success Criteria
- [ ] 0 TODO comments in production code
- [ ] 0 dead_code warnings in Rust build
- [ ] 0 console.log in TypeScript (except dev mode)
- [ ] 0 `any` types in TypeScript
- [ ] All functions < 50 lines
- [ ] No duplicate code blocks > 10 lines
- [ ] All dependencies on latest security patches

### Why Last?
- Cleanup can introduce bugs (tests catch them)
- Lower priority than functionality
- Can be done incrementally after production

---

## TIMELINE SUMMARY

| Wave | Name | Duration | Cumulative |
|------|------|----------|------------|
| 0 | Unblocking | 2-4 hours | Day 1 |
| 1 | Security | 16-24 hours | Week 1 |
| 2 | Service Connectivity | 16-24 hours | Week 2 |
| 3 | Mock Replacement | 24-32 hours | Week 3 |
| 4 | Frontend Alignment | 16-20 hours | Week 4 |
| 5 | Stabilization | 32-40 hours | Week 5-6 |
| 6 | Testing | 40-48 hours | Week 7-8 |
| 7 | Technical Debt | 24-32 hours | Week 9-10 |

**Total Estimated Effort**: 170-224 hours (4-6 weeks with single developer)
**Parallel Execution**: 3-4 weeks with 2-3 developers

---

## QUICK START COMMANDS

```bash
# WAVE 0 - Immediate (run now)
cd C:/Users/17175/Desktop/fog-compute
rm nul nul_npm_audit.json  # Fix Windows reserved file

# Create conftest.py for imports
cat > backend/tests/conftest.py << 'EOF'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
EOF

# Verify fixes
rg --version  # Should work without error
pytest backend/tests/ --collect-only  # Should find tests
```

---

## RISK MITIGATION

| Risk | Wave | Mitigation |
|------|------|------------|
| Security breach before Wave 1 complete | 1 | Do NOT deploy externally until complete |
| Service changes break frontend | 4 | Run E2E tests after each backend change |
| Performance regression during stabilization | 5-6 | Run benchmarks before/after each change |
| New bugs during debt cleanup | 7 | Require 100% test pass before merge |

---

## CHECKPOINTS

After each wave, validate:
1. All wave success criteria met
2. No regressions in previous waves (run full test suite)
3. Update this document with actual completion times
4. Create GitHub milestone for next wave

---

**Document Owner**: Project Lead
**Review Cadence**: Weekly during remediation
**Completion Target**: 6 weeks (aggressive) / 10 weeks (conservative)
