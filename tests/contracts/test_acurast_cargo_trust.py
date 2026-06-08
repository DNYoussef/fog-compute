from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend.server.services.acurast_cargo import FOG_RESULT_TRUST_KEY, annotate_acurast_result_trust


VALID_HASH = "a" * 64


def _result(receipt_marker=None, provider: str = "acurast_cargo"):
    execution = {
        "provider": provider,
        "deployment_id": "Acurast:test:trust",
    }
    if receipt_marker is not None:
        execution["receipt"] = receipt_marker

    return {
        "schema_version": "fog.acurast-cargo.result.v1",
        "task_id": "task-acurast-trust",
        "execution": execution,
        "result": {"value": 29, "value_type": "number"},
    }


def _trust(receipt_marker=None):
    annotated = annotate_acurast_result_trust(_result(receipt_marker))
    assert annotated is not None
    return annotated[FOG_RESULT_TRUST_KEY]


def test_non_acurast_result_is_not_annotated():
    annotated = annotate_acurast_result_trust(_result(provider="local"))

    assert annotated is not None
    assert FOG_RESULT_TRUST_KEY not in annotated


def test_acurast_missing_receipt_is_untrusted():
    trust = _trust()

    assert trust["trusted"] is False
    assert trust["receipt_state"] == "missing"


def test_acurast_malformed_receipt_is_untrusted():
    trust = _trust({"kind": "bridge"})

    assert trust["trusted"] is False
    assert trust["receipt_state"] == "malformed"
    assert "payload_hash" in trust["reason"]


def test_acurast_present_receipt_is_unverified_not_trusted():
    trust = _trust({"kind": "bridge", "payload_hash": VALID_HASH, "signature": "sig"})

    assert trust["trusted"] is False
    assert trust["receipt_state"] == "present_unverified"


def test_acurast_expired_receipt_is_untrusted():
    trust = _trust(
        {
            "kind": "bridge",
            "payload_hash": VALID_HASH,
            "signature": "sig",
            "expires_at": (datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
        }
    )

    assert trust["trusted"] is False
    assert trust["receipt_state"] == "expired"


def test_acurast_invalid_receipt_expiry_is_malformed_untrusted():
    trust = _trust(
        {
            "kind": "bridge",
            "payload_hash": VALID_HASH,
            "signature": "sig",
            "expires_at": "not-a-date",
        }
    )

    assert trust["trusted"] is False
    assert trust["receipt_state"] == "malformed"
    assert "expires_at" in trust["reason"]


def test_acurast_future_time_bound_receipt_remains_unverified_not_trusted():
    trust = _trust(
        {
            "kind": "bridge",
            "payload_hash": VALID_HASH,
            "signature": "sig",
            "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        }
    )

    assert trust["trusted"] is False
    assert trust["receipt_state"] == "present_unverified"
