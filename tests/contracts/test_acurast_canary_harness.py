import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS = REPO_ROOT / "scripts" / "acurast" / "run_canary_deploy.py"


def load_harness():
    spec = importlib.util.spec_from_file_location("run_canary_deploy", HARNESS)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_artifacts(tmp_path):
    result = tmp_path / "fog_task_result.acurast.json"
    receipt = tmp_path / "receipt.raw.json"
    result.write_text('{"task_id":"wave18","value":29}\n', encoding="utf-8")
    receipt.write_text('{"receipt":"present-unverified"}\n', encoding="utf-8")
    return result, receipt


def base_env(tmp_path):
    secrets = tmp_path / "operator-secrets"
    secrets.mkdir()
    return {
        "ACURAST_CANARY_SECRETS_DIR": str(secrets),
        "ACURAST_CANARY_PROCESSOR_ADDRESS": "processor-address-12345",
    }


def fake_runner(args, **kwargs):
    command = [str(part) for part in args]
    if "preflight_cargo.py" in command[1]:
        return subprocess.CompletedProcess(args, 0, stdout="OK preflight\n", stderr="")
    if command[-1] == "--version":
        return subprocess.CompletedProcess(args, 0, stdout="0.8.1\n", stderr="")
    if len(command) >= 3 and command[-2:] == ["deploy", "fog-cargo-minimal"]:
        stdout = "Deployment submitted: Acurast:5FakeCanaryAddress:42\n"
        stderr = "ACURAST_MNEMONIC=do not serialize\n"
        return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr=stderr)
    raise AssertionError(f"unexpected command: {command}")


def run_harness(module, tmp_path, monkeypatch, extra_args=None, env=None):
    result, receipt = write_artifacts(tmp_path)
    evidence = tmp_path / "evidence.json"
    raw = tmp_path / "raw"
    monkeypatch.setattr(module.shutil, "which", lambda name: r"C:\tools\acurast.CMD" if name == "acurast" else None)
    args = [
        "--evidence-out",
        str(evidence),
        "--raw-output-dir",
        str(raw),
        "--result-artifact",
        str(result),
        "--receipt-metadata",
        str(receipt),
        "--deployment-status",
        "completed",
    ]
    if extra_args:
        args.extend(extra_args)
    completed = module.main(args, environ=env or base_env(tmp_path), runner=fake_runner)
    return completed, evidence, raw


def test_canary_harness_writes_valid_sanitized_evidence(tmp_path, monkeypatch):
    module = load_harness()

    exit_code, evidence_path, raw_dir = run_harness(module, tmp_path, monkeypatch)

    assert exit_code == 0
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["deployment"]["deployment_id"] == "Acurast:5FakeCanaryAddress:42"
    assert evidence["deployment"]["processor_matching"] == "explicit"
    assert evidence["deployment"]["processor_address"] == "processor-address-12345"
    assert evidence["result"]["trust"]["trusted"] is False
    assert evidence["result"]["trust"]["receipt_state"] == "present_unverified"
    assert "ACURAST_MNEMONIC" not in evidence_path.read_text(encoding="utf-8")
    assert (raw_dir / "acurast-deploy.stderr.raw.txt").exists()


def test_canary_harness_rejects_repo_local_raw_output_dir(tmp_path, monkeypatch):
    module = load_harness()
    result, receipt = write_artifacts(tmp_path)
    evidence = tmp_path / "evidence.json"
    monkeypatch.setattr(module.shutil, "which", lambda name: r"C:\tools\acurast.CMD")

    exit_code = module.main(
        [
            "--evidence-out",
            str(evidence),
            "--raw-output-dir",
            str(REPO_ROOT / "prototypes" / "acurast-cargo" / "canary-evidence" / "raw"),
            "--result-artifact",
            str(result),
            "--receipt-metadata",
            str(receipt),
        ],
        environ=base_env(tmp_path),
        runner=fake_runner,
    )

    assert exit_code == 1
    assert not evidence.exists()


def test_canary_harness_rejects_repo_local_result_artifact(tmp_path, monkeypatch):
    module = load_harness()
    _result, receipt = write_artifacts(tmp_path)
    evidence = tmp_path / "evidence.json"
    raw = tmp_path / "raw"
    monkeypatch.setattr(module.shutil, "which", lambda name: r"C:\tools\acurast.CMD")

    exit_code = module.main(
        [
            "--evidence-out",
            str(evidence),
            "--raw-output-dir",
            str(raw),
            "--result-artifact",
            str(REPO_ROOT / "prototypes" / "acurast-cargo" / "app" / "fog_task_payload.json"),
            "--receipt-metadata",
            str(receipt),
        ],
        environ=base_env(tmp_path),
        runner=fake_runner,
    )

    assert exit_code == 1
    assert not evidence.exists()


def test_canary_harness_requires_open_match_override(tmp_path, monkeypatch):
    module = load_harness()
    env = base_env(tmp_path)
    env.pop("ACURAST_CANARY_PROCESSOR_ADDRESS")

    exit_code, evidence_path, _raw_dir = run_harness(module, tmp_path, monkeypatch, env=env)

    assert exit_code == 1
    assert not evidence_path.exists()


def test_canary_harness_allows_explicit_open_match(tmp_path, monkeypatch):
    module = load_harness()
    env = base_env(tmp_path)
    env.pop("ACURAST_CANARY_PROCESSOR_ADDRESS")
    env["ACURAST_CANARY_ALLOW_OPEN_MATCH"] = "1"

    exit_code, evidence_path, _raw_dir = run_harness(module, tmp_path, monkeypatch, env=env)

    assert exit_code == 0
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["deployment"]["processor_matching"] == "open"
    assert "processor_address" not in evidence["deployment"]


def test_canary_harness_refuses_receipt_state_without_metadata(tmp_path, monkeypatch):
    module = load_harness()
    result, _receipt = write_artifacts(tmp_path)
    evidence = tmp_path / "evidence.json"
    raw = tmp_path / "raw"
    monkeypatch.setattr(module.shutil, "which", lambda name: r"C:\tools\acurast.CMD")

    exit_code = module.main(
        [
            "--evidence-out",
            str(evidence),
            "--raw-output-dir",
            str(raw),
            "--result-artifact",
            str(result),
            "--receipt-state",
            "present_unverified",
        ],
        environ=base_env(tmp_path),
        runner=fake_runner,
    )

    assert exit_code == 1
    assert not evidence.exists()


def test_canary_harness_help_loads():
    completed = subprocess.run(
        [sys.executable, str(HARNESS), "--help"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "sanitized evidence" in completed.stdout
