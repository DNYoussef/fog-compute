# Wave 18 Acurast Canary Deploy Harness

**Date**: 2026-05-20
**Status**: Guarded live canary harness added; no live deployment run.

## Scope

Wave 18 adds a source-reviewed harness for the first live Acurast Cargo canary
attempt:

```powershell
python scripts\acurast\run_canary_deploy.py `
  --evidence-out <sanitized-evidence.json> `
  --raw-output-dir <external-raw-output-dir> `
  --result-artifact <external-result-artifact> `
  --receipt-metadata <external-receipt-metadata>
```

The harness refuses to proceed unless:

- `scripts\acurast\preflight_cargo.py --require-canary-operator` passes,
- raw deployment output is outside the repository,
- result and receipt artifacts are outside the repository,
- explicit processor matching is configured, or open match is deliberately
  enabled through `ACURAST_CANARY_ALLOW_OPEN_MATCH=1`,
- generated evidence passes `scripts\acurast\validate_canary_evidence.py`.

## Trust Boundary

The harness cannot emit trusted Acurast results. The generated evidence always
sets:

```json
{
  "result": {
    "trust": {
      "trusted": false
    }
  }
}
```

This remains true even when a receipt metadata file is present. A future
verifier must be a separate reviewed change.

## Raw Artifact Boundary

Raw CLI stdout/stderr are written as `*.raw.txt` under the external raw output
directory. They are not copied into the repository, and their contents are not
serialized into the sanitized evidence. This matters because live CLI output may
include local paths, wallet setup hints, or other operator-specific material.

## Live Run Still Blocked

No live deployment was run in this wave. A real run still needs external
operator material:

- throwaway canary wallet outside the repository,
- cACU/faucet balance,
- a 64-bit Android Acurast Core processor address, unless open matching is
  explicitly accepted,
- external storage for raw deployment logs, result artifact, and receipt
  metadata.

## Regression Commands

```powershell
python -m pytest tests\contracts\test_acurast_canary_harness.py -q
python -m pytest tests\contracts\test_acurast_canary_evidence.py tests\contracts\test_acurast_cargo_preflight.py -q
python -m pytest tests\contracts --maxfail=5 -q
git diff --check
git ls-files | rg -i '(^|/)([^/]*(wallet|mnemonic|secret|private)[^/]*|.*\.(pem|key|env))$'
```
