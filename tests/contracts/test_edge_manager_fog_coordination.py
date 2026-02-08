"""Contract tests for edge-to-fog task coordination."""

from datetime import UTC, datetime

import pytest

from src.idle.edge_manager import (
    DeviceCapabilities,
    DeviceType,
    EdgeDeployment,
    EdgeDevice,
    EdgeManager,
    EdgeState,
    FogNode,
)


def _caps(cpu_cores: int = 4, max_tasks: int = 4) -> DeviceCapabilities:
    return DeviceCapabilities(
        cpu_cores=cpu_cores,
        ram_total_mb=8192,
        ram_available_mb=6144,
        storage_available_gb=128.0,
        gpu_available=False,
        gpu_memory_mb=0,
        battery_powered=False,
        max_concurrent_tasks=max_tasks,
    )


def _device(device_id: str, state: EdgeState = EdgeState.ONLINE) -> EdgeDevice:
    now = datetime.now(UTC)
    return EdgeDevice(
        device_id=device_id,
        device_name=device_id,
        device_type=DeviceType.DESKTOP,
        capabilities=_caps(),
        state=state,
        registered_at=now,
        last_seen=now,
    )


class TestEdgeManagerFogCoordination:
    @pytest.mark.asyncio
    async def test_process_fog_tasks_builds_nodes_and_assigns_running_deployments(self):
        manager = EdgeManager(config={"fog_group_count": 2})
        manager.devices = {
            "dev-a": _device("dev-a"),
            "dev-b": _device("dev-b"),
            "dev-c": _device("dev-c"),
        }
        manager.deployments = {
            "dep-1": EdgeDeployment(
                deployment_id="dep-1",
                device_id="dev-a",
                model_id="m1",
                deployment_type="inference",
                state="running",
                priority=10,
            ),
            "dep-2": EdgeDeployment(
                deployment_id="dep-2",
                device_id="dev-b",
                model_id="m2",
                deployment_type="inference",
                state="running",
                priority=5,
            ),
        }

        await manager._process_fog_tasks()

        assert len(manager.fog_nodes) >= 1
        assert manager.stats["fog_compute_tasks"] == 2
        for fog_node in manager.fog_nodes.values():
            assert fog_node.coordinator_device in manager.devices
            assert fog_node.active_tasks <= fog_node.max_tasks

    @pytest.mark.asyncio
    async def test_process_fog_tasks_clears_state_without_eligible_devices(self):
        manager = EdgeManager()
        manager.devices = {
            "dev-offline": _device("dev-offline", state=EdgeState.OFFLINE),
        }
        manager.fog_nodes = {
            "fog-node-0": FogNode(
                node_id="fog-node-0",
                device_ids=["dev-offline"],
                coordinator_device="dev-offline",
                compute_capacity=1.0,
                active_tasks=3,
                max_tasks=4,
            )
        }
        manager.stats["fog_compute_tasks"] = 7

        await manager._process_fog_tasks()

        assert manager.fog_nodes == {}
        assert manager.stats["fog_compute_tasks"] == 0

    @pytest.mark.asyncio
    async def test_process_fog_tasks_respects_group_capacity(self):
        manager = EdgeManager(config={"fog_group_count": 1})
        now = datetime.now(UTC)
        manager.devices = {
            "dev-a": EdgeDevice(
                device_id="dev-a",
                device_name="dev-a",
                device_type=DeviceType.DESKTOP,
                capabilities=_caps(max_tasks=1),
                state=EdgeState.ONLINE,
                registered_at=now,
                last_seen=now,
            ),
            "dev-b": EdgeDevice(
                device_id="dev-b",
                device_name="dev-b",
                device_type=DeviceType.DESKTOP,
                capabilities=_caps(max_tasks=1),
                state=EdgeState.ONLINE,
                registered_at=now,
                last_seen=now,
            ),
        }
        manager.deployments = {
            f"dep-{i}": EdgeDeployment(
                deployment_id=f"dep-{i}",
                device_id="dev-a",
                model_id=f"m{i}",
                deployment_type="inference",
                state="running",
                priority=10 - i,
            )
            for i in range(3)
        }

        await manager._process_fog_tasks()

        assert len(manager.fog_nodes) == 1
        assert manager.stats["fog_compute_tasks"] == 2
