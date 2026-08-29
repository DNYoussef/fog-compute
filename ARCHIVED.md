# ARCHIVED (KILL disposition)

Per the 2026-07-05 portfolio audit (SYNERGY-PLAN.md), fog-compute is **KILL-listed**:
both headline features are theater (sleep-derived benchmarks, phantom deployments) and
it had unauthenticated mutating control-plane endpoints. Kept as reversible git history.

Security hardening applied before archival:
- All six mutating control-plane endpoints now require `Depends(require_api_key)`
  (betanet POST /deploy, POST/PUT/DELETE /nodes; scheduler POST /jobs, DELETE /jobs).
  Verified: `POST /api/betanet/deploy` without a key returns 401 (was executing).

Do not resume active development. Verify no live deploy is running, then leave archived.
This marker is reversible (`git rm ARCHIVED.md`).
