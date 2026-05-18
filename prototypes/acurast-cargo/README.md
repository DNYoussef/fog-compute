# Acurast Cargo Feasibility Prototype

This package is a local, source-only spike for GitHub issue #24. It tests whether
a minimal Fog Compute task can be represented as an Acurast Cargo `Shell`
runtime workload while Fog keeps routing, scheduling, and accounting outside the
container.

## Current Boundary

- The workload is deterministic and uses no secrets.
- The runner performs only local CPU/hash work.
- The container does not call Fog APIs.
- Acurast execution metadata is treated as untrusted by Fog until a receipt
  verifier exists in the backend.

## Official Cargo Shape

Acurast Cargo is exposed as the Acurast `Shell` runtime. The deployment config
uses `runtime: "Shell"`, an aarch64 Linux image URL/SHA256, and an entrypoint
script. At runtime, Acurast exposes host services through the `BRIDGE_SOCKET`
environment variable.

References:

- https://docs.acurast.com/developers/getting-started/quickstart-cargo/
- https://docs.acurast.com/developers/build/deployment-config/
- https://docs.acurast.com/developers/tools/cli/

## Local Run

```powershell
python prototypes\acurast-cargo\app\fog_task_runner.py `
  --input prototypes\acurast-cargo\app\fog_task_payload.json `
  --output prototypes\acurast-cargo\app\fog_task_result.local.json
```

The generated `fog_task_result.local.json` is local output and should not be
committed.

## Cargo Package Contents

- `acurast.json`: canary `Shell` runtime deployment template.
- `app/start.sh`: entrypoint used by Cargo.
- `app/fog_task_runner.py`: deterministic runner.
- `app/fog_task_payload.json`: sample Fog task payload.

## Deployment Preconditions

Do not deploy this from the main release branch. A live Cargo deployment still
needs:

- A 64-bit Android Processor Core assigned to the target Acurast network.
- A funded Acurast deployer account or canary faucet balance.
- A confirmed Python runtime in the selected image, or a bundled aarch64 runner
  binary replacing `fog_task_runner.py`.
- A receipt/attestation verifier before Fog marks Acurast results trusted.
