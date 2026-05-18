# Wave 8 Regression Baseline

**Date**: 2026-05-18
**Repo**: https://github.com/DNYoussef/fog-compute
**Local HEAD**: 440d1c7
**Purpose**: Baseline before Acurast comparison, outreach, or feasibility prototype work.

---

## Worktree Context

The repo is dirty before Wave 8 implementation. This baseline does not imply the worktree is ready to merge; it only records that the currently dirty tree can pass the selected regression gates.

Key dirty areas before Wave 8:

- Control-panel API routes and pages
- Backend database, scheduler, fog bridge, pipeline, control plane, and task engine files
- New backend tests and control-plane migration files
- `docs/FOG-COMPUTE-COMPETITIVE-ANALYSIS.md`
- `docs/FOG-COMPUTE-V2-ARCHITECTURE.md`
- `playwright.smoke.config.ts`
- `tests/e2e/smoke.spec.ts`

---

## Commands Run

| Gate | Command | Result |
|------|---------|--------|
| Diff whitespace | `git diff --check -- docs\PRIORITY-CASCADE-PLAN.md docs\TECHNICAL-DEBT-CASCADE-PLAN.md package.json docs\ACURAST-FOG-COMPUTE-OUTREACH.md docs\FOG-COMPUTE-COMPETITIVE-ANALYSIS.md` | PASS |
| Mock/stub leak gate | `python scripts\ci\check_prod_mocks.py` | PASS |
| Placeholder gate | `python scripts\ci\check_placeholders.py` | PASS |
| Contract tests | `python -m pytest tests\contracts --maxfail=5` | 123 passed, 25 warnings |
| Backend tests | `python -m pytest backend\tests --maxfail=5` | 1015 passed, 30 skipped, 191 warnings |
| Control-panel build | `npm --prefix apps/control-panel run build` | PASS |
| Smoke E2E | `npm run test:e2e:smoke` | 2 passed |

---

## Post-Change Verification

After adding the Wave 8 comparison, outreach, feasibility scope, and plan updates:

| Gate | Command | Result |
|------|---------|--------|
| Diff whitespace | `git diff --check -- docs\PRIORITY-CASCADE-PLAN.md docs\TECHNICAL-DEBT-CASCADE-PLAN.md package.json docs\FOG-COMPUTE-COMPETITIVE-ANALYSIS.md docs\ACURAST-FOG-COMPUTE-OUTREACH.md docs\WAVE8-REGRESSION-BASELINE.md docs\WAVE8-ACURAST-FEASIBILITY-SCOPE.md` | PASS, CRLF warnings only |
| Mock/stub leak gate | `python scripts\ci\check_prod_mocks.py` | PASS |
| Placeholder gate | `python scripts\ci\check_placeholders.py` | PASS |
| Contract tests | `python -m pytest tests\contracts --maxfail=5` | 123 passed, 25 warnings |

Tracking issue: https://github.com/DNYoussef/fog-compute/issues/24

---

## Observations

- Control-panel build warns that `baseline-browser-mapping` and Browserslist data are stale. This is not a Wave 8 blocker.
- Smoke E2E accepts backend health `503` as documented dependency behavior.
- During smoke E2E, `/api/fog/topology` returned `404`; the dashboard shell still passed. Treat this as a follow-up API completeness issue, not a blocker for Acurast documentation work.
- Contract tests and backend tests pass despite deprecation warnings. Do not hide these warnings if preparing a release branch.

---

## Baseline Decision

Wave 8 can proceed with documentation, comparison, outreach, and a scoped feasibility plan.

Do not implement an Acurast Cargo prototype or Android attestation prototype until:

1. The dirty worktree is reviewed or isolated into a branch/PR.
2. This baseline is re-run.
3. The chosen spike has rollback and regression criteria.
