# Acurast / Fog Compute Outreach Brief

**Date**: 2026-05-18
**Purpose**: Prepare a concise, technically defensible email to the Acurast team linking their smartphone compute work with Fog Compute.
**Fog Compute GitHub**: https://github.com/DNYoussef/fog-compute

---

## Source Project Identification

The transcript appears to refer to **Acurast**, despite spelling variants such as "Acurass" and "Acuras."

Verified public routes:

| Route | Link |
|-------|------|
| Website | https://acurast.com |
| Documentation | https://docs.acurast.com |
| GitHub organization | https://github.com/acurast |
| Public contact | hi@acurast.com |
| Cargo announcement | https://acurast.com/blog/feature-update/codename-cargo/ |
| Mainnet/TGE announcement | https://acurast.com/blog/announcements/acurast-mainnet-tge-are-live-a-new-era-for-decentralized-compute-has-arrived/ |
| White paper | https://arxiv.org/abs/2503.15654 |

Public team references:

| Reference | Names |
|-----------|-------|
| Acurast white paper authors | Christian Killer, Alessandro De Carli, Pascal Brun, Amadeo Victor Charle, Mike Godenzi, Simon Wehrli |
| Public company-profile founder references | Alessandro De Carli; Pascal Brun |
| Acurast ecosystem entities | Acurast Association; Papers |

---

## Why This Matters To Fog Compute

| Dimension | Acurast | Fog Compute | Concrete Question |
|-----------|---------|-------------|-------------------|
| Device supply | Live smartphone-based processor network | Idle compute harvesting is a core thesis, but the repo lacks a production mobile SDK | Should Fog target Android first and treat iOS as a later, constrained runtime? |
| Workload model | Node.js today; Cargo Linux containers on attested Android devices | Planned VM/WASM/Docker runtime and scheduler integration | Could a minimal Fog workload run as a Cargo feasibility test? |
| Verification | Smartphone TEE and hardware-backed attestation | Attestation is planned but not implemented | What attestation claims are realistic for commodity phones? |
| Privacy model | Confidential execution on device | Mixnet/onion routed task distribution through BetaNet/VPN layers | Could confidential execution plus route privacy be a distinct joint story? |
| Economics | ACU token, staking, compute rewards | DAO/tokenomics exists but production incentives are incomplete | Which incentive mechanics should Fog copy, avoid, or interoperate with? |
| Developer UX | CLI, SDK, Hub, app onboarding | Control panel and API exist, but deployment flow is still being stabilized | What is the smallest developer journey that would make Fog credible? |
| Network maturity | Mainnet launched and public network metrics exist | Pre-deploy, repo-heavy prototype | Treat Acurast as the mobile-compute baseline, not a side note |

---

## Draft Email

**To**: hi@acurast.com
**Optional CC / Mention**: Acurast GitHub organization, Acurast Association / Papers public channels
**Subject**: Fog Compute and Acurast: comparing privacy-routed fog workloads with phone-based confidential compute

Hi Acurast team,

I found Acurast through a recent walkthrough of phone-based AI compute and then reviewed the docs, GitHub organization, Cargo announcement, and white paper. I am working on Fog Compute, an open-source fog computing project that explores privacy-routed distributed workloads, idle device compute, P2P messaging, and a scheduler/tokenomics layer:

https://github.com/DNYoussef/fog-compute

The overlap is direct enough that I want to compare the projects seriously instead of guessing from a video transcript. Acurast appears strongest where Fog Compute is currently weakest: live smartphone onboarding, hardware-backed attestation, a production economic layer, and now Cargo-style Linux workloads on Android. Fog Compute's differentiator is the combination of compute with network privacy: BetaNet/onion routing, BitChat-style P2P messaging, and a plan for privacy-preserving task distribution.

I would like to do one concrete, bounded thing first:

1. Publish a short technical comparison of Acurast and Fog Compute, with Acurast reviewed for accuracy before sharing.
2. Scope a minimal Fog workload that could run through Acurast Cargo, if Cargo is the right developer path.
3. Use that result to decide whether Fog's routing/privacy layer could complement Acurast-style confidential smartphone execution.

No partnership claim, token promotion, or endorsement is implied. The goal is an engineering comparison and, if useful, a small reproducible proof of concept.

If there is a preferred technical contact, GitHub repo, Discord channel, or builder program route for this kind of comparison, please point me there.

Best,

[Name]

---

## Attach Or Link

- Fog Compute GitHub: https://github.com/DNYoussef/fog-compute
- Competitive analysis: `docs/FOG-COMPUTE-COMPETITIVE-ANALYSIS.md`
- Baseline test snapshot: `docs/WAVE8-REGRESSION-BASELINE.md`
- Proposed feasibility scope: `docs/WAVE8-ACURAST-FEASIBILITY-SCOPE.md`

---

## Guardrails Before Sending

- Do not claim Acurast partnership, endorsement, token alignment, or deployment support.
- Do not ask for private token, mainnet, or investor information.
- Do not send until Fog Compute has a current README/architecture pointer that accurately reflects repo state.
- If a code prototype is proposed, record baseline regressions first: backend tests, control-panel tests, and Playwright smoke/e2e.

---

## Research Notes

- Acurast docs describe a serverless smartphone processor network with TEE-based verifiable execution and ACU/USDC payment paths.
- Acurast docs currently describe 250,000+ compute units worldwide.
- Acurast announced Mainnet and TGE on 2026-01-20, reporting over 169K phones onboarded, 364K deployments, and 589M+ on-chain transactions at launch.
- Acurast announced Cargo on Canary in April 2026 as a Linux-based container model for attested Android smartphones.
- Acurast GitHub is verified for `acurast.com` and lists `hi@acurast.com` as the public contact.
- The Acurast white paper authors are Christian Killer, Alessandro De Carli, Pascal Brun, Amadeo Victor Charle, Mike Godenzi, and Simon Wehrli.
