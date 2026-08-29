from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.server.routes import mesh
from backend.server.schemas.device_mesh import (
    DeviceCapability,
    DeviceProfile,
    DeviceRole,
    DeviceState,
    DeviceStatus,
    LivenessState,
)


def _device_state(
    device_id: str = "mesh-wor-1",
    *,
    role: DeviceRole = DeviceRole.WORKER,
    status: DeviceStatus = DeviceStatus.ONLINE,
    zone: str = "default",
    current_load: float = 0.25,
) -> DeviceState:
    now = datetime.now(UTC)
    return DeviceState(
        device_id=device_id,
        device_name=f"Device {device_id}",
        role=role,
        status=status,
        zone=zone,
        profile=DeviceProfile(
            hostname=device_id,
            capabilities=[DeviceCapability.CPU, DeviceCapability.MEMORY],
            cpu_cores=4,
            ram_gb=8.0,
            storage_gb=100.0,
            bandwidth_mbps=50.0,
            max_concurrent_tasks=2,
        ),
        liveness=LivenessState(
            device_id=device_id,
            last_seen=now,
            status=status,
            is_healthy=status != DeviceStatus.OFFLINE,
        ),
        joined_at=now,
        last_heartbeat=now,
        current_load=current_load,
    )


class FakePersistence:
    def __init__(self):
        self.token_map = {"valid-token": "mesh-wor-1"}
        self.states = {
            "mesh-pri-1": _device_state("mesh-pri-1", role=DeviceRole.PRIMARY, current_load=0.1),
            "mesh-wor-1": _device_state("mesh-wor-1", role=DeviceRole.WORKER, zone="edge", current_load=0.5),
        }

    async def get_device_by_token(self, token: str):
        return self.token_map.get(token)

    async def get_primary_device(self):
        return SimpleNamespace(device_id="mesh-pri-1")

    async def list_devices(self, zone=None, status=None, role=None, include_offline=True):
        devices = list(self.states.values())
        if zone is not None:
            devices = [device for device in devices if device.zone == zone]
        if status is not None:
            devices = [device for device in devices if device.status == status]
        if role is not None:
            devices = [device for device in devices if device.role == role]
        if not include_offline:
            devices = [device for device in devices if device.status != DeviceStatus.OFFLINE]
        return devices

    def to_device_state(self, device):
        return device

    async def get_device_state(self, device_id: str):
        return self.states.get(device_id)

    async def update_device_heartbeat(self, **_kwargs):
        return True

    async def update_device(self, device_id: str, **kwargs):
        state = self.states.get(device_id)
        if state is None:
            return None
        update = state.model_copy()
        if kwargs.get("device_name") is not None:
            update.device_name = kwargs["device_name"]
        self.states[device_id] = update
        return update

    async def remove_device(self, device_id: str, reason: str = "removed"):
        return device_id in self.states


class FakeMeshService:
    heartbeat_interval_sec = 30
    sync_interval_sec = 60

    async def join_mesh(self, **kwargs):
        assert kwargs["owner_id"] == "owner-1"
        assert kwargs["public_key"] == "pub-key"
        return "mesh-wor-new", "mesh-token", kwargs["preferred_role"], kwargs["zone"]

    async def process_heartbeat(self, **_kwargs):
        return True, [], False, 31


def _client(monkeypatch):
    fake_persistence = FakePersistence()
    monkeypatch.setattr(mesh, "get_mesh_persistence", lambda: fake_persistence)
    monkeypatch.setattr(mesh, "get_mesh_service", lambda: FakeMeshService())

    app = FastAPI()
    app.include_router(mesh.router)
    return TestClient(app)


def test_join_mesh_returns_tls_aware_websocket_url(monkeypatch):
    client = _client(monkeypatch)

    response = client.post(
        "/api/mesh/join",
        json={
            "device_name": "Worker",
            "owner_id": "owner-1",
            "public_key": "pub-key",
            "preferred_role": "worker",
            "preferred_zone": "edge",
            "profile": {
                "hostname": "worker",
                "capabilities": ["cpu"],
                "cpu_cores": 2,
                "ram_gb": 4.0,
                "storage_gb": 50.0,
                "bandwidth_mbps": 25.0,
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["device_id"] == "mesh-wor-new"
    assert body["assigned_zone"] == "edge"
    assert body["websocket_url"].endswith("/api/mesh/ws/mesh-wor-new")


def test_list_devices_requires_valid_mesh_token(monkeypatch):
    client = _client(monkeypatch)

    unauthorized = client.get("/api/mesh/devices")
    assert unauthorized.status_code == 401

    response = client.get("/api/mesh/devices", headers={"X-Mesh-Token": "valid-token"})
    assert response.status_code == 200
    assert {device["device_id"] for device in response.json()} == {"mesh-pri-1", "mesh-wor-1"}


def test_topology_aggregates_persisted_mesh_devices(monkeypatch):
    client = _client(monkeypatch)

    response = client.get("/api/mesh/topology", headers={"Authorization": "Bearer valid-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["total_devices"] == 2
    assert body["primary_device_id"] == "mesh-pri-1"
    assert body["zones"]["edge"]["device_count"] == 1
    assert body["total_capacity"]["cpu_cores"] == 8.0
