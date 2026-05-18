# Wave 9 Dirty Worktree Release Hygiene

**Date**: 2026-05-18
**Branch**: `stabilization/bplus-recovery`
**Remote**: `https://github.com/DNYoussef/fog-compute.git`
**Tracking Issue**: https://github.com/DNYoussef/fog-compute/issues/25
**Decision**: Review, classify, and stabilize the dirty worktree before any Acurast Cargo prototype or publish step.

---

## Purpose

Wave 8 proved that Acurast is the closest live smartphone-compute baseline and created the Cargo feasibility issue. Wave 9 exists because the repo still contains a large dirty change set. Prototype work now would mix research code with pending release work and make regression ownership unclear.

---

## Dirty Buckets

| Bucket | Files | Release Decision |
|--------|-------|------------------|
| Planning and competitive docs | `docs/PRIORITY-CASCADE-PLAN.md`, `docs/TECHNICAL-DEBT-CASCADE-PLAN.md`, `docs/FOG-COMPUTE-COMPETITIVE-ANALYSIS.md`, `docs/ACURAST-FOG-COMPUTE-OUTREACH.md`, Wave 8 docs | Keep together as Wave 8/Wave 9 documentation changes |
| Backend control plane and migrations | `backend/server/services/control_plane.py`, `backend/server/services/fog_task_control_plane.py`, `backend/server/models/control_plane.py`, `backend/alembic/versions/009_add_fog_task_control_plane_schema.py`, related tests | Treat as intended backend release candidate; requires migration review before publish |
| Backend scheduler, fog bridge, pipeline, task engine | `backend/server/routes/fog_bridge.py`, `backend/server/routes/scheduler.py`, `backend/pipeline/*`, `backend/task_engine/*`, related tests | Keep only with targeted route, scheduler, and recovery tests passing |
| Frontend control panel | `apps/control-panel/app/**`, UI components, lockfile/package changes, smoke spec | Keep only with lint, build, and smoke E2E passing |
| P2P, onion, load balancing | `src/p2p/**`, `src/vpn/fog_onion_coordinator.py`, `src/fog/load_balancer.py`, related tests | Keep only with serialization and stable identity tests passing |
| Generated or volatile artifacts | `test.db`, `test_profiling_reports/test_report.html`, `test_data/files/**` | Do not publish without explicit decision; do not delete in this wave without owner approval |

---

## Hygiene Fixes Applied

- Removed trailing whitespace from tracked `test_profiling_reports/test_report.html` so full `git diff --check` passes.
- Added `test_data/files/` to `.gitignore` to stop future file-transfer runtime output from widening the dirty worktree.
- Left tracked `test.db`, tracked `test_profiling_reports/test_report.html`, and already-tracked `test_data/files/**` entries untouched because they may be prior wave artifacts and should not be reverted blindly.

---

## Regression Results

| Gate | Command | Result |
|------|---------|--------|
| Full diff hygiene | `git diff --check` | PASS, CRLF warnings only |
| Production mock gate | `python scripts\ci\check_prod_mocks.py` | PASS |
| Placeholder gate | `python scripts\ci\check_placeholders.py` | PASS |
| Contract tests | `python -m pytest tests\contracts --maxfail=5` | 123 passed, 25 warnings |
| Backend full suite | `python -m pytest backend\tests --maxfail=5` | 1015 passed, 30 skipped, 191 warnings |
| Control-panel build | `npm --prefix apps/control-panel run build` | PASS |
| Control-panel lint | `npm --prefix apps/control-panel run lint` | PASS |
| Smoke E2E | `npm run test:e2e:smoke` | 2 passed |
| Backend dirty-target tests | `python -m pytest backend\tests\test_control_plane.py backend\tests\test_database_migration_state.py backend\tests\test_fog_bridge_control_plane.py backend\tests\test_pipeline_recovery.py backend\tests\test_scheduler_routes.py backend\tests\test_unified_p2p_system.py --maxfail=5` | 34 passed, 26 warnings |
| New Python security tests | `python -m pytest tests\python\test_fog_onion_serialization.py tests\python\test_load_balancer_security.py --maxfail=5` | 3 passed |

Known smoke observations:

- `/api/health` returns `503` when the backend dependency is unavailable; this is expected by the smoke test.
- `/api/fog/topology` still returns `404`; dashboard smoke passes, but this remains an API completeness follow-up.
- Browser data warnings remain stale for `baseline-browser-mapping` and `caniuse-lite`.

---

## Next Actions

1. Review migration `009_add_fog_task_control_plane_schema.py` against the model and service assumptions.
2. Decide whether `test.db`, `test_profiling_reports/test_report.html`, and `test_data/files/**` are publishable artifacts, ignored artifacts, or local-only generated data.
3. Split publishable work into at least three PR scopes: docs/research, backend control plane, frontend control panel.
4. Re-run the full Wave 9 gates after any split or cleanup.
5. Only then start GitHub issue #24 for the Acurast Cargo feasibility spike.

---

## Non-Goals

- Do not implement the Acurast Cargo prototype in this wave.
- Do not delete or revert dirty artifacts without an explicit ownership decision.
- Do not deploy from this branch while generated data and release scopes are mixed.
