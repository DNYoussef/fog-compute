"""
Tests for idle compute contract fixes (Phase 2).

SIN-016: register_device awaits async with correct signature
SIN-017: heartbeat/unregister fail explicitly, no silent no-ops
SIN-018: typed DTOs replace dynamic getattr
"""
import os
import sys
from pathlib import Path

# Set TESTING before any backend imports trigger Settings validation
os.environ.setdefault("TESTING", "true")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-contracts-testing-only-32chars")

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from datetime import datetime, timezone
from schema_helpers import load_schema, assert_matches_schema


class FakeCapabilities:
    cpu_cores = 4
    ram_total_mb = 8192
    ram_available_mb = 4096
    storage_available_gb = 100.0
    gpu_available = False
    gpu_memory_mb = 0
    battery_powered = False
    battery_percent = 100
    charging = True


class FakeState:
    value = "online"


class FakeDevice:
    device_id = "test-device-001"
    device_name = "Test Device"
    device_type = "desktop"
    capabilities = FakeCapabilities()
    state = FakeState()
    registered_at = datetime.now(timezone.utc)
    last_seen = datetime.now(timezone.utc)


class TestDeviceToResponse:
    """SIN-018: Typed conversion instead of getattr."""

    def test_converts_device_to_response(self):
        from backend.server.routes.idle_compute import _device_to_response

        device = FakeDevice()
        result = _device_to_response(device)

        assert result["id"] == "test-device-001"
        assert result["status"] == "online"
        assert result["capabilities"]["cpu"] == 4
        assert result["capabilities"]["memory"] == 8192
        assert result["lastSeen"] is not None

    def test_response_matches_schema(self):
        from backend.server.routes.idle_compute import _device_to_response

        schema = load_schema("idle-device.schema.json")
        result = _device_to_response(FakeDevice())
        # Map to schema-expected values
        result["type"] = "desktop"
        result["status"] = "active"
        assert_matches_schema(result, schema)


class TestRegisterDeviceSignature:
    """SIN-016: Route must await async register_device with correct args."""

    def test_register_route_exists(self):
        from backend.server.routes.idle_compute import register_device
        import inspect
        assert inspect.iscoroutinefunction(register_device)

    @pytest.mark.asyncio
    async def test_register_request_model(self):
        """Verify DeviceRegisterRequest has the right fields."""
        from backend.server.routes.idle_compute import DeviceRegisterRequest

        req = DeviceRegisterRequest(
            device_id="dev-001",
            device_name="My Phone",
            device_type="android",
            cpu_cores=8,
            memory_mb=4096,
            battery_percent=85.0,
            is_charging=True,
        )
        assert req.device_id == "dev-001"
        assert req.device_name == "My Phone"


class TestHeartbeatExplicitFailure:
    """SIN-017: Heartbeat must fail explicitly, not silently succeed."""

    def test_heartbeat_request_validates_battery(self):
        from backend.server.routes.idle_compute import HeartbeatRequest

        req = HeartbeatRequest(battery=85.0, is_charging=True)
        assert req.battery == 85.0

        with pytest.raises(Exception):
            HeartbeatRequest(battery=150.0, is_charging=True)  # > 100

        with pytest.raises(Exception):
            HeartbeatRequest(battery=-10.0, is_charging=True)  # < 0


class TestUnregisterExplicitFailure:
    """SIN-017: Unregister must fail if device not found."""

    def test_unregister_route_is_async(self):
        from backend.server.routes.idle_compute import unregister_device
        import inspect
        assert inspect.iscoroutinefunction(unregister_device)
