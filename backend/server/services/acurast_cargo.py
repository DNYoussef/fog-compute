"""Trust handling for Acurast Cargo result envelopes."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

ACURAST_CARGO_PROVIDER = "acurast_cargo"
FOG_RESULT_TRUST_KEY = "_fog_result_trust"
REQUIRED_RECEIPT_FIELDS = ("kind", "payload_hash", "signature")


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
