#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROTOTYPE_DIR = REPO_ROOT / "prototypes" / "acurast-cargo"
PREFLIGHT = REPO_ROOT / "scripts" / "acurast" / "preflight_cargo.py"
EVIDENCE_VALIDATOR = REPO_ROOT / "scripts" / "acurast" / "validate_canary_evidence.py"
CANARY_PROCESSOR_ENV = "ACURAST_CANARY_PROCESSOR_ADDRESS"
CANARY_ALLOW_OPEN_MATCH_ENV = "ACURAST_CANARY_ALLOW_OPEN_MATCH"
DEPLOYMENT_ID_RE = re.compile(r"\bAcurast:[A-Za-z0-9_.:-]+:\d+\b")
RECEIPT_STATES = ("missing", "malformed", "present_unverified", "expired")
DEPLOYMENT_STATUSES = ("submitted", "matched", "running", "completed", "failed", "unknown")
RunCallable = Callable[..., subprocess.CompletedProcess[str]]


class CanaryDeployError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _is_inside_repo(path: Path) -> bool:
    try:
        path.resolve().relative_to(REPO_ROOT)
        return True
    except ValueError:
        return False


def _truthy(value: str | None) -> bool:
    return value is not None and value.lower() in {"1", "true", "yes", "y"}


def _require_external_path(path: Path, label: str, must_exist: bool = False) -> Path:
    resolved = path.expanduser().resolve()
    if _is_inside_repo(resolved):
        raise CanaryDeployError(f"{label} must be outside the repository: {resolved}")
    if must_exist and not resolved.exists():
        raise CanaryDeployError(f"{label} does not exist: {resolved}")
    return resolved


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CanaryDeployError(f"invalid JSON in {path}: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise CanaryDeployError(f"JSON root must be an object: {path}")
    return value


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO_ROOT),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception as exc:
        raise CanaryDeployError("could not resolve prototype git commit") from exc


def _resolve_cli() -> str:
    cli = shutil.which("acurast")
    if not cli:
        raise CanaryDeployError("Acurast CLI is not installed or not on PATH")
    return cli


def _cli_version(cli: str, runner: RunCallable) -> str:
    with tempfile.TemporaryDirectory(prefix="fog-acurast-cli-") as tmpdir:
        completed = runner(
            [cli, "--version"],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=30,
        )
    if completed.returncode != 0:
        raise CanaryDeployError("Acurast CLI --version failed after preflight")
    version = (completed.stdout or completed.stderr).strip()
    if not version:
        raise CanaryDeployError("Acurast CLI --version returned no version")
    return version


def _run_preflight(environ: Mapping[str, str], runner: RunCallable) -> None:
    completed = runner(
        [sys.executable, str(PREFLIGHT), "--require-canary-operator"],
        cwd=str(REPO_ROOT),
        env=dict(environ),
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        details = (completed.stdout or completed.stderr).strip()
        raise CanaryDeployError(f"canary operator preflight failed: {details}")


def _processor_decision(environ: Mapping[str, str]) -> tuple[str, str | None]:
    processor = environ.get(CANARY_PROCESSOR_ENV)
    allow_open_match = _truthy(environ.get(CANARY_ALLOW_OPEN_MATCH_ENV))
    if processor:
        return "explicit", processor
    if allow_open_match:
        return "open", None
    raise CanaryDeployError(
        f"{CANARY_PROCESSOR_ENV} must be set, or {CANARY_ALLOW_OPEN_MATCH_ENV}=1 must be explicit"
    )


def _copy_prototype(prototype_dir: Path, workspace_root: Path) -> Path:
    source = prototype_dir.resolve()
    if not source.exists():
        raise CanaryDeployError(f"prototype directory does not exist: {source}")
    target = workspace_root / "acurast-cargo"
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns("canary-evidence", "fog_task_result*.json", "*.raw.json", "*.raw.txt"),
    )
    return target


def _configure_processor(workdir: Path, matching: str, processor: str | None) -> None:
    config_path = workdir / "acurast.json"
    config = _load_json(config_path)
    projects = config.get("projects")
    if not isinstance(projects, dict) or len(projects) != 1:
        raise CanaryDeployError("acurast.json must define exactly one project")
    project = next(iter(projects.values()))
    if not isinstance(project, dict):
        raise CanaryDeployError("Acurast project config must be an object")

    assignment = project.setdefault("assignmentStrategy", {})
    if not isinstance(assignment, dict):
        raise CanaryDeployError("assignmentStrategy must be an object")
    assignment["type"] = "Single"

    if matching == "explicit":
        if processor is None:
            raise CanaryDeployError("explicit matching requires a processor address")
        assignment["instantMatch"] = [
            {
                "processor": processor,
                "maxAllowedStartDelayInMs": project.get("maxAllowedStartDelayInMs", 10000),
            }
        ]
        project["numberOfReplicas"] = 1
    else:
        assignment.pop("instantMatch", None)

    _write_json(config_path, config)


def _extract_deployment_id(output: str) -> str:
    match = DEPLOYMENT_ID_RE.search(output)
    return match.group(0) if match else "unknown"


def _write_raw_deploy_output(raw_output_dir: Path, stdout: str, stderr: str) -> None:
    raw_output_dir.mkdir(parents=True, exist_ok=True)
    (raw_output_dir / "acurast-deploy.stdout.raw.txt").write_text(stdout, encoding="utf-8")
    (raw_output_dir / "acurast-deploy.stderr.raw.txt").write_text(stderr, encoding="utf-8")


def _run_deploy(
    workdir: Path,
    raw_output_dir: Path,
    cli: str,
    project_name: str,
    timeout: int,
    environ: Mapping[str, str],
    runner: RunCallable,
) -> tuple[str, str]:
    completed = runner(
        [cli, "deploy", project_name],
        cwd=str(workdir),
        env=dict(environ),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    _write_raw_deploy_output(raw_output_dir, stdout, stderr)
    deployment_id = _extract_deployment_id(stdout + "\n" + stderr)
    status = "submitted" if completed.returncode == 0 else "failed"
    return deployment_id, status


def _receipt_state(args: argparse.Namespace) -> str:
    if args.receipt_state:
        state = args.receipt_state
    else:
        state = "present_unverified" if args.receipt_metadata else "missing"

    if state == "missing" and args.receipt_metadata is not None:
        raise CanaryDeployError("receipt metadata cannot be supplied when receipt state is missing")
    if state != "missing" and args.receipt_metadata is None:
        raise CanaryDeployError(f"receipt state {state} requires --receipt-metadata")
    return state


def _build_evidence(
    *,
    cli_version: str,
    deployment_id: str,
    deployment_status: str,
    matching: str,
    processor: str | None,
    result_artifact: Path,
    receipt_metadata: Path | None,
    receipt_state: str,
    task_id: str,
    result_success: bool,
) -> dict[str, Any]:
    trust_reason = "receipt captured but no public verifier is wired into Fog"
    if receipt_state == "missing":
        trust_reason = "no Acurast receipt metadata was captured"
    elif receipt_state == "malformed":
        trust_reason = "receipt metadata was captured but was malformed"
    elif receipt_state == "expired":
        trust_reason = "receipt metadata was captured but is expired"

    deployment: dict[str, Any] = {
        "project_name": "fog-cargo-minimal",
        "deployment_id": deployment_id,
        "status": deployment_status,
        "processor_matching": matching,
    }
    if processor is not None:
        deployment["processor_address"] = processor

    receipt: dict[str, Any] = {
        "captured": receipt_state != "missing",
        "state": receipt_state,
    }
    if receipt_metadata is not None:
        receipt["metadata_sha256"] = _sha256_file(receipt_metadata)

    return {
        "schema_version": "fog.acurast-cargo.canary-evidence.v1",
        "captured_at": _utc_now(),
        "network": "canary",
        "prototype_git_commit": _git_commit(),
        "operator_boundary": {
            "secrets_in_repo": False,
            "raw_artifacts_in_repo": False,
            "evidence_sanitized": True,
        },
        "acurast_cli": {
            "version": cli_version,
        },
        "deployment": deployment,
        "result": {
            "schema_version": "fog.acurast-cargo.result.v1",
            "task_id": task_id,
            "provider": "acurast_cargo",
            "success": result_success,
            "artifact_sha256": _sha256_file(result_artifact),
            "trust": {
                "trusted": False,
                "receipt_state": receipt_state,
                "reason": trust_reason,
            },
        },
        "receipt": receipt,
        "notes": [
            "sanitized evidence generated by scripts/acurast/run_canary_deploy.py",
            "raw deployment artifacts are kept outside the repository",
        ],
    }


def _validate_evidence(path: Path) -> None:
    spec = importlib.util.spec_from_file_location("validate_canary_evidence", EVIDENCE_VALIDATOR)
    if spec is None or spec.loader is None:
        raise CanaryDeployError("could not load canary evidence validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    exit_code = module.validate_evidence(path)
    if exit_code != 0:
        raise CanaryDeployError("generated canary evidence failed validation")


def run_canary_deploy(args: argparse.Namespace, environ: Mapping[str, str], runner: RunCallable) -> int:
    try:
        raw_output_dir = _require_external_path(args.raw_output_dir, "raw output directory")
        result_artifact = _require_external_path(args.result_artifact, "result artifact", must_exist=True)
        receipt_metadata = (
            _require_external_path(args.receipt_metadata, "receipt metadata", must_exist=True)
            if args.receipt_metadata
            else None
        )
        receipt_state = _receipt_state(args)

        _run_preflight(environ, runner)
        matching, processor = _processor_decision(environ)
        cli = _resolve_cli()
        version = _cli_version(cli, runner)

        with tempfile.TemporaryDirectory(prefix="fog-acurast-canary-work-") as tmpdir:
            workdir = _copy_prototype(args.prototype_dir, Path(tmpdir))
            _configure_processor(workdir, matching, processor)

            if args.skip_deploy:
                deployment_id = args.deployment_id or "unknown"
                deployment_status = args.deployment_status or "unknown"
            else:
                deployment_id, deployment_status = _run_deploy(
                    workdir,
                    raw_output_dir,
                    cli,
                    "fog-cargo-minimal",
                    args.timeout,
                    environ,
                    runner,
                )
                if args.deployment_id:
                    deployment_id = args.deployment_id
                if args.deployment_status:
                    deployment_status = args.deployment_status

        evidence = _build_evidence(
            cli_version=version,
            deployment_id=deployment_id,
            deployment_status=deployment_status,
            matching=matching,
            processor=processor,
            result_artifact=result_artifact,
            receipt_metadata=receipt_metadata,
            receipt_state=receipt_state,
            task_id=args.task_id,
            result_success=args.result_success,
        )
        _write_json(args.evidence_out, evidence)
        _validate_evidence(args.evidence_out)
        print(f"OK   sanitized canary evidence written: {args.evidence_out}")
        return 0
    except CanaryDeployError as exc:
        print(f"FAIL {exc}")
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a guarded Acurast canary deploy and emit sanitized evidence.")
    parser.add_argument("--prototype-dir", type=Path, default=DEFAULT_PROTOTYPE_DIR)
    parser.add_argument("--evidence-out", type=Path, required=True)
    parser.add_argument("--raw-output-dir", type=Path, required=True)
    parser.add_argument("--result-artifact", type=Path, required=True)
    parser.add_argument("--receipt-metadata", type=Path)
    parser.add_argument("--receipt-state", choices=RECEIPT_STATES)
    parser.add_argument("--deployment-id")
    parser.add_argument("--deployment-status", choices=DEPLOYMENT_STATUSES)
    parser.add_argument("--task-id", default="wave18-acurast-canary")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--skip-deploy", action="store_true", help="Build evidence from existing external artifacts.")
    parser.add_argument("--result-failed", dest="result_success", action="store_false")
    parser.set_defaults(result_success=True)
    return parser


def main(
    argv: Sequence[str] | None = None,
    environ: Mapping[str, str] | None = None,
    runner: RunCallable = subprocess.run,
) -> int:
    args = build_parser().parse_args(argv)
    return run_canary_deploy(args, environ or os.environ, runner)


if __name__ == "__main__":
    raise SystemExit(main())
