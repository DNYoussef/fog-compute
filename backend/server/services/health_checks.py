"""
Health Check System
Monitors service health with configurable checks, history tracking, and recovery actions
"""
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import logging
from collections import deque

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check"""
    service_name: str
    status: HealthStatus
    timestamp: datetime
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    response_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "service_name": self.service_name,
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "details": self.details,
            "response_time_ms": self.response_time_ms
        }


@dataclass
class HealthCheckConfig:
    """Configuration for a health check"""
    service_name: str
    check_interval: int = 30  # seconds
    timeout: int = 5  # seconds
    failure_threshold: int = 3  # consecutive failures before unhealthy
    recovery_threshold: int = 2  # consecutive successes to recover
    enabled: bool = True
    auto_recovery: bool = True


class HealthChecker:
    """
    Performs health checks on services
    Tracks history, detects failures, and triggers recovery
    """

    def __init__(self, config: HealthCheckConfig):
        self.config = config
        self.history: deque = deque(maxlen=100)  # Last 100 checks
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.last_check: Optional[HealthCheckResult] = None
        self.is_running = False
        self._check_task: Optional[asyncio.Task] = None
        self.on_failure_callback: Optional[Callable] = None
        self.on_recovery_callback: Optional[Callable] = None

    async def perform_check(self, service: Any) -> HealthCheckResult:
        """
        Perform a health check on a service
        Returns health check result
        """
        start_time = datetime.now()

        try:
            # Try multiple health check methods
            status = HealthStatus.UNKNOWN
            message = "No health check method available"
            details = {}

            # Method 1: get_health() method
            if hasattr(service, 'get_health'):
                try:
                    health_data = await asyncio.wait_for(
                        service.get_health(),
                        timeout=self.config.timeout
                    ) if asyncio.iscoroutinefunction(service.get_health) else service.get_health()

                    status = HealthStatus.HEALTHY
                    message = "Service health check passed"
                    details = health_data if isinstance(health_data, dict) else {"data": str(health_data)}
                except asyncio.TimeoutError:
                    status = HealthStatus.UNHEALTHY
                    message = "Health check timed out"
                except Exception as e:
                    status = HealthStatus.UNHEALTHY
                    message = f"Health check failed: {str(e)}"

            # Method 2: is_healthy() method
            elif hasattr(service, 'is_healthy'):
                try:
                    is_healthy = await asyncio.wait_for(
                        service.is_healthy(),
                        timeout=self.config.timeout
                    ) if asyncio.iscoroutinefunction(service.is_healthy) else service.is_healthy()

                    status = HealthStatus.HEALTHY if is_healthy else HealthStatus.UNHEALTHY
                    message = "Service is healthy" if is_healthy else "Service is unhealthy"
                except asyncio.TimeoutError:
                    status = HealthStatus.UNHEALTHY
                    message = "Health check timed out"
                except Exception as e:
                    status = HealthStatus.UNHEALTHY
                    message = f"Health check failed: {str(e)}"

            # Method 3: Basic attribute check
            elif service is not None:
                status = HealthStatus.HEALTHY
                message = "Service is running (basic check)"
                details = {"type": type(service).__name__}
            else:
                status = HealthStatus.UNHEALTHY
                message = "Service is None"

            # Calculate response time
            response_time = (datetime.now() - start_time).total_seconds() * 1000

            result = HealthCheckResult(
                service_name=self.config.service_name,
                status=status,
                timestamp=datetime.now(),
                message=message,
                details=details,
                response_time_ms=response_time
            )

            # Update counters
            if status == HealthStatus.HEALTHY:
                self.consecutive_successes += 1
                self.consecutive_failures = 0
            else:
                self.consecutive_failures += 1
                self.consecutive_successes = 0

            # Store in history
            self.history.append(result)
            self.last_check = result

            # Trigger callbacks
            if self.consecutive_failures >= self.config.failure_threshold:
                if self.on_failure_callback:
                    await self.on_failure_callback(result)
            elif self.consecutive_successes >= self.config.recovery_threshold:
                if self.on_recovery_callback:
                    await self.on_recovery_callback(result)

            return result

        except Exception as e:
            logger.error(f"Error performing health check for {self.config.service_name}: {e}")
            result = HealthCheckResult(
                service_name=self.config.service_name,
                status=HealthStatus.UNKNOWN,
                timestamp=datetime.now(),
                message=f"Health check error: {str(e)}"
            )
            self.history.append(result)
            self.last_check = result
            return result

    async def start_monitoring(self, service: Any) -> None:
        """Start continuous health monitoring"""
        if self.is_running:
            logger.warning(f"Health monitoring already running for {self.config.service_name}")
            return

        self.is_running = True

        async def monitor_loop():
            while self.is_running:
                try:
                    await self.perform_check(service)
                    await asyncio.sleep(self.config.check_interval)
                except Exception as e:
                    logger.error(f"Error in health monitor loop for {self.config.service_name}: {e}")
                    await asyncio.sleep(self.config.check_interval)

        self._check_task = asyncio.create_task(monitor_loop())
        logger.info(f"Started health monitoring for {self.config.service_name}")

    async def stop_monitoring(self) -> None:
        """Stop health monitoring"""
        self.is_running = False
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
        logger.info(f"Stopped health monitoring for {self.config.service_name}")

    def get_current_status(self) -> HealthStatus:
        """Get current health status"""
        if not self.last_check:
            return HealthStatus.UNKNOWN

        # Check if unhealthy based on consecutive failures
        if self.consecutive_failures >= self.config.failure_threshold:
            return HealthStatus.UNHEALTHY
        elif self.consecutive_failures > 0:
            return HealthStatus.DEGRADED

        return self.last_check.status

    def get_history(self, limit: int = 10) -> List[HealthCheckResult]:
        """Get recent health check history"""
        return list(self.history)[-limit:]

    def get_uptime_percentage(self, duration: timedelta = timedelta(hours=1)) -> float:
        """Calculate uptime percentage over duration"""
        if not self.history:
            return 0.0

        cutoff_time = datetime.now() - duration
        recent_checks = [
            check for check in self.history
            if check.timestamp >= cutoff_time
        ]

        if not recent_checks:
            return 0.0

        healthy_checks = sum(
            1 for check in recent_checks
            if check.status == HealthStatus.HEALTHY
        )

        return (healthy_checks / len(recent_checks)) * 100


class HealthCheckManager:
    """
    Manages health checks for all services
    Provides composite health status and alerting
    """

    def __init__(self):
        self.checkers: Dict[str, HealthChecker] = {}

    def register_service(
        self,
        service_name: str,
        config: Optional[HealthCheckConfig] = None
    ) -> HealthChecker:
        """Register a service for health monitoring"""
        if config is None:
            config = HealthCheckConfig(service_name=service_name)

        checker = HealthChecker(config)
        self.checkers[service_name] = checker

        logger.info(f"Registered health checker for {service_name}")
        return checker

    def unregister_service(self, service_name: str) -> None:
        """Unregister a service"""
        if service_name in self.checkers:
            del self.checkers[service_name]
            logger.info(f"Unregistered health checker for {service_name}")

    async def start_all(self, services: Dict[str, Any]) -> None:
        """Start health monitoring for all registered services"""
        for service_name, checker in self.checkers.items():
            if service_name in services and checker.config.enabled:
                await checker.start_monitoring(services[service_name])

    async def stop_all(self) -> None:
        """Stop all health monitoring"""
        for checker in self.checkers.values():
            await checker.stop_monitoring()

    def get_composite_health(self) -> HealthStatus:
        """
        Get composite health status across all services
        - HEALTHY: All services healthy
        - DEGRADED: Some services degraded
        - UNHEALTHY: Any service unhealthy
        - UNKNOWN: No health data available
        """
        if not self.checkers:
            return HealthStatus.UNKNOWN

        statuses = [checker.get_current_status() for checker in self.checkers.values()]

        if not statuses:
            return HealthStatus.UNKNOWN

        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        elif all(s == HealthStatus.HEALTHY for s in statuses):
            return HealthStatus.HEALTHY
        else:
            return HealthStatus.UNKNOWN

    def get_all_statuses(self) -> Dict[str, Dict[str, Any]]:
        """Get health status for all services"""
        return {
            name: {
                "status": checker.get_current_status().value,
                "last_check": checker.last_check.to_dict() if checker.last_check else None,
                "consecutive_failures": checker.consecutive_failures,
                "uptime_1h": checker.get_uptime_percentage(timedelta(hours=1))
            }
            for name, checker in self.checkers.items()
        }

    async def check_all_now(self, services: Dict[str, Any]) -> Dict[str, HealthCheckResult]:
        """Perform immediate health check on all services"""
        results = {}

        for service_name, checker in self.checkers.items():
            if service_name in services:
                result = await checker.perform_check(services[service_name])
                results[service_name] = result

        return results

    def get_unhealthy_services(self) -> List[str]:
        """Get list of unhealthy services"""
        return [
            name for name, checker in self.checkers.items()
            if checker.get_current_status() == HealthStatus.UNHEALTHY
        ]

    def get_degraded_services(self) -> List[str]:
        """Get list of degraded services"""
        return [
            name for name, checker in self.checkers.items()
            if checker.get_current_status() == HealthStatus.DEGRADED
        ]
