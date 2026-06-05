"""Behavioral tests for DELETE /api/deployment/{deployment_id}."""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT / "src"))

from server.models.deployment import DeploymentStatus, ReplicaStatus
from server.routes import deployment as deployment_routes
from server.services import rewards as reward_module


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        return self._value


class _QueuedDB:
    def __init__(self, *results):
        self._results = list(results)
        self.added = []
        self.flushes = 0
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, _query):
        if not self._results:
            raise AssertionError("unexpected query")
        return _ScalarResult(self._results.pop(0))

    def add(self, item):
        self.added.append(item)

    async def flush(self):
        self.flushes += 1

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class _RewardService:
    def __init__(self):
        self.calls = []

    async def cleanup_with_distribution(self, *, deployment_id, user_id, db):
        self.calls.append((deployment_id, user_id, db))
        return SimpleNamespace(
            success=True,
            rewards_distributed=2,
            rewards_amount=Decimal("1.5"),
            error_message=None,
        )


@pytest.fixture
def deletion_dependencies(monkeypatch):
    reward_service = _RewardService()
    cache_service = SimpleNamespace(publish_event=AsyncMock())
    load_balancer = AsyncMock(return_value=True)

    monkeypatch.setattr(reward_module, "get_reward_service", lambda: reward_service)
    monkeypatch.setattr(deployment_routes, "cache_service", cache_service)
    monkeypatch.setattr(deployment_routes, "_update_load_balancer_routes", load_balancer)

    return reward_service, cache_service, load_balancer


@pytest.mark.asyncio
async def test_delete_deployment_soft_deletes_owned_deployment(deletion_dependencies):
    deployment_id = uuid4()
    user_id = uuid4()
    user = SimpleNamespace(id=user_id, username="owner")
    deployment = SimpleNamespace(
        id=deployment_id,
        user_id=user_id,
        status=DeploymentStatus.RUNNING,
        deleted_at=None,
        updated_at=None,
    )
    running = SimpleNamespace(
        id=uuid4(),
        node_id=uuid4(),
        status=ReplicaStatus.RUNNING,
        stopped_at=None,
        updated_at=None,
    )
    starting = SimpleNamespace(
        id=uuid4(),
        node_id=uuid4(),
        status=ReplicaStatus.STARTING,
        stopped_at=None,
        updated_at=None,
    )
    failed = SimpleNamespace(
        id=uuid4(),
        node_id=uuid4(),
        status=ReplicaStatus.FAILED,
        stopped_at=None,
        updated_at=None,
    )
    resources = SimpleNamespace(cpu_cores=2.0, memory_mb=1024, gpu_units=0, storage_gb=10)
    db = _QueuedDB(deployment, [running, starting, failed], resources)

    response = await deployment_routes.delete_deployment(
        str(deployment_id),
        db=db,
        current_user=user,
    )

    reward_service, cache_service, load_balancer = deletion_dependencies
    assert response["success"] is True
    assert response["deployment_id"] == str(deployment_id)
    assert response["replicas_stopped"] == 2
    assert response["resources_released"] is True
    assert response["rewards_distributed"] == 2
    assert deployment.status == DeploymentStatus.DELETED
    assert isinstance(deployment.deleted_at, datetime)
    assert deployment.deleted_at.tzinfo is not None
    assert running.status == ReplicaStatus.STOPPED
    assert starting.status == ReplicaStatus.STOPPED
    assert failed.status == ReplicaStatus.FAILED
    assert running.stopped_at.tzinfo is not None
    assert starting.stopped_at.tzinfo is not None
    assert db.flushes == 2
    assert db.commits == 1
    assert db.rollbacks == 0
    assert len(db.added) == 1
    history = db.added[0]
    assert history.deployment_id == deployment_id
    assert history.old_status == DeploymentStatus.RUNNING.value
    assert history.new_status == DeploymentStatus.DELETED.value
    assert history.changed_by == user_id
    assert reward_service.calls == [(deployment_id, user_id, db)]
    load_balancer.assert_awaited_once_with(str(deployment_id), action="remove")
    assert cache_service.publish_event.await_count == 2


@pytest.mark.asyncio
async def test_delete_deployment_denies_other_user_without_mutation(deletion_dependencies):
    deployment_id = uuid4()
    owner_id = uuid4()
    attacker = SimpleNamespace(id=uuid4(), username="attacker")
    other_deployment = SimpleNamespace(
        id=deployment_id,
        user_id=owner_id,
        status=DeploymentStatus.RUNNING,
        deleted_at=None,
    )
    db = _QueuedDB(None, other_deployment)

    with pytest.raises(HTTPException) as exc:
        await deployment_routes.delete_deployment(
            str(deployment_id),
            db=db,
            current_user=attacker,
        )

    assert exc.value.status_code == 404
    assert "access denied" in exc.value.detail
    assert other_deployment.deleted_at is None
    assert db.commits == 0
    assert db.rollbacks == 1
    assert db.added == []


def test_deployment_deletion_contract_has_no_placeholder_stubs():
    source = Path(__file__).read_text(encoding="utf-8")
    parsed = ast.parse(source)

    assert "TO" + "DO" not in source
    assert not any(isinstance(node, ast.Pass) for node in ast.walk(parsed))
