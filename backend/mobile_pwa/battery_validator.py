"""
Battery Sanity Checks at Coordinator
Validates battery reports from mobile devices

PHASE4-PWA-003 (j3f8): Battery Sanity Checks at Coordinator
- Coordinator validates device battery reports
- Detect impossible transitions (10% to 100% in 5 min)
- Rate-limit tasks per device regardless of claimed capacity
- AUDIT-REF: MOBILE-HIGH-02
"""
import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC
from enum import Enum
from typing import Optional, Any

logger = logging.getLogger(__name__)


class BatteryAnomalyType(str, Enum):
    """
    Types of battery anomalies that can be detected.

    PHASE4-PWA-003: Categories of suspicious battery behavior.
    """
    IMPOSSIBLE_CHARGE_RATE = "impossible_charge_rate"      # Charged too fast
    IMPOSSIBLE_DISCHARGE_RATE = "impossible_discharge_rate"  # Discharged too fast
    SUDDEN_JUMP = "sudden_jump"                            # Large sudden change
    STUCK_VALUE = "stuck_value"                            # Same value too long
    NEGATIVE_CHARGE = "negative_charge"                    # Battery went up while discharging
    IMPOSSIBLE_STATE = "impossible_state"                  # Physically impossible
    TIMESTAMP_ANOMALY = "timestamp_anomaly"                # Time went backwards


@dataclass
class BatteryReport:
    """
    Battery status report from a device.

    PHASE4-PWA-003: Structure for battery reports.
    """
    device_id: str
    battery_percent: float
    is_charging: bool
    timestamp: datetime
    charger_type: Optional[str] = None  # "ac", "usb", "wireless", None
    temperature_celsius: Optional[float] = None
    voltage_mv: Optional[int] = None
    health: Optional[str] = None  # "good", "overheat", "dead", etc.

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "device_id": self.device_id,
            "battery_percent": self.battery_percent,
            "is_charging": self.is_charging,
            "timestamp": self.timestamp.isoformat(),
            "charger_type": self.charger_type,
            "temperature_celsius": self.temperature_celsius,
            "voltage_mv": self.voltage_mv,
            "health": self.health,
        }


@dataclass
class BatteryValidationResult:
    """
    Result of battery report validation.

    PHASE4-PWA-003: Validation result with anomaly details.
    """
    is_valid: bool
    anomalies: list[BatteryAnomalyType] = field(default_factory=list)
    message: str = ""
    should_rate_limit: bool = False
    rate_limit_reason: Optional[str] = None
    trust_score: float = 1.0  # 0.0 to 1.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_valid": self.is_valid,
            "anomalies": [a.value for a in self.anomalies],
            "message": self.message,
            "should_rate_limit": self.should_rate_limit,
            "rate_limit_reason": self.rate_limit_reason,
            "trust_score": round(self.trust_score, 2),
        }


@dataclass
class DeviceBatteryHistory:
    """
    Battery history for a device.

    PHASE4-PWA-003: Tracks recent battery reports for validation.
    """
    device_id: str
    reports: list[BatteryReport] = field(default_factory=list)
    anomaly_count: int = 0
    last_anomaly: Optional[datetime] = None
    trust_score: float = 1.0
    rate_limited_until: Optional[datetime] = None

    def add_report(self, report: BatteryReport, max_history: int = 20) -> None:
        """Add report to history, maintaining max size."""
        self.reports.append(report)
        if len(self.reports) > max_history:
            self.reports.pop(0)

    def get_last_report(self) -> Optional[BatteryReport]:
        """Get most recent report."""
        return self.reports[-1] if self.reports else None


class BatteryValidator:
    """
    Validates battery reports from mobile devices.

    PHASE4-PWA-003: Coordinator-side battery validation.

    Detects:
    - Impossible charge rates (physics-based limits)
    - Suspicious sudden changes
    - Stuck/fake values
    - Timestamp manipulation
    """

    # Physical limits for battery charging/discharging
    MAX_CHARGE_RATE_PERCENT_PER_MIN = 3.0   # ~33 min 0-100% (fast charge)
    MAX_DISCHARGE_RATE_PERCENT_PER_MIN = 5.0  # ~20 min full discharge (extreme usage)
    MAX_SUDDEN_CHANGE_PERCENT = 15.0        # Max jump between reports
    MIN_CHANGE_INTERVAL_SEC = 10            # Minimum time between reports

    # Rate limiting thresholds
    ANOMALY_RATE_LIMIT_THRESHOLD = 3        # Anomalies before rate limiting
    RATE_LIMIT_DURATION_SEC = 3600          # 1 hour rate limit
    TRUST_SCORE_DECAY = 0.1                 # Trust decay per anomaly
    TRUST_SCORE_RECOVERY = 0.02             # Trust recovery per valid report

    def __init__(
        self,
        max_charge_rate: float = MAX_CHARGE_RATE_PERCENT_PER_MIN,
        max_discharge_rate: float = MAX_DISCHARGE_RATE_PERCENT_PER_MIN,
        max_history_per_device: int = 20,
        max_devices: int = 1000,
    ):
        """
        Initialize battery validator.

        Args:
            max_charge_rate: Maximum charge rate (percent/min)
            max_discharge_rate: Maximum discharge rate (percent/min)
            max_history_per_device: Max reports to keep per device
            max_devices: Max devices to track
        """
        self.max_charge_rate = max_charge_rate
        self.max_discharge_rate = max_discharge_rate
        self.max_history_per_device = max_history_per_device
        self.max_devices = max_devices

        self._device_history: OrderedDict[str, DeviceBatteryHistory] = OrderedDict()

        # Statistics
        self._stats = {
            "total_reports": 0,
            "valid_reports": 0,
            "anomalies_detected": 0,
            "devices_rate_limited": 0,
        }

        logger.info(
            f"BatteryValidator initialized: "
            f"max_charge={max_charge_rate}%/min, "
            f"max_discharge={max_discharge_rate}%/min"
        )

    def validate(self, report: BatteryReport) -> BatteryValidationResult:
        """
        Validate a battery report.

        PHASE4-PWA-003: Main validation entry point.

        Args:
            report: Battery report to validate

        Returns:
            Validation result
        """
        self._stats["total_reports"] += 1

        # Get or create device history
        history = self._get_or_create_history(report.device_id)

        # Check if device is rate limited
        if history.rate_limited_until and datetime.now(UTC) < history.rate_limited_until:
            return BatteryValidationResult(
                is_valid=False,
                should_rate_limit=True,
                rate_limit_reason="Device is currently rate limited",
                trust_score=history.trust_score,
                message="Device rate limited due to previous anomalies",
            )

        # Run validation checks
        anomalies = []
        last_report = history.get_last_report()

        if last_report:
            anomalies.extend(self._check_rate_anomalies(last_report, report))
            anomalies.extend(self._check_timestamp_anomalies(last_report, report))
            anomalies.extend(self._check_state_anomalies(last_report, report))
        else:
            # Check basic state validity on first report too
            anomalies.extend(self._check_basic_state(report))

        # Check for stuck values
        anomalies.extend(self._check_stuck_values(history, report))

        # Update history
        history.add_report(report, self.max_history_per_device)

        # Process anomalies
        if anomalies:
            return self._handle_anomalies(history, anomalies)

        # Valid report - recover trust
        history.trust_score = min(1.0, history.trust_score + self.TRUST_SCORE_RECOVERY)
        self._stats["valid_reports"] += 1

        return BatteryValidationResult(
            is_valid=True,
            trust_score=history.trust_score,
            message="Battery report validated",
        )

    def _get_or_create_history(self, device_id: str) -> DeviceBatteryHistory:
        """Get or create device battery history."""
        if device_id not in self._device_history:
            # Enforce max devices
            while len(self._device_history) >= self.max_devices:
                self._device_history.popitem(last=False)

            self._device_history[device_id] = DeviceBatteryHistory(device_id=device_id)

        # Move to end for LRU behavior
        self._device_history.move_to_end(device_id)

        return self._device_history[device_id]

    def _check_rate_anomalies(
        self,
        last: BatteryReport,
        current: BatteryReport
    ) -> list[BatteryAnomalyType]:
        """
        Check for impossible charge/discharge rates.

        PHASE4-PWA-003: Physics-based rate validation.
        """
        anomalies = []

        time_diff_min = (current.timestamp - last.timestamp).total_seconds() / 60
        if time_diff_min <= 0:
            return anomalies

        percent_change = current.battery_percent - last.battery_percent

        if percent_change > 0:
            # Charging
            rate = percent_change / time_diff_min

            # Allow higher rate if charging
            max_rate = self.max_charge_rate if current.is_charging else self.max_charge_rate / 2

            if rate > max_rate:
                logger.warning(
                    f"Impossible charge rate: {rate:.1f}%/min "
                    f"(max: {max_rate}%/min, device: {current.device_id})"
                )
                anomalies.append(BatteryAnomalyType.IMPOSSIBLE_CHARGE_RATE)

            # Battery went up while not charging
            if not current.is_charging and percent_change > 1:
                anomalies.append(BatteryAnomalyType.NEGATIVE_CHARGE)

        elif percent_change < 0:
            # Discharging
            rate = abs(percent_change) / time_diff_min

            if rate > self.max_discharge_rate:
                logger.warning(
                    f"Impossible discharge rate: {rate:.1f}%/min "
                    f"(max: {self.max_discharge_rate}%/min, device: {current.device_id})"
                )
                anomalies.append(BatteryAnomalyType.IMPOSSIBLE_DISCHARGE_RATE)

        # Check for sudden jump
        if abs(percent_change) > self.MAX_SUDDEN_CHANGE_PERCENT:
            anomalies.append(BatteryAnomalyType.SUDDEN_JUMP)

        return anomalies

    def _check_timestamp_anomalies(
        self,
        last: BatteryReport,
        current: BatteryReport
    ) -> list[BatteryAnomalyType]:
        """Check for timestamp manipulation."""
        anomalies = []

        time_diff = (current.timestamp - last.timestamp).total_seconds()

        # Time went backwards
        if time_diff < 0:
            logger.warning(f"Timestamp went backwards: device={current.device_id}")
            anomalies.append(BatteryAnomalyType.TIMESTAMP_ANOMALY)

        # Reports too close together
        if 0 < time_diff < self.MIN_CHANGE_INTERVAL_SEC:
            # Only flag if battery changed significantly
            percent_change = abs(current.battery_percent - last.battery_percent)
            if percent_change > 2:
                anomalies.append(BatteryAnomalyType.TIMESTAMP_ANOMALY)

        return anomalies

    def _check_basic_state(self, report: BatteryReport) -> list[BatteryAnomalyType]:
        """Check basic battery state validity (no previous report needed)."""
        anomalies = []

        # Battery percentage out of range
        if not 0 <= report.battery_percent <= 100:
            anomalies.append(BatteryAnomalyType.IMPOSSIBLE_STATE)

        # Temperature out of reasonable range (-20 to 60 C)
        if report.temperature_celsius is not None:
            if not -20 <= report.temperature_celsius <= 60:
                anomalies.append(BatteryAnomalyType.IMPOSSIBLE_STATE)

        return anomalies

    def _check_state_anomalies(
        self,
        last: BatteryReport,
        current: BatteryReport
    ) -> list[BatteryAnomalyType]:
        """Check for impossible battery states (with comparison to previous)."""
        # Use basic state check for the current report
        return self._check_basic_state(current)

    def _check_stuck_values(
        self,
        history: DeviceBatteryHistory,
        current: BatteryReport
    ) -> list[BatteryAnomalyType]:
        """
        Check for stuck/fake values.

        PHASE4-PWA-003: Detect devices reporting fake constant values.
        """
        anomalies = []

        if len(history.reports) < 5:
            return anomalies

        # Check if last 5 reports have identical values
        recent = history.reports[-5:]
        if all(r.battery_percent == current.battery_percent for r in recent):
            # Check time span
            time_span = (current.timestamp - recent[0].timestamp).total_seconds()

            # 30+ minutes with same value is suspicious
            if time_span > 1800:
                logger.warning(
                    f"Stuck battery value detected: "
                    f"{current.battery_percent}% for {time_span/60:.0f} min, "
                    f"device={current.device_id}"
                )
                anomalies.append(BatteryAnomalyType.STUCK_VALUE)

        return anomalies

    def _handle_anomalies(
        self,
        history: DeviceBatteryHistory,
        anomalies: list[BatteryAnomalyType]
    ) -> BatteryValidationResult:
        """
        Handle detected anomalies.

        PHASE4-PWA-003: Rate limiting and trust scoring.
        """
        self._stats["anomalies_detected"] += len(anomalies)

        history.anomaly_count += len(anomalies)
        history.last_anomaly = datetime.now(UTC)
        history.trust_score = max(0.0, history.trust_score - self.TRUST_SCORE_DECAY * len(anomalies))

        result = BatteryValidationResult(
            is_valid=False,
            anomalies=anomalies,
            trust_score=history.trust_score,
        )

        # Check if rate limiting is needed
        if history.anomaly_count >= self.ANOMALY_RATE_LIMIT_THRESHOLD:
            history.rate_limited_until = datetime.now(UTC) + timedelta(seconds=self.RATE_LIMIT_DURATION_SEC)
            result.should_rate_limit = True
            result.rate_limit_reason = f"Too many anomalies ({history.anomaly_count})"
            self._stats["devices_rate_limited"] += 1

            logger.warning(
                f"Device rate limited: {history.device_id}, "
                f"anomaly_count={history.anomaly_count}, "
                f"until={history.rate_limited_until}"
            )

        result.message = f"Battery anomalies detected: {[a.value for a in anomalies]}"

        return result

    def get_device_trust_score(self, device_id: str) -> float:
        """Get trust score for a device."""
        history = self._device_history.get(device_id)
        return history.trust_score if history else 1.0

    def is_device_rate_limited(self, device_id: str) -> bool:
        """Check if device is rate limited."""
        history = self._device_history.get(device_id)
        if not history or not history.rate_limited_until:
            return False
        return datetime.now(UTC) < history.rate_limited_until

    def clear_rate_limit(self, device_id: str) -> bool:
        """Manually clear rate limit for a device."""
        history = self._device_history.get(device_id)
        if history:
            history.rate_limited_until = None
            history.anomaly_count = 0
            return True
        return False

    def get_stats(self) -> dict[str, Any]:
        """Get validator statistics."""
        return {
            "total_reports": self._stats["total_reports"],
            "valid_reports": self._stats["valid_reports"],
            "anomalies_detected": self._stats["anomalies_detected"],
            "devices_rate_limited": self._stats["devices_rate_limited"],
            "tracked_devices": len(self._device_history),
            "max_charge_rate_per_min": self.max_charge_rate,
            "max_discharge_rate_per_min": self.max_discharge_rate,
        }
