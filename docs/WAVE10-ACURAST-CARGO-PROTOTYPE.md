# Wave 10 Acurast Cargo Prototype

**Date**: 2026-05-18
**Tracking Issue**: https://github.com/DNYoussef/fog-compute/issues/24
**Decision**: Add a local Cargo-shaped workload package and trust-boundary tests before any live Acurast deployment.

## Scope

This wave implements the smallest useful feasibility artifact:

- JSON contracts for Fog task input and result output.
- A local `Shell` runtime package under `prototypes/acurast-cargo/`.
- Backend result trust annotation for Acurast-labeled execution results.
- Regression tests proving missing or malformed Acurast receipt metadata is not trusted.

## Cargo Mapping

| Acurast Cargo Field | Prototype Value |
|---------------------|-----------------|
| Runtime | `Shell` |
| Image | Termux Ubuntu aarch64 PRoot image with pinned SHA256 |
| Entrypoint | `app/start.sh` |
| App files | `app/fog_task_runner.py`, `app/fog_task_payload.json` |
| Network | `canary` |
| Secrets | None |
| Fog scheduling | Outside the container |
| Fog result accounting | Outside the container |

## Evidence

The Acurast docs describe Cargo as a `Shell` runtime that boots an aarch64 Linux distro image with PRoot, runs an entrypoint from `fileUrl`, and exposes host services with `BRIDGE_SOCKET`.

References:

- https://docs.acurast.com/developers/getting-started/quickstart-cargo/
- https://docs.acurast.com/developers/build/deployment-config/
- https://docs.acurast.com/developers/tools/cli/

## Trust Boundary

The prototype deliberately does not mark Acurast Cargo results as trusted. If a
result advertises `execution.provider == "acurast_cargo"`, Fog annotates it with
`_fog_result_trust.trusted == false` unless a future verifier can validate the
receipt against Acurast-supported metadata.

This avoids a subtle security failure: a worker can claim Acurast execution in
plain JSON, but Fog should not convert that claim into trust.

## Remaining Before Live Deployment

- Confirm whether the selected aarch64 image includes `python3`; otherwise ship
  a static aarch64 runner binary.
- Add a backend verifier once Acurast receipt semantics are pinned to a public
  API or supported developer path.
- Run `acurast init` and live deploy from a throwaway branch with a canary
  deployer wallet, not from the release branch.
- Record the deployment ID, processor address, result artifact, and verifier
  state in this document.
