# Technical Debt Cascade Plan
## Dependency-Based Execution with Playbooks & Agents

**Generated**: 2025-11-25
**Source**: TODO-DEBT-REGISTER.md (30 TODOs, 326 hours)
**Agent Registry**: 203 agents across 10 categories

---

## Executive Summary

This plan maps each technical debt item to:
1. **Playbook**: The workflow template for execution
2. **Skill**: The specialized capability to invoke
3. **Agent**: The appropriate agent from the 203-agent registry
4. **Dependencies**: What must complete first
5. **Parallelization**: What can run concurrently

---

## Dependency Graph Overview

```
WAVE 1: Security Foundation (P0) - 86 hours
    |
    +---> [Parallel Group A - No Dependencies]
    |     +---> SEC-02: Security Headers (4h)
    |     +---> SEC-06: Log Sanitization (8h)
    |     +---> SEC-07: Error Handling Middleware (6h)
    |
    +---> [Parallel Group B - No Dependencies]
    |     +---> SEC-01: CSRF Protection (8h) [ALREADY DONE in Wave 1]
    |     +---> SEC-05: API Key Auth (8h)
    |
    +---> [Sequential - Requires Redis]
    |     +---> SEC-03: Token Blacklist (12h) --> needs Redis
    |
    +---> [Parallel Group C - No Dependencies]
    |     +---> SEC-08: Audit Logging (16h) --> needs DB schema
    |     +---> SEC-04: MFA (24h) --> complex, can parallel
    |
    v
WAVE 2: Infrastructure Setup (Unlocks P1) - 16 hours
    |
    +---> Redis Setup (4h) --> unlocks SEC-03, PERF-02
    +---> DB Schema for Deployments (8h) --> unlocks FUNC-01-05
    +---> DB Schema for Audit Logs (4h) --> unlocks SEC-08
    |
    v
WAVE 3: Core Functionality - Deployment System (P1) - 64 hours
    |
    +---> [Sequential Chain]
    |     +---> FUNC-04: Deployment Listing (8h) --> Foundation
    |           |
    |           +---> FUNC-03: Status Lookup (8h) --> Needs listing
    |                 |
    |                 +---> FUNC-01: Scheduling Logic (24h) --> Needs status
    |                       |
    |                       +---> FUNC-02: Scaling Logic (16h) --> Needs scheduler
    |                             |
    |                             +---> FUNC-05: Deletion Logic (12h) --> Needs all above
    |
    v
WAVE 4: Monitoring & Betanet Integration (P1) - 28 hours
    |
    +---> [Parallel - Independent of Wave 3]
    |     +---> FUNC-06: Betanet Metrics Fetch (16h)
    |           |
    |           +---> FUNC-07: Metric Collection (12h)
    |
    v
WAVE 5: Tokenomics & Reputation (P1) - 68 hours
    |
    +---> [Parallel Group]
    |     +---> FUNC-08: Reward Distribution (16h) --> Critical bug
    |     +---> FUNC-09: Daily Limit Tracking (12h)
    |
    +---> [Sequential - Complex]
          +---> FUNC-10: Full Reputation System (40h)
                |
                +---> TEST-08: Re-enable Reputation Test (2h)
    |
    v
WAVE 6: Testing Infrastructure (P2) - 42 hours
    |
    +---> [Parallel Group A - Security Tests]
    |     +---> TEST-01: Password Reset Tests (6h)
    |     +---> TEST-02: Account Lockout Tests (8h)
    |     +---> TEST-03: Refresh Token Tests (6h)
    |     +---> TEST-04: File Upload Tests (8h)
    |
    +---> [Parallel Group B - E2E Tests]
          +---> TEST-05: Login UI E2E (4h)
          +---> TEST-06: Registration UI E2E (4h)
          +---> TEST-07: Route Protection E2E (4h)
    |
    v
WAVE 7: Performance & Polish (P3) - 34 hours
    |
    +---> [Parallel - Final Optimization]
          +---> PERF-01: Memory Profiling (8h)
          +---> PERF-02: Caching Layer (12h)
          +---> UI-01: Quality Panel Integration Tests (6h)
          +---> UI-02: Quality Panel E2E Tests (8h)
```

---

## WAVE 1: SECURITY FOUNDATION (P0)
**Total Effort**: 86 hours
**Dependencies**: None (START HERE)
**Parallelization**: 3 parallel groups

### Playbook: `security-audit` + `backend-api-development`
### Skills: `security-hardening`, `sparc-methodology`

| ID | Task | Effort | Agent | Agent Source | Parallel Group |
|----|------|--------|-------|--------------|----------------|
| SEC-02 | Security Headers Middleware | 4h | `security-compliance` | security/compliance/soc-compliance-auditor.md | A |
| SEC-06 | Log Sanitization | 8h | `backend-dev` | delivery/development/backend/dev-backend-api.md | A |
| SEC-07 | Error Handling Middleware | 6h | `backend-dev` | delivery/development/backend/dev-backend-api.md | A |
| SEC-01 | CSRF Protection | 8h | `security-compliance` | security/compliance/soc-compliance-auditor.md | B (DONE) |
| SEC-05 | API Key Authentication | 8h | `backend-dev` | delivery/development/backend/dev-backend-api.md | B |
| SEC-03 | Token Blacklist | 12h | `backend-dev` | delivery/development/backend/dev-backend-api.md | Needs Redis |
| SEC-08 | Audit Logging | 16h | `database-architect` | platforms/data/database/database-architect.md | C |
| SEC-04 | Multi-Factor Auth | 24h | `backend-dev` | delivery/development/backend/dev-backend-api.md | C |

### Execution Strategy

```javascript
// Parallel Group A (18 hours total, ~6 hours parallel)
[Single Message]:
  Task("Security Compliance Agent", "Implement security headers middleware with HSTS, CSP, X-Frame-Options...", "security-compliance")
  Task("Backend Developer 1", "Implement log sanitization to redact PII, passwords, tokens from all log levels...", "backend-dev")
  Task("Backend Developer 2", "Implement error handling middleware with correlation IDs, safe error responses...", "backend-dev")

// Parallel Group B (16 hours total, ~8 hours parallel)
[Single Message]:
  Task("Security Compliance Agent", "Implement API key authentication with generation, validation, rate limiting...", "security-compliance")
  // SEC-01 (CSRF) already done in previous remediation

// After Redis Setup (Wave 2)
[Sequential]:
  Task("Backend Developer", "Implement JWT token blacklist with Redis for secure logout...", "backend-dev")

// Parallel Group C (40 hours total, ~24 hours parallel)
[Single Message]:
  Task("Database Architect", "Design and implement audit logging system with immutable logs, query API...", "database-architect")
  Task("Backend Developer", "Implement TOTP-based MFA with enrollment, verification, backup codes...", "backend-dev")
```

---

## WAVE 2: INFRASTRUCTURE SETUP
**Total Effort**: 16 hours
**Dependencies**: Partial Wave 1 complete
**Unlocks**: SEC-03, SEC-08, FUNC-01-05, PERF-02

### Playbook: `infrastructure-setup` + `database-migration`
### Skills: `terraform-iac`, `sql-database-specialist`

| ID | Task | Effort | Agent | Agent Source | Unlocks |
|----|------|--------|-------|--------------|---------|
| INFRA-01 | Redis Setup | 4h | `docker-containerization` | operations/devops/docker/docker-containerization.md | SEC-03, PERF-02 |
| INFRA-02 | Deployment DB Schema | 8h | `database-architect` | platforms/data/database/database-architect.md | FUNC-01-05 |
| INFRA-03 | Audit Log DB Schema | 4h | `database-architect` | platforms/data/database/database-architect.md | SEC-08 |

### Execution Strategy

```javascript
// All infrastructure can run in parallel
[Single Message]:
  Task("Docker Specialist", "Setup Redis container with persistence, configure for token blacklist and caching...", "docker-containerization")
  Task("Database Architect 1", "Create deployment database schema with tables for deployments, replicas, resources, status history...", "database-architect")
  Task("Database Architect 2", "Create audit log schema with immutable tables, indexes for query performance...", "database-architect")
```

---

## WAVE 3: DEPLOYMENT SYSTEM (P1)
**Total Effort**: 64 hours
**Dependencies**: Wave 2 (INFRA-02) complete
**Execution**: Sequential chain

### Playbook: `backend-api-development` + `three-loop-system`
### Skills: `sparc-methodology`, `feature-dev-complete`

| Order | ID | Task | Effort | Agent | Agent Source | Prerequisites |
|-------|-----|------|--------|-------|--------------|---------------|
| 1 | FUNC-04 | Deployment Listing | 8h | `backend-dev` | delivery/development/backend/dev-backend-api.md | INFRA-02 |
| 2 | FUNC-03 | Status Lookup | 8h | `backend-dev` | delivery/development/backend/dev-backend-api.md | FUNC-04 |
| 3 | FUNC-01 | Scheduling Logic | 24h | `system-architect` | delivery/architecture/system-design/arch-system-design.md | FUNC-03 |
| 4 | FUNC-02 | Scaling Logic | 16h | `kubernetes-specialist` | operations/infrastructure/kubernetes/kubernetes-specialist.md | FUNC-01 |
| 5 | FUNC-05 | Deletion Logic | 12h | `backend-dev` | delivery/development/backend/dev-backend-api.md | FUNC-02 |

### Execution Strategy

```javascript
// Sequential execution - each step depends on previous
// Step 1: Foundation
Task("Backend Developer", "Implement deployment listing from database with filtering, pagination, search...", "backend-dev")
// Wait for completion

// Step 2: Status
Task("Backend Developer", "Implement real deployment status lookup with health checks, resource metrics...", "backend-dev")
// Wait for completion

// Step 3: Scheduling (most complex - 24h)
Task("System Architect", "Design and implement deployment scheduling with resource allocation, queue management, container orchestration...", "system-architect")
// Wait for completion

// Step 4: Scaling
Task("Kubernetes Specialist", "Implement horizontal scaling with HPA integration, metrics-based triggers, scaling policies...", "kubernetes-specialist")
// Wait for completion

// Step 5: Deletion
Task("Backend Developer", "Implement deployment deletion with cascading cleanup, resource deallocation, load balancer updates...", "backend-dev")
```

---

## WAVE 4: MONITORING & BETANET (P1)
**Total Effort**: 28 hours
**Dependencies**: None (can run parallel with Wave 3)
**Execution**: Sequential within wave

### Playbook: `backend-api-development` + `performance-optimization-deep-dive`
### Skills: `rust-systems-programming`, `monitoring-setup`

| Order | ID | Task | Effort | Agent | Agent Source | Prerequisites |
|-------|-----|------|--------|-------|--------------|---------------|
| 1 | FUNC-06 | Betanet Metrics Fetch | 16h | `rust-dev` | specialists/rust/rust-systems-developer.md | None |
| 2 | FUNC-07 | Metric Collection | 12h | `rust-dev` | specialists/rust/rust-systems-developer.md | FUNC-06 |

### Execution Strategy

```javascript
// Can run in parallel with Wave 3
// Step 1: Metrics Fetching
Task("Rust Developer", "Implement Betanet API integration in Prometheus exporter, fetch real metrics from port 9000...", "rust-dev")
// Wait for completion

// Step 2: Collection
Task("Rust Developer", "Implement metric collectors with aggregation, time-series storage, export to monitoring systems...", "rust-dev")
```

---

## WAVE 5: TOKENOMICS & REPUTATION (P1)
**Total Effort**: 68 hours
**Dependencies**: Wave 3 partial (FUNC-01 for scheduler)
**Execution**: Mixed parallel/sequential

### Playbook: `three-loop-system` + `backend-api-development`
### Skills: `sparc-methodology`, `rust-systems-programming`

| ID | Task | Effort | Agent | Agent Source | Parallel | Prerequisites |
|----|------|--------|-------|--------------|----------|---------------|
| FUNC-08 | Reward Distribution | 16h | `backend-dev` | delivery/development/backend/dev-backend-api.md | Yes | None |
| FUNC-09 | Daily Limit Tracking | 12h | `backend-dev` | delivery/development/backend/dev-backend-api.md | Yes | None |
| FUNC-10 | Reputation System | 40h | `rust-dev` | specialists/rust/rust-systems-developer.md | No | None |
| TEST-08 | Re-enable Rep Test | 2h | `tester` | quality/testing/test-orchestrator.md | No | FUNC-10 |

### Execution Strategy

```javascript
// Parallel group - Tokenomics fixes
[Single Message]:
  Task("Backend Developer 1", "Implement pending reward distribution before cleanup - query, distribute, rollback on failure...", "backend-dev")
  Task("Backend Developer 2", "Implement daily limit tracking with usage collection, enforcement, daily reset...", "backend-dev")

// Sequential - Reputation System (complex, 40h)
Task("Rust Developer", "Implement full reputation system with cost_of_forgery, decay, persistence, relay selection integration...", "rust-dev")
// Wait for completion

// After FUNC-10
Task("Tester", "Re-enable reputation system test at test_relay_lottery.rs:137, verify passes...", "tester")
```

---

## WAVE 6: TESTING INFRASTRUCTURE (P2)
**Total Effort**: 42 hours
**Dependencies**: Wave 1 security features, Wave 3 deployment features
**Execution**: Two parallel groups

### Playbook: `testing-quality` + `e2e-testing`
### Skills: `tester`, `e2e-testing-specialist`

| ID | Task | Effort | Agent | Agent Source | Parallel Group |
|----|------|--------|-------|--------------|----------------|
| TEST-01 | Password Reset Tests | 6h | `tester` | quality/testing/test-orchestrator.md | A (Security) |
| TEST-02 | Account Lockout Tests | 8h | `tester` | quality/testing/test-orchestrator.md | A (Security) |
| TEST-03 | Refresh Token Tests | 6h | `tester` | quality/testing/test-orchestrator.md | A (Security) |
| TEST-04 | File Upload Tests | 8h | `tester` | quality/testing/test-orchestrator.md | A (Security) |
| TEST-05 | Login UI E2E | 4h | `e2e-tester` | quality/testing/e2e-testing-specialist.md | B (E2E) |
| TEST-06 | Registration UI E2E | 4h | `e2e-tester` | quality/testing/e2e-testing-specialist.md | B (E2E) |
| TEST-07 | Route Protection E2E | 4h | `e2e-tester` | quality/testing/e2e-testing-specialist.md | B (E2E) |

### Execution Strategy

```javascript
// Parallel Group A - Security Tests (28 hours total, ~8 hours parallel)
[Single Message]:
  Task("Tester 1", "Write comprehensive password reset tests - flow, email, token validation, update...", "tester")
  Task("Tester 2", "Implement account lockout tests - failed attempts, lockout trigger, duration, unlock...", "tester")
  Task("Tester 3", "Write refresh token mechanism tests - refresh flow, rotation, expiration, revocation...", "tester")
  Task("Tester 4", "Implement file upload security tests - type validation, size limits, malicious detection...", "tester")

// Parallel Group B - E2E Tests (12 hours total, ~4 hours parallel)
[Single Message]:
  Task("E2E Tester 1", "Write E2E tests for login UI - success, failure, validation, redirect...", "e2e-tester")
  Task("E2E Tester 2", "Write E2E tests for registration UI - success, duplicate, validation, email...", "e2e-tester")
  Task("E2E Tester 3", "Write E2E tests for protected routes - unauthenticated blocked, authenticated allowed, RBAC...", "e2e-tester")
```

---

## WAVE 7: PERFORMANCE & POLISH (P3)
**Total Effort**: 34 hours
**Dependencies**: All functional work complete
**Execution**: Fully parallel

### Playbook: `performance-optimization-deep-dive` + `testing-quality`
### Skills: `performance-optimizer`, `e2e-testing-specialist`

| ID | Task | Effort | Agent | Agent Source |
|----|------|--------|-------|--------------|
| PERF-01 | Memory Profiling | 8h | `performance-optimizer` | operations/optimization/performance-tuning.md |
| PERF-02 | Caching Layer | 12h | `backend-dev` | delivery/development/backend/dev-backend-api.md |
| UI-01 | Quality Panel Integration Tests | 6h | `frontend-tester` | quality/testing/test-orchestrator.md |
| UI-02 | Quality Panel E2E Tests | 8h | `e2e-tester` | quality/testing/e2e-testing-specialist.md |

### Execution Strategy

```javascript
// All P3 tasks can run in parallel (34 hours total, ~12 hours parallel)
[Single Message]:
  Task("Performance Optimizer", "Implement memory profiling with leak detection, baselines, continuous monitoring, alerting...", "performance-optimizer")
  Task("Backend Developer", "Implement Redis caching layer with invalidation, warming, >80% hit rate target...", "backend-dev")
  Task("Frontend Tester", "Write integration tests for TestExecutionPanel - interactions, state, API integration...", "frontend-tester")
  Task("E2E Tester", "Write E2E tests for TestExecutionPanel user flows - complete workflows, errors, performance...", "e2e-tester")
```

---

## TIMELINE SUMMARY

| Wave | Name | Effort | Duration (Parallel) | Cumulative |
|------|------|--------|---------------------|------------|
| 1 | Security Foundation | 86h | ~30h (3 parallel groups) | Week 1-2 |
| 2 | Infrastructure Setup | 16h | ~6h (all parallel) | Week 2 |
| 3 | Deployment System | 64h | 64h (sequential) | Week 3-4 |
| 4 | Monitoring & Betanet | 28h | 28h (sequential, parallel w/ Wave 3) | Week 3-4 |
| 5 | Tokenomics & Reputation | 68h | ~44h (2 parallel + 40h sequential) | Week 5-6 |
| 6 | Testing Infrastructure | 42h | ~12h (2 parallel groups) | Week 6-7 |
| 7 | Performance & Polish | 34h | ~12h (all parallel) | Week 7-8 |

**Total Effort**: 338 hours (326h debt + 12h infrastructure)
**Parallel Execution**: ~196 hours (42% reduction)
**Estimated Calendar Time**: 8 weeks (1 developer) / 4 weeks (2 developers)

---

## AGENT SELECTION SUMMARY

| Category | Count | Agent Types Used |
|----------|-------|------------------|
| delivery/development/backend | 12 | backend-dev |
| security/compliance | 3 | security-compliance |
| platforms/data/database | 3 | database-architect |
| operations/devops | 1 | docker-containerization |
| delivery/architecture | 1 | system-architect |
| operations/infrastructure | 1 | kubernetes-specialist |
| specialists/rust | 3 | rust-dev |
| quality/testing | 8 | tester, e2e-tester |
| operations/optimization | 1 | performance-optimizer |

**Total Agent Invocations**: 33 across 9 agent categories

---

## PLAYBOOK MAPPING

| Wave | Primary Playbook | Secondary Playbook |
|------|------------------|-------------------|
| 1 | security-audit | backend-api-development |
| 2 | infrastructure-setup | database-migration |
| 3 | backend-api-development | three-loop-system |
| 4 | backend-api-development | performance-optimization-deep-dive |
| 5 | three-loop-system | backend-api-development |
| 6 | testing-quality | e2e-testing |
| 7 | performance-optimization-deep-dive | testing-quality |

---

## SUCCESS CRITERIA

### Wave 1 (Security)
- [ ] Security headers present in all responses
- [ ] Logs sanitized (no PII, passwords, tokens)
- [ ] Error responses generic (no stack traces)
- [ ] API key auth functional
- [ ] Token blacklist working (after Wave 2)
- [ ] Audit logging operational (after Wave 2)
- [ ] MFA enrollment and verification working

### Wave 2 (Infrastructure)
- [ ] Redis container running
- [ ] Deployment database schema created
- [ ] Audit log schema created

### Wave 3 (Deployment)
- [ ] Deployments persisted to database
- [ ] Real status returned from endpoints
- [ ] Scheduling with resource allocation working
- [ ] Auto-scaling functional
- [ ] Deletion with cleanup working

### Wave 4 (Monitoring)
- [ ] Real Betanet metrics in Prometheus
- [ ] Metric collection and aggregation working

### Wave 5 (Tokenomics)
- [ ] No rewards lost during cleanup
- [ ] Daily limits enforced
- [ ] Full reputation system operational
- [ ] Reputation test re-enabled and passing

### Wave 6 (Testing)
- [ ] 90%+ security feature coverage
- [ ] All E2E auth flows tested
- [ ] Tests run in CI/CD

### Wave 7 (Performance)
- [ ] Memory profiling detecting leaks
- [ ] Cache hit rate >80%
- [ ] Quality panel fully tested

---

## RISK MITIGATION

| Risk | Wave | Mitigation |
|------|------|------------|
| Security vulnerabilities before Wave 1 | 1 | Do NOT deploy externally until complete |
| Database migrations break existing data | 2 | Run on test database first, backup production |
| Scheduler complexity underestimated | 3 | Use three-loop-system playbook for complex design |
| Betanet API unavailable | 4 | Implement graceful degradation, mock fallback |
| Reputation system scope creep | 5 | Strict 40h timebox, defer non-essential features |
| Test flakiness in E2E | 6 | Implement retry logic, deterministic test data |
| Performance regressions | 7 | Benchmark before/after each change |

---

## QUICK START COMMANDS

```bash
# Wave 1 - Security (run immediately)
cd C:/Users/17175/Desktop/fog-compute

# Check current security status
rg "TODO:.*security" backend/
rg "TODO:.*auth" backend/

# Verify CSRF middleware exists (from previous remediation)
cat backend/server/middleware/csrf.py

# Wave 2 - Infrastructure
# Setup Redis
docker run -d --name fog-redis -p 6379:6379 redis:alpine

# Create deployment schema
python -c "from backend.server.database import create_all; create_all()"

# Wave 3-7 - Execute with Task agents
# Use the execution strategies above with appropriate agents
```

---

## NOTES

1. **Wave 3 is critical path**: The sequential deployment system takes 64 hours and cannot be parallelized. Consider allocating most experienced developer.

2. **Wave 4 can overlap Wave 3**: Betanet monitoring is independent and can run in parallel with deployment work.

3. **Wave 5 FUNC-10 is largest single task**: 40 hours for reputation system. May need to break into sub-tasks.

4. **Wave 6 depends on Wave 1 & 3 features**: Tests verify security and deployment features.

5. **Wave 7 is lowest risk**: Performance optimizations and polish can be deferred if needed.

---

**Document Owner**: Technical Debt Team
**Review Frequency**: Weekly during sprints
**Update Trigger**: Task completion or dependency change
