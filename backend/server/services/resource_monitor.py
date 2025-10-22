"""
Resource Monitor - Real-time resource metrics and alerting

Features:
- Real-time resource metrics (CPU, memory, disk, network)
- Threshold-based alerting
- Resource usage trending
- Capacity planning recommendations
- Auto-scaling triggers
"""

import asyncio
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional

import psutil

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ResourceType(Enum):
    """Resource types to monitor"""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"


@dataclass
class ResourceMetrics:
    """Snapshot of resource metrics"""
    timestamp: datetime = field(default_factory=datetime.now)

    # CPU metrics
    cpu_percent: float = 0.0
    cpu_count: int = 0
    cpu_freq_current: float = 0.0

    # Memory metrics
    memory_total_mb: float = 0.0
    memory_available_mb: float = 0.0
    memory_used_mb: float = 0.0
    memory_percent: float = 0.0

    # Disk metrics
    disk_total_gb: float = 0.0
    disk_used_gb: float = 0.0
    disk_free_gb: float = 0.0
    disk_percent: float = 0.0
    disk_read_mbps: float = 0.0
    disk_write_mbps: float = 0.0

    # Network metrics
    network_sent_mbps: float = 0.0
    network_recv_mbps: float = 0.0
    network_connections: int = 0

    @classmethod
    def capture(cls) -> 'ResourceMetrics':
        """Capture current resource metrics"""
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()

        # Memory
        mem = psutil.virtual_memory()

        # Disk
        disk = psutil.disk_usage('/')
        disk_io = psutil.disk_io_counters()

        # Network
        net_io = psutil.net_io_counters()
        net_connections = len(psutil.net_connections())

        return cls(
            cpu_percent=cpu_percent,
            cpu_count=cpu_count or 0,
            cpu_freq_current=cpu_freq.current if cpu_freq else 0.0,
            memory_total_mb=mem.total / (1024 * 1024),
            memory_available_mb=mem.available / (1024 * 1024),
            memory_used_mb=mem.used / (1024 * 1024),
            memory_percent=mem.percent,
            disk_total_gb=disk.total / (1024 * 1024 * 1024),
            disk_used_gb=disk.used / (1024 * 1024 * 1024),
            disk_free_gb=disk.free / (1024 * 1024 * 1024),
            disk_percent=disk.percent,
            disk_read_mbps=0.0,  # Calculated by monitor
            disk_write_mbps=0.0,  # Calculated by monitor
            network_sent_mbps=0.0,  # Calculated by monitor
            network_recv_mbps=0.0,  # Calculated by monitor
            network_connections=net_connections,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "cpu": {
                "percent": round(self.cpu_percent, 2),
                "count": self.cpu_count,
                "freq_mhz": round(self.cpu_freq_current, 2),
            },
            "memory": {
                "total_mb": round(self.memory_total_mb, 2),
                "available_mb": round(self.memory_available_mb, 2),
                "used_mb": round(self.memory_used_mb, 2),
                "percent": round(self.memory_percent, 2),
            },
            "disk": {
                "total_gb": round(self.disk_total_gb, 2),
                "used_gb": round(self.disk_used_gb, 2),
                "free_gb": round(self.disk_free_gb, 2),
                "percent": round(self.disk_percent, 2),
                "read_mbps": round(self.disk_read_mbps, 2),
                "write_mbps": round(self.disk_write_mbps, 2),
            },
            "network": {
                "sent_mbps": round(self.network_sent_mbps, 2),
                "recv_mbps": round(self.network_recv_mbps, 2),
                "connections": self.network_connections,
            },
        }


@dataclass
class Alert:
    """Resource alert"""
    level: AlertLevel
    resource_type: ResourceType
    message: str
    value: float
    threshold: float
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "level": self.level.value,
            "resource_type": self.resource_type.value,
            "message": self.message,
            "value": round(self.value, 2),
            "threshold": round(self.threshold, 2),
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class Threshold:
    """Resource threshold configuration"""
    resource_type: ResourceType
    warning_level: float  # Percentage
    critical_level: float  # Percentage
    enabled: bool = True


class ResourceTrend:
    """Track resource usage trends for capacity planning"""

    def __init__(self, window_size: int = 60):
        self.window_size = window_size  # Number of samples
        self._cpu_history: Deque[float] = deque(maxlen=window_size)
        self._memory_history: Deque[float] = deque(maxlen=window_size)
        self._disk_history: Deque[float] = deque(maxlen=window_size)

    def record(self, metrics: ResourceMetrics) -> None:
        """Record metrics for trend analysis"""
        self._cpu_history.append(metrics.cpu_percent)
        self._memory_history.append(metrics.memory_percent)
        self._disk_history.append(metrics.disk_percent)

    def _calculate_trend(self, history: Deque[float]) -> str:
        """Calculate trend direction"""
        if len(history) < 10:
            return "insufficient_data"

        # Simple linear regression
        recent = list(history)[-10:]
        older = list(history)[-20:-10] if len(history) >= 20 else list(history)[:-10]

        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older) if older else recent_avg

        diff = recent_avg - older_avg

        if diff > 5:
            return "increasing"
        elif diff < -5:
            return "decreasing"
        else:
            return "stable"

    def get_trends(self) -> Dict[str, Any]:
        """Get current trends"""
        return {
            "cpu": {
                "trend": self._calculate_trend(self._cpu_history),
                "current_avg": round(sum(self._cpu_history) / len(self._cpu_history), 2) if self._cpu_history else 0,
                "samples": len(self._cpu_history),
            },
            "memory": {
                "trend": self._calculate_trend(self._memory_history),
                "current_avg": round(sum(self._memory_history) / len(self._memory_history), 2) if self._memory_history else 0,
                "samples": len(self._memory_history),
            },
            "disk": {
                "trend": self._calculate_trend(self._disk_history),
                "current_avg": round(sum(self._disk_history) / len(self._disk_history), 2) if self._disk_history else 0,
                "samples": len(self._disk_history),
            },
        }

    def get_capacity_recommendations(self) -> List[str]:
        """Get capacity planning recommendations"""
        recommendations = []

        trends = self.get_trends()

        for resource, data in trends.items():
            if data["trend"] == "increasing":
                if data["current_avg"] > 70:
                    recommendations.append(
                        f"{resource.upper()} usage is increasing and currently at {data['current_avg']:.1f}%. "
                        f"Consider adding more {resource} capacity."
                    )
                elif data["current_avg"] > 50:
                    recommendations.append(
                        f"{resource.upper()} usage trending upward ({data['current_avg']:.1f}%). "
                        f"Monitor for potential capacity needs."
                    )

        if not recommendations:
            recommendations.append("No immediate capacity concerns detected.")

        return recommendations


class ResourceMonitor:
    """
    Real-time resource monitoring with alerting

    Tracks CPU, memory, disk, and network usage with configurable thresholds
    """

    def __init__(self, interval: float = 5.0):
        self.interval = interval
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None

        # Metrics storage
        self._current_metrics: Optional[ResourceMetrics] = None
        self._metrics_history: Deque[ResourceMetrics] = deque(maxlen=1000)

        # Alerts
        self._alerts: Deque[Alert] = deque(maxlen=100)
        self._alert_callbacks: List[Callable[[Alert], None]] = []

        # Thresholds
        self._thresholds = {
            ResourceType.CPU: Threshold(ResourceType.CPU, 80.0, 95.0),
            ResourceType.MEMORY: Threshold(ResourceType.MEMORY, 85.0, 95.0),
            ResourceType.DISK: Threshold(ResourceType.DISK, 85.0, 95.0),
            ResourceType.NETWORK: Threshold(ResourceType.NETWORK, 80.0, 95.0),
        }

        # Trending
        self._trend_tracker = ResourceTrend()

        # Previous I/O counters for rate calculation
        self._prev_disk_io: Optional[Any] = None
        self._prev_net_io: Optional[Any] = None
        self._prev_io_time: Optional[float] = None

        logger.info(f"ResourceMonitor initialized (interval={interval}s)")

    def set_threshold(
        self,
        resource_type: ResourceType,
        warning_level: float,
        critical_level: float,
    ) -> None:
        """Set threshold for a resource type"""
        self._thresholds[resource_type] = Threshold(
            resource_type, warning_level, critical_level
        )
        logger.info(
            f"Set threshold for {resource_type.value}: "
            f"warning={warning_level}%, critical={critical_level}%"
        )

    def register_alert_callback(self, callback: Callable[[Alert], None]) -> None:
        """Register callback for alerts"""
        self._alert_callbacks.append(callback)

    def _trigger_alert(self, alert: Alert) -> None:
        """Trigger an alert"""
        self._alerts.append(alert)
        logger.log(
            logging.CRITICAL if alert.level == AlertLevel.CRITICAL else logging.WARNING,
            f"ALERT [{alert.level.value.upper()}] {alert.resource_type.value}: {alert.message}",
        )

        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")

    def _check_thresholds(self, metrics: ResourceMetrics) -> None:
        """Check if any thresholds are exceeded"""
        checks = [
            (ResourceType.CPU, metrics.cpu_percent),
            (ResourceType.MEMORY, metrics.memory_percent),
            (ResourceType.DISK, metrics.disk_percent),
        ]

        for resource_type, value in checks:
            threshold = self._thresholds.get(resource_type)
            if not threshold or not threshold.enabled:
                continue

            if value >= threshold.critical_level:
                self._trigger_alert(Alert(
                    level=AlertLevel.CRITICAL,
                    resource_type=resource_type,
                    message=f"{resource_type.value.upper()} usage critical: {value:.1f}%",
                    value=value,
                    threshold=threshold.critical_level,
                ))
            elif value >= threshold.warning_level:
                self._trigger_alert(Alert(
                    level=AlertLevel.WARNING,
                    resource_type=resource_type,
                    message=f"{resource_type.value.upper()} usage high: {value:.1f}%",
                    value=value,
                    threshold=threshold.warning_level,
                ))

    def _calculate_io_rates(self, metrics: ResourceMetrics) -> None:
        """Calculate I/O rates from counters"""
        try:
            current_time = time.time()
            disk_io = psutil.disk_io_counters()
            net_io = psutil.net_io_counters()

            if self._prev_disk_io and self._prev_net_io and self._prev_io_time:
                time_delta = current_time - self._prev_io_time

                if time_delta > 0:
                    # Disk rates
                    disk_read_bytes = disk_io.read_bytes - self._prev_disk_io.read_bytes
                    disk_write_bytes = disk_io.write_bytes - self._prev_disk_io.write_bytes
                    metrics.disk_read_mbps = (disk_read_bytes / time_delta) / (1024 * 1024)
                    metrics.disk_write_mbps = (disk_write_bytes / time_delta) / (1024 * 1024)

                    # Network rates
                    net_sent_bytes = net_io.bytes_sent - self._prev_net_io.bytes_sent
                    net_recv_bytes = net_io.bytes_recv - self._prev_net_io.bytes_recv
                    metrics.network_sent_mbps = (net_sent_bytes / time_delta) / (1024 * 1024)
                    metrics.network_recv_mbps = (net_recv_bytes / time_delta) / (1024 * 1024)

            # Update previous counters
            self._prev_disk_io = disk_io
            self._prev_net_io = net_io
            self._prev_io_time = current_time

        except Exception as e:
            logger.error(f"Error calculating I/O rates: {e}")

    def _monitor_loop(self) -> None:
        """Main monitoring loop"""
        while self._monitoring:
            try:
                # Capture metrics
                metrics = ResourceMetrics.capture()

                # Calculate I/O rates
                self._calculate_io_rates(metrics)

                # Store metrics
                self._current_metrics = metrics
                self._metrics_history.append(metrics)

                # Record for trending
                self._trend_tracker.record(metrics)

                # Check thresholds
                self._check_thresholds(metrics)

            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")

            time.sleep(self.interval)

    def start(self) -> None:
        """Start monitoring"""
        if self._monitoring:
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Resource monitoring started")

    def stop(self) -> None:
        """Stop monitoring"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=self.interval + 1.0)
            self._monitor_thread = None
        logger.info("Resource monitoring stopped")

    def get_current_metrics(self) -> Optional[Dict[str, Any]]:
        """Get current metrics"""
        if self._current_metrics:
            return self._current_metrics.to_dict()
        return None

    def get_metrics_history(self, seconds: int = 60) -> List[Dict[str, Any]]:
        """Get metrics history for the last N seconds"""
        cutoff = datetime.now() - timedelta(seconds=seconds)
        return [
            m.to_dict()
            for m in self._metrics_history
            if m.timestamp >= cutoff
        ]

    def get_recent_alerts(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get recent alerts"""
        return [alert.to_dict() for alert in list(self._alerts)[-count:]]

    def get_trends(self) -> Dict[str, Any]:
        """Get resource usage trends"""
        return self._trend_tracker.get_trends()

    def get_capacity_recommendations(self) -> List[str]:
        """Get capacity planning recommendations"""
        return self._trend_tracker.get_capacity_recommendations()

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive monitoring stats"""
        current = self.get_current_metrics()

        return {
            "monitoring": self._monitoring,
            "interval_seconds": self.interval,
            "current_metrics": current,
            "metrics_history_size": len(self._metrics_history),
            "total_alerts": len(self._alerts),
            "recent_alerts": self.get_recent_alerts(5),
            "trends": self.get_trends(),
            "recommendations": self.get_capacity_recommendations(),
            "thresholds": {
                rt.value: {
                    "warning": t.warning_level,
                    "critical": t.critical_level,
                    "enabled": t.enabled,
                }
                for rt, t in self._thresholds.items()
            },
        }


# Singleton instance
_monitor = ResourceMonitor()


def get_resource_monitor() -> ResourceMonitor:
    """Get the singleton ResourceMonitor instance"""
    return _monitor
