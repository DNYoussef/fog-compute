"""
Service Registry
Provides service discovery, metadata management, and heartbeat tracking
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)


class ServiceStatus(str, Enum):
    """Service registration status"""
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class ServiceMetadata:
    """Metadata for a registered service"""
    name: str
    service_type: str
    status: ServiceStatus
    version: str = "1.0.0"
    endpoints: Dict[str, str] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    optional_dependencies: List[str] = field(default_factory=list)
    registered_at: datetime = field(default_factory=datetime.now)
    last_heartbeat: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "service_type": self.service_type,
            "status": self.status.value,
            "version": self.version,
            "endpoints": self.endpoints,
            "dependencies": self.dependencies,
            "optional_dependencies": self.optional_dependencies,
            "registered_at": self.registered_at.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "uptime_seconds": (datetime.now() - self.registered_at).total_seconds(),
            "metadata": self.metadata
        }


class ServiceRegistry:
    """
    Central registry for service discovery and management
    Handles registration, deregistration, and heartbeat tracking
    """

    def __init__(self, heartbeat_interval: int = 60, heartbeat_timeout: int = 180):
        """
        Initialize service registry

        Args:
            heartbeat_interval: Expected heartbeat interval in seconds (default: 60s)
            heartbeat_timeout: Time before service considered dead (default: 180s)
        """
        self.services: Dict[str, ServiceMetadata] = {}
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_timeout = heartbeat_timeout
        self._monitor_task: Optional[asyncio.Task] = None
        self._is_monitoring = False

    def register(
        self,
        name: str,
        service_type: str,
        version: str = "1.0.0",
        endpoints: Optional[Dict[str, str]] = None,
        dependencies: Optional[List[str]] = None,
        optional_dependencies: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ServiceMetadata:
        """
        Register a service in the registry

        Args:
            name: Service name
            service_type: Type of service
            version: Service version
            endpoints: Service endpoints
            dependencies: Required dependencies
            optional_dependencies: Optional dependencies
            metadata: Additional metadata

        Returns:
            ServiceMetadata object
        """
        if name in self.services:
            logger.warning(f"Service {name} already registered, updating metadata")

        service_meta = ServiceMetadata(
            name=name,
            service_type=service_type,
            status=ServiceStatus.STARTING,
            version=version,
            endpoints=endpoints or {},
            dependencies=dependencies or [],
            optional_dependencies=optional_dependencies or [],
            last_heartbeat=datetime.now(),
            metadata=metadata or {}
        )

        self.services[name] = service_meta
        logger.info(f"Registered service: {name} (type: {service_type}, version: {version})")

        return service_meta

    def deregister(self, name: str) -> bool:
        """
        Deregister a service

        Args:
            name: Service name

        Returns:
            True if service was deregistered, False if not found
        """
        if name in self.services:
            del self.services[name]
            logger.info(f"Deregistered service: {name}")
            return True
        return False

    def update_status(self, name: str, status: ServiceStatus) -> bool:
        """
        Update service status

        Args:
            name: Service name
            status: New status

        Returns:
            True if updated, False if service not found
        """
        if name in self.services:
            old_status = self.services[name].status
            self.services[name].status = status
            logger.info(f"Service {name} status changed: {old_status.value} -> {status.value}")
            return True
        return False

    def heartbeat(self, name: str) -> bool:
        """
        Record a heartbeat for a service

        Args:
            name: Service name

        Returns:
            True if heartbeat recorded, False if service not found
        """
        if name in self.services:
            self.services[name].last_heartbeat = datetime.now()
            return True
        return False

    def get_service(self, name: str) -> Optional[ServiceMetadata]:
        """Get service metadata by name"""
        return self.services.get(name)

    def get_all_services(self) -> List[ServiceMetadata]:
        """Get all registered services"""
        return list(self.services.values())

    def get_services_by_type(self, service_type: str) -> List[ServiceMetadata]:
        """Get all services of a specific type"""
        return [
            service for service in self.services.values()
            if service.service_type == service_type
        ]

    def get_services_by_status(self, status: ServiceStatus) -> List[ServiceMetadata]:
        """Get all services with a specific status"""
        return [
            service for service in self.services.values()
            if service.status == status
        ]

    def get_dependencies(self, name: str) -> List[str]:
        """Get dependencies for a service"""
        service = self.get_service(name)
        return service.dependencies if service else []

    def get_dependents(self, name: str) -> List[str]:
        """Get services that depend on this service"""
        dependents = []
        for service in self.services.values():
            if name in service.dependencies or name in service.optional_dependencies:
                dependents.append(service.name)
        return dependents

    def is_alive(self, name: str) -> bool:
        """
        Check if a service is alive based on heartbeat

        Args:
            name: Service name

        Returns:
            True if service has sent recent heartbeat, False otherwise
        """
        service = self.get_service(name)
        if not service or not service.last_heartbeat:
            return False

        time_since_heartbeat = datetime.now() - service.last_heartbeat
        return time_since_heartbeat.total_seconds() < self.heartbeat_timeout

    def get_stale_services(self) -> List[str]:
        """Get services that haven't sent heartbeat within timeout period"""
        stale = []
        timeout_threshold = datetime.now() - timedelta(seconds=self.heartbeat_timeout)

        for name, service in self.services.items():
            if service.last_heartbeat and service.last_heartbeat < timeout_threshold:
                stale.append(name)

        return stale

    async def start_monitoring(self) -> None:
        """Start heartbeat monitoring"""
        if self._is_monitoring:
            logger.warning("Registry monitoring already started")
            return

        self._is_monitoring = True

        async def monitor_loop():
            while self._is_monitoring:
                try:
                    # Check for stale services
                    stale_services = self.get_stale_services()

                    for service_name in stale_services:
                        service = self.get_service(service_name)
                        if service and service.status == ServiceStatus.RUNNING:
                            logger.warning(
                                f"Service {service_name} heartbeat timeout, "
                                f"marking as failed"
                            )
                            self.update_status(service_name, ServiceStatus.FAILED)

                    # Wait for next check
                    await asyncio.sleep(self.heartbeat_interval)

                except Exception as e:
                    logger.error(f"Error in registry monitor loop: {e}")
                    await asyncio.sleep(self.heartbeat_interval)

        self._monitor_task = asyncio.create_task(monitor_loop())
        logger.info("Started service registry monitoring")

    async def stop_monitoring(self) -> None:
        """Stop heartbeat monitoring"""
        self._is_monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped service registry monitoring")

    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics"""
        total = len(self.services)
        by_status = {}
        by_type = {}
        alive_count = 0

        for service in self.services.values():
            # Count by status
            status_key = service.status.value
            by_status[status_key] = by_status.get(status_key, 0) + 1

            # Count by type
            by_type[service.service_type] = by_type.get(service.service_type, 0) + 1

            # Count alive services
            if self.is_alive(service.name):
                alive_count += 1

        return {
            "total_services": total,
            "alive_services": alive_count,
            "by_status": by_status,
            "by_type": by_type,
            "heartbeat_interval": self.heartbeat_interval,
            "heartbeat_timeout": self.heartbeat_timeout
        }
