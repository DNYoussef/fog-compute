# Wave 16 Acurast Canary Evidence Gate

**Date**: 2026-05-19
**Status**: Sanitized evidence contract and validator added; live deployment still blocked on external operator material.

## Scope

Wave 16 prepares the live Acurast canary run for review without running it. The
goal is to make the next live attempt auditable before any deployment output is
created.

## Contract

Sanitized canary evidence must validate against:

```powershell
python scripts\acurast\validate_canary_evidence.py <sanitized-evidence.json>
```

The evidence envelope records only reviewable facts:

- canary network,
- Acurast CLI version,
- deployment ID and status,
- explicit processor matching or documented open match,
- result artifact SHA256,
- receipt state,
- `_fog_result_trust.trusted == false`.

## Rejected By Design

The validator rejects:

- wallet, mnemonic, private key, seed phrase, token, password, or API-key keys,
- local filesystem paths,
- `operator_boundary.secrets_in_repo == true`,
- `operator_boundary.raw_artifacts_in_repo == true`,
- `result.trust.trusted == true`,
- receipt state mismatches between result trust and receipt metadata.

Raw live logs and result files belong outside the repository. Only a sanitized
evidence JSON that passes the validator should enter review.

## Next Live Run

Before the live run, the operator still needs:

- throwaway canary wallet outside the repo,
- cACU/faucet balance,
- explicit processor address or documented open match,
- `python scripts\acurast\preflight_cargo.py --require-canary-operator` passing.
