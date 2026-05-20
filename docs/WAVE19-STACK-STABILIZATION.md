# Wave 19 Stack Stabilization

**Date**: 2026-05-20
**Status**: PR stack merge states cleaned; CI reality gate remains next.

## Purpose

Wave 19 stops adding feature work on top of stale red branches. The goal is to
make each open review scope have an explicit base, fate, and verification
boundary before the real Acurast canary phase continues.

## Remote Actions Taken

- Retargeted PR #33 to `main` and renamed it as the combined CI/E2E
  stabilization base.
- Closed PR #31 as superseded by #33. PR #31 fixed contract dependencies but
  was still a known-failing intermediate because it did not include the later
  E2E stabilization commits.
- Retargeted PRs #26, #27, #28, and #29 onto
  `wave12/e2e-pythonpath-ci` so they no longer pretend to be independently
  mergeable against `main`.
- Merged the CI/E2E stabilization base into #26, #27, #28, and #29 so their
  head commits no longer carry stale red check state.
- Merged the updated #27 base through the Acurast stack:
  #30 -> #32 -> #34 -> #35 -> #36 -> #37 -> #38.

## Current Open PR Ledger

| PR | Branch | Base | Merge State | Fate |
| --- | --- | --- | --- | --- |
| #33 | `wave12/e2e-pythonpath-ci` | `main` | Clean | Land first; CI/E2E base |
| #26 | `wave12/docs-research` | `wave12/e2e-pythonpath-ci` | Clean | Docs/research scope |
| #28 | `wave12/frontend-control-panel` | `wave12/e2e-pythonpath-ci` | Clean | Frontend control panel scope |
| #29 | `wave12/artifact-ledger-hygiene` | `wave12/e2e-pythonpath-ci` | Clean | Artifact hygiene and ledger cleanup |
| #27 | `wave12/backend-control-plane` | `wave12/e2e-pythonpath-ci` | Clean | Backend control plane base for Acurast stack |
| #30 | `wave12/acurast-cargo-prototype-preflight` | `wave12/backend-control-plane` | Clean | Acurast prototype/preflight |
| #32 | `wave13/acurast-cli-preflight` | `wave12/acurast-cargo-prototype-preflight` | Clean | CLI setup |
| #34 | `wave14/acurast-canary-readiness` | `wave13/acurast-cli-preflight` | Clean | Canary readiness gate |
| #35 | `wave15/acurast-receipt-trust-boundary` | `wave14/acurast-canary-readiness` | Clean | Receipt trust boundary |
| #36 | `wave16/acurast-canary-evidence` | `wave15/acurast-receipt-trust-boundary` | Clean | Evidence validator |
| #37 | `wave17/acurast-comparison-outreach` | `wave16/acurast-canary-evidence` | Clean | Comparison/outreach |
| #38 | `wave18/acurast-canary-harness` | `wave17/acurast-comparison-outreach` | Clean | Canary harness |

PR #31 is closed as superseded by #33.

## Required Merge Order

Merge in this order unless CI exposes a new blocker:

1. #33
2. #26
3. #28
4. #29
5. #27
6. #30
7. #32
8. #34
9. #35
10. #36
11. #37
12. #38

The frontend scope (#28) should land before final publish verification. Running
`next lint` on the Acurast-only top branch exposed frontend lint failures in
pages fixed by the frontend control panel scope, so final publish must test the
combined landing order rather than the Acurast stack alone.

## Verification Performed

Retarget/merge hygiene:

```powershell
gh pr list --repo DNYoussef/fog-compute --state open --json number,title,headRefName,baseRefName,mergeStateStatus
```

Result: every open PR reports `CLEAN`.

Local checks:

```powershell
git diff --check
python -m pytest tests\contracts --maxfail=5 -q
npm run lint
```

Results:

- #26 after base merge: contracts `123 passed, 25 warnings`.
- #27 after base merge: contracts `123 passed, 25 warnings`.
- #29 after base merge: contracts `123 passed, 25 warnings`.
- #28 after conflict repair: contracts `123 passed, 25 warnings`; control-panel lint passed.
- Top Wave 18 after stack propagation: contracts `155 passed, 25 warnings`.
- Top Wave 18 `git diff --check`: pass.

Known lint reality:

- `npm run lint` on the Acurast-only top branch fails on frontend pages that are
  outside the Acurast scope and should be covered by #28 before final publish.

## Remaining Blocker

GitHub currently reports no checks on the retargeted stack. This is not a pass.
It means the workflows did not rerun after the stack surgery.

Wave 20 must create a meaningful CI reality gate before new feature work:

- trigger GitHub workflows on #33 or a combined landing branch,
- record run URLs and conclusions,
- treat missing checks as a blocker,
- only proceed to live Acurast canary work after CI has run on the intended
  landing path.

## Non-Negotiable Boundary

No Acurast trust semantics changed in this wave. Acurast evidence remains
untrusted until a separate verifier exists.
