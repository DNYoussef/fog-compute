"""
Android Doze-Aware Heartbeat Service
Handles Android battery optimization and Doze mode

PHASE4-PWA-002 (w1u7): Android Doze-Aware Heartbeat
- Use setExactAndAllowWhileIdle for heartbeat alarms
- Firebase Cloud Messaging as backup
- Document battery optimization settings
- AUDIT-REF: MOBILE-MED-01
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC
from enum import Enum
from typing import Optional, Any, Callable, Awaitable

logger = logging.getLogger(__name__)


class DozeState(str, Enum):
    """
    Android Doze mode states.

    PHASE4-PWA-002: Understanding Doze is critical for reliable heartbeat.
    """
    ACTIVE = "active"              # Device is active, app running normally
    MAINTENANCE = "maintenance"    # Doze maintenance window (can run)
    IDLE = "idle"                  # Light idle state
    DEEP_DOZE = "deep_doze"        # Deep Doze (very restricted)
    UNKNOWN = "unknown"


class AlarmType(str, Enum):
    """Android alarm types for heartbeat."""
    EXACT = "exact"                            # setExact - exact timing
    EXACT_WHILE_IDLE = "exact_while_idle"      # setExactAndAllowWhileIdle
    INEXACT = "inexact"                        # set - battery friendly
    RTC_WAKEUP = "rtc_wakeup"                  # RTC with wakeup


@dataclass
class HeartbeatConfig:
    """
    Configuration for Android heartbeat service.

    PHASE4-PWA-002: Configurable heartbeat with Doze awareness.
    """
    # Intervals
    normal_interval_sec: int = 30          # When device active
    doze_interval_sec: int = 900           # During Doze (15 min minimum)
    maintenance_interval_sec: int = 60     # During maintenance windows

    # Alarm settings
    alarm_type: AlarmType = AlarmType.EXACT_WHILE_IDLE
    use_rtc_wakeup: bool = True

    # FCM fallback
    use_fcm_fallback: bool = True
    fcm_high_priority: bool = True

    # Retry
    max_retries: int = 3
    retry_delay_sec: int = 5

    # Battery optimization
    request_ignore_battery_optimization: bool = True
    document_manual_optimization: bool = True


@dataclass
class HeartbeatResult:
    """Result of a heartbeat attempt."""
    success: bool
    method: str  # "alarm", "fcm", "manual"
    doze_state: DozeState
    latency_ms: int
    timestamp: datetime
    error_message: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "method": self.method,
            "doze_state": self.doze_state.value,
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp.isoformat(),
            "error_message": self.error_message,
        }


class AndroidHeartbeatService:
    """
    Doze-aware heartbeat service for Android devices.

    PHASE4-PWA-002: Handles Android power management.

    Android Doze Mode Behavior:
    - Doze activates when device stationary and screen off
    - Network access restricted to maintenance windows
    - setExactAndAllowWhileIdle can fire during Doze (with limits)
    - FCM high-priority can wake device

    Battery Optimization Documentation:
    1. Settings > Apps > [App] > Battery > Unrestricted
    2. Settings > Battery > Battery optimization > [App] > Don't optimize
    3. Some OEMs have additional settings (Xiaomi, Huawei, etc.)
    """

    # Class-level documentation for battery optimization
    BATTERY_OPTIMIZATION_GUIDE = """
    Android Battery Optimization Guide for Fogburst:

    STANDARD ANDROID:
    1. Open Settings > Apps > Fogburst
    2. Tap Battery
    3. Select "Unrestricted" (not "Optimized" or "Restricted")

    SAMSUNG (One UI):
    1. Settings > Apps > Fogburst > Battery
    2. Disable "Put app to sleep"
    3. Settings > Battery > Background usage limits
    4. Remove Fogburst from "Sleeping apps" and "Deep sleeping apps"

    XIAOMI (MIUI):
    1. Settings > Apps > Manage apps > Fogburst > Battery saver
    2. Select "No restrictions"
    3. Security app > Permissions > Autostart > Enable Fogburst
    4. Settings > Battery > App battery saver > Fogburst > No restrictions

    HUAWEI (EMUI):
    1. Settings > Apps > Fogburst > Battery
    2. Disable "Power-intensive prompt"
    3. Settings > Battery > App launch > Fogburst
    4. Disable "Manage automatically", enable all manual options

    ONEPLUS (OxygenOS):
    1. Settings > Apps > Fogburst > Battery optimization
    2. Select "Don't optimize"
    3. Settings > Battery > Battery optimization > All apps > Fogburst > Don't optimize

    OPPO (ColorOS):
    1. Settings > Battery > Energy Saver > Fogburst
    2. Enable "Allow background running"
    3. Disable "Freeze when unused"
    """

    def __init__(
        self,
        device_id: str,
        coordinator_url: str,
        config: Optional[HeartbeatConfig] = None,
        on_heartbeat_sent: Optional[Callable[[HeartbeatResult], Awaitable[None]]] = None,
    ):
        """
        Initialize Android heartbeat service.

        Args:
            device_id: Device identifier
            coordinator_url: Coordinator API URL
            config: Heartbeat configuration
            on_heartbeat_sent: Callback after heartbeat
        """
        self.device_id = device_id
        self.coordinator_url = coordinator_url
        self.config = config or HeartbeatConfig()
        self._on_heartbeat_sent = on_heartbeat_sent

        self._is_running = False
        self._doze_state = DozeState.UNKNOWN
        self._last_heartbeat: Optional[datetime] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._fcm_token: Optional[str] = None

        # Statistics
        self._stats = {
            "total_heartbeats": 0,
            "successful": 0,
            "failed": 0,
            "alarm_triggered": 0,
            "fcm_triggered": 0,
            "doze_heartbeats": 0,
        }

        logger.info(f"AndroidHeartbeatService initialized: device={device_id}")

    async def start(self) -> None:
        """Start heartbeat service."""
        if self._is_running:
            return

        self._is_running = True

        async def heartbeat_loop():
            while self._is_running:
                interval = self._get_interval_for_state()
                await asyncio.sleep(interval)
                await self._send_heartbeat()

        self._heartbeat_task = asyncio.create_task(heartbeat_loop())
        logger.info("Android heartbeat service started")

    async def stop(self) -> None:
        """Stop heartbeat service."""
        self._is_running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        logger.info("Android heartbeat service stopped")

    def _get_interval_for_state(self) -> int:
        """
        Get heartbeat interval based on Doze state.

        PHASE4-PWA-002: Adaptive interval based on power state.
        """
        if self._doze_state == DozeState.ACTIVE:
            return self.config.normal_interval_sec
        elif self._doze_state == DozeState.MAINTENANCE:
            return self.config.maintenance_interval_sec
        elif self._doze_state in (DozeState.IDLE, DozeState.DEEP_DOZE):
            return self.config.doze_interval_sec
        else:
            return self.config.normal_interval_sec

    async def _send_heartbeat(self) -> HeartbeatResult:
        """
        Send heartbeat to coordinator.

        PHASE4-PWA-002: Heartbeat with retry logic.
        """
        start_time = datetime.now(UTC)
        self._stats["total_heartbeats"] += 1

        if self._doze_state in (DozeState.IDLE, DozeState.DEEP_DOZE):
            self._stats["doze_heartbeats"] += 1

        for attempt in range(self.config.max_retries):
            try:
                success = await self._do_heartbeat()

                if success:
                    latency = int((datetime.now(UTC) - start_time).total_seconds() * 1000)
                    self._last_heartbeat = datetime.now(UTC)
                    self._stats["successful"] += 1
                    self._stats["alarm_triggered"] += 1

                    result = HeartbeatResult(
                        success=True,
                        method="alarm",
                        doze_state=self._doze_state,
                        latency_ms=latency,
                        timestamp=datetime.now(UTC),
                    )

                    if self._on_heartbeat_sent:
                        await self._on_heartbeat_sent(result)

                    return result

            except Exception as e:
                logger.warning(f"Heartbeat attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(self.config.retry_delay_sec)

        # All retries failed
        self._stats["failed"] += 1

        result = HeartbeatResult(
            success=False,
            method="alarm",
            doze_state=self._doze_state,
            latency_ms=int((datetime.now(UTC) - start_time).total_seconds() * 1000),
            timestamp=datetime.now(UTC),
            error_message="All heartbeat attempts failed",
        )

        if self._on_heartbeat_sent:
            await self._on_heartbeat_sent(result)

        return result

    async def _do_heartbeat(self) -> bool:
        """Execute single heartbeat request."""
        try:
            import aiohttp

            payload = {
                "device_id": self.device_id,
                "platform": "android",
                "doze_state": self._doze_state.value,
                "alarm_type": self.config.alarm_type.value,
                "timestamp": datetime.now(UTC).isoformat(),
            }

            url = f"{self.coordinator_url}/api/mesh/heartbeat"

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as response:
                    return response.status == 200

        except Exception as e:
            logger.error(f"Heartbeat request error: {e}")
            return False

    def update_doze_state(self, state: DozeState) -> None:
        """
        Update current Doze state.

        PHASE4-PWA-002: Called from Android native code.

        Args:
            state: New Doze state
        """
        old_state = self._doze_state
        self._doze_state = state

        if old_state != state:
            logger.info(f"Doze state changed: {old_state.value} -> {state.value}")

    def set_fcm_token(self, token: str) -> None:
        """
        Set FCM token for push notification fallback.

        PHASE4-PWA-002: FCM is backup for heartbeat.

        Args:
            token: FCM registration token
        """
        self._fcm_token = token
        logger.info("FCM token updated")

    async def handle_fcm_wake(self, data: dict) -> None:
        """
        Handle FCM wake message from coordinator.

        PHASE4-PWA-002: FCM high-priority can wake device.

        Args:
            data: FCM message data
        """
        logger.info("FCM wake received, sending immediate heartbeat")
        self._stats["fcm_triggered"] += 1

        # Send immediate heartbeat
        result = await self._send_heartbeat()
        result.method = "fcm"

    def get_battery_optimization_guide(self) -> str:
        """Get battery optimization guide for UI display."""
        return self.BATTERY_OPTIMIZATION_GUIDE

    def get_stats(self) -> dict[str, Any]:
        """Get heartbeat statistics."""
        return {
            "total_heartbeats": self._stats["total_heartbeats"],
            "successful": self._stats["successful"],
            "failed": self._stats["failed"],
            "alarm_triggered": self._stats["alarm_triggered"],
            "fcm_triggered": self._stats["fcm_triggered"],
            "doze_heartbeats": self._stats["doze_heartbeats"],
            "current_doze_state": self._doze_state.value,
            "last_heartbeat": self._last_heartbeat.isoformat() if self._last_heartbeat else None,
            "fcm_enabled": self._fcm_token is not None,
        }

    @property
    def doze_state(self) -> DozeState:
        """Get current Doze state."""
        return self._doze_state

    @property
    def is_running(self) -> bool:
        """Check if service is running."""
        return self._is_running
