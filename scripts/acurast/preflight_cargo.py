#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

try:
    from jsonschema import validate
except ImportError:  # pragma: no cover - exercised by environments missing test deps
    validate = None


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROTOTYPE_DIR = REPO_ROOT / "prototypes" / "acurast-cargo"
TASK_SCHEMA = REPO_ROOT / "docs" / "contracts" / "acurast-cargo-task.schema.json"
RESULT_SCHEMA = REPO_ROOT / "docs" / "contracts" / "acurast-cargo-result.schema.json"
HEX_64_RE = re.compile(r"^[a-f0-9]{64}$")
PROCESSOR_ADDRESS_RE = re.compile(r"^[A-Za-z0-9:_-]{16,255}$")
CANARY_SECRETS_DIR_ENV = "ACURAST_CANARY_SECRETS_DIR"
CANARY_PROCESSOR_ENV = "ACURAST_CANARY_PROCESSOR_ADDRESS"
CANARY_ALLOW_OPEN_MATCH_ENV = "ACURAST_CANARY_ALLOW_OPEN_MATCH"


class Preflight:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.notes: list[str] = []

    def ok(self, message: str) -> None:
        self.notes.append(f"OK   {message}")

    def warn(self, message: str) -> None:
        self.warnings.append(f"WARN {message}")

    def fail(self, message: str) -> None:
        self.errors.append(f"FAIL {message}")

    def emit(self) -> None:
        for line in [*self.notes, *self.warnings, *self.errors]:
            print(line)

    def exit_code(self) -> int:
        return 1 if self.errors else 0


def _load_json(path: Path, preflight: Preflight) -> dict[str, Any]:
    if not path.exists():
        preflight.fail(f"missing JSON file: {path}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        preflight.fail(f"invalid JSON in {path}: {exc.msg}")
        return {}
    if not isinstance(value, dict):
        preflight.fail(f"JSON root must be an object: {path}")
        return {}
    return value


def _validate_schema(payload: dict[str, Any], schema_path: Path, preflight: Preflight, label: str) -> None:
    schema = _load_json(schema_path, preflight)
    if not schema:
        return
    if validate is None:
        preflight.fail("jsonschema is required for preflight schema validation")
        return
    try:
        validate(instance=payload, schema=schema)
    except Exception as exc:
        preflight.fail(f"{label} does not match {schema_path.name}: {exc}")
        return
    preflight.ok(f"{label} matches {schema_path.name}")


def _git_file_mode(path: Path) -> str | None:
    try:
        output = subprocess.check_output(
            ["git", "ls-files", "--stage", "--", str(path.relative_to(REPO_ROOT))],
            cwd=str(REPO_ROOT),
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return None
    first = output.split(maxsplit=1)[0] if output.strip() else None
    return first


def _check_entrypoint(entrypoint: Path, preflight: Preflight) -> None:
    if not entrypoint.exists():
        preflight.fail(f"entrypoint does not exist: {entrypoint}")
        return
    raw = entrypoint.read_bytes()
    if raw.startswith(b"#!/bin/sh\n"):
        preflight.ok("entrypoint uses /bin/sh shebang")
    else:
        preflight.fail("entrypoint must start with '#!/bin/sh' and LF newline")
    if b"\r\n" in raw:
        preflight.fail("entrypoint contains CRLF line endings; Cargo Linux images need LF")
    else:
        preflight.ok("entrypoint uses LF line endings")

    mode = _git_file_mode(entrypoint)
    if mode == "100755":
        preflight.ok("entrypoint is executable in git index")
    elif mode is None:
        preflight.warn("could not verify entrypoint git mode")
    else:
        preflight.fail(f"entrypoint git mode is {mode}, expected 100755")


def _check_gitignore(preflight: Preflight) -> None:
    gitignore = REPO_ROOT / ".gitignore"
    text = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    if "prototypes/acurast-cargo/app/fog_task_result*.json" in text:
        preflight.ok("local Cargo result artifacts are ignored")
    else:
        preflight.fail("local Cargo result artifacts are not ignored")


def _validate_config(prototype_dir: Path, preflight: Preflight) -> tuple[dict[str, Any], Path | None, Path | None]:
    config_path = prototype_dir / "acurast.json"
    config = _load_json(config_path, preflight)
    projects = config.get("projects")
    if not isinstance(projects, dict) or len(projects) != 1:
        preflight.fail("acurast.json must define exactly one project")
        return config, None, None

    project_name, project = next(iter(projects.items()))
    if not isinstance(project, dict):
        preflight.fail("Acurast project config must be an object")
        return config, None, None
    if project.get("projectName") != project_name:
        preflight.fail("projectName must match the projects map key")
    else:
        preflight.ok(f"project name is stable: {project_name}")

    if project.get("runtime") == "Shell":
        preflight.ok("Acurast runtime is Shell")
    else:
        preflight.fail("Acurast runtime must be Shell for Cargo")

    if project.get("network") == "canary":
        preflight.ok("Acurast network is canary")
    else:
        preflight.fail("prototype must target canary, not mainnet")

    if project.get("onlyAttestedDevices") is True:
        preflight.ok("onlyAttestedDevices is enabled")
    else:
        preflight.fail("onlyAttestedDevices must be true for this spike")

    usage_limit = project.get("usageLimit")
    if isinstance(usage_limit, dict) and usage_limit.get("maxNetworkRequests") == 0:
        preflight.ok("workload declares no network requests")
    else:
        preflight.fail("usageLimit.maxNetworkRequests must be 0")

    if project.get("includeEnvironmentVariables") == []:
        preflight.ok("no environment variables are bundled into config")
    else:
        preflight.fail("includeEnvironmentVariables must be empty")

    image = project.get("image")
    if not isinstance(image, dict):
        preflight.fail("image config must be present")
    else:
        url = image.get("url")
        sha256 = image.get("sha256")
        if isinstance(url, str) and url.startswith("https://") and url.endswith((".tar.xz", ".tar.gz")):
            preflight.ok("image URL is an HTTPS Linux archive")
        else:
            preflight.fail("image URL must be an HTTPS .tar.xz or .tar.gz archive")
        if isinstance(sha256, str) and HEX_64_RE.match(sha256):
            preflight.ok("image SHA256 is pinned")
        else:
            preflight.fail("image SHA256 must be a 64-character lowercase hex string")

    file_url = project.get("fileUrl")
    entrypoint_name = project.get("entrypoint")
    if not isinstance(file_url, str) or not file_url.startswith("./"):
        preflight.fail("fileUrl must be a local relative path beginning with ./")
        app_dir = None
    else:
        app_dir = (prototype_dir / file_url[2:]).resolve()
        if app_dir.exists() and app_dir.is_dir():
            preflight.ok(f"fileUrl directory exists: {app_dir.relative_to(REPO_ROOT)}")
        else:
            preflight.fail(f"fileUrl directory does not exist: {app_dir}")
    if not isinstance(entrypoint_name, str) or "/" in entrypoint_name or "\\" in entrypoint_name:
        preflight.fail("entrypoint must be a file name inside fileUrl")
        entrypoint = None
    else:
        entrypoint = app_dir / entrypoint_name if app_dir is not None else None
        if entrypoint is not None:
            _check_entrypoint(entrypoint, preflight)

    return config, app_dir, entrypoint


def _run_local_workload(app_dir: Path, preflight: Preflight) -> None:
    payload_path = app_dir / "fog_task_payload.json"
    runner_path = app_dir / "fog_task_runner.py"
    payload = _load_json(payload_path, preflight)
    _validate_schema(payload, TASK_SCHEMA, preflight, "sample task payload")

    if not runner_path.exists():
        preflight.fail(f"runner missing: {runner_path}")
        return

    with tempfile.TemporaryDirectory(prefix="fog-acurast-preflight-") as tmpdir:
        output_path = Path(tmpdir) / "result.json"
        completed = subprocess.run(
            [
                sys.executable,
                str(runner_path),
                "--input",
                str(payload_path),
                "--output",
                str(output_path),
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            preflight.fail(f"local runner failed: {completed.stderr.strip() or completed.stdout.strip()}")
            return
        result = _load_json(output_path, preflight)
        _validate_schema(result, RESULT_SCHEMA, preflight, "local runner result")
        if result.get("result", {}).get("value") == 29 and result.get("execution", {}).get("provider") == "local":
            preflight.ok("local runner returns deterministic result")
        else:
            preflight.fail("local runner result is not the expected deterministic local result")


def _check_cli(preflight: Preflight, require_cli: bool) -> None:
    cli = shutil.which("acurast")
    if cli:
        preflight.ok(f"Acurast CLI found: {cli}")
        try:
            with tempfile.TemporaryDirectory(prefix="fog-acurast-cli-") as tmpdir:
                version = subprocess.run(
                    [cli, "--version"],
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
        except OSError as exc:
            preflight.warn(f"Acurast CLI is installed but --version failed: {exc}")
            return
        if version.returncode == 0:
            preflight.ok(f"Acurast CLI version: {(version.stdout or version.stderr).strip()}")
        else:
            preflight.warn("Acurast CLI is installed but --version failed")
        return

    message = "Acurast CLI is not installed; live canary deployment is blocked"
    if require_cli:
        preflight.fail(message)
    else:
        preflight.warn(message)


def _is_inside_repo(path: Path) -> bool:
    try:
        path.resolve().relative_to(REPO_ROOT)
        return True
    except ValueError:
        return False


def _env_truthy(value: str | None) -> bool:
    return value is not None and value.lower() in {"1", "true", "yes", "y"}


def _check_canary_operator_boundary(preflight: Preflight, environ: Mapping[str, str] = os.environ) -> None:
    secrets_dir_value = environ.get(CANARY_SECRETS_DIR_ENV)
    if not secrets_dir_value:
        preflight.fail(f"{CANARY_SECRETS_DIR_ENV} must point to an external canary secret directory")
    else:
        secrets_dir = Path(secrets_dir_value).expanduser().resolve()
        if not secrets_dir.exists() or not secrets_dir.is_dir():
            preflight.fail(f"{CANARY_SECRETS_DIR_ENV} does not exist or is not a directory: {secrets_dir}")
        elif _is_inside_repo(secrets_dir):
            preflight.fail(f"{CANARY_SECRETS_DIR_ENV} must be outside the repository: {secrets_dir}")
        else:
            preflight.ok(f"{CANARY_SECRETS_DIR_ENV} is external to the repository")

    processor = environ.get(CANARY_PROCESSOR_ENV)
    allow_open_match = _env_truthy(environ.get(CANARY_ALLOW_OPEN_MATCH_ENV))
    if not processor:
        if allow_open_match:
            preflight.warn(f"{CANARY_PROCESSOR_ENV} is unset; open canary matching was explicitly allowed")
        else:
            preflight.fail(
                f"{CANARY_PROCESSOR_ENV} must identify the canary processor, or set "
                f"{CANARY_ALLOW_OPEN_MATCH_ENV}=1 for an intentional open match"
            )
        return

    if PROCESSOR_ADDRESS_RE.match(processor):
        preflight.ok(f"{CANARY_PROCESSOR_ENV} is present and path-safe")
    else:
        preflight.fail(
            f"{CANARY_PROCESSOR_ENV} must be 16-255 chars with only letters, digits, ':', '_', or '-'"
        )


def run_preflight(prototype_dir: Path, require_cli: bool, require_canary_operator: bool = False) -> int:
    preflight = Preflight()
    prototype_dir = prototype_dir.resolve()
    if not prototype_dir.exists():
        preflight.fail(f"prototype directory does not exist: {prototype_dir}")
        preflight.emit()
        return preflight.exit_code()

    _check_gitignore(preflight)
    _config, app_dir, _entrypoint = _validate_config(prototype_dir, preflight)
    if app_dir is not None:
        _run_local_workload(app_dir, preflight)
    _check_cli(preflight, require_cli=require_cli or require_canary_operator)
    if require_canary_operator:
        _check_canary_operator_boundary(preflight)
    preflight.emit()
    return preflight.exit_code()


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight the Fog Acurast Cargo prototype.")
    parser.add_argument("--prototype-dir", type=Path, default=DEFAULT_PROTOTYPE_DIR)
    parser.add_argument(
        "--require-cli",
        action="store_true",
        help="Fail if the Acurast CLI is not installed. Use this before live canary deployment.",
    )
    parser.add_argument(
        "--require-canary-operator",
        action="store_true",
        help=(
            "Fail unless the Acurast CLI is installed and canary operator inputs "
            "are supplied outside the repository."
        ),
    )
    args = parser.parse_args()
    return run_preflight(
        args.prototype_dir,
        require_cli=args.require_cli,
        require_canary_operator=args.require_canary_operator,
    )


if __name__ == "__main__":
    raise SystemExit(main())
