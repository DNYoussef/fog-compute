# Wave 15 Acurast Receipt Trust Boundary

**Date**: 2026-05-19
**Status**: Receipt matrix hardened; no Acurast result is marked trusted.

## Scope

This wave keeps the conservative Wave 10 decision intact: a worker can claim
`execution.provider == "acurast_cargo"`, but Fog cannot trust that claim until
there is a real verifier for Acurast-supported receipt semantics.

## Change

- Added an explicit `expired` receipt state for time-bounded receipts.
- Accepted optional `receipt.expires_at` in the result contract.
- Added a direct trust-boundary contract matrix covering:
  - non-Acurast results,
  - missing receipts,
  - malformed receipts,
  - present-but-unverified receipts,
  - expired receipts,
  - future time-bounded receipts.

Every Acurast state still emits `_fog_result_trust.trusted == false`. A future
verifier must be a separate, reviewed change with cryptographic validation and
negative tests before this boundary can change.

## Regression Command

```powershell
python -m pytest tests\contracts\test_acurast_cargo_trust.py tests\contracts\test_acurast_cargo_contract.py -q
```
