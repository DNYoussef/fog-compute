"""Phase 3 regressions for fog-compute runtime correctness findings."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from server.routes import dashboard
from server.services.file_transfer import FileTransferService
from server.services.rewards import RewardDistributionService


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
        self.commits = 0

    async def execute(self, _query):
        if not self._results:
            raise AssertionError("unexpected query")
        return _ScalarResult(self._results.pop(0))

    async def commit(self):
        self.commits += 1

    async def refresh(self, _obj):
        return None


class _TransferRow(SimpleNamespace):
    def to_dict(self):
        return dict(self.__dict__)


class _ChunkRow(SimpleNamespace):
    def to_dict(self):
        return dict(self.__dict__)


class _RecordingLock:
    def __init__(self):
        self.entries = 0
        self._lock = asyncio.Lock()

    async def __aenter__(self):
        self.entries += 1
        await self._lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._lock.release()
        return False


@pytest.mark.asyncio
async def test_deployment_runtime_rewards_use_defined_utc_clock():
    deployment_id = uuid4()
    user_id = uuid4()
    replica_id = uuid4()
    deployment = SimpleNamespace(id=deployment_id, user_id=user_id, name="api")
    replica = SimpleNamespace(
        id=replica_id,
        started_at=datetime.now(UTC) - timedelta(hours=2),
    )
    db = _QueuedDB(deployment, [replica])
    token_system = SimpleNamespace(accounts={})
    service = RewardDistributionService(token_system=token_system)

    rewards = await service.get_pending_rewards(
        user_id=user_id,
        deployment_id=deployment_id,
        db=db,
    )

    assert len(rewards) == 1
    reward = rewards[0]
    assert reward.account_id == str(user_id)
    assert reward.reason == "Deployment runtime rewards for api"
    assert reward.metadata["replica_id"] == str(replica_id)
    assert reward.amount >= Decimal("19.9")


def test_network_metrics_use_delta_not_lifetime_counters():
    dashboard._network_sample = None
    first = SimpleNamespace(bytes_sent=8_000_000_000, bytes_recv=2_000_000_000)
    second = SimpleNamespace(bytes_sent=8_000_000_000, bytes_recv=2_000_000_000)
    third = SimpleNamespace(bytes_sent=8_012_500_000, bytes_recv=2_000_000_000)

    assert dashboard._calculate_network_metrics(first, now=100.0) == {
        "throughput": 0.0,
        "networkUtilization": 0.0,
    }
    assert dashboard._calculate_network_metrics(second, now=101.0) == {
        "throughput": 0.0,
        "networkUtilization": 0.0,
    }

    metrics = dashboard._calculate_network_metrics(third, now=102.0)
    assert metrics["throughput"] == pytest.approx(100.0)
    assert metrics["networkUtilization"] == pytest.approx(10.0)


@pytest.mark.asyncio
async def test_upload_download_and_assembly_use_persistent_file_lock(tmp_path):
    service = FileTransferService(storage_path=str(tmp_path), bandwidth_limit_mbps=None)
    file_id = "file-1"
    lock = _RecordingLock()
    service._file_locks[file_id] = lock

    upload_chunk = _ChunkRow(
        file_id=file_id,
        chunk_index=0,
        uploaded=False,
        chunk_hash="",
        uploaded_at=None,
        stored_path="",
    )
    upload_transfer = _TransferRow(
        file_id=file_id,
        filename="example.txt",
        uploaded_chunks=0,
        total_chunks=2,
        status="pending",
        completed_at=None,
    )
    await service.upload_chunk(
        file_id,
        0,
        b"hello",
        _QueuedDB(upload_transfer, upload_chunk),
    )
    assert lock.entries == 1

    download_chunk = _ChunkRow(
        file_id=file_id,
        chunk_index=0,
        uploaded=True,
        chunk_hash=upload_chunk.chunk_hash,
    )
    assert await service.download_chunk(file_id, 0, _QueuedDB(download_chunk)) == b"hello"
    assert lock.entries == 2

    second_chunk_path = service._get_chunk_path(file_id, 1)
    second_chunk_path.parent.mkdir(parents=True, exist_ok=True)
    second_chunk_path.write_bytes(b" world")
    assemble_transfer = _TransferRow(file_id=file_id, filename="example.txt")
    assemble_chunks = [
        _ChunkRow(file_id=file_id, chunk_index=0, uploaded=True),
        _ChunkRow(file_id=file_id, chunk_index=1, uploaded=True),
    ]

    await service._assemble_file(file_id, _QueuedDB(assemble_transfer, assemble_chunks))

    assert lock.entries == 3
    assert service._get_file_path(file_id, "example.txt").read_bytes() == b"hello world"
