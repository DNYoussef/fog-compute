# Acurast Creator Outreach Email

**Date**: 2026-05-20
**Purpose**: Draft outreach that links Acurast's smartphone compute work with
Fog Compute without overstating partnership, trust, or production readiness.

## Draft

Subject: Fog Compute + Acurast Cargo technical validation

Hi Acurast team,

I am building Fog Compute, an open-source control plane for routing small,
bounded workloads across heterogeneous edge compute providers:

https://github.com/DNYoussef/fog-compute

We have been evaluating Acurast Cargo as a possible smartphone-backed execution
provider for Fog. The current prototype is intentionally conservative: it maps a
deterministic Fog task into an Acurast Cargo/Shell workload, targets Canary,
keeps wallet material outside the repository, and refuses to mark Acurast
results trusted until Fog has a real receipt or attestation verifier.

The relevant work is in these areas:

- `prototypes/acurast-cargo/`
- `scripts/acurast/preflight_cargo.py`
- `scripts/acurast/validate_canary_evidence.py`
- `docs/WAVE10-ACURAST-CARGO-PROTOTYPE.md`
- `docs/WAVE16-ACURAST-CANARY-EVIDENCE.md`

We would appreciate technical feedback on five points:

1. For Cargo/Shell deployments, what receipt or attestation metadata should Fog
   treat as canonical when proving a processor actually executed the workload?
2. Is there a recommended verifier path for deployment receipts, processor
   identity, and attestation state that can run inside a third-party backend?
3. For a first canary run, do you recommend explicit `instantMatch` against a
   known 64-bit Android Core processor, or open matching on Canary?
4. Are there current constraints around Python inside the Termux/proot images
   that would make a bundled aarch64 binary a better first production target?
5. Are there examples of sanitized deployment evidence you would consider safe
   to publish in an open-source PR without exposing wallet material, `.env`
   contents, raw logs, or private operator paths?

The goal is not to duplicate Acurast. Fog would keep scheduling, policy,
accounting, and provider abstraction in its own backend while using Acurast as a
phone-backed execution provider where the security boundary is clear.

If this is interesting, I would be glad to open a focused issue or discussion
with the exact contract and evidence fields we are using.

Thanks,

DNYoussef

## Send Checklist

- Recheck the public GitHub URL before sending.
- Link the final PR or branch for the Acurast work, not a stale local branch.
- Do not include wallet addresses, mnemonics, cACU balance screenshots, raw
  deployment logs, local machine paths, or token price claims.
- If referencing the public video walkthrough, describe it only as market
  context unless the Acurast team confirms details.
