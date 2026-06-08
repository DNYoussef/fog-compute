# Wave 14 Acurast Canary Readiness Gate

**Date**: 2026-05-19
**Status**: Non-secret readiness gate added; live deployment still waits on external operator material.

## Audit Finding

Wave 13 correctly resolved the Windows `.CMD` shim before executing the Acurast
CLI, but the audit found one hygiene gap: `acurast --version` writes local CLI
state under `.acurast/` in the current working directory. Running the preflight
from the repo could therefore create ignored Acurast logs in the repo even when
no wallet was initialized.

## Fix

- The CLI version probe now runs from a temporary directory, not the repository.
- `.acurast/` is explicitly ignored as a defense-in-depth guard.
- `--require-canary-operator` now fails unless the operator supplies canary
  inputs through environment variables that keep secrets outside the repo.

## Operator Gate

Before any live canary deployment, run:

```powershell
$env:ACURAST_CANARY_SECRETS_DIR = "C:\Users\17175\.fog-compute-canary"
$env:ACURAST_CANARY_PROCESSOR_ADDRESS = "<64-bit-android-acurast-core-processor-address>"
python scripts\acurast\preflight_cargo.py --require-canary-operator
git status --short --untracked-files=all
```

`ACURAST_CANARY_SECRETS_DIR` must exist and must be outside this repository.
`ACURAST_CANARY_PROCESSOR_ADDRESS` must be a path-safe processor identifier.
If the operator intentionally wants open canary matching instead of an explicit
processor, set `ACURAST_CANARY_ALLOW_OPEN_MATCH=1` and document that decision
in the deployment notes.

## Still Not Done

This wave does not run `acurast init` or deploy live Cargo work. The next wave
still needs a throwaway canary wallet, cACU/faucet balance, and an operator
decision on explicit processor matching versus open match. Wallet material and
raw deployment artifacts must remain outside the repository.
