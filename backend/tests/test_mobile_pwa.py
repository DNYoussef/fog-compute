"""
Tests for Mobile PWA Support
PHASE4-PWA-001 through PHASE4-PWA-004

Tests iOS monitor-only mode, Android Doze-aware heartbeat,
battery validation, and push notifications.
"""
import asyncio
import pytest
from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, MagicMock, patch

# Import mobile PWA components
from mobile_pwa import (
    # iOS
    IOSMonitorClient,
    IOSCapabilities,
    IOSLimitations,
    # Android
    AndroidHeartbeatService,
    DozeState,
    HeartbeatConfig,
    # Battery
    BatteryValidator,
    BatteryReport,
    BatteryValidationResult,
    BatteryAnomalyType,
    # Push
    PushNotificationService,
    PushMessage,
    PushPlatform,
    ServiceWorkerConfig,
)
from mobile_pwa.ios_monitor import IOSDeviceInfo
from mobile_pwa.android_heartbeat import HeartbeatResult, AlarmType
from mobile_pwa.battery_validator import DeviceBatteryHistory
from mobile_pwa.push_notifications import (
    PushPriority,
    MessageType,
    DevicePushRegistration,
)


# =============================================================================
# PHASE4-PWA-001: iOS Monitor-Only Role Tests
# =============================================================================

class TestIOSCapabilities:
    """Test iOS capability declarations."""

    def test_ios_cannot_execute_tasks(self):
        """PHASE4-PWA-001: iOS cannot execute tasks."""
        caps = IOSCapabilities()
        assert caps.can_execute_tasks is False

    def test_ios_cannot_maintain_connection(self):
        """PHASE4-PWA-001: iOS cannot maintain WebSocket."""
        caps = IOSCapabilities()
        assert caps.can_maintain_connection is False

    def test_ios_cannot_send_heartbeat(self):
        """PHASE4-PWA-001: iOS cannot send reliable heartbeat."""
        caps = IOSCapabilities()
        assert caps.can_send_heartbeat is False

    def test_ios_can_monitor_mesh(self):
        """PHASE4-PWA-001: iOS can monitor mesh status."""
        caps = IOSCapabilities()
        assert caps.can_monitor_mesh_status is True
        assert caps.can_view_device_list is True
        assert caps.can_view_task_history is True
        assert caps.can_view_metrics is True

    def test_ios_can_trigger_tasks(self):
        """PHASE4-PWA-001: iOS can submit tasks to run on other devices."""
        caps = IOSCapabilities()
        assert caps.can_trigger_tasks is True

    def test_ios_can_receive_push(self):
        """PHASE4-PWA-001: iOS can receive push notifications."""
        caps = IOSCapabilities()
        assert caps.can_receive_status_updates is True
        assert caps.can_receive_alerts is True

    def test_capabilities_to_dict(self):
        """Test capabilities serialization."""
        caps = IOSCapabilities()
        d = caps.to_dict()
        assert isinstance(d, dict)
        assert d["can_execute_tasks"] is False
        assert d["can_monitor_mesh_status"] is True


class TestIOSLimitations:
    """Test iOS limitation documentation."""

    def test_limitation_types_exist(self):
        """PHASE4-PWA-001: All limitation types documented."""
        assert IOSLimitations.NO_BACKGROUND_EXECUTION.value == "no_background_execution"
        assert IOSLimitations.NO_PERSISTENT_CONNECTIONS.value == "no_persistent_connections"
        assert IOSLimitations.LIMITED_CPU_BACKGROUND.value == "limited_cpu_background"
        assert IOSLimitations.STRICT_MEMORY_LIMITS.value == "strict_memory_limits"
        assert IOSLimitations.PUSH_REQUIRED.value == "push_required"
        assert IOSLimitations.NO_WAKELOCK.value == "no_wakelock"


class TestIOSMonitorClient:
    """Test iOS monitor client."""

    def test_init(self):
        """Test client initialization."""
        client = IOSMonitorClient(
            device_id="ios-test-123",
            coordinator_url="http://localhost:8000",
        )
        assert client.device_id == "ios-test-123"
        assert client.coordinator_url == "http://localhost:8000"
        assert client.is_registered is False

    def test_can_execute_tasks_always_false(self):
        """PHASE4-PWA-001: can_execute_tasks property always False."""
        client = IOSMonitorClient("id", "url")
        assert client.can_execute_tasks is False

    def test_get_capabilities(self):
        """Test capabilities retrieval."""
        client = IOSMonitorClient("id", "url")
        caps = client.get_capabilities()
        assert caps["can_execute_tasks"] is False
        assert caps["can_monitor_mesh_status"] is True

    def test_limitations_documentation(self):
        """Test limitations documentation is available."""
        client = IOSMonitorClient("id", "url")
        doc = client.get_limitations_documentation()
        assert "NO BACKGROUND EXECUTION" in doc
        assert "NO PERSISTENT WEBSOCKET" in doc
        assert "Monitor-only" in doc

    @pytest.mark.asyncio
    async def test_register_sends_monitor_role(self):
        """PHASE4-PWA-001: Registration specifies monitor role."""
        client = IOSMonitorClient(
            device_id="ios-123",
            coordinator_url="http://test:8000",
            push_token="apns-token-123",
        )

        device_info = IOSDeviceInfo(
            device_id="ios-123",
            device_name="Test iPhone",
            ios_version="17.0",
            model="iPhone 15",
            registered_at=datetime.now(UTC),
            last_seen=datetime.now(UTC),
        )

        with patch("aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response

            result = await client.register(device_info)

            # Verify registration payload contains role=monitor
            call_args = mock_session.return_value.__aenter__.return_value.post.call_args
            payload = call_args.kwargs["json"]
            assert payload["role"] == "monitor"
            assert payload["platform"] == "ios"


# =============================================================================
# PHASE4-PWA-002: Android Doze-Aware Heartbeat Tests
# =============================================================================

class TestDozeState:
    """Test Android Doze states."""

    def test_doze_states_exist(self):
        """PHASE4-PWA-002: All Doze states defined."""
        assert DozeState.ACTIVE.value == "active"
        assert DozeState.MAINTENANCE.value == "maintenance"
        assert DozeState.IDLE.value == "idle"
        assert DozeState.DEEP_DOZE.value == "deep_doze"
        assert DozeState.UNKNOWN.value == "unknown"


class TestHeartbeatConfig:
    """Test heartbeat configuration."""

    def test_default_intervals(self):
        """PHASE4-PWA-002: Default intervals configured."""
        config = HeartbeatConfig()
        assert config.normal_interval_sec == 30
        assert config.doze_interval_sec == 900  # 15 min minimum for Doze
        assert config.maintenance_interval_sec == 60

    def test_alarm_type_default(self):
        """PHASE4-PWA-002: setExactAndAllowWhileIdle is default."""
        config = HeartbeatConfig()
        assert config.alarm_type == AlarmType.EXACT_WHILE_IDLE

    def test_fcm_fallback_enabled(self):
        """PHASE4-PWA-002: FCM fallback enabled by default."""
        config = HeartbeatConfig()
        assert config.use_fcm_fallback is True
        assert config.fcm_high_priority is True


class TestAndroidHeartbeatService:
    """Test Android heartbeat service."""

    def test_init(self):
        """Test service initialization."""
        service = AndroidHeartbeatService(
            device_id="android-123",
            coordinator_url="http://test:8000",
        )
        assert service.device_id == "android-123"
        assert service.is_running is False
        assert service.doze_state == DozeState.UNKNOWN

    def test_update_doze_state(self):
        """PHASE4-PWA-002: Doze state updates tracked."""
        service = AndroidHeartbeatService("id", "url")

        service.update_doze_state(DozeState.ACTIVE)
        assert service.doze_state == DozeState.ACTIVE

        service.update_doze_state(DozeState.DEEP_DOZE)
        assert service.doze_state == DozeState.DEEP_DOZE

    def test_interval_for_active_state(self):
        """PHASE4-PWA-002: Active state uses normal interval."""
        service = AndroidHeartbeatService("id", "url")
        service.update_doze_state(DozeState.ACTIVE)

        interval = service._get_interval_for_state()
        assert interval == service.config.normal_interval_sec

    def test_interval_for_doze_state(self):
        """PHASE4-PWA-002: Doze state uses longer interval."""
        service = AndroidHeartbeatService("id", "url")
        service.update_doze_state(DozeState.DEEP_DOZE)

        interval = service._get_interval_for_state()
        assert interval == service.config.doze_interval_sec

    def test_interval_for_maintenance_state(self):
        """PHASE4-PWA-002: Maintenance window uses medium interval."""
        service = AndroidHeartbeatService("id", "url")
        service.update_doze_state(DozeState.MAINTENANCE)

        interval = service._get_interval_for_state()
        assert interval == service.config.maintenance_interval_sec

    def test_set_fcm_token(self):
        """PHASE4-PWA-002: FCM token can be set."""
        service = AndroidHeartbeatService("id", "url")
        service.set_fcm_token("fcm-token-123")

        stats = service.get_stats()
        assert stats["fcm_enabled"] is True

    def test_battery_optimization_guide(self):
        """PHASE4-PWA-002: Battery optimization guide available."""
        service = AndroidHeartbeatService("id", "url")
        guide = service.get_battery_optimization_guide()

        # Should include OEM-specific instructions
        assert "SAMSUNG" in guide
        assert "XIAOMI" in guide
        assert "HUAWEI" in guide
        assert "Unrestricted" in guide

    def test_stats_tracking(self):
        """Test statistics tracking."""
        service = AndroidHeartbeatService("id", "url")
        stats = service.get_stats()

        assert stats["total_heartbeats"] == 0
        assert stats["successful"] == 0
        assert stats["failed"] == 0
        assert stats["doze_heartbeats"] == 0


# =============================================================================
# PHASE4-PWA-003: Battery Sanity Checks Tests
# =============================================================================

class TestBatteryAnomalyType:
    """Test battery anomaly types."""

    def test_anomaly_types_exist(self):
        """PHASE4-PWA-003: All anomaly types defined."""
        assert BatteryAnomalyType.IMPOSSIBLE_CHARGE_RATE.value == "impossible_charge_rate"
        assert BatteryAnomalyType.IMPOSSIBLE_DISCHARGE_RATE.value == "impossible_discharge_rate"
        assert BatteryAnomalyType.SUDDEN_JUMP.value == "sudden_jump"
        assert BatteryAnomalyType.STUCK_VALUE.value == "stuck_value"
        assert BatteryAnomalyType.NEGATIVE_CHARGE.value == "negative_charge"
        assert BatteryAnomalyType.IMPOSSIBLE_STATE.value == "impossible_state"
        assert BatteryAnomalyType.TIMESTAMP_ANOMALY.value == "timestamp_anomaly"


class TestBatteryReport:
    """Test battery report structure."""

    def test_report_creation(self):
        """Test creating battery report."""
        report = BatteryReport(
            device_id="dev-123",
            battery_percent=75.0,
            is_charging=True,
            timestamp=datetime.now(UTC),
            charger_type="ac",
        )
        assert report.device_id == "dev-123"
        assert report.battery_percent == 75.0
        assert report.is_charging is True

    def test_report_to_dict(self):
        """Test report serialization."""
        report = BatteryReport(
            device_id="dev-123",
            battery_percent=50.0,
            is_charging=False,
            timestamp=datetime.now(UTC),
        )
        d = report.to_dict()
        assert d["device_id"] == "dev-123"
        assert d["battery_percent"] == 50.0
        assert d["is_charging"] is False


class TestBatteryValidator:
    """Test battery validation."""

    def test_init(self):
        """Test validator initialization."""
        validator = BatteryValidator()
        assert validator.max_charge_rate == BatteryValidator.MAX_CHARGE_RATE_PERCENT_PER_MIN
        assert validator.max_discharge_rate == BatteryValidator.MAX_DISCHARGE_RATE_PERCENT_PER_MIN

    def test_valid_report(self):
        """PHASE4-PWA-003: Valid report passes validation."""
        validator = BatteryValidator()

        report = BatteryReport(
            device_id="dev-123",
            battery_percent=50.0,
            is_charging=False,
            timestamp=datetime.now(UTC),
        )

        result = validator.validate(report)
        assert result.is_valid is True
        assert len(result.anomalies) == 0

    def test_impossible_charge_rate_detected(self):
        """PHASE4-PWA-003: Detect impossible charge rate (10% to 100% in 5 min)."""
        validator = BatteryValidator()
        now = datetime.now(UTC)

        # First report: 10%
        report1 = BatteryReport(
            device_id="dev-123",
            battery_percent=10.0,
            is_charging=True,
            timestamp=now,
        )
        validator.validate(report1)

        # Second report: 100% after 5 minutes (18%/min - impossible!)
        report2 = BatteryReport(
            device_id="dev-123",
            battery_percent=100.0,
            is_charging=True,
            timestamp=now + timedelta(minutes=5),
        )
        result = validator.validate(report2)

        assert result.is_valid is False
        assert BatteryAnomalyType.IMPOSSIBLE_CHARGE_RATE in result.anomalies

    def test_impossible_discharge_rate_detected(self):
        """PHASE4-PWA-003: Detect impossible discharge rate."""
        validator = BatteryValidator()
        now = datetime.now(UTC)

        # First report: 100%
        report1 = BatteryReport(
            device_id="dev-123",
            battery_percent=100.0,
            is_charging=False,
            timestamp=now,
        )
        validator.validate(report1)

        # Second report: 0% after 5 minutes (20%/min - impossible!)
        report2 = BatteryReport(
            device_id="dev-123",
            battery_percent=0.0,
            is_charging=False,
            timestamp=now + timedelta(minutes=5),
        )
        result = validator.validate(report2)

        assert result.is_valid is False
        assert BatteryAnomalyType.IMPOSSIBLE_DISCHARGE_RATE in result.anomalies

    def test_sudden_jump_detected(self):
        """PHASE4-PWA-003: Detect sudden battery jump."""
        validator = BatteryValidator()
        now = datetime.now(UTC)

        # First report
        report1 = BatteryReport(
            device_id="dev-123",
            battery_percent=50.0,
            is_charging=True,
            timestamp=now,
        )
        validator.validate(report1)

        # Sudden jump > 15%
        report2 = BatteryReport(
            device_id="dev-123",
            battery_percent=70.0,
            is_charging=True,
            timestamp=now + timedelta(seconds=30),
        )
        result = validator.validate(report2)

        assert result.is_valid is False
        assert BatteryAnomalyType.SUDDEN_JUMP in result.anomalies

    def test_stuck_value_detected(self):
        """PHASE4-PWA-003: Detect stuck battery value."""
        validator = BatteryValidator()
        base_time = datetime.now(UTC)

        # Report same value for 35+ minutes
        for i in range(6):
            report = BatteryReport(
                device_id="dev-123",
                battery_percent=50.0,  # Same value
                is_charging=False,
                timestamp=base_time + timedelta(minutes=i * 7),
            )
            result = validator.validate(report)

        # Last report should detect stuck value
        assert result.is_valid is False
        assert BatteryAnomalyType.STUCK_VALUE in result.anomalies

    def test_negative_charge_detected(self):
        """PHASE4-PWA-003: Detect battery going up while not charging."""
        validator = BatteryValidator()
        now = datetime.now(UTC)

        report1 = BatteryReport(
            device_id="dev-123",
            battery_percent=50.0,
            is_charging=False,
            timestamp=now,
        )
        validator.validate(report1)

        # Battery went up but not charging
        report2 = BatteryReport(
            device_id="dev-123",
            battery_percent=55.0,
            is_charging=False,
            timestamp=now + timedelta(minutes=5),
        )
        result = validator.validate(report2)

        assert result.is_valid is False
        assert BatteryAnomalyType.NEGATIVE_CHARGE in result.anomalies

    def test_impossible_state_out_of_range(self):
        """PHASE4-PWA-003: Detect impossible battery percentage."""
        validator = BatteryValidator()

        report = BatteryReport(
            device_id="dev-123",
            battery_percent=105.0,  # Impossible!
            is_charging=False,
            timestamp=datetime.now(UTC),
        )
        result = validator.validate(report)

        assert result.is_valid is False
        assert BatteryAnomalyType.IMPOSSIBLE_STATE in result.anomalies

    def test_timestamp_backwards_detected(self):
        """PHASE4-PWA-003: Detect timestamp going backwards."""
        validator = BatteryValidator()
        now = datetime.now(UTC)

        report1 = BatteryReport(
            device_id="dev-123",
            battery_percent=50.0,
            is_charging=False,
            timestamp=now,
        )
        validator.validate(report1)

        # Timestamp in the past
        report2 = BatteryReport(
            device_id="dev-123",
            battery_percent=49.0,
            is_charging=False,
            timestamp=now - timedelta(minutes=5),
        )
        result = validator.validate(report2)

        assert result.is_valid is False
        assert BatteryAnomalyType.TIMESTAMP_ANOMALY in result.anomalies

    def test_rate_limiting_after_anomalies(self):
        """PHASE4-PWA-003: Rate limit device after multiple anomalies."""
        validator = BatteryValidator()
        now = datetime.now(UTC)

        # Generate multiple anomalies
        for i in range(5):
            report = BatteryReport(
                device_id="dev-bad",
                battery_percent=float(10 + i * 20),  # Wild swings
                is_charging=True,
                timestamp=now + timedelta(seconds=i * 5),
            )
            result = validator.validate(report)

        # Should be rate limited
        assert result.should_rate_limit is True
        assert validator.is_device_rate_limited("dev-bad") is True

    def test_trust_score_decay(self):
        """PHASE4-PWA-003: Trust score decreases with anomalies."""
        validator = BatteryValidator()

        initial_trust = validator.get_device_trust_score("dev-123")
        assert initial_trust == 1.0

        now = datetime.now(UTC)
        report1 = BatteryReport(
            device_id="dev-123",
            battery_percent=10.0,
            is_charging=True,
            timestamp=now,
        )
        validator.validate(report1)

        # Create anomaly
        report2 = BatteryReport(
            device_id="dev-123",
            battery_percent=100.0,
            is_charging=True,
            timestamp=now + timedelta(minutes=1),
        )
        result = validator.validate(report2)

        assert result.trust_score < 1.0

    def test_clear_rate_limit(self):
        """Test manually clearing rate limit."""
        validator = BatteryValidator()
        now = datetime.now(UTC)

        # Generate anomalies to get rate limited
        for i in range(5):
            report = BatteryReport(
                device_id="dev-clear",
                battery_percent=float(10 + i * 20),
                is_charging=True,
                timestamp=now + timedelta(seconds=i * 5),
            )
            validator.validate(report)

        assert validator.is_device_rate_limited("dev-clear") is True

        # Clear rate limit
        validator.clear_rate_limit("dev-clear")
        assert validator.is_device_rate_limited("dev-clear") is False

    def test_validation_stats(self):
        """Test validation statistics."""
        validator = BatteryValidator()

        # Valid report
        report = BatteryReport(
            device_id="dev-stats",
            battery_percent=50.0,
            is_charging=False,
            timestamp=datetime.now(UTC),
        )
        validator.validate(report)

        stats = validator.get_stats()
        assert stats["total_reports"] == 1
        assert stats["valid_reports"] == 1
        assert stats["tracked_devices"] == 1


# =============================================================================
# PHASE4-PWA-004: Push Notification Fallback Tests
# =============================================================================

class TestPushPlatform:
    """Test push platform types."""

    def test_platforms_exist(self):
        """PHASE4-PWA-004: All platforms defined."""
        assert PushPlatform.FCM.value == "fcm"
        assert PushPlatform.APNS.value == "apns"
        assert PushPlatform.WEB_PUSH.value == "web_push"


class TestMessageType:
    """Test message types."""

    def test_message_types_exist(self):
        """PHASE4-PWA-004: All message types defined."""
        assert MessageType.HEARTBEAT_WAKE.value == "heartbeat_wake"
        assert MessageType.TASK_ASSIGNED.value == "task_assigned"
        assert MessageType.TASK_COMPLETED.value == "task_completed"
        assert MessageType.MESH_UPDATE.value == "mesh_update"
        assert MessageType.ALERT.value == "alert"


class TestPushMessage:
    """Test push message structure."""

    def test_message_creation(self):
        """Test creating push message."""
        msg = PushMessage(
            message_id="msg-123",
            message_type=MessageType.TASK_ASSIGNED,
            title="New Task",
            body="Task assigned to your device",
            priority=PushPriority.HIGH,
        )
        assert msg.message_id == "msg-123"
        assert msg.priority == PushPriority.HIGH

    def test_to_fcm_format(self):
        """PHASE4-PWA-004: FCM format for Android."""
        msg = PushMessage(
            message_id="msg-fcm",
            message_type=MessageType.HEARTBEAT_WAKE,
            title="Fogburst",
            body="Heartbeat required",
            priority=PushPriority.HIGH,
        )

        fcm = msg.to_fcm_format()
        assert "message" in fcm
        assert "notification" in fcm["message"]
        assert fcm["message"]["notification"]["title"] == "Fogburst"
        assert fcm["message"]["android"]["priority"] == "high"

    def test_to_apns_format(self):
        """PHASE4-PWA-004: APNs format for iOS."""
        msg = PushMessage(
            message_id="msg-apns",
            message_type=MessageType.ALERT,
            title="Alert",
            body="Critical alert",
        )

        apns = msg.to_apns_format()
        assert "aps" in apns
        assert apns["aps"]["alert"]["title"] == "Alert"
        assert apns["aps"]["content-available"] == 1

    def test_to_web_push_format(self):
        """PHASE4-PWA-004: Web Push format for browsers."""
        msg = PushMessage(
            message_id="msg-web",
            message_type=MessageType.MESH_UPDATE,
            title="Mesh Update",
            body="Mesh status changed",
        )

        wp = msg.to_web_push_format()
        assert "notification" in wp
        assert wp["notification"]["title"] == "Mesh Update"
        assert "icon" in wp["notification"]


class TestPushNotificationService:
    """Test push notification service."""

    def test_init(self):
        """Test service initialization."""
        service = PushNotificationService()
        stats = service.get_stats()
        assert stats["total_sent"] == 0
        assert stats["registered_devices"] == 0

    def test_register_device(self):
        """Test device registration."""
        service = PushNotificationService()

        result = service.register_device(
            device_id="dev-123",
            platform=PushPlatform.FCM,
            push_token="fcm-token-abc",
        )

        assert result is True
        assert service.is_device_registered("dev-123") is True
        assert service.get_device_platform("dev-123") == PushPlatform.FCM

    def test_unregister_device(self):
        """Test device unregistration."""
        service = PushNotificationService()

        service.register_device("dev-123", PushPlatform.FCM, "token")
        assert service.is_device_registered("dev-123") is True

        service.unregister_device("dev-123")
        assert service.is_device_registered("dev-123") is False

    def test_get_service_worker_config(self):
        """PHASE4-PWA-004: Service Worker config for PWA."""
        service = PushNotificationService(
            web_push_public_key="test-public-key",
        )

        config = service.get_service_worker_config()
        assert isinstance(config, ServiceWorkerConfig)
        assert config.push_public_key == "test-public-key"

    def test_service_worker_config_to_dict(self):
        """Test Service Worker config serialization."""
        config = ServiceWorkerConfig(
            push_public_key="vapid-key",
            sw_scope="/",
            enable_background_sync=True,
        )

        d = config.to_dict()
        assert d["pushPublicKey"] == "vapid-key"
        assert d["swScope"] == "/"
        assert d["enableBackgroundSync"] is True

    @pytest.mark.asyncio
    async def test_send_to_unregistered_device(self):
        """Test sending to unregistered device fails."""
        service = PushNotificationService()

        msg = PushMessage(
            message_id="msg-1",
            message_type=MessageType.ALERT,
            title="Test",
            body="Test body",
        )

        result = await service.send_to_device("unknown-device", msg)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_heartbeat_wake(self):
        """PHASE4-PWA-004: Send heartbeat wake notification."""
        service = PushNotificationService(fcm_server_key="test-key")
        service.register_device("dev-123", PushPlatform.FCM, "token")

        with patch.object(service, "_send_fcm", new_callable=AsyncMock) as mock_fcm:
            mock_fcm.return_value = True

            result = await service.send_heartbeat_wake("dev-123")

            assert result is True
            mock_fcm.assert_called_once()

            # Check message type
            call_args = mock_fcm.call_args
            msg = call_args[0][1]
            assert msg.message_type == MessageType.HEARTBEAT_WAKE
            assert msg.priority == PushPriority.HIGH

    @pytest.mark.asyncio
    async def test_send_task_notification(self):
        """Test sending task notification."""
        service = PushNotificationService(fcm_server_key="test-key")
        service.register_device("dev-123", PushPlatform.FCM, "token")

        with patch.object(service, "_send_fcm", new_callable=AsyncMock) as mock_fcm:
            mock_fcm.return_value = True

            result = await service.send_task_notification(
                device_id="dev-123",
                command_id="cmd-abc-123",
                task_type="compute",
                assigned=True,
            )

            assert result is True

    def test_stats_tracking(self):
        """Test stats tracking."""
        service = PushNotificationService()

        service.register_device("dev-1", PushPlatform.FCM, "t1")
        service.register_device("dev-2", PushPlatform.APNS, "t2")

        stats = service.get_stats()
        assert stats["registered_devices"] == 2


class TestDevicePushRegistration:
    """Test device push registration structure."""

    def test_registration_creation(self):
        """Test creating registration."""
        reg = DevicePushRegistration(
            device_id="dev-123",
            platform=PushPlatform.FCM,
            push_token="token-abc",
            registered_at=datetime.now(UTC),
        )
        assert reg.is_valid is True
        assert reg.error_count == 0


# =============================================================================
# Integration Tests
# =============================================================================

class TestMobilePWAIntegration:
    """Integration tests for mobile PWA components."""

    @pytest.mark.asyncio
    async def test_battery_validation_with_push_notification(self):
        """Test battery validation triggering push notification."""
        validator = BatteryValidator()
        push_service = PushNotificationService(fcm_server_key="test-key")

        push_service.register_device("dev-123", PushPlatform.FCM, "token")

        # Validate a suspicious report
        now = datetime.now(UTC)
        report1 = BatteryReport(
            device_id="dev-123",
            battery_percent=10.0,
            is_charging=True,
            timestamp=now,
        )
        validator.validate(report1)

        report2 = BatteryReport(
            device_id="dev-123",
            battery_percent=100.0,
            is_charging=True,
            timestamp=now + timedelta(minutes=1),
        )
        result = validator.validate(report2)

        # If anomaly detected, we could send alert
        if not result.is_valid:
            with patch.object(push_service, "_send_fcm", new_callable=AsyncMock) as mock:
                mock.return_value = True

                msg = PushMessage(
                    message_id="alert-1",
                    message_type=MessageType.ALERT,
                    title="Battery Anomaly",
                    body=f"Anomalies: {result.anomalies}",
                    priority=PushPriority.HIGH,
                )
                await push_service.send_to_device("dev-123", msg)
                mock.assert_called_once()

    def test_ios_capabilities_prevent_task_execution(self):
        """Test iOS device cannot be assigned tasks."""
        ios_caps = IOSCapabilities()

        # Simulated task assignment check
        can_assign = ios_caps.can_execute_tasks and ios_caps.can_maintain_connection
        assert can_assign is False

    def test_android_doze_affects_heartbeat_interval(self):
        """Test Android Doze state affects heartbeat timing."""
        service = AndroidHeartbeatService("dev-123", "http://test:8000")

        # Active - short interval
        service.update_doze_state(DozeState.ACTIVE)
        active_interval = service._get_interval_for_state()

        # Deep Doze - long interval
        service.update_doze_state(DozeState.DEEP_DOZE)
        doze_interval = service._get_interval_for_state()

        assert doze_interval > active_interval
        assert doze_interval >= 900  # At least 15 minutes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
