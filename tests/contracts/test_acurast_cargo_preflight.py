import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT = REPO_ROOT / "scripts" / "acurast" / "preflight_cargo.py"


def test_acurast_cargo_preflight_passes_without_live_cli():
    completed = subprocess.run(
        [sys.executable, str(PREFLIGHT)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "OK   Acurast runtime is Shell" in completed.stdout
    assert "OK   local runner returns deterministic result" in completed.stdout


def test_acurast_cargo_preflight_require_cli_blocks_when_missing():
    if shutil.which("acurast"):
        return

    completed = subprocess.run(
        [sys.executable, str(PREFLIGHT), "--require-cli"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert "FAIL Acurast CLI is not installed" in completed.stdout
