import logging

import pytest
from fastapi import HTTPException

from server.middleware import api_key_auth
from server.middleware.api_key_auth import APIKeyRateLimiter


def test_api_key_rate_limit_is_shared_across_worker_instances(tmp_path):
    storage_path = str(tmp_path / "api-key-rate-limits.sqlite3")
    worker_a = APIKeyRateLimiter(storage_path=storage_path, window_size=3600)
    worker_b = APIKeyRateLimiter(storage_path=storage_path, window_size=3600)

    assert worker_a.is_allowed("api-key-1", rate_limit=2)[0] is True
    assert worker_b.is_allowed("api-key-1", rate_limit=2)[0] is True

    allowed, current_count, retry_after = worker_a.is_allowed("api-key-1", rate_limit=2)

    assert allowed is False
    assert current_count == 2
    assert retry_after > 0


def test_api_key_rate_limiter_fails_closed_when_shared_store_is_unavailable(tmp_path):
    bad_storage_path = str(tmp_path)
    limiter = APIKeyRateLimiter(storage_path=bad_storage_path, window_size=60)

    allowed, current_count, retry_after = limiter.is_allowed("api-key-1", rate_limit=10)

    assert allowed is False
    assert current_count == 10
    assert retry_after == 60


@pytest.mark.asyncio
async def test_invalid_api_key_logs_no_reusable_prefix(monkeypatch, caplog):
    secret = "fog_live_secret_prefix_that_must_not_appear"

    async def fake_validate_key(api_key, db):
        assert api_key == secret
        return None

    monkeypatch.setattr(api_key_auth.APIKeyManager, "validate_key", fake_validate_key)
    caplog.set_level(logging.WARNING, logger="server.middleware.api_key_auth")

    assert await api_key_auth.get_api_key_user(secret, db=None) is None
    with pytest.raises(HTTPException):
        await api_key_auth.require_api_key(secret, db=None)

    log_text = caplog.text
    assert "Invalid API key attempt" in log_text
    assert f"length={len(secret)}" in log_text
    assert secret not in log_text
    assert secret[:15] not in log_text
