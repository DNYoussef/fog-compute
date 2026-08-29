# Wave 11 Acurast Cargo Canary Preflight

**Date**: 2026-05-19
**Tracking Issue**: https://github.com/DNYoussef/fog-compute/issues/24
**Decision**: Add a deterministic preflight gate before any live Acurast Canary deployment.

## Current Status

The local Cargo-shaped package is ready for repeatable validation, but this
machine does not currently have the `acurast` CLI installed. Live canary
deployment is blocked until the CLI and a throwaway canary deployer wallet are
available outside the repo.

## Preflight Command

Run the source-only preflight:

```powershell
python scripts\acurast\preflight_cargo.py
```

Run the live-deploy readiness preflight:

```powershell
python scripts\acurast\preflight_cargo.py --require-cli
```

The first command may pass without the CLI. The second command must fail until
`acurast` is installed and discoverable on `PATH`.

## What The Preflight Checks

- `acurast.json` defines exactly one project.
- The project uses `runtime: "Shell"` and the `canary` network.
- `onlyAttestedDevices` is enabled.
- The image URL is HTTPS and the SHA256 is pinned.
- No environment variables or network requests are bundled into the prototype.
- The `fileUrl` directory and entrypoint exist.
- The shell entrypoint uses LF line endings and is executable in the git index.
- The sample task payload matches the contract schema.
- The local runner emits the expected deterministic result and result schema.
- Local generated result artifacts are ignored.
- The live-deploy path explicitly checks for the Acurast CLI.

## Line Ending Guard

`.gitattributes` pins `prototypes/acurast-cargo/app/*.sh` to LF. This is not
cosmetic: a CRLF shebang can break inside a Linux image even when Windows tests
pass.

## Live Deployment Blockers

- Install and verify the Acurast CLI.
- Use a throwaway canary deployer wallet outside the repo.
- Confirm the selected aarch64 PRoot image has `python3`; otherwise replace the
  runner with a bundled static aarch64 binary.
- Capture deployment ID, processor address, result artifact, execution logs, and
  any exposed receipt metadata.
- Keep `_fog_result_trust.trusted == false` unless a backend verifier validates
  an Acurast-supported receipt.
