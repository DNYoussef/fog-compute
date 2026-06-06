"""Phase 5 claim-control tests for fog-compute backend surfaces."""

from __future__ import annotations

from datetime import UTC, datetime
import platform
from types import SimpleNamespace

import pytest

from server.routes import tokenomics


class _TokenManager:
    total_supply = 1_000
    stakes = {"alice": {"amount": 100}}

    def get_pending_rewards(self, _address):
        return 12.5


class _DAO:
    initialized = True

    def __init__(self, token_manager=None):
        self.token_manager = token_manager or _TokenManager()
        self.proposals = {
            "active": {"status": "active"},
            "closed": {"status": "closed"},
        }


def _install_dao(monkeypatch, dao):
    monkeypatch.setattr(
        tokenomics.service_manager,
        "get",
        lambda name: dao if name == "dao" else None,
    )


@pytest.mark.asyncio
async def test_tokenomics_stats_do_not_fabricate_market_cap_or_apr(monkeypatch):
    _install_dao(monkeypatch, _DAO())

    stats = await tokenomics.get_tokenomics_stats()

    assert stats["totalSupply"] == 1_000
    assert stats["circulatingSupply"] == 900
    assert stats["proposalsActive"] == 1
    assert stats["marketCap"] is None
    assert stats["tokenPrice"] is None
    assert stats["stakingAPR"] is None
    assert stats["evidenceStatus"]["marketCap"] == "unavailable_no_live_price_feed"
    assert stats["evidenceStatus"]["stakingAPR"] == "unavailable_no_reward_rate_model"


@pytest.mark.asyncio
async def test_tokenomics_stats_use_real_price_when_configured(monkeypatch):
    manager = SimpleNamespace(
        total_supply=1_000,
        stakes={},
        token_price=2.25,
        staking_apr=3.5,
    )
    _install_dao(monkeypatch, _DAO(token_manager=manager))

    stats = await tokenomics.get_tokenomics_stats()

    assert stats["tokenPrice"] == 2.25
    assert stats["marketCap"] == 2_250
    assert stats["stakingAPR"] == 3.5
    assert stats["evidenceStatus"]["marketCap"] == "measured"
    assert stats["evidenceStatus"]["stakingAPR"] == "measured"


@pytest.mark.asyncio
async def test_rewards_rate_is_unavailable_without_reward_rate_model(monkeypatch):
    _install_dao(monkeypatch, _DAO())

    rewards = await tokenomics.get_rewards("alice")

    assert rewards["pendingRewards"] == 12.5
    assert rewards["rewardsRate"] is None
    assert rewards["evidenceStatus"]["rewardsRate"] == "unavailable_no_reward_rate_model"


def test_uvicorn_reload_is_dev_opt_in_not_production_default(monkeypatch):
    from server import main as server_main

    assert server_main.resolve_uvicorn_reload({}) is False
    assert server_main.resolve_uvicorn_reload({"FOG_COMPUTE_API_RELOAD": "true"}) is True
    assert server_main.resolve_uvicorn_reload({"UVICORN_RELOAD": "1"}) is True
    assert server_main.resolve_uvicorn_reload(
        {"APP_ENV": "production", "FOG_COMPUTE_API_RELOAD": "true"}
    ) is False
    assert server_main.resolve_uvicorn_reload(
        {"RAILWAY_ENVIRONMENT": "production", "UVICORN_RELOAD": "true"}
    ) is False

    calls = []
    monkeypatch.delenv("FOG_COMPUTE_API_RELOAD", raising=False)
    monkeypatch.delenv("UVICORN_RELOAD", raising=False)
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    monkeypatch.delenv("RAILWAY_PROJECT_ID", raising=False)
    monkeypatch.setattr(server_main.uvicorn, "run", lambda *args, **kwargs: calls.append(kwargs))

    server_main.main()

    assert calls
    assert calls[0]["reload"] is False


@pytest.mark.asyncio
async def test_task_sandbox_wires_filesystem_and_network_validators_before_execution():
    from server.services.task_sandbox import SandboxStatus, TaskSandboxService

    service = TaskSandboxService()

    path_result = await service.execute_task(
        task_type="compute",
        command=["this-command-must-not-run"],
        filesystem_paths=["/etc/passwd"],
    )

    assert path_result.status == SandboxStatus.FAILED
    assert "not allowed" in (path_result.error_message or "")
    assert service.get_active_executions() == []

    network_result = await service.execute_task(
        task_type="transfer",
        command=["this-command-must-not-run"],
        network_targets=[("example.com", 443)],
    )

    assert network_result.status == SandboxStatus.FAILED
    assert "not allowed" in (network_result.error_message or "")
    assert service.get_active_executions() == []


@pytest.mark.asyncio
async def test_windows_process_sandbox_resource_limit_claim_fails_closed(monkeypatch):
    from server.services import task_sandbox

    monkeypatch.setenv("FOGBURST_ALLOW_PROCESS_SANDBOX", "1")
    monkeypatch.setattr(task_sandbox.platform, "system", lambda: "Windows")

    sandbox = task_sandbox.TaskSandbox(
        task_sandbox.SandboxConfig(
            sandbox_type=task_sandbox.SandboxType.PROCESS,
            max_execution_time_sec=1,
        )
    )

    try:
        await sandbox.setup()
        result = await sandbox.execute(["cmd", "/c", "echo", "should-not-run"])
    finally:
        await sandbox.cleanup()

    assert result.status == task_sandbox.SandboxStatus.FAILED
    assert "Windows process sandbox resource limits are not implemented" in (result.error_message or "")


@pytest.mark.asyncio
async def test_bayesian_reputation_engine_updates_trust_and_scheduler_reads_it():
    from src.batch.placement import FogNode, FogScheduler
    from src.reputation import BayesianReputationEngine

    engine = BayesianReputationEngine(prior_successes=1, prior_failures=1)
    initial_score = engine.get_reputation_score("node-a")
    success_score = engine.record_task_result("node-a", success=True, latency_ms=10)
    failure_score = engine.record_task_result("node-a", success=False, latency_ms=100)

    assert initial_score == 0.5
    assert success_score > initial_score
    assert failure_score != 0.8
    assert failure_score == engine.get_trust_score("node-a")

    scheduler = FogScheduler(reputation_engine=engine)
    node = FogNode(node_id="node-a", endpoint="http://node-a.local")
    await scheduler.register_node(node)
    await scheduler.update_node_status("node-a", {"success_rate": 0.25})

    assert scheduler.node_registry["node-a"].trust_score == engine.get_reputation_score("node-a")


def test_fog_bridge_state_persists_registry_queue_and_quotas(tmp_path):
    from server.routes import fog_bridge

    previous_store = fog_bridge._fog_bridge_store
    try:
        fog_bridge.configure_fog_bridge_state_store(tmp_path / "fog_bridge_state.json")
        now = datetime.now(UTC)
        fog_bridge._registered_devices["device-a"] = {
            "device_name": "Device A",
            "device_type": fog_bridge.DeviceType.DESKTOP,
            "capabilities": {"cpu_cores": 4, "memory_mb": 4096},
            "region": "test",
            "timezone": "UTC",
            "owner_id": "owner-a",
            "status": fog_bridge.DeviceStatus.ONLINE,
            "registered_at": now,
            "last_heartbeat": now,
            "current_task_id": None,
            "total_tasks_completed": 0,
            "uptime_percent": 100.0,
            "reputation_score": 0.73,
        }
        fog_bridge._task_queue["task-a"] = {
            "task_id": "task-a",
            "task_type": "compute",
            "status": "queued",
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "assigned_device_id": None,
        }
        fog_bridge._device_quotas["device-a"] = fog_bridge.DeviceQuota(
            device_id="device-a",
            tasks_today=7,
            quota_reset_at=now,
        )

        fog_bridge.persist_fog_bridge_state()
        fog_bridge._registered_devices.clear()
        fog_bridge._task_queue.clear()
        fog_bridge._device_quotas.clear()

        fog_bridge.reload_fog_bridge_state()

        assert fog_bridge._registered_devices["device-a"]["device_name"] == "Device A"
        assert isinstance(fog_bridge._registered_devices["device-a"]["registered_at"], datetime)
        assert fog_bridge._task_queue["task-a"]["status"] == "queued"
        assert isinstance(fog_bridge._task_queue["task-a"]["created_at"], datetime)
        assert fog_bridge._device_quotas["device-a"].tasks_today == 7
        assert isinstance(fog_bridge._device_quotas["device-a"], fog_bridge.DeviceQuota)
    finally:
        fog_bridge._bind_fog_bridge_store(previous_store)
