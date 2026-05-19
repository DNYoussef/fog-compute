# Wave Status Ledger — Independent Audit

**Audit date:** 2026-05-18
**Source under review:** `docs/WAVE-STATUS-LEDGER.md` at commit `2ffcd94`
**Repo state at audit:** branch `stabilization/bplus-recovery`, ahead of origin by **8 commits** (ledger says 7).
**Auditor:** independent re-read of every claim against the repo's actual state. No tests re-run; some claims (test counts) are checked only for structural plausibility.

---

## Headline

The Acurast prototype, preflight, contract schemas, trust annotation, and CI mock-check scripts are **real**. The Wave 12-17 plan is well-scoped with explicit exit criteria.

The ledger has **three accuracy problems** the reviewer should know about before pushing:

1. The Wave 9 "generated-artifact hygiene" claim does not match the diff. `0fd1b27` adds **one line** to `.gitignore` and removes **nothing** from git's tracking. `test.db`, `.coverage`, `.swarm/memory.db`, `backend/data/dao_tokenomics.db`, and two profiling HTML reports remain tracked.
2. Commit count is **8 ahead**, not 7. The unaccounted-for commit is `440d1c7` — the "B+ recovery baseline" itself, which the ledger treats as a starting point but which is also unpushed.
3. The "Verification Already Run" results cite a B+ baseline that is not yet on `origin`. Anyone reviewing PRs from `origin` will see neither the baseline nor the wave commits.

Nothing in the audit suggests the code is unsafe or theater. The work is real. The bookkeeping is off, and a couple of bookkeeping fixes should land before Wave 12 publishes.

---

## Commit-by-commit findings

The 8 unpushed commits, oldest first:

| Commit | Date | Subject | Audit finding |
|---|---|---|---|
| `440d1c7` | 2026-02-08 | chore: complete B+ remediation phases and infra placeholder implementations | **Inherited pre-session work.** ~50+ new files, thousands of lines. Adds `.coverage` binary (53KB) and `test.db` to tracking. Adds six "FUNC-XX-COMPLETION-SUMMARY" / "WAVE6-E2E-IMPLEMENTATION-COMPLETE" docs at repo root (2,332 lines). Adds 25 library README stubs under `lib/library/*/README.md`. Placeholder density in `backend/container_runtime/scheduler.py` is 5 occurrences in 916 lines (~0.5%), consistent with optional-fallback patterns, not theater. **Not mentioned in the ledger's wave table.** |
| `f5bd6af` | 2026-05-18 | docs: split Acurast research and release hygiene plans | Docs-only. Within stated scope. |
| `eac8d99` | 2026-05-18 | feat: split backend control plane release scope | Real, large change. 1788-line `services/control_plane.py` added, 240-line `models/control_plane.py`, 269-line migration verifier, 559-line `test_control_plane.py`, plus `test_pipeline_recovery.py`, `test_fog_bridge_control_plane.py`, `test_database_migration_state.py`. Migration `009_add_fog_task_control_plane_schema.py` adds 148 lines. Scope matches "Wave 9 backend control plane" description. |
| `87df6e56` | 2026-05-18 | feat: split control panel release scope | 42 files, +810/-344. Real route handlers, UI components (Card, Badge, Button, Progress, Tabs), Playwright smoke spec (`tests/e2e/smoke.spec.ts`, 19 lines), smoke config (39 lines), package-lock updates (audit-fix only per ledger). New API route shims under `apps/control-panel/app/api/scheduler/*` and `app/api/tokenomics/*` are 2-line files — typical Next.js re-export pattern, not stubs. |
| `0fd1b27` | 2026-05-18 | chore: isolate generated artifact review scope | **One-line `.gitignore` change.** Adds `test_data/files/`. Nothing removed from git's tracking. The ledger's phrasing ("tracked `test.db` and profiling drift removed from review scope") implies a `git rm`. Plain `git ls-files` still returns `test.db`, `.coverage`, `.swarm/memory.db`, `backend/data/dao_tokenomics.db`, `backend/test_profiling_reports/test_report.html`, `test_profiling_reports/test_report.html`. |
| `88e6704` | 2026-05-18 | feat: add Acurast Cargo feasibility prototype | Real prototype. `backend/server/services/acurast_cargo.py` (51 lines) hardcodes `"trusted": False` and classifies receipts into `missing` / `malformed` / `present_unverified` — never emits a trusted state. Contract schemas (`docs/contracts/acurast-cargo-{task,result}.schema.json`) are constraint-rich (required fields, enums, length limits, anyOf). Prototype layout (`prototypes/acurast-cargo/{README.md, acurast.json, app/start.sh, app/fog_task_runner.py, app/fog_task_payload.json}`) is internally consistent with what `preflight_cargo.py` later validates. |
| `f00ec29` | 2026-05-18 | chore: add Acurast Cargo canary preflight | Real gate. 290-line `scripts/acurast/preflight_cargo.py` performs jsonschema validation against the prototype's manifest + payload, hex-regex SHA256 checks, file-mode checks, optional `--require-cli` mode. Not a print-and-exit-0 stub. New `tests/contracts/test_acurast_cargo_preflight.py` (35 lines). |
| `2ffcd94` | 2026-05-18 | docs: record wave status ledger | The ledger itself. Audit subject. |

---

## Ledger claims vs reality

### "Completed Work" table

| Ledger claim | Reality | Match |
|---|---|---|
| Wave 8/9 docs and research at `f5bd6af` | Docs-only commit, scope matches | ✅ |
| Wave 9 backend control plane at `eac8d99` | Real services + tests + migration; scope matches | ✅ |
| Wave 9 frontend control panel at `87df6e56` | Real route + UI + smoke; scope matches | ✅ |
| Wave 9 generated-artifact hygiene at `0fd1b27` | One-line `.gitignore` addition. Tracked `test.db` and profiling reports **still tracked**. | ❌ Claim overstated. |
| Wave 10 Acurast Cargo prototype at `88e6704` | Real prototype with hard `trusted: false` enforcement | ✅ |
| Wave 11 Acurast canary preflight at `f00ec29` | Real preflight with jsonschema + CLI-blocking option | ✅ |

### "Remote status" and commit-ahead count

| Ledger claim | Reality | Match |
|---|---|---|
| "ahead of `origin/stabilization/bplus-recovery` by 7 commits" | Actually **8** (`440d1c7` is also unpushed) | ❌ Off-by-one. |
| "work completed after the B+ recovery baseline" | The baseline commit `440d1c7` is **not on origin** | ⚠️ Misleading framing — origin has neither the baseline nor the work. |

### "Verification Already Run" table

These were not re-run as part of this audit. Structural plausibility only:

| Claimed result | Plausibility check |
|---|---|
| `python scripts\ci\check_prod_mocks.py` Pass | Script exists (88 lines), is real regex-based scanning of `backend/server/` and `src/`. Plausible. |
| `python scripts\ci\check_placeholders.py` Pass | Script exists (129 lines). Not deeply audited; assumed real. |
| `pytest tests\contracts --maxfail=5` → 129 passed, 25 warnings | 12 test files on disk under `tests/contracts/`. ~11 tests/file average. Plausible. |
| `pytest backend\tests --maxfail=5` → 1017 passed, 30 skipped | 46 test files on disk under `backend/tests/`. ~22 tests/file average. Plausible if parametrized; verify by running. |
| `npm --prefix apps/control-panel run build` Pass | `apps/control-panel/package.json` exists; build command would run. Not re-verified. |
| `npm run test:e2e:smoke` 2 passed | `tests/e2e/smoke.spec.ts` is 19 lines, 2 tests plausible. Not re-verified. |
| `python scripts\acurast\preflight_cargo.py` Pass | Script supports the no-CLI mode (warn, not fail). Plausible. |
| `python scripts\acurast\preflight_cargo.py --require-cli` Fails as intended | Script has explicit CLI presence check. Plausible. |

### "Current Blockers" table

All five blockers are real and correctly scoped. Specifically:

- **Acurast CLI not installed** — matches preflight script behavior (warns by default, fails with `--require-cli`).
- **No throwaway wallet** — confirmed by `git ls-files | grep -iE 'wallet|secret|\.pem$|\.key$'` returning empty.
- **Receipt semantics not pinned** — matches `acurast_cargo.py` hardcoded `trusted: false`.
- **Python availability in PRoot image** — outside-of-repo concern, accurately flagged.
- **Migration verifier admin role** — confirmed by `backend/scripts/verify_fog_task_control_plane_migrations.py` existing as a runnable script (269 lines, added in `eac8d99`).

---

## Tracked artifact contamination

These files are currently tracked by git despite being generated/runtime artifacts. They will appear in any PR diff against `origin/main` and should be excised from the branch before Wave 12 publishes:

```
.coverage                                            (53KB binary, added in 440d1c7)
.swarm/memory.db                                     (runtime SQLite)
backend/data/dao_tokenomics.db                       (DB file)
backend/test_profiling_reports/test_report.html      (generated report)
test.db                                              (added in 440d1c7)
test_profiling_reports/test_report.html              (generated report)
```

The ledger's Wave 9 row implies these were "removed from review scope" but `git ls-files` still returns all six. The `.gitignore` change in `0fd1b27` only prevents future additions of `test_data/files/`. To actually remove from review scope:

```
git rm --cached .coverage .swarm/memory.db backend/data/dao_tokenomics.db \
                backend/test_profiling_reports/test_report.html test.db \
                test_profiling_reports/test_report.html
git commit -m "chore: untrack generated artifacts (Wave 9 follow-up)"
```

Either land this as a separate Wave 9 follow-up commit before Wave 12, or update the ledger to acknowledge they remain tracked.

---

## Repo-root pollution

Repository root currently contains 13 `.md` planning/completion docs predating this session, plus 6 added in `440d1c7`:

```
AUDIT-LOGGING-INTEGRATION.md          BETANET-INTEGRATION-FIX-SUMMARY.md
CI-FIX-PLAN-2026-01-02.md             CI_CD_FIX_IMPLEMENTATION_PLAN.md
CONFIGURATION_DELIVERY.md             DOCKER_QUICK_REFERENCE.md
E2E-CI-FIX-PLAN.md                    FOG-COMPUTE-ANALYSIS-REPORT.md
FUNC-01-COMPLETION-SUMMARY.md         FUNC-07-COMPLETE.md
FUNC-08-IMPLEMENTATION-SUMMARY.md     FUNC-09-COMPLETION-SUMMARY.md
MOCK-04-DASHBOARD-API-FIX-SUMMARY.md  PR-DESCRIPTION.md
WAVE6-E2E-IMPLEMENTATION-COMPLETE.md  (+ others)
```

Not this session's contribution, but worth flagging because Wave 12 talks about "PRs small enough to review." Reviewers will see this clutter even on small PRs. Either:
- Leave alone (out of scope this session).
- Move under `docs/archive/<date>/` in a separate hygiene PR before Wave 12.

---

## Wave 12-17 plan audit

The forward plan is well-scoped. Notes per wave:

**Wave 12 (Publish and Review Boundaries).** Solid. Two suggestions before pushing:
- Decide what to do about `440d1c7`. It's the largest commit on the branch and the ledger doesn't acknowledge it as a separate PR scope. Either push it as its own PR first (so the wave commits land against a known baseline) or rebase to fold it into the same first PR with clear evidence.
- Land the `git rm --cached` follow-up for the six tracked artifacts before opening review scopes, or each PR will carry them in its diff.

**Wave 13 (CLI + Wallet).** Correct framing. The `--require-cli` preflight gate already exists and is the right exit-criteria signal.

**Wave 14 (Live Canary Deploy).** Correctly conservative: "Do not claim compatibility or partnership from a single successful run." Matches the `trusted: false` discipline in `acurast_cargo.py`.

**Wave 15 (Receipt Verifier).** Test matrix (missing, malformed, present-unverified, verified) matches the four states `_receipt_state()` already returns. The interface name `verify_acurast_cargo_receipt(result)` is sensible. One additional case worth adding: **expired receipt** if Acurast issues time-bounded receipts.

**Wave 16 (Product Integration Decision).** Correctly framed as a decision, not a refactor. Good.

**Wave 17 (Release Hardening).** All five items are real follow-ups. No issues.

---

## Recommended actions before Wave 12 pushes

In order, smallest first:

1. **Fix the ledger's off-by-one and acknowledge `440d1c7`.** One-line edit. Either update "ahead by 7" → "ahead by 8" with a row for the baseline commit, or push the baseline to origin first so the count becomes accurate at 7.

2. **Reconcile the Wave 9 hygiene claim.** Either land `git rm --cached` for the six tracked artifacts and add a row to the ledger, OR edit the Wave 9 row's "Scope" cell to honestly say "added gitignore for `test_data/files/`; six legacy generated artifacts remain tracked, scoped to a follow-up."

3. **Verify the test counts by re-running** before opening review scopes. If `pytest backend/tests --maxfail=5` no longer returns 1017 passed, the ledger needs updating before the PR description quotes it.

4. **Optional: move root-level `.md` clutter** into `docs/archive/<date>/` as a separate one-commit hygiene PR before Wave 12. Reviewers' diffs get a lot cleaner.

5. Then proceed with Wave 12 as documented.

---

## What this audit explicitly did NOT do

- Did not re-run any of the verification gates. Test counts are checked for structural plausibility only.
- Did not exhaustively review the 50+ files added in `440d1c7`. Spot-check on `backend/container_runtime/scheduler.py` (placeholder density 0.5%) was the only deep look.
- Did not audit the lib/library/* README stubs added in `440d1c7` to confirm whether the libraries they document are real or future-intent.
- Did not run `scripts/ci/check_placeholders.py`. Spot-check on `scripts/ci/check_prod_mocks.py` confirmed it is real.
- Did not validate Acurast network behavior. The prototype design is sound at the contract/preflight level; whether it actually deploys is what Wave 14 will tell us.
