"""
Fogburst Mobile PWA Support
Cross-platform mobile progressive web app components

PHASE4-PWA-001: iOS Monitor-Only Role
PHASE4-PWA-002: Android Doze-Aware Heartbeat
PHASE4-PWA-003: Battery Sanity Checks at Coordinator
PHASE4-PWA-004: Push Notification Fallback
"""
from .ios_monitor import (
    IOSMonitorClient,
    IOSCapabilities,
    IOSLimitations,
)
from .android_heartbeat import (
    AndroidHeartbeatService,
    DozeState,
    HeartbeatConfig,
)
from .battery_validator import (
    BatteryValidator,
    BatteryReport,
    BatteryValidationResult,
    BatteryAnomalyType,
)
from .push_notifications import (
    PushNotificationService,
    PushMessage,
    PushPlatform,
    ServiceWorkerConfig,
)

__all__ = [
    # iOS
    "IOSMonitorClient",
    "IOSCapabilities",
    "IOSLimitations",
    # Android
    "AndroidHeartbeatService",
    "DozeState",
    "HeartbeatConfig",
    # Battery
    "BatteryValidator",
    "BatteryReport",
    "BatteryValidationResult",
    "BatteryAnomalyType",
    # Push
    "PushNotificationService",
    "PushMessage",
    "PushPlatform",
    "ServiceWorkerConfig",
]

__version__ = "0.1.0"
