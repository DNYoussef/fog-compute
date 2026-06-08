# Wave Status Ledger Audit

Date: 2026-06-08

## Findings

- `wave20/ci-reality-gate` contains the prior Acurast/control-plane stack tips
  and is the correct source for that work.
- Directly merging `stabilization/bplus-recovery` would duplicate work and
  introduce avoidable conflicts in UI primitives, Playwright config, fog bridge
  routes, and generated artifacts.
- `wave12/artifact-ledger-hygiene` is valuable as cleanup intent, but stale as a
  branch tip. The cleanup is applied as source hygiene on the integration branch.
- `phase2/vis-001-device-mesh` conflicts with newer mesh persistence and token
  handling. It should be selectively ported rather than merged.

## Artifact Cleanup

The integration branch removes tracked runtime/generated files:

- `.coverage`
- `.swarm/memory.db`
- `backend/data/dao_tokenomics.db`
- `backend/test_profiling_reports/test_report.html`
- `test.db`
- `test_profiling_reports/test_report.html`

The ignore rules now cover those generated outputs plus Playwright artifacts,
test data files, and local Acurast canary outputs.

## Required Validation

Before promoting this integration branch, run backend control-plane tests,
Acurast contract tests, mesh tests, frontend build checks, and smoke E2E checks.
