import importlib.util
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


def test_acurast_cargo_preflight_uses_resolved_cli_path(monkeypatch):
    spec = importlib.util.spec_from_file_location("preflight_cargo", PREFLIGHT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    resolved_cli = r"C:\tools\acurast.CMD"
    calls = []

    monkeypatch.setattr(module.shutil, "which", lambda name: resolved_cli if name == "acurast" else None)

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, stdout="0.8.1\n", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    preflight = module.Preflight()
    module._check_cli(preflight, require_cli=True)

    assert calls[0][0] == [resolved_cli, "--version"]
    assert calls[0][1]["timeout"] == 30
    assert "OK   Acurast CLI version: 0.8.1" in preflight.notes
