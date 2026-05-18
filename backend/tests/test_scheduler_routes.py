"""Regression tests for truthful scheduler route failures."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from server.routes import scheduler as scheduler_routes


def _set_scheduler(monkeypatch, scheduler):
    monkeypatch.setattr(
        scheduler_routes.service_manager,
        "get",
        lambda service_name: scheduler if service_name == "scheduler" else None,
    )


@pytest.mark.asyncio
async def test_get_scheduler_stats_fails_explicitly_on_mismatched_scheduler(monkeypatch):
    """Stats route must 503 instead of returning empty metrics for the wrong scheduler type."""
    _set_scheduler(monkeypatch, SimpleNamespace(get_job_queue=lambda: []))

    with pytest.raises(HTTPException) as exc:
        await scheduler_routes.get_scheduler_stats()

    assert exc.value.status_code == 503
    assert "misconfigured" in exc.value.detail
    assert "get_metrics" in exc.value.detail


@pytest.mark.asyncio
async def test_submit_job_rejects_mismatched_scheduler_before_db_write(monkeypatch):
    """Submit route must fail before touching the DB when scheduler wiring is broken."""
    _set_scheduler(monkeypatch, SimpleNamespace(get_job_queue=lambda: []))
    db = SimpleNamespace(
        add=Mock(),
        flush=AsyncMock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
        rollback=AsyncMock(),
    )
    request = scheduler_routes.JobSubmitRequest(
        name="demo",
        sla_tier="gold",
        cpu_required=1.0,
        memory_required=512.0,
    )

    with pytest.raises(HTTPException) as exc:
        await scheduler_routes.submit_job(request, db=db)

    assert exc.value.status_code == 503
    assert not db.add.called
    assert db.flush.await_count == 0
    assert db.commit.await_count == 0
    assert db.refresh.await_count == 0


@pytest.mark.asyncio
async def test_update_job_fails_instead_of_reporting_success_on_mismatch(monkeypatch):
    """Update route must not silently report success when the scheduler lacks the write API."""
    _set_scheduler(monkeypatch, SimpleNamespace(get_job_queue=lambda: []))

    with pytest.raises(HTTPException) as exc:
        await scheduler_routes.update_job(
            "job-123",
            scheduler_routes.JobUpdateRequest(status="cancelled"),
        )

    assert exc.value.status_code == 503
    assert "update_job_status" in exc.value.detail


@pytest.mark.asyncio
async def test_get_nodes_fails_instead_of_returning_empty_list_on_mismatch(monkeypatch):
    """Nodes route must not pretend the cluster is empty when scheduler wiring is wrong."""
    _set_scheduler(monkeypatch, SimpleNamespace())

    with pytest.raises(HTTPException) as exc:
        await scheduler_routes.get_nodes()

    assert exc.value.status_code == 503
    assert "nodes" in exc.value.detail
