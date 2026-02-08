"""
Tests for Fog Bridge API - Fog Compute Mesh

Tests cover:
- Device registration and authentication
- Schemas validation
- Service functionality
"""
import pytest
from datetime import datetime, UTC, timedelta
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import schemas (these don't need full app context)
from backend.server.schemas.fog_bridge import (
    DeviceType,
    DeviceStatus,
    DeviceCapabilities,
    DeviceRegisterRequest,
    TaskType,
    TaskPriority,
    HeartbeatRequest,
    FogTaskCreate,
    WSMessageType,
)

# Import auth service directly
from backend.server.services.device_auth import DeviceAuthService


class TestDeviceAuthService:
    """Tests for the device authentication service"""

    @pytest.fixture
    def auth_service(self):
        """Create a fresh auth service for testing"""
        return DeviceAuthService(
            secret_key="test-secret-key-for-unit-tests-only-32ch",
            access_token_expire_minutes=30,
            refresh_token_expire_days=7
        )

    @pytest.mark.asyncio
    async def test_register_device(self, auth_service):
        """Test device registration creates valid credentials"""
        device_id, device_secret, access_token, refresh_token, expires_at = \
            await auth_service.register_device(
                device_name="Test Desktop",
                device_type="desktop",
                capabilities={"cpu_cores": 8, "memory_mb": 16384},
                owner_id="user-123",
                region="us-east"
            )

        assert device_id.startswith("fog-desktop-")
        assert len(device_secret) > 20
        assert len(access_token) > 50
        assert len(refresh_token) > 50
        assert expires_at > datetime.now(UTC)

    @pytest.mark.asyncio
    async def test_validate_access_token(self, auth_service):
        """Test access token validation"""
        device_id, _, access_token, _, _ = await auth_service.register_device(
            device_name="Test Device",
            device_type="laptop",
            capabilities={}
        )

        validated_device = await auth_service.validate_access_token(access_token)
        assert validated_device == device_id

    @pytest.mark.asyncio
    async def test_invalid_token_rejected(self, auth_service):
        """Test that invalid tokens are rejected"""
        result = await auth_service.validate_access_token("invalid-token")
        assert result is None

    @pytest.mark.asyncio
    async def test_refresh_token_flow(self, auth_service):
        """Test refresh token generates new access token"""
        device_id, _, _, refresh_token, _ = await auth_service.register_device(
            device_name="Test Device",
            device_type="mobile",
            capabilities={}
        )

        result = await auth_service.refresh_access_token(refresh_token)
        assert result is not None

        new_access_token, new_expires_at = result
        assert len(new_access_token) > 50
        assert new_expires_at > datetime.now(UTC)

    @pytest.mark.asyncio
    async def test_revoke_device(self, auth_service):
        """Test device revocation invalidates tokens"""
        device_id, _, access_token, _, _ = await auth_service.register_device(
            device_name="Test Device",
            device_type="server",
            capabilities={}
        )

        # Revoke device
        revoked = await auth_service.revoke_device(device_id)
        assert revoked is True

        # Token should now be invalid
        result = await auth_service.validate_access_token(access_token)
        assert result is None

    @pytest.mark.asyncio
    async def test_link_to_owner(self, auth_service):
        """Test linking device to an owner"""
        device_id, _, _, _, _ = await auth_service.register_device(
            device_name="Test Device",
            device_type="desktop",
            capabilities={}
        )

        linked = await auth_service.link_to_owner(device_id, "owner-456")
        assert linked is True

        info = await auth_service.get_device_info(device_id)
        assert info["owner_id"] == "owner-456"

    @pytest.mark.asyncio
    async def test_list_owner_devices(self, auth_service):
        """Test listing devices for an owner"""
        # Register multiple devices for same user
        await auth_service.register_device(
            device_name="Desktop",
            device_type="desktop",
            capabilities={},
            owner_id="test-user-789"
        )
        await auth_service.register_device(
            device_name="Laptop",
            device_type="laptop",
            capabilities={},
            owner_id="test-user-789"
        )
        await auth_service.register_device(
            device_name="Other User Device",
            device_type="mobile",
            capabilities={},
            owner_id="other-user"
        )

        devices = await auth_service.list_owner_devices("test-user-789")
        assert len(devices) == 2

    @pytest.mark.asyncio
    async def test_get_stats(self, auth_service):
        """Test service statistics"""
        await auth_service.register_device(
            device_name="Device 1",
            device_type="desktop",
            capabilities={}
        )
        device_id, _, _, _, _ = await auth_service.register_device(
            device_name="Device 2",
            device_type="laptop",
            capabilities={}
        )

        # Revoke one device
        await auth_service.revoke_device(device_id)

        stats = auth_service.get_stats()
        assert stats["total_devices"] == 2
        assert stats["active_devices"] == 1
        assert stats["revoked_devices"] == 1


class TestSchemas:
    """Tests for Pydantic schema validation"""

    def test_device_capabilities_defaults(self):
        """Test device capabilities have sensible defaults"""
        caps = DeviceCapabilities()

        assert caps.cpu_cores == 1
        assert caps.memory_mb == 512
        assert caps.storage_mb == 1024
        assert caps.gpu_available is False

    def test_device_capabilities_custom_values(self):
        """Test device capabilities with custom values"""
        caps = DeviceCapabilities(
            cpu_cores=16,
            memory_mb=65536,
            storage_mb=2048000,
            gpu_available=True,
            gpu_name="NVIDIA A100",
            supports_docker=True,
            python_version="3.11.5"
        )

        assert caps.cpu_cores == 16
        assert caps.memory_mb == 65536
        assert caps.gpu_name == "NVIDIA A100"
        assert caps.supports_docker is True

    def test_device_register_request_valid(self):
        """Test valid device registration request"""
        request = DeviceRegisterRequest(
            device_name="My Workstation",
            device_type=DeviceType.DESKTOP,
            capabilities=DeviceCapabilities(cpu_cores=8)
        )
        assert request.device_name == "My Workstation"
        assert request.device_type == DeviceType.DESKTOP

    def test_device_register_request_strips_whitespace(self):
        """Test device name whitespace handling"""
        request = DeviceRegisterRequest(
            device_name="  Workstation Name  ",
            device_type=DeviceType.LAPTOP,
            capabilities=DeviceCapabilities()
        )
        assert request.device_name == "Workstation Name"

    def test_device_register_request_invalid_name(self):
        """Test device registration request validation rejects bad names"""
        with pytest.raises(ValueError):
            DeviceRegisterRequest(
                device_name="Device; DROP TABLE devices;",
                device_type=DeviceType.DESKTOP,
                capabilities=DeviceCapabilities()
            )

    def test_heartbeat_request_valid(self):
        """Test valid heartbeat request"""
        hb = HeartbeatRequest(
            device_id="fog-desktop-abc123",
            cpu_usage_percent=45.5,
            memory_usage_percent=62.3,
            current_task_id="task-xyz"
        )
        assert hb.device_id == "fog-desktop-abc123"
        assert hb.cpu_usage_percent == 45.5

    def test_heartbeat_request_bounds(self):
        """Test heartbeat request percentage bounds"""
        # Valid at boundaries
        hb = HeartbeatRequest(
            device_id="test",
            cpu_usage_percent=0.0,
            memory_usage_percent=100.0
        )
        assert hb.cpu_usage_percent == 0.0
        assert hb.memory_usage_percent == 100.0

        # Invalid - over 100
        with pytest.raises(ValueError):
            HeartbeatRequest(
                device_id="test",
                cpu_usage_percent=150.0
            )

    def test_task_create_request(self):
        """Test task creation request"""
        task = FogTaskCreate(
            task_type=TaskType.COMPUTE,
            priority=TaskPriority.HIGH,
            payload={"operation": "matrix_multiply", "size": 1000},
            timeout_seconds=600
        )
        assert task.task_type == TaskType.COMPUTE
        assert task.priority == TaskPriority.HIGH
        assert task.timeout_seconds == 600

    def test_task_create_with_requirements(self):
        """Test task creation with resource requirements"""
        task = FogTaskCreate(
            task_type=TaskType.AI_INFERENCE,
            priority=TaskPriority.CRITICAL,
            payload={"model": "llama2"},
            resource_requirements=DeviceCapabilities(
                cpu_cores=8,
                memory_mb=16384,
                gpu_available=True
            )
        )
        assert task.resource_requirements is not None
        assert task.resource_requirements.gpu_available is True

    def test_device_type_enum(self):
        """Test device type enum values"""
        assert DeviceType.DESKTOP.value == "desktop"
        assert DeviceType.LAPTOP.value == "laptop"
        assert DeviceType.MOBILE.value == "mobile"
        assert DeviceType.SERVER.value == "server"
        assert DeviceType.IOT.value == "iot"
        assert DeviceType.EDGE.value == "edge"

    def test_device_status_enum(self):
        """Test device status enum values"""
        assert DeviceStatus.ONLINE.value == "online"
        assert DeviceStatus.OFFLINE.value == "offline"
        assert DeviceStatus.IDLE.value == "idle"
        assert DeviceStatus.BUSY.value == "busy"
        assert DeviceStatus.MAINTENANCE.value == "maintenance"

    def test_task_priority_enum(self):
        """Test task priority enum values"""
        assert TaskPriority.CRITICAL.value == "critical"
        assert TaskPriority.HIGH.value == "high"
        assert TaskPriority.NORMAL.value == "normal"
        assert TaskPriority.LOW.value == "low"
        assert TaskPriority.BACKGROUND.value == "background"

    def test_task_type_enum(self):
        """Test task type enum values"""
        assert TaskType.COMPUTE.value == "compute"
        assert TaskType.AI_INFERENCE.value == "ai_inference"
        assert TaskType.DATA_PROCESSING.value == "data_processing"
        assert TaskType.BUILD.value == "build"
        assert TaskType.TEST.value == "test"
        assert TaskType.SYNC.value == "sync"
        assert TaskType.PIPELINE.value == "pipeline"

    def test_ws_message_type_enum(self):
        """Test WebSocket message type enum"""
        assert WSMessageType.HEARTBEAT.value == "heartbeat"
        assert WSMessageType.TASK_ASSIGNED.value == "task_assigned"
        assert WSMessageType.SYNC_UPDATE.value == "sync_update"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
