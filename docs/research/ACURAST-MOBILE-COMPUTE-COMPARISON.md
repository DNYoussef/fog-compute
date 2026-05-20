# Acurast Mobile Compute Comparison

**Date**: 2026-05-20
**Scope**: Compare Acurast smartphone compute with Fog Compute's current
Acurast Cargo prototype and control-plane direction.

## Source Boundaries

Authoritative protocol sources checked:

- Acurast CLI: https://docs.acurast.com/developers/tools/cli/
- Acurast deployment config: https://docs.acurast.com/developers/build/deployment-config/
- Acurast Cargo quickstart: https://docs.acurast.com/developers/getting-started/quickstart-cargo/

User-supplied market context:

- YouTube transcript: `https://www.youtube.com/watch?v=HiXb0n3UUys`

The transcript is useful for market positioning: phones as cheap edge compute,
Core versus Lite onboarding, and miner/operator economics. It is not used as a
protocol authority. Claims about token price, mainnet date, payout behavior, or
hardware profitability must be rechecked against primary sources before they
enter product copy or investor material.

## What Acurast Gives Fog

Acurast already has the operator-side primitive Fog would otherwise need to
build from scratch:

- smartphone processor onboarding,
- Canary and Mainnet network selection,
- Shell/Cargo runtime for Linux-style workloads,
- a CLI and SDK deployment path,
- processor matching knobs including explicit instant matching,
- encrypted deployment environment variables,
- a Hub-centered operator workflow.

For Fog, the practical value is not "phones mine tokens." The value is a
candidate execution substrate for cheap, geographically broad, low-trust edge
compute. Fog can keep scheduling, policy, accounting, and trust decisions in its
own backend while using Acurast as one provider behind a provider interface.

## Current Fit

The current Fog prototype maps cleanly onto the official Cargo shape:

| Concern | Fog Current State | Acurast Shape |
| --- | --- | --- |
| Runtime | `prototypes/acurast-cargo` uses a Shell workload | `runtime: "Shell"` |
| Package | `fileUrl: "./app"` with `start.sh` | Cargo uploads app files next to image |
| OS image | pinned aarch64 Termux/proot distro URL and SHA256 | Shell runtime requires image URL and SHA256 |
| Network | canary only | `network: "canary"` supported |
| Processor target | explicit processor preferred | `instantMatch` supports processor SS58 address |
| Secrets | none bundled | `.env` exists outside reviewable source |
| Trust | never trusted | no Fog verifier wired yet |

The good part: the prototype is narrow, deterministic, and reviewable. The bad
part: the remaining risk is not code style. It is execution evidence and trust.

## Key Differences

Fog Compute is trying to be a control plane. Acurast is already a phone-backed
execution network.

That means Fog should not copy Acurast. It should integrate it as a provider
only where the boundaries are explicit:

- Fog scheduler decides what is eligible for phone execution.
- Fog task contract decides what inputs and outputs look like.
- Acurast executes a bounded workload.
- Fog verifier decides whether a receipt is useful.
- Fog accounting records provider cost, timing, and reliability.

If Fog lets Acurast-specific metadata leak into general task semantics, the
provider abstraction gets weak. If Fog marks Acurast output trusted without a
verifier, the security model is theater.

## Security Gaps

These remain hard blockers before production claims:

- **Receipt semantics**: Fog does not yet have a public, cryptographic verifier
  for Acurast execution evidence.
- **Operator secrets**: Acurast CLI initialization creates `.env`; wallet and
  mnemonic material must stay outside this repository.
- **Raw artifact handling**: live deploy logs and result artifacts must not be
  committed unless sanitized through the Wave 16 validator.
- **Processor selection**: explicit processor matching is preferable for first
  canary. Open match must be a recorded operator decision.
- **Runtime dependency risk**: the current Python runner assumes the selected
  Shell image can execute Python. A bundled aarch64 binary may be cleaner for
  production.
- **Economic claims**: revenue, token price, wattage, and phone ROI claims are
  marketing/economic assertions and need date-stamped sourcing.

## Product Gaps

The transcript shows why the idea is sellable: spare phones, low wattage, and
daily crypto rewards are easy to understand. Fog's current advantage is not that
story. Fog's advantage is orchestration across heterogeneous providers.

For Fog to be publishable around this integration, the product story should be:

- route small deterministic jobs to cheap edge providers,
- preserve trust boundaries instead of pretending every provider receipt is
  valid,
- compare Acurast, local fog nodes, and future providers through the same task
  contract,
- expose evidence and provider status in the control panel without exposing
  secrets.

## Recommended Next Engineering Move

Build the live canary harness as a source-reviewed script before running a real
deployment. The harness should:

- run from a temporary or external directory,
- require the existing canary operator preflight,
- keep `.env`, wallet, mnemonic, and raw logs outside the repo,
- emit only sanitized evidence accepted by
  `scripts/acurast/validate_canary_evidence.py`,
- preserve `_fog_result_trust.trusted == false`.

That is the smallest honest bridge from prototype to live evidence.
