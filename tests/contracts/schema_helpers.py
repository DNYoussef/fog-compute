"""
Schema validation helpers for contract tests.
"""
import json
from pathlib import Path
from jsonschema import validate, ValidationError

CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "docs" / "contracts"


def load_schema(name: str) -> dict:
    path = CONTRACTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Contract schema not found: {path}")
    with open(path) as f:
        return json.load(f)


def assert_matches_schema(payload: dict, schema: dict, msg: str = ""):
    """Validate a payload against a JSON schema. Raises on mismatch."""
    try:
        validate(instance=payload, schema=schema)
    except ValidationError as exc:
        detail = f"Contract violation{(' - ' + msg) if msg else ''}: {exc.message}"
        raise AssertionError(detail) from exc
