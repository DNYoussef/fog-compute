# Wave 8 Acurast Feasibility Scope

**Date**: 2026-05-18
**Decision**: Scope a Cargo workload spike first. Do not implement Android attestation inside Fog Compute yet.

---

## Why Cargo First

Acurast Cargo is the smallest meaningful comparison point because it tests whether Fog Compute workloads can run on the live phone-compute execution path without changing Fog's mobile runtime. Android attestation integration would require new mobile code, device enrollment changes, and trust-boundary decisions before Fog has a production mobile SDK.

---

## Spike Goal

Prove or disprove this statement:

> A minimal Fog Compute task can be packaged as a Linux workload suitable for Acurast Cargo, while Fog Compute keeps routing, scheduling, and result accounting outside the Cargo container.

---

## Minimal Workload Candidate

Use a deterministic CPU-bound task with no secrets and no network dependency:

- Input: JSON payload with task id, operation, operands, and expected schema version.
- Work: simple compute operation plus timing/resource metadata.
- Output: JSON result with deterministic answer, elapsed time, and runtime metadata.
- Exclusions: no token transfer, no private keys, no production workload, no PII.

---

## Interfaces To Define Before Code

| Interface | Required Decision |
|-----------|-------------------|
| Packaging | Cargo container format, runtime language, binary/script entrypoint |
| Input | How Fog scheduler would serialize task payload |
| Output | How result is retrieved and verified |
| Attestation | What Acurast proof/receipt is available to a caller |
| Accounting | Whether Fog records only a result or also Acurast deployment metadata |
| Privacy | Whether task submission can later be routed through BetaNet/onion layers |

---

## Regression Gates For Any Prototype

Before prototype:

- `python scripts\ci\check_prod_mocks.py`
- `python scripts\ci\check_placeholders.py`
- `python -m pytest tests\contracts --maxfail=5`
- `python -m pytest backend\tests --maxfail=5`
- `npm --prefix apps/control-panel run build`
- `npm run test:e2e:smoke`

After prototype:

- Same gates as above
- Add one contract test for the packaged workload schema
- Add one backend unit test proving Fog does not treat Acurast execution as a trusted result unless an attestation/receipt field is present
- Add one negative test for missing or malformed Acurast result metadata

---

## Rollback Criteria

Abort the prototype and keep the work as research-only if:

- Cargo docs or tooling cannot provide a reproducible local packaging path.
- The minimal workload requires secrets or privileged device access.
- Result retrieval cannot be represented as a deterministic artifact.
- Acurast attestation/receipt semantics cannot be verified from public docs or a supported developer path.
- The prototype requires broad rewrites in scheduler, task engine, or mobile code.

---

## Follow-Up Issue

GitHub issue: https://github.com/DNYoussef/fog-compute/issues/24

This issue is only for the Cargo spike, not for Android attestation. It links:

- `docs/FOG-COMPUTE-COMPETITIVE-ANALYSIS.md`
- `docs/WAVE8-REGRESSION-BASELINE.md`
- `docs/ACURAST-FOG-COMPUTE-OUTREACH.md`

---

## Non-Goals

- Do not claim partnership or compatibility with Acurast.
- Do not deploy production workloads.
- Do not move tokenomics, staking, or rewards into the spike.
- Do not add Android SDK code in this wave.
- Do not route secrets through third-party compute.
