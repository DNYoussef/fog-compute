"""Trust handling for Acurast Cargo result envelopes."""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

ACURAST_CARGO_PROVIDER = "acurast_cargo"
FOG_RESULT_TRUST_KEY = "_fog_result_trust"
REQUIRED_RECEIPT_FIELDS = ("kind", "payload_hash", "signature")


def _parse_receipt_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    if "T" not in value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(UTC)


def _receipt_state(receipt: Any) -> tuple[str, str]:
    if receipt is None:
        return "missing", "Acurast Cargo result did not include a receipt"
    if not isinstance(receipt, dict):
        return "malformed", "Acurast Cargo receipt must be an object"

    missing = [
        field
        for field in REQUIRED_RECEIPT_FIELDS
        if not isinstance(receipt.get(field), str) or not receipt.get(field)
    ]
    if missing:
        return "malformed", f"Acurast Cargo receipt missing fields: {', '.join(missing)}"

    expires_at = receipt.get("expires_at")
    if expires_at is not None:
        parsed_expires_at = _parse_receipt_timestamp(expires_at)
        if parsed_expires_at is None:
            return "malformed", "Acurast Cargo receipt expires_at must be an RFC3339 timestamp"
        if parsed_expires_at <= datetime.now(UTC):
            return "expired", f"Acurast Cargo receipt expired at {parsed_expires_at.isoformat()}"

    return "present_unverified", "Acurast Cargo receipt is present but not cryptographically verified"


def annotate_acurast_result_trust(result: dict[str, Any] | None) -> dict[str, Any] | None:
    """Annotate Acurast-labeled results without trusting self-reported metadata."""
    if result is None:
        return None
    if not isinstance(result, dict):
        return result

    execution = result.get("execution")
    legacy_provider = result.get("execution_provider")
    provider = execution.get("provider") if isinstance(execution, dict) else legacy_provider
    if provider != ACURAST_CARGO_PROVIDER:
        return result

    annotated = deepcopy(result)
    execution = annotated.get("execution")
    receipt = execution.get("receipt") if isinstance(execution, dict) else None
    state, reason = _receipt_state(receipt)
    annotated[FOG_RESULT_TRUST_KEY] = {
        "provider": ACURAST_CARGO_PROVIDER,
        "trusted": False,
        "receipt_state": state,
        "reason": reason,
    }
    return annotated
