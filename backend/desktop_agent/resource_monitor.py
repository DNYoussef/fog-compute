"""
Resource Monitor for Desktop Agent
Monitors CPU/RAM usage and enforces resource limits

PHASE3-AGENT-004: Resource Limits Enforcement
- Agent monitors CPU/RAM usage
- Only accept tasks when below threshold (configurable)
- Report metrics in heartbeat
- Pause accepting if overloaded
"""
import asyncio
import logging
import platform
import psutil
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Optional, Any, Callable, Awaitable

logger = logging.getLogger(__name__)


class ResourceStatus(str, Enum):
    """Resource availability status"""
    AVAILABLE = "available"      # Can accept tasks
    LIMITED = "limited"          # Near threshold, limited acceptance
    OVERLOADED = "overloaded"    # Above threshold, rejecting tasks
    PAUSED = "paused"            # Manually paused
    UNKNOWN = "unknown"          # Cannot determine status


@dataclass
class ResourceThresholds:
    """
    Resource threshold configuration.

    PHASE3-AGENT-004: Configurable thresholds.
    """
    # CPU thresholds (percent)
    cpu_available: float = 50.0    # Below this = available
    cpu_limited: float = 70.0      # Below this = limited
    cpu_overloaded: float = 90.0   # Above this = overloaded

    # Memory thresholds (percent)
    memory_available: float = 50.0
    memory_limited: float = 70.0
    memory_overloaded: float = 85.0

    # Disk thresholds (percent)
    disk_available: float = 50.0
    disk_limited: float = 80.0
    disk_overloaded: float = 95.0

    # Sampling
    sample_interval_sec: float = 5.0
    sample_window_count: int = 6  # Use average of last N samples

    # Hysteresis to prevent flapping
    hysteresis_samples: int = 3  # Must stay in state for N samples


@dataclass
class ResourceMetrics:
    """
    Current resource metrics.

    PHASE3-AGENT-004: Metrics for heartbeat.
    """
    # CPU
    cpu_percent: float = 0.0
    cpu_count: int = 1
    cpu_freq_mhz: Optional[float] = None

    # Memory
    memory_percent: float = 0.0
    memory_total_mb: float = 0.0
    memory_available_mb: float = 0.0
    memory_used_mb: float = 0.0

    # Disk
    disk_percent: float = 0.0
    disk_total_gb: float = 0.0
    disk_free_gb: float = 0.0

    # Network (bytes/sec)
    network_bytes_sent: int = 0
    network_bytes_recv: int = 0

    # Process
    process_count: int = 0
    active_tasks: int = 0

    # Status
    status: ResourceStatus = ResourceStatus.UNKNOWN
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for heartbeat."""
        return {
            "cpu_percent": round(self.cpu_percent, 2),
            "cpu_count": self.cpu_count,
            "memory_percent": round(self.memory_percent, 2),
            "memory_total_mb": round(self.memory_total_mb, 2),
            "memory_available_mb": round(self.memory_available_mb, 2),
            "disk_percent": round(self.disk_percent, 2),
            "disk_free_gb": round(self.disk_free_gb, 2),
            "network_bytes_sent": self.network_bytes_sent,
            "network_bytes_recv": self.network_bytes_recv,
            "process_count": self.process_count,
            "active_tasks": self.active_tasks,
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
        }


class ResourceMonitor:
    """
    Monitors system resources and enforces limits.

    PHASE3-AGENT-004: Resource Limits Enforcement.
    Tracks CPU/RAM usage and determines if agent can accept tasks.
    """

    def __init__(
        self,
        thresholds: Optional[ResourceThresholds] = None,
        on_status_change: Optional[Callable[[ResourceStatus, ResourceStatus], Awaitable[None]]] = None,
    ):
        """
        Initialize resource monitor.

        Args:
            thresholds: Resource thresholds (uses defaults if None)
            on_status_change: Callback when status changes
        """
        self.thresholds = thresholds or ResourceThresholds()
        self._on_status_change = on_status_change

        self._samples: list[ResourceMetrics] = []
        self._current_status = ResourceStatus.UNKNOWN
        self._status_count = 0
        self._is_running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._paused = False
        self._active_tasks = 0

        # Network tracking for delta calculation
        self._last_net_io: Optional[tuple[int, int]] = None

        logger.info(
            f"ResourceMonitor initialized: "
            f"cpu_threshold={self.thresholds.cpu_overloaded}%, "
            f"mem_threshold={self.thresholds.memory_overloaded}%"
        )

    async def start(self) -> None:
        """Start background monitoring."""
        if self._is_running:
            return

        self._is_running = True

        async def monitor_loop():
            while self._is_running:
                await self._collect_sample()
                await asyncio.sleep(self.thresholds.sample_interval_sec)

        self._monitor_task = asyncio.create_task(monitor_loop())
        logger.info("Resource monitoring started")

    async def stop(self) -> None:
        """Stop background monitoring."""
        self._is_running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Resource monitoring stopped")

    def pause(self) -> None:
        """
        Pause accepting tasks.

        PHASE3-AGENT-004: Manual pause functionality.
        """
        self._paused = True
        logger.info("Resource monitor paused - rejecting all tasks")

    def resume(self) -> None:
        """Resume accepting tasks."""
        self._paused = False
        logger.info("Resource monitor resumed")

    def set_active_tasks(self, count: int) -> None:
        """Update active task count."""
        self._active_tasks = count

    def increment_active_tasks(self) -> None:
        """Increment active task count."""
        self._active_tasks += 1

    def decrement_active_tasks(self) -> None:
        """Decrement active task count."""
        self._active_tasks = max(0, self._active_tasks - 1)

    async def _collect_sample(self) -> None:
        """Collect resource metrics sample."""
        metrics = self._get_current_metrics()

        # Add to samples window
        self._samples.append(metrics)
        if len(self._samples) > self.thresholds.sample_window_count:
            self._samples.pop(0)

        # Determine status based on averaged metrics
        new_status = self._determine_status(metrics)

        # Apply hysteresis
        if new_status == self._current_status:
            self._status_count = 0
        else:
            self._status_count += 1
            if self._status_count >= self.thresholds.hysteresis_samples:
                old_status = self._current_status
                self._current_status = new_status
                self._status_count = 0

                logger.info(f"Resource status changed: {old_status.value} -> {new_status.value}")

                if self._on_status_change:
                    try:
                        await self._on_status_change(old_status, new_status)
                    except Exception as e:
                        logger.error(f"Status change callback error: {e}")

    def _get_current_metrics(self) -> ResourceMetrics:
        """
        Get current system metrics.

        PHASE3-AGENT-004: Cross-platform metric collection.
        """
        metrics = ResourceMetrics()
        metrics.timestamp = datetime.now(UTC)
        metrics.active_tasks = self._active_tasks

        try:
            # CPU
            metrics.cpu_percent = psutil.cpu_percent(interval=0.1)
            metrics.cpu_count = psutil.cpu_count() or 1

            try:
                freq = psutil.cpu_freq()
                if freq:
                    metrics.cpu_freq_mhz = freq.current
            except Exception:
                pass

            # Memory
            mem = psutil.virtual_memory()
            metrics.memory_percent = mem.percent
            metrics.memory_total_mb = mem.total / (1024 * 1024)
            metrics.memory_available_mb = mem.available / (1024 * 1024)
            metrics.memory_used_mb = mem.used / (1024 * 1024)

            # Disk
            try:
                disk = psutil.disk_usage("/")
                metrics.disk_percent = disk.percent
                metrics.disk_total_gb = disk.total / (1024 ** 3)
                metrics.disk_free_gb = disk.free / (1024 ** 3)
            except Exception:
                # Windows might fail with "/" path
                try:
                    disk = psutil.disk_usage("C:\\")
                    metrics.disk_percent = disk.percent
                    metrics.disk_total_gb = disk.total / (1024 ** 3)
                    metrics.disk_free_gb = disk.free / (1024 ** 3)
                except Exception:
                    pass

            # Network
            try:
                net_io = psutil.net_io_counters()
                if self._last_net_io:
                    metrics.network_bytes_sent = net_io.bytes_sent - self._last_net_io[0]
                    metrics.network_bytes_recv = net_io.bytes_recv - self._last_net_io[1]
                self._last_net_io = (net_io.bytes_sent, net_io.bytes_recv)
            except Exception:
                pass

            # Process count
            metrics.process_count = len(psutil.pids())

        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")

        return metrics

    def _determine_status(self, metrics: ResourceMetrics) -> ResourceStatus:
        """
        Determine resource status based on metrics.

        PHASE3-AGENT-004: Status determination logic.
        """
        if self._paused:
            return ResourceStatus.PAUSED

        # Check for overload (any resource over threshold)
        if (metrics.cpu_percent >= self.thresholds.cpu_overloaded or
            metrics.memory_percent >= self.thresholds.memory_overloaded or
            metrics.disk_percent >= self.thresholds.disk_overloaded):
            return ResourceStatus.OVERLOADED

        # Check for limited capacity
        if (metrics.cpu_percent >= self.thresholds.cpu_limited or
            metrics.memory_percent >= self.thresholds.memory_limited or
            metrics.disk_percent >= self.thresholds.disk_limited):
            return ResourceStatus.LIMITED

        # Check for available
        if (metrics.cpu_percent <= self.thresholds.cpu_available and
            metrics.memory_percent <= self.thresholds.memory_available and
            metrics.disk_percent <= self.thresholds.disk_available):
            return ResourceStatus.AVAILABLE

        return ResourceStatus.LIMITED

    def can_accept_task(self, required_memory_mb: float = 0, required_cpu_percent: float = 0) -> bool:
        """
        Check if agent can accept a new task.

        PHASE3-AGENT-004: Task acceptance check.

        Args:
            required_memory_mb: Memory required by task
            required_cpu_percent: CPU required by task

        Returns:
            True if task can be accepted
        """
        if self._paused:
            return False

        if self._current_status in (ResourceStatus.OVERLOADED, ResourceStatus.PAUSED):
            return False

        # Check if we have enough headroom for the task
        if self._samples:
            latest = self._samples[-1]

            # Check memory headroom
            if required_memory_mb > 0:
                available_mb = latest.memory_available_mb
                if required_memory_mb > available_mb * 0.8:  # Leave 20% buffer
                    return False

            # Check CPU headroom (rough estimate)
            if required_cpu_percent > 0:
                available_cpu = 100 - latest.cpu_percent
                if required_cpu_percent > available_cpu * 0.8:
                    return False

        return True

    def get_current_metrics(self) -> ResourceMetrics:
        """
        Get current resource metrics.

        PHASE3-AGENT-004: For heartbeat reporting.
        """
        if self._samples:
            metrics = self._samples[-1]
            metrics.status = self._current_status
            return metrics

        # Collect fresh if no samples
        metrics = self._get_current_metrics()
        metrics.status = self._current_status
        return metrics

    def get_averaged_metrics(self) -> ResourceMetrics:
        """Get averaged metrics over sample window."""
        if not self._samples:
            return self.get_current_metrics()

        # Average numeric fields
        avg_metrics = ResourceMetrics()
        n = len(self._samples)

        avg_metrics.cpu_percent = sum(s.cpu_percent for s in self._samples) / n
        avg_metrics.memory_percent = sum(s.memory_percent for s in self._samples) / n
        avg_metrics.disk_percent = sum(s.disk_percent for s in self._samples) / n

        # Use latest for non-averaged fields
        latest = self._samples[-1]
        avg_metrics.cpu_count = latest.cpu_count
        avg_metrics.memory_total_mb = latest.memory_total_mb
        avg_metrics.memory_available_mb = latest.memory_available_mb
        avg_metrics.disk_total_gb = latest.disk_total_gb
        avg_metrics.disk_free_gb = latest.disk_free_gb
        avg_metrics.process_count = latest.process_count
        avg_metrics.active_tasks = latest.active_tasks
        avg_metrics.status = self._current_status
        avg_metrics.timestamp = datetime.now(UTC)

        return avg_metrics

    def get_status(self) -> ResourceStatus:
        """Get current resource status."""
        return self._current_status

    def get_stats(self) -> dict[str, Any]:
        """Get monitor statistics."""
        return {
            "status": self._current_status.value,
            "paused": self._paused,
            "active_tasks": self._active_tasks,
            "sample_count": len(self._samples),
            "thresholds": {
                "cpu_overloaded": self.thresholds.cpu_overloaded,
                "memory_overloaded": self.thresholds.memory_overloaded,
                "disk_overloaded": self.thresholds.disk_overloaded,
            },
            "platform": platform.system(),
        }
