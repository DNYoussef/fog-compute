import json
import os
import subprocess
import sys
from pathlib import Path

from schema_helpers import assert_matches_schema, load_schema

REPO_ROOT = Path(__file__).resolve().parents[2]
PROTOTYPE_DIR = REPO_ROOT / "prototypes" / "acurast-cargo"
APP_DIR = PROTOTYPE_DIR / "app"


def test_acurast_cargo_task_payload_matches_schema():
    schema = load_schema("acurast-cargo-task.schema.json")
    payload = json.loads((APP_DIR / "fog_task_payload.json").read_text(encoding="utf-8"))

    assert_matches_schema(payload, schema)


def test_acurast_cargo_config_uses_shell_runtime():
    config = json.loads((PROTOTYPE_DIR / "acurast.json").read_text(encoding="utf-8"))
    project = config["projects"]["fog-cargo-minimal"]

    assert project["runtime"] == "Shell"
    assert project["entrypoint"] == "start.sh"
    assert project["fileUrl"] == "./app"
    assert project["network"] == "canary"
    assert project["onlyAttestedDevices"] is True
    assert project["image"]["url"].endswith(".tar.xz")
    assert len(project["image"]["sha256"]) == 64


def test_acurast_cargo_runner_emits_contract_result(tmp_path):
    schema = load_schema("acurast-cargo-result.schema.json")
    output = tmp_path / "result.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(APP_DIR / "fog_task_runner.py"),
            "--input",
            str(APP_DIR / "fog_task_payload.json"),
            "--output",
            str(output),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(output.read_text(encoding="utf-8"))
    assert_matches_schema(result, schema)
    assert result["result"]["value"] == 29
    assert result["execution"]["provider"] == "local"


def test_acurast_cargo_runner_marks_bridge_socket_provider(tmp_path):
    output = tmp_path / "result.json"
    env = os.environ.copy()
    env["BRIDGE_SOCKET"] = "acurast-bridge"

    completed = subprocess.run(
        [
            sys.executable,
            str(APP_DIR / "fog_task_runner.py"),
            "--input",
            str(APP_DIR / "fog_task_payload.json"),
            "--output",
            str(output),
        ],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["execution"]["provider"] == "acurast_cargo"
    assert result["execution"]["bridge_socket_present"] is True
