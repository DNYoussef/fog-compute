# Wave 13 Acurast CLI And Canary Wallet Setup

**Date**: 2026-05-19
**Status**: CLI installed and verified; canary wallet remains intentionally unconfigured in-repo.

## Sources Checked

- Acurast CLI docs: https://docs.acurast.com/developers/tools/cli
- Acurast Cargo quickstart: https://docs.acurast.com/developers/getting-started/quickstart-cargo/

## Local CLI Verification

Commands run:

```powershell
node -v
npm -v
npm view @acurast/cli version
npm install -g @acurast/cli
where.exe acurast
acurast --version
python scripts\acurast\preflight_cargo.py --require-cli
```

Results:

- Node: `v22.22.0`
- npm: `10.9.4`
- Published `@acurast/cli` version resolved by npm: `0.8.1`
- Installed CLI version: `0.8.1`
- `python scripts\acurast\preflight_cargo.py --require-cli`: pass

The preflight exposed and fixed a Windows-specific bug: `shutil.which("acurast")`
resolved `acurast.CMD`, but the script then executed bare `acurast` with
`subprocess.run(..., shell=False)`. The script now executes the resolved CLI
path directly and has a regression test for that behavior.

## Wallet Boundary

No wallet, mnemonic, private key, `.env`, deploy log, or raw Acurast result
artifact was created or committed in this wave.

`acurast init` was not run against the repository. The official CLI docs state
that `init` creates `acurast.json` and `.env`; this repo already has a reviewed
prototype config, and wallet material must remain outside the repo.

## Remaining Wave 13 Blocker

Live canary deployment is still blocked until the operator provides, outside
the repo:

- a throwaway canary deployer wallet,
- cACU or faucet balance,
- a target 64-bit Android Acurast Core processor address if using instant match.

After those exist, rerun:

```powershell
python scripts\acurast\preflight_cargo.py --require-cli
git status --short --untracked-files=all
```

The working tree must remain free of wallet/key/deploy artifacts before Wave 14.
