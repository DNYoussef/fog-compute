#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft7Validator, FormatChecker
except ImportError:  # pragma: no cover - exercised by environments missing test deps
    Draft7Validator = None
    FormatChecker = None


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "docs" / "contracts" / "acurast-canary-evidence.schema.json"
SENSITIVE_KEY_RE = re.compile(
    r"(mnemonic|private[_-]?key|seed[_-]?phrase|password|access[_-]?token|refresh[_-]?token|secret[_-]?key|api[_-]?key)",
    re.IGNORECASE,
)
PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
ENV_ASSIGNMENT_RE = re.compile(r"(?im)^\s*(MNEMONIC|PRIVATE_KEY|SECRET_KEY|API_KEY|PASSWORD|TOKEN)\s*=")
ABSOLUTE_PATH_RE = re.compile(r"^(?:[A-Za-z]:\\|/Users/|/home/|/tmp/|/var/)")


class EvidenceReport:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.notes: list[str] = []

    def ok(self, message: str) -> None:
        self.notes.append(f"OK   {message}")

    def fail(self, message: str) -> None:
        self.errors.append(f"FAIL {message}")

    def emit(self) -> None:
        for line in [*self.notes, *self.errors]:
            print(line)

    def exit_code(self) -> int:
        return 1 if self.errors else 0


def _load_json(path: Path, report: EvidenceReport, label: str) -> dict[str, Any]:
    if not path.exists():
        report.fail(f"{label} does not exist: {path}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        report.fail(f"{label} is invalid JSON: {exc.msg}")
        return {}
    if not isinstance(value, dict):
        report.fail(f"{label} root must be an object")
        return {}
    return value


def _scan_sensitive(value: Any, report: EvidenceReport, pointer: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_pointer = f"{pointer}.{key}"
            if SENSITIVE_KEY_RE.search(key):
                report.fail(f"sensitive key is not allowed in sanitized evidence: {child_pointer}")
            _scan_sensitive(child, report, child_pointer)
        return

    if isinstance(value, list):
        for index, child in enumerate(value):
            _scan_sensitive(child, report, f"{pointer}[{index}]")
        return

    if not isinstance(value, str):
        return

    if PRIVATE_KEY_RE.search(value) or ENV_ASSIGNMENT_RE.search(value):
        report.fail(f"sensitive value is not allowed in sanitized evidence: {pointer}")
    if ABSOLUTE_PATH_RE.match(value):
        report.fail(f"local filesystem paths are not allowed in sanitized evidence: {pointer}")


def _validate_schema(evidence: dict[str, Any], report: EvidenceReport) -> None:
    schema = _load_json(SCHEMA_PATH, report, "schema")
    if not schema:
        return
    if Draft7Validator is None or FormatChecker is None:
        report.fail("jsonschema is required for canary evidence validation")
        return

    validator = Draft7Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(evidence), key=lambda error: list(error.path))
    if errors:
        for error in errors:
            path = "$" + "".join(f".{part}" for part in error.path)
            report.fail(f"schema violation at {path}: {error.message}")
        return
    report.ok("evidence matches acurast-canary-evidence.schema.json")


def _validate_semantics(evidence: dict[str, Any], report: EvidenceReport) -> None:
    deployment = evidence.get("deployment")
    if isinstance(deployment, dict):
        matching = deployment.get("processor_matching")
        has_processor = "processor_address" in deployment
        if matching == "explicit" and not has_processor:
            report.fail("explicit processor matching requires deployment.processor_address")
        if matching == "open" and has_processor:
            report.fail("open processor matching must not include deployment.processor_address")

    receipt = evidence.get("receipt")
    trust = evidence.get("result", {}).get("trust") if isinstance(evidence.get("result"), dict) else None
    if isinstance(receipt, dict) and isinstance(trust, dict):
        if receipt.get("state") != trust.get("receipt_state"):
            report.fail("receipt.state must match result.trust.receipt_state")
        if trust.get("trusted") is not False:
            report.fail("Acurast canary evidence must not mark results trusted")

    boundary = evidence.get("operator_boundary")
    if isinstance(boundary, dict):
        if boundary.get("secrets_in_repo") is not False:
            report.fail("operator_boundary.secrets_in_repo must be false")
        if boundary.get("raw_artifacts_in_repo") is not False:
            report.fail("operator_boundary.raw_artifacts_in_repo must be false")
        if boundary.get("evidence_sanitized") is not True:
            report.fail("operator_boundary.evidence_sanitized must be true")


def validate_evidence(path: Path) -> int:
    report = EvidenceReport()
    evidence = _load_json(path, report, "evidence")
    if evidence:
        _scan_sensitive(evidence, report)
        _validate_schema(evidence, report)
        _validate_semantics(evidence, report)
    if not report.errors:
        report.ok(f"sanitized canary evidence is reviewable: {path}")
    report.emit()
    return report.exit_code()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate sanitized Acurast canary evidence.")
    parser.add_argument("evidence", type=Path, help="Path to sanitized canary evidence JSON")
    args = parser.parse_args()
    return validate_evidence(args.evidence)


if __name__ == "__main__":
    raise SystemExit(main())
