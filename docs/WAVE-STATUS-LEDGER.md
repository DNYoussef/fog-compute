# Wave Status Ledger

Last updated: 2026-06-08

This ledger records how the outstanding fog-compute branches were consolidated
into `integration/fog-compute-unified`.

## Integrated Stack

`wave20/ci-reality-gate` is the integration source for the Acurast/control-plane
stack. It supersedes these branch tips:

- `wave12/backend-control-plane`
- `wave12/acurast-cargo-prototype-preflight`
- `wave13/acurast-cli-preflight`
- `wave14/acurast-canary-readiness`
- `wave15/acurast-receipt-trust-boundary`
- `wave16/acurast-canary-evidence`
- `wave17/acurast-comparison-outreach`
- `wave18/acurast-canary-harness`
- `wave19/stack-stabilization-ledger`
- `wave20/ci-reality-gate`

The merge preserves the durable fog task control plane, Acurast Cargo prototype,
preflight checks, receipt trust-boundary tests, canary evidence validation, and
guarded canary harness.

## Already Merged Upstream

These branch tips are already ancestors of `origin/main` and do not need replay:

- `fix/p0x-fog-compute`
- `wave12/ci-contract-deps`
- `wave12/docs-research`
- `wave12/e2e-pythonpath-ci`
- `wave12/frontend-control-panel`

## Selective Ports

`wave12/artifact-ledger-hygiene` contributes generated-artifact cleanup and this
refreshed ledger. Its historical branch tip is not merged.

`stabilization/bplus-recovery` is an omnibus recovery branch. It is not merged as
a branch tip because it overlaps heavily with the Acurast stack and current main.
Only still-relevant fixes should be ported individually.

`phase2/vis-001-device-mesh` is treated as a prototype source. Its route/API
ideas should be ported onto the current persistence-backed mesh implementation;
the in-memory token registry should not replace current mesh persistence.
