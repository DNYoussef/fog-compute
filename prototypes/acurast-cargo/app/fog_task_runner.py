#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any

TASK_SCHEMA_VERSION = "fog.acurast-cargo.task.v1"
RESULT_SCHEMA_VERSION = "fog.acurast-cargo.result.v1"
SUPPORTED_OPERATIONS = {"add", "multiply", "sum", "sha256"}


class PayloadError(ValueError):
    """Raised when a Fog task payload cannot be executed deterministically."""


def _read_payload(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise PayloadError(f"invalid JSON payload: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise PayloadError("payload must be a JSON object")
    return payload, raw


def _as_number(value: Any) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PayloadError("numeric operations require number operands")
    return value


def _validate_payload(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != TASK_SCHEMA_VERSION:
        raise PayloadError(f"schema_version must be {TASK_SCHEMA_VERSION}")
    task_id = payload.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        raise PayloadError("task_id must be a non-empty string")
    operation = payload.get("operation")
    if operation not in SUPPORTED_OPERATIONS:
        raise PayloadError("operation is not supported")
    operands = payload.get("operands")
    if not isinstance(operands, list) or not operands:
        raise PayloadError("operands must be a non-empty array")
    if len(operands) > 64:
        raise PayloadError("operands must not exceed 64 entries")


def _run_operation(operation: str, operands: list[Any]) -> tuple[int | float | str, str]:
    if operation == "sha256":
        digest_input = "\n".join(str(item) for item in operands).encode("utf-8")
        return hashlib.sha256(digest_input).hexdigest(), "string"

    numbers = [_as_number(item) for item in operands]
    if operation in {"add", "sum"}:
        return sum(numbers), "number"
    if operation == "multiply":
        value: int | float = 1
        for item in numbers:
            value *= item
        return value, "number"
    raise PayloadError("operation is not supported")


def _execution_metadata() -> dict[str, Any]:
    bridge_socket = os.getenv("BRIDGE_SOCKET")
    provider = "acurast_cargo" if bridge_socket else "local"
    execution: dict[str, Any] = {
        "provider": provider,
        "bridge_socket_present": bool(bridge_socket),
    }

    deployment_id = os.getenv("ACURAST_DEPLOYMENT_ID")
    processor = os.getenv("ACURAST_PROCESSOR")
    if deployment_id:
        execution["deployment_id"] = deployment_id
    if processor:
        execution["processor"] = processor
    return execution


def run_payload(payload: dict[str, Any], raw_payload: bytes) -> dict[str, Any]:
    start = time.perf_counter()
    _validate_payload(payload)
    value, value_type = _run_operation(payload["operation"], payload["operands"])
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "task_id": payload["task_id"],
        "success": True,
        "operation": payload["operation"],
        "result": {
            "value": value,
            "value_type": value_type,
        },
        "input_sha256": hashlib.sha256(raw_payload).hexdigest(),
        "runtime": {
            "runner": "fog_task_runner.py",
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "elapsed_ms": elapsed_ms,
        },
        "execution": _execution_metadata(),
        "error": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a deterministic Fog task payload.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    try:
        payload, raw_payload = _read_payload(args.input)
        result = run_payload(payload, raw_payload)
        return_code = 0
    except Exception as exc:
        result = {
            "schema_version": RESULT_SCHEMA_VERSION,
            "task_id": "unknown",
            "success": False,
            "operation": "sum",
            "result": {
                "value": "",
                "value_type": "string",
            },
            "input_sha256": hashlib.sha256(b"").hexdigest(),
            "runtime": {
                "runner": "fog_task_runner.py",
                "python_version": platform.python_version(),
                "platform": platform.platform(),
                "elapsed_ms": 0.0,
            },
            "execution": _execution_metadata(),
            "error": str(exc),
        }
        return_code = 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return return_code


if __name__ == "__main__":
    sys.exit(main())
