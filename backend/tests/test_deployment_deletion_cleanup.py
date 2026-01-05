"""
Tests for deployment deletion cleanup behavior.

Validates that replica containers are stopped and removed when deleting deployments.
"""
import asyncio
from unittest.mock import AsyncMock
from types import SimpleNamespace

from server.services.replica_cleanup import stop_replica_for_deletion
from server.models.deployment import ReplicaStatus


class _ReplicaStub(SimpleNamespace):
    """Lightweight replica stub for deletion tests."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.stopped_at = None
        self.updated_at = None


def test_stop_replica_removes_container_and_updates_status():
    """Ensure stop/remove is invoked and status transitions to STOPPED."""
    replica = _ReplicaStub(
        id="replica-123",
        node_id="node-1",
        status=ReplicaStatus.RUNNING,
        container_id="stub-container-123",
    )

    db = AsyncMock()
    docker_client = AsyncMock()

    asyncio.run(stop_replica_for_deletion(replica, db, docker_client))

    db.flush.assert_awaited_once()
    docker_client.stop_container.assert_awaited_once_with("stub-container-123")
    docker_client.remove_container.assert_awaited_once_with("stub-container-123")
    assert replica.status == ReplicaStatus.STOPPED
    assert replica.stopped_at is not None
    assert replica.updated_at is not None
