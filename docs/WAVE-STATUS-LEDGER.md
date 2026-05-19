# Wave Status Ledger

**Date**: 2026-05-19
**Branch**: `stabilization/bplus-recovery`
**Remote status**: local branch is ahead of `origin/stabilization/bplus-recovery` by 9 commits and ahead of `origin/main` by 8 commits
**Baseline status**: B+ recovery baseline `440d1c7` is on `origin/main` but not on `origin/stabilization/bplus-recovery`
**Publish status**: not pushed

This ledger records the B+ recovery baseline, the work completed after that
baseline, and the remaining waves needed before live Acurast deployment or
broader release.

---

## Completed Work

| Wave | Commit | Status | Scope |
|------|--------|--------|-------|
| B+ recovery baseline | `440d1c7` | Baseline on `origin/main` | B+ remediation phases and infra placeholder implementations inherited before Wave 8; included here because `origin/stabilization/bplus-recovery` is one commit behind `origin/main` |
| Wave 8/9 docs and research | `f5bd6af` | Complete locally | Acurast comparison, outreach brief, regression baseline, feasibility scope, release-hygiene docs |
| Wave 9 backend control plane | `eac8d99` | Complete locally | Durable fog task control-plane services, migrations, scheduler/fog bridge integration, recovery/security tests |
| Wave 9 frontend control panel | `87df6e56` | Complete locally | Control-panel route shims, UI/package updates, build/smoke scripts, non-breaking audit lockfile fixes |
| Wave 9 generated-artifact hygiene | `0fd1b27` | Partial locally | `.gitignore` added for runtime file-transfer output; audit found legacy generated artifacts still tracked |
| Wave 9 generated-artifact cleanup follow-up | audit-fix commit | Complete locally | `git rm --cached` for `.coverage`, `.swarm/memory.db`, `backend/data/dao_tokenomics.db`, profiling HTML reports, and `test.db`; `.gitignore` extended so they stay out of review scope |
| Wave 10 Acurast Cargo prototype | `88e6704` | Complete locally | Local Cargo-shaped `Shell` workload, JSON task/result contracts, backend untrusted-result annotation, tests |
| Wave 11 Acurast canary preflight | `f00ec29` | Complete locally | Deterministic preflight gate, LF shell entrypoint guard, CLI-blocking check, preflight docs/tests |

---

## Verification Already Run

Latest complete post-audit gates, re-run on 2026-05-19 after the generated-artifact cleanup:

| Gate | Latest Result |
|------|---------------|
| `git diff --check origin/main..HEAD` | Pass |
| `python scripts\ci\check_prod_mocks.py` | Pass |
| `python scripts\ci\check_placeholders.py` | Pass |
| `python -m pytest tests\contracts --maxfail=5` | 129 passed, 25 warnings |
| `python -m pytest backend\tests --maxfail=5` | 1017 passed, 30 skipped, 191 warnings |
| `npm --prefix apps/control-panel run build` | Pass, stale browser-data warnings only |
| `npm run test:e2e:smoke` | 2 passed |
| `python scripts\acurast\preflight_cargo.py` | Pass with Acurast CLI missing warning |
| `python scripts\acurast\preflight_cargo.py --require-cli` | Fails as intended because `acurast` is not installed |

Known expected observations:

- `/api/fog/topology` returns `404` during smoke, while the dashboard shell still passes.
- `/api/health` returns dependency `503` during smoke when the backend dependency is unavailable.
- Next build/dev warns that `baseline-browser-mapping` and Browserslist data are stale.
- The migration verifier still needs a CREATEDB-capable Postgres admin URL.
- Remaining `npm audit` findings require breaking forced upgrades and should be separate upgrade PRs.

Issue records updated:

- Issue #25 has final Wave 9 split/review evidence.
- Issue #24 has Wave 10 prototype evidence and Wave 11 preflight evidence.

---

## Current Blockers

| Blocker | Impact | Required Resolution |
|---------|--------|---------------------|
| Acurast CLI not installed | Live canary deploy cannot run | Install and verify `acurast` on `PATH`; rerun `python scripts\acurast\preflight_cargo.py --require-cli` |
| No throwaway canary deployer wallet configured | Live deployment must not use repo secrets or personal production keys | Configure wallet outside the repo and confirm no wallet/key artifacts are tracked |
| Acurast receipt semantics not pinned to a verifier | Fog must not treat Acurast-labeled results as trusted | Keep `_fog_result_trust.trusted == false` until receipt verification is implemented |
| Unknown Python availability in selected aarch64 PRoot image | The prototype may need a bundled static runner | Confirm `python3` in the image or replace with an aarch64 binary |
| Local migration verifier lacks CREATEDB-capable admin role | Fresh/upgrade migration verification cannot complete locally | Set `FOG_MIGRATION_VERIFY_ADMIN_DATABASE_URL` to a superuser or CREATEDB-capable role |

---

## Waves Left

### Wave 12: Publish And Review Boundaries

Goal: get the local stack into reviewable remote PR scopes before more live-deploy churn.

Steps:

1. Push `stabilization/bplus-recovery` or split into separate branches.
2. Open review scopes in this order:
   - docs/research: `f5bd6af`
   - backend control plane: `eac8d99`
   - frontend control panel: `87df6e56`
   - generated artifact hygiene: `0fd1b27`
   - Acurast prototype/preflight: `88e6704` and `f00ec29`
3. Re-run:
   - `git diff --check origin/main..HEAD`
   - contracts
   - backend full suite
   - control-panel build
   - smoke E2E
4. Do not include generated DBs, profiling HTML, wallet files, deploy logs, or result artifacts.

Exit criteria:

- PRs are small enough to review.
- CI agrees with local regression results or failures are triaged.
- Generated artifacts stay out of the branch.

### Wave 13: Acurast CLI And Canary Wallet Setup

Goal: make live deploy possible without contaminating the repo.

Steps:

1. Install Acurast CLI from official instructions.
2. Verify `acurast --version`.
3. Configure a throwaway canary deployer wallet outside the repo.
4. Run `python scripts\acurast\preflight_cargo.py --require-cli`.
5. Record only sanitized setup facts in docs.

Exit criteria:

- `--require-cli` preflight passes.
- `git status --short --untracked-files=all` shows no wallet/key/deploy artifacts.

### Wave 14: Live Acurast Canary Deployment

Goal: deploy the minimal workload once and collect evidence.

Steps:

1. Deploy `prototypes/acurast-cargo/acurast.json` to Acurast Canary.
2. Capture deployment ID, processor identifier if exposed, result artifact, logs, cost, and failure reason if any.
3. Confirm whether the selected image has `python3`.
4. If Python is missing, stop and replace the runner with a static aarch64 binary in a later scope.
5. Do not claim compatibility or partnership from a single successful run.

Exit criteria:

- Either one successful canary execution is recorded, or the exact reproducible blocker is documented.
- No secrets or generated artifacts are committed.

### Wave 15: Receipt And Trust Verifier

Goal: replace self-reported Acurast trust metadata with a verifiable backend boundary if the public API supports it.

Steps:

1. Identify Acurast receipt/proof fields available for Cargo execution.
2. Add a narrow verifier interface, for example `verify_acurast_cargo_receipt(result)`.
3. Keep all unknown, missing, malformed, or unverified receipts untrusted.
4. Add tests for:
   - missing receipt
   - malformed receipt
   - present but unverified receipt
   - expired receipt if Acurast issues time-bounded receipts
   - verified receipt only if public semantics are pinned

Exit criteria:

- Fog never trusts a plain JSON claim.
- Verified trust is behind one audited function.

### Wave 16: Product Integration Decision

Goal: decide whether Acurast is an integration path, a comparison baseline, or a research-only result.

Steps:

1. Compare live canary result against Fog's own scheduler/control-plane path.
2. Decide whether Acurast execution should be:
   - a documented external deployment target
   - a scheduler adapter
   - a research-only appendix
3. If adapter work is justified, define a new PR with no wallet/deploy artifacts.
4. Decide whether the control panel should expose Acurast state or stay backend-only.

Exit criteria:

- One explicit decision with evidence.
- No broad scheduler rewrite unless canary and verifier evidence justify it.

### Wave 17: Release Hardening Cleanup

Goal: close known non-Acurast blockers before any broader release claim.

Steps:

1. Run migration verifier with a CREATEDB-capable Postgres admin URL.
2. Address `/api/fog/topology` completeness or keep it documented as non-blocking.
3. Plan breaking `npm audit` upgrades in dedicated PRs.
4. Refresh browser baseline data if the frontend PR is otherwise ready.
5. Re-run full backend, contracts, build, and smoke gates.

Exit criteria:

- Migration verification is green.
- Dependency upgrade risk is isolated.
- Release notes accurately list remaining non-blocking warnings.

---

## Operating Rules For Remaining Waves

- Keep each wave reviewable and source-only unless a generated artifact is explicitly accepted.
- Never commit wallet files, private keys, deploy secrets, or raw local result artifacts.
- Treat Acurast execution as untrusted until verifier semantics are implemented.
- Run the preflight before any live deploy attempt.
- Re-run regression gates after every wave that changes backend, frontend, schemas, or deploy packaging.
