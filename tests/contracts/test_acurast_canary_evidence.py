import copy
import json
import subprocess
import sys
from pathlib import Path

from schema_helpers import assert_matches_schema, load_schema

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "acurast" / "validate_canary_evidence.py"
HEX_40 = "b" * 40
HEX_64 = "a" * 64


def valid_evidence():
    return {
        "schema_version": "fog.acurast-cargo.canary-evidence.v1",
        "captured_at": "2026-05-19T22:00:00Z",
        "network": "canary",
        "prototype_git_commit": HEX_40,
        "operator_boundary": {
            "secrets_in_repo": False,
            "raw_artifacts_in_repo": False,
            "evidence_sanitized": True,
        },
        "acurast_cli": {
            "version": "0.8.1",
        },
        "deployment": {
            "project_name": "fog-cargo-minimal",
            "deployment_id": "Acurast:canary:demo-1",
            "status": "completed",
            "processor_matching": "explicit",
            "processor_address": "processor-address-12345",
        },
        "result": {
            "schema_version": "fog.acurast-cargo.result.v1",
            "task_id": "wave16-acurast-canary",
            "provider": "acurast_cargo",
            "success": True,
            "artifact_sha256": HEX_64,
            "trust": {
                "trusted": False,
                "receipt_state": "present_unverified",
                "reason": "receipt captured but no public verifier is wired into Fog",
            },
        },
        "receipt": {
            "captured": True,
            "state": "present_unverified",
            "metadata_sha256": HEX_64,
        },
        "notes": [
            "sanitized evidence only",
        ],
    }


def run_validator(tmp_path, evidence):
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(evidence), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )


def test_acurast_canary_evidence_matches_schema():
    schema = load_schema("acurast-canary-evidence.schema.json")

    assert_matches_schema(valid_evidence(), schema)


def test_canary_evidence_validator_accepts_sanitized_evidence(tmp_path):
    completed = run_validator(tmp_path, valid_evidence())

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "sanitized canary evidence is reviewable" in completed.stdout


def test_canary_evidence_rejects_trusted_result(tmp_path):
    evidence = copy.deepcopy(valid_evidence())
    evidence["result"]["trust"]["trusted"] = True

    completed = run_validator(tmp_path, evidence)

    assert completed.returncode == 1
    assert "trusted" in completed.stdout


def test_canary_evidence_rejects_raw_artifacts_in_repo(tmp_path):
    evidence = copy.deepcopy(valid_evidence())
    evidence["operator_boundary"]["raw_artifacts_in_repo"] = True

    completed = run_validator(tmp_path, evidence)

    assert completed.returncode == 1
    assert "raw_artifacts_in_repo" in completed.stdout


def test_canary_evidence_rejects_sensitive_keys(tmp_path):
    evidence = copy.deepcopy(valid_evidence())
    evidence["private_key"] = "do-not-commit"

    completed = run_validator(tmp_path, evidence)

    assert completed.returncode == 1
    assert "sensitive key" in completed.stdout


def test_canary_evidence_rejects_local_paths(tmp_path):
    evidence = copy.deepcopy(valid_evidence())
    evidence["notes"] = [r"C:\Users\17175\.fog-compute-canary\wallet.json"]

    completed = run_validator(tmp_path, evidence)

    assert completed.returncode == 1
    assert "local filesystem paths" in completed.stdout


def test_canary_evidence_requires_explicit_processor_address(tmp_path):
    evidence = copy.deepcopy(valid_evidence())
    evidence["deployment"].pop("processor_address")

    completed = run_validator(tmp_path, evidence)

    assert completed.returncode == 1
    assert "explicit processor matching requires" in completed.stdout


def test_canary_evidence_open_match_must_not_include_processor_address(tmp_path):
    evidence = copy.deepcopy(valid_evidence())
    evidence["deployment"]["processor_matching"] = "open"

    completed = run_validator(tmp_path, evidence)

    assert completed.returncode == 1
    assert "open processor matching" in completed.stdout


def test_canary_evidence_receipt_state_must_match_trust_state(tmp_path):
    evidence = copy.deepcopy(valid_evidence())
    evidence["receipt"]["state"] = "expired"

    completed = run_validator(tmp_path, evidence)

    assert completed.returncode == 1
    assert "receipt.state must match" in completed.stdout
