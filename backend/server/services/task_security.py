"""
Task Security Service
Security constraints and capability validation for fog compute tasks

PHASE0-SEC-005 (0anh): Task Allowlist
- Define system-wide allowed task types
- Restrict filesystem access to /tmp/fogburst
- Block network access except to coordinator
- Validate task types against allowlist

PHASE2-TASK-002 (uolh): Task Capability Negotiation
- Device declares task types in profile
- Coordinator validates task assignments match device capabilities
- Match task requirements to device hardware
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any
import logging
import re

from ..schemas.device_mesh import DeviceProfile, DeviceCapability

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """
    Allowed task types in the fog compute system.

    PHASE0-SEC-005: Only these task types are permitted.
    """
    COMPUTE = "compute"           # CPU-bound computation
    GPU_COMPUTE = "gpu_compute"   # GPU-accelerated computation
    INFERENCE = "inference"       # ML model inference
    STORAGE = "storage"           # Data storage operations
    TRANSFER = "transfer"         # Data transfer between devices
    AGGREGATE = "aggregate"       # Data aggregation tasks


class SecurityLevel(str, Enum):
    """Security level for task execution"""
    SANDBOXED = "sandboxed"       # Full sandboxing (default)
    ELEVATED = "elevated"         # Some restrictions relaxed
    TRUSTED = "trusted"           # Minimal restrictions (internal only)


@dataclass
class TaskSecurityConstraints:
    """
    Security constraints for a task type.

    PHASE0-SEC-005: Defines what resources a task can access.
    """
    # Filesystem constraints
    allowed_filesystem_paths: list[str] = field(default_factory=lambda: ["/tmp/fogburst"])
    filesystem_read_only: bool = False
    max_file_size_mb: int = 100

    # Network constraints
    network_allowed: bool = False
    allowed_network_hosts: list[str] = field(default_factory=list)  # Empty = coordinator only
    allow_coordinator_only: bool = True  # If True, only coordinator IP allowed

    # Resource constraints
    max_memory_mb: int = 512
    max_cpu_percent: int = 50
    max_execution_time_sec: int = 300  # 5 minutes

    # Process constraints
    allow_subprocess: bool = False
    allow_network_bind: bool = False
    allow_raw_sockets: bool = False

    # Security level
    security_level: SecurityLevel = SecurityLevel.SANDBOXED


@dataclass
class TaskCapabilityRequirements:
    """
    Hardware/software requirements for a task type.

    PHASE2-TASK-002: Used to match tasks to capable devices.
    """
    required_capabilities: list[DeviceCapability] = field(default_factory=list)
    min_cpu_cores: int = 1
    min_ram_gb: float = 0.5
    min_gpu_vram_gb: Optional[float] = None  # None = no GPU required
    min_storage_gb: float = 1.0
    min_bandwidth_mbps: float = 1.0


# PHASE0-SEC-005: Task Allowlist Configuration
# Maps task types to their security constraints and capability requirements

TASK_ALLOWLIST: dict[TaskType, tuple[TaskSecurityConstraints, TaskCapabilityRequirements]] = {
    TaskType.COMPUTE: (
        TaskSecurityConstraints(
            allowed_filesystem_paths=["/tmp/fogburst"],
            max_memory_mb=1024,
            max_cpu_percent=80,
            max_execution_time_sec=600,
            network_allowed=False,
            allow_coordinator_only=True,
        ),
        TaskCapabilityRequirements(
            required_capabilities=[DeviceCapability.CPU],
            min_cpu_cores=1,
            min_ram_gb=0.5,
        ),
    ),

    TaskType.GPU_COMPUTE: (
        TaskSecurityConstraints(
            allowed_filesystem_paths=["/tmp/fogburst"],
            max_memory_mb=2048,
            max_cpu_percent=90,
            max_execution_time_sec=1800,  # 30 minutes for GPU tasks
            network_allowed=False,
            allow_coordinator_only=True,
        ),
        TaskCapabilityRequirements(
            required_capabilities=[DeviceCapability.CPU, DeviceCapability.GPU],
            min_cpu_cores=2,
            min_ram_gb=4.0,
            min_gpu_vram_gb=2.0,
        ),
    ),

    TaskType.INFERENCE: (
        TaskSecurityConstraints(
            allowed_filesystem_paths=["/tmp/fogburst", "/tmp/fogburst/models"],
            filesystem_read_only=True,  # Models are read-only
            max_memory_mb=4096,
            max_cpu_percent=95,
            max_execution_time_sec=120,  # Inference should be fast
            network_allowed=False,
            allow_coordinator_only=True,
        ),
        TaskCapabilityRequirements(
            required_capabilities=[DeviceCapability.CPU],
            min_cpu_cores=2,
            min_ram_gb=2.0,
        ),
    ),

    TaskType.STORAGE: (
        TaskSecurityConstraints(
            allowed_filesystem_paths=["/tmp/fogburst/storage"],
            max_file_size_mb=500,
            max_memory_mb=256,
            max_cpu_percent=20,
            max_execution_time_sec=60,
            network_allowed=False,
            allow_coordinator_only=True,
        ),
        TaskCapabilityRequirements(
            required_capabilities=[DeviceCapability.STORAGE],
            min_storage_gb=10.0,
        ),
    ),

    TaskType.TRANSFER: (
        TaskSecurityConstraints(
            allowed_filesystem_paths=["/tmp/fogburst/transfer"],
            max_file_size_mb=1000,
            max_memory_mb=512,
            max_cpu_percent=30,
            max_execution_time_sec=300,
            network_allowed=True,  # Transfer needs network
            allow_coordinator_only=True,  # But only to coordinator
        ),
        TaskCapabilityRequirements(
            required_capabilities=[DeviceCapability.NETWORK],
            min_bandwidth_mbps=10.0,
        ),
    ),

    TaskType.AGGREGATE: (
        TaskSecurityConstraints(
            allowed_filesystem_paths=["/tmp/fogburst"],
            max_memory_mb=2048,
            max_cpu_percent=60,
            max_execution_time_sec=600,
            network_allowed=False,
            allow_coordinator_only=True,
        ),
        TaskCapabilityRequirements(
            required_capabilities=[DeviceCapability.CPU, DeviceCapability.MEMORY],
            min_cpu_cores=2,
            min_ram_gb=4.0,
        ),
    ),
}


@dataclass
class TaskValidationResult:
    """Result of task validation"""
    is_valid: bool
    error_message: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    constraints: Optional[TaskSecurityConstraints] = None
    requirements: Optional[TaskCapabilityRequirements] = None


class TaskSecurityService:
    """
    Service for validating task security and device capabilities.

    PHASE0-SEC-005: Enforces task allowlist
    PHASE2-TASK-002: Validates device capabilities for task assignment
    """

    def __init__(self, coordinator_host: str = "0.0.0.0", coordinator_port: int = 8000):
        """
        Initialize task security service.

        Args:
            coordinator_host: Coordinator IP for network allowlist
            coordinator_port: Coordinator port
        """
        self.coordinator_host = coordinator_host
        self.coordinator_port = coordinator_port
        self._custom_constraints: dict[str, TaskSecurityConstraints] = {}

        logger.info(f"TaskSecurityService initialized with coordinator {coordinator_host}:{coordinator_port}")

    def is_task_type_allowed(self, task_type: str) -> bool:
        """
        Check if a task type is in the allowlist.

        PHASE0-SEC-005: Only allowlisted task types can be executed.

        Args:
            task_type: Task type to check

        Returns:
            True if task type is allowed
        """
        try:
            TaskType(task_type)
            return True
        except ValueError:
            return False

    def get_allowed_task_types(self) -> list[str]:
        """
        Get list of all allowed task types.

        PHASE0-SEC-005: Returns the complete allowlist.

        Returns:
            List of allowed task type strings
        """
        return [t.value for t in TaskType]

    def get_security_constraints(self, task_type: str) -> Optional[TaskSecurityConstraints]:
        """
        Get security constraints for a task type.

        PHASE0-SEC-005: Returns constraints that must be enforced during execution.

        Args:
            task_type: Task type to get constraints for

        Returns:
            Security constraints or None if task type not allowed
        """
        # Check custom constraints first
        if task_type in self._custom_constraints:
            return self._custom_constraints[task_type]

        try:
            tt = TaskType(task_type)
            constraints, _ = TASK_ALLOWLIST[tt]
            return constraints
        except (ValueError, KeyError):
            return None

    def get_capability_requirements(self, task_type: str) -> Optional[TaskCapabilityRequirements]:
        """
        Get capability requirements for a task type.

        PHASE2-TASK-002: Returns requirements for device matching.

        Args:
            task_type: Task type to get requirements for

        Returns:
            Capability requirements or None if task type not allowed
        """
        try:
            tt = TaskType(task_type)
            _, requirements = TASK_ALLOWLIST[tt]
            return requirements
        except (ValueError, KeyError):
            return None

    def validate_task_type(self, task_type: str) -> TaskValidationResult:
        """
        Validate a task type against the allowlist.

        PHASE0-SEC-005: First step of task validation.

        Args:
            task_type: Task type to validate

        Returns:
            Validation result with constraints if valid
        """
        if not self.is_task_type_allowed(task_type):
            return TaskValidationResult(
                is_valid=False,
                error_message=f"Task type '{task_type}' is not in the allowlist. "
                             f"Allowed types: {self.get_allowed_task_types()}"
            )

        constraints = self.get_security_constraints(task_type)
        requirements = self.get_capability_requirements(task_type)

        return TaskValidationResult(
            is_valid=True,
            constraints=constraints,
            requirements=requirements
        )

    def validate_device_capability(
        self,
        task_type: str,
        device_profile: DeviceProfile
    ) -> TaskValidationResult:
        """
        Validate that a device can execute a task type.

        PHASE2-TASK-002: Core capability negotiation logic.

        Args:
            task_type: Task type to validate
            device_profile: Device profile with capabilities

        Returns:
            Validation result indicating if device can handle the task
        """
        # First validate task type
        type_result = self.validate_task_type(task_type)
        if not type_result.is_valid:
            return type_result

        requirements = type_result.requirements
        if requirements is None:
            return TaskValidationResult(
                is_valid=False,
                error_message=f"No capability requirements defined for task type '{task_type}'"
            )

        warnings = []

        # Check if device declares support for this task type
        if task_type not in device_profile.task_types:
            return TaskValidationResult(
                is_valid=False,
                error_message=f"Device does not declare support for task type '{task_type}'. "
                             f"Device supports: {device_profile.task_types}"
            )

        # Check required capabilities
        device_caps = set(device_profile.capabilities)
        required_caps = set(requirements.required_capabilities)
        missing_caps = required_caps - device_caps

        if missing_caps:
            return TaskValidationResult(
                is_valid=False,
                error_message=f"Device missing required capabilities: {[c.value for c in missing_caps]}"
            )

        # Check CPU cores
        if device_profile.cpu_cores < requirements.min_cpu_cores:
            return TaskValidationResult(
                is_valid=False,
                error_message=f"Device has {device_profile.cpu_cores} CPU cores, "
                             f"but task requires at least {requirements.min_cpu_cores}"
            )

        # Check RAM
        if device_profile.ram_gb < requirements.min_ram_gb:
            return TaskValidationResult(
                is_valid=False,
                error_message=f"Device has {device_profile.ram_gb}GB RAM, "
                             f"but task requires at least {requirements.min_ram_gb}GB"
            )

        # Check GPU VRAM if required
        if requirements.min_gpu_vram_gb is not None:
            if device_profile.gpu_vram_gb is None:
                return TaskValidationResult(
                    is_valid=False,
                    error_message=f"Task requires {requirements.min_gpu_vram_gb}GB GPU VRAM, "
                                 f"but device has no GPU"
                )
            if device_profile.gpu_vram_gb < requirements.min_gpu_vram_gb:
                return TaskValidationResult(
                    is_valid=False,
                    error_message=f"Device has {device_profile.gpu_vram_gb}GB GPU VRAM, "
                                 f"but task requires at least {requirements.min_gpu_vram_gb}GB"
                )

        # Check storage
        if device_profile.storage_gb < requirements.min_storage_gb:
            warnings.append(
                f"Device storage ({device_profile.storage_gb}GB) is below recommended "
                f"({requirements.min_storage_gb}GB)"
            )

        # Check bandwidth
        if device_profile.bandwidth_mbps < requirements.min_bandwidth_mbps:
            warnings.append(
                f"Device bandwidth ({device_profile.bandwidth_mbps}Mbps) is below recommended "
                f"({requirements.min_bandwidth_mbps}Mbps)"
            )

        return TaskValidationResult(
            is_valid=True,
            warnings=warnings,
            constraints=type_result.constraints,
            requirements=requirements
        )

    def validate_filesystem_path(
        self,
        path: str,
        task_type: str
    ) -> tuple[bool, Optional[str]]:
        """
        Validate a filesystem path for a task type.

        PHASE0-SEC-005: Restricts filesystem access to allowed paths.

        Args:
            path: Path to validate
            task_type: Task type requesting access

        Returns:
            Tuple of (is_allowed, error_message)
        """
        constraints = self.get_security_constraints(task_type)
        if constraints is None:
            return False, f"Unknown task type: {task_type}"

        # Normalize path
        normalized_path = path.replace("\\", "/")
        if not normalized_path.startswith("/"):
            normalized_path = "/" + normalized_path

        # Check against allowed paths
        for allowed in constraints.allowed_filesystem_paths:
            if normalized_path.startswith(allowed):
                return True, None

        return False, (
            f"Path '{path}' not allowed for task type '{task_type}'. "
            f"Allowed paths: {constraints.allowed_filesystem_paths}"
        )

    def validate_network_access(
        self,
        host: str,
        port: int,
        task_type: str
    ) -> tuple[bool, Optional[str]]:
        """
        Validate network access for a task type.

        PHASE0-SEC-005: Restricts network to coordinator only by default.

        Args:
            host: Target host
            port: Target port
            task_type: Task type requesting access

        Returns:
            Tuple of (is_allowed, error_message)
        """
        constraints = self.get_security_constraints(task_type)
        if constraints is None:
            return False, f"Unknown task type: {task_type}"

        if not constraints.network_allowed:
            return False, f"Network access not allowed for task type '{task_type}'"

        # Check coordinator-only constraint
        if constraints.allow_coordinator_only:
            # Allow localhost, 127.0.0.1, or the configured coordinator
            allowed_hosts = [
                "localhost",
                "127.0.0.1",
                self.coordinator_host,
            ]
            if self.coordinator_host == "0.0.0.0":
                allowed_hosts.append("0.0.0.0")

            if host not in allowed_hosts:
                return False, (
                    f"Network access to '{host}:{port}' not allowed. "
                    f"Only coordinator ({self.coordinator_host}:{self.coordinator_port}) is permitted."
                )

            # For coordinator, any port on the coordinator is allowed
            # (in production, you might want to restrict this further)

        # Check explicit allowed hosts
        if constraints.allowed_network_hosts:
            host_port = f"{host}:{port}"
            if host not in constraints.allowed_network_hosts and host_port not in constraints.allowed_network_hosts:
                return False, (
                    f"Host '{host}' not in allowed network hosts: "
                    f"{constraints.allowed_network_hosts}"
                )

        return True, None

    def find_capable_devices(
        self,
        task_type: str,
        device_profiles: list[DeviceProfile]
    ) -> list[DeviceProfile]:
        """
        Find devices capable of executing a task type.

        PHASE2-TASK-002: Used by coordinator for task scheduling.

        Args:
            task_type: Task type to match
            device_profiles: List of device profiles to search

        Returns:
            List of capable device profiles, sorted by suitability
        """
        capable = []

        for profile in device_profiles:
            result = self.validate_device_capability(task_type, profile)
            if result.is_valid:
                capable.append(profile)

        # Sort by number of capabilities (more capable devices first)
        # and by available resources
        def score_device(p: DeviceProfile) -> tuple:
            return (
                len(p.capabilities),  # More capabilities = better
                p.cpu_cores,
                p.ram_gb,
                p.gpu_vram_gb or 0,
            )

        capable.sort(key=score_device, reverse=True)

        return capable

    def set_custom_constraints(
        self,
        task_type: str,
        constraints: TaskSecurityConstraints
    ) -> None:
        """
        Set custom constraints for a task type (for testing/configuration).

        Note: This should only be used for legitimate customization, not
        to bypass security restrictions.

        Args:
            task_type: Task type to customize
            constraints: Custom constraints
        """
        if self.is_task_type_allowed(task_type):
            self._custom_constraints[task_type] = constraints
            logger.info(f"Custom constraints set for task type: {task_type}")
        else:
            logger.warning(f"Cannot set custom constraints for unknown task type: {task_type}")


# Global instance
_task_security_service: Optional[TaskSecurityService] = None


def get_task_security_service() -> TaskSecurityService:
    """Get or create the task security service instance"""
    global _task_security_service

    if _task_security_service is None:
        # Import settings here to avoid circular imports
        from ..config import settings
        _task_security_service = TaskSecurityService(
            coordinator_host=settings.API_HOST,
            coordinator_port=settings.API_PORT
        )

    return _task_security_service
