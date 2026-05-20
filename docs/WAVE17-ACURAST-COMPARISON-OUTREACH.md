# Wave 17 Acurast Comparison And Outreach

**Date**: 2026-05-20
**Status**: Docs-only missed step closed; no deployment run.

## Scope

Wave 17 closes the previously requested comparison and outreach step before
live canary work continues.

Added:

- `docs/research/ACURAST-MOBILE-COMPUTE-COMPARISON.md`
- `docs/outreach/ACURAST-CREATORS-EMAIL.md`

## Decisions

- Treat Acurast as a candidate execution provider, not as Fog's control plane.
- Treat the user-supplied YouTube transcript as market context only.
- Use official Acurast docs for protocol claims.
- Keep all trust language conservative: Acurast results remain untrusted until
  Fog has a reviewed verifier.
- Do not include token price, ROI, or payout claims in the outreach draft.

## Sources

- Acurast CLI: https://docs.acurast.com/developers/tools/cli/
- Deployment config: https://docs.acurast.com/developers/build/deployment-config/
- Cargo quickstart: https://docs.acurast.com/developers/getting-started/quickstart-cargo/
- User-supplied market transcript:
  `https://www.youtube.com/watch?v=HiXb0n3UUys`

## Regression Scope

This wave changes docs only. Regression still needs the normal lightweight
source checks before publish:

```powershell
git diff --check
git ls-files | rg -i '(^|/)([^/]*(wallet|mnemonic|secret|private)[^/]*|.*\.(pem|key|env))$'
python -m pytest tests\contracts --maxfail=5 -q
```

## Next Wave

Wave 18 should build the live canary harness before any real Acurast deployment
is attempted. The harness must emit only sanitized evidence accepted by
`scripts/acurast/validate_canary_evidence.py`.
