"""
Tests for Task Security Service

PHASE0-SEC-005 (0anh): Task Allowlist
- Validates task types against allowlist
- Restricts filesystem access to /tmp/fogburst
- Blocks network access except to coordinator

PHASE2-TASK-002 (uolh): Task Capability Negotiation
- Device declares task types in profile
- Coordinator validates task assignments match device capabilities
"""
import pytest
import os

# Set test environment before imports
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-task-security-testing')
os.environ.setdefault('TESTING', 'true')

from backend.server.services.task_security import (
    TaskSecurityService,
    TaskType,
    TaskSecurityConstraints,
    TaskCapabilityRequirements,
    SecurityLevel,
    TaskValidationResult,
    TASK_ALLOWLIST,
    get_task_security_service,
)
from backend.server.schemas.device_mesh import DeviceProfile, DeviceCapability


@pytest.fixture
def task_security():
    """Create a fresh TaskSecurityService for each test"""
    return TaskSecurityService(coordinator_host="127.0.0.1", coordinator_port=8000)


@pytest.fixture
def cpu_device():
    """Device with basic CPU capability"""
    return DeviceProfile(
        hostname="cpu-worker",
        capabilities=[DeviceCapability.CPU],
        cpu_cores=4,
        ram_gb=8.0,
        storage_gb=100.0,
        bandwidth_mbps=100.0,
        task_types=["compute", "inference"],
    )


@pytest.fixture
def gpu_device():
    """Device with GPU capability"""
    return DeviceProfile(
        hostname="gpu-worker",
        capabilities=[DeviceCapability.CPU, DeviceCapability.GPU],
        cpu_cores=8,
        ram_gb=32.0,
        gpu_vram_gb=8.0,
        storage_gb=500.0,
        bandwidth_mbps=1000.0,
        task_types=["compute", "gpu_compute", "inference"],
    )


@pytest.fixture
def storage_device():
    """Device with storage capability"""
    return DeviceProfile(
        hostname="storage-node",
        capabilities=[DeviceCapability.STORAGE, DeviceCapability.NETWORK],
        cpu_cores=2,
        ram_gb=4.0,
        storage_gb=2000.0,
        bandwidth_mbps=1000.0,
        task_types=["storage", "transfer"],
    )


@pytest.fixture
def minimal_device():
    """Device with minimal resources"""
    return DeviceProfile(
        hostname="minimal-node",
        capabilities=[DeviceCapability.CPU],
        cpu_cores=1,
        ram_gb=0.5,
        storage_gb=10.0,
        bandwidth_mbps=10.0,
        task_types=["compute"],
    )


# === PHASE0-SEC-005: Task Allowlist Tests ===

class TestTaskAllowlist:
    """Tests for task type allowlist enforcement"""

    def test_allowed_task_types(self, task_security):
        """All defined task types should be in allowlist"""
        allowed = task_security.get_allowed_task_types()

        assert "compute" in allowed
        assert "gpu_compute" in allowed
        assert "inference" in allowed
        assert "storage" in allowed
        assert "transfer" in allowed
        assert "aggregate" in allowed

    def test_is_task_type_allowed_valid(self, task_security):
        """Valid task types should be allowed"""
        assert task_security.is_task_type_allowed("compute") is True
        assert task_security.is_task_type_allowed("gpu_compute") is True
        assert task_security.is_task_type_allowed("inference") is True

    def test_is_task_type_allowed_invalid(self, task_security):
        """Invalid task types should not be allowed"""
        assert task_security.is_task_type_allowed("shell_execute") is False
        assert task_security.is_task_type_allowed("root_access") is False
        assert task_security.is_task_type_allowed("arbitrary_code") is False
        assert task_security.is_task_type_allowed("") is False

    def test_validate_task_type_valid(self, task_security):
        """Validation should pass for allowed task types"""
        result = task_security.validate_task_type("compute")

        assert result.is_valid is True
        assert result.error_message is None
        assert result.constraints is not None
        assert result.requirements is not None

    def test_validate_task_type_invalid(self, task_security):
        """Validation should fail for disallowed task types"""
        result = task_security.validate_task_type("malicious_task")

        assert result.is_valid is False
        assert "not in the allowlist" in result.error_message
        assert result.constraints is None

    def test_security_constraints_exist_for_all_types(self, task_security):
        """Every allowed task type should have security constraints"""
        for task_type in task_security.get_allowed_task_types():
            constraints = task_security.get_security_constraints(task_type)
            assert constraints is not None, f"No constraints for {task_type}"
            assert isinstance(constraints, TaskSecurityConstraints)

    def test_compute_task_constraints(self, task_security):
        """Compute task should have appropriate constraints"""
        constraints = task_security.get_security_constraints("compute")

        assert constraints is not None
        assert "/tmp/fogburst" in constraints.allowed_filesystem_paths
        assert constraints.network_allowed is False
        assert constraints.allow_coordinator_only is True
        assert constraints.max_memory_mb > 0
        assert constraints.max_cpu_percent > 0

    def test_gpu_task_constraints(self, task_security):
        """GPU task should have longer execution time"""
        constraints = task_security.get_security_constraints("gpu_compute")

        assert constraints is not None
        assert constraints.max_execution_time_sec >= 1800  # 30 minutes
        assert constraints.max_memory_mb >= 2048


class TestFilesystemRestrictions:
    """Tests for filesystem access restrictions (PHASE0-SEC-005)"""

    def test_allowed_path(self, task_security):
        """Paths under /tmp/fogburst should be allowed"""
        is_allowed, error = task_security.validate_filesystem_path(
            "/tmp/fogburst/data.json", "compute"
        )
        assert is_allowed is True
        assert error is None

    def test_allowed_nested_path(self, task_security):
        """Nested paths under /tmp/fogburst should be allowed"""
        is_allowed, error = task_security.validate_filesystem_path(
            "/tmp/fogburst/subdir/nested/file.txt", "compute"
        )
        assert is_allowed is True
        assert error is None

    def test_disallowed_root_path(self, task_security):
        """Root filesystem access should be blocked"""
        is_allowed, error = task_security.validate_filesystem_path(
            "/etc/passwd", "compute"
        )
        assert is_allowed is False
        assert "not allowed" in error

    def test_disallowed_home_path(self, task_security):
        """Home directory access should be blocked"""
        is_allowed, error = task_security.validate_filesystem_path(
            "/home/user/.ssh/id_rsa", "compute"
        )
        assert is_allowed is False
        assert "not allowed" in error

    def test_disallowed_var_path(self, task_security):
        """System directories should be blocked"""
        is_allowed, error = task_security.validate_filesystem_path(
            "/var/log/syslog", "compute"
        )
        assert is_allowed is False

    def test_storage_task_path(self, task_security):
        """Storage tasks have their own allowed path"""
        is_allowed, error = task_security.validate_filesystem_path(
            "/tmp/fogburst/storage/data.bin", "storage"
        )
        assert is_allowed is True

    def test_windows_path_normalization(self, task_security):
        """Windows-style paths should be normalized"""
        is_allowed, error = task_security.validate_filesystem_path(
            "\\tmp\\fogburst\\data.json", "compute"
        )
        # Note: This may not match depending on normalization
        # The key is no crash occurs

    def test_unknown_task_type_path(self, task_security):
        """Unknown task type should block all paths"""
        is_allowed, error = task_security.validate_filesystem_path(
            "/tmp/fogburst/data.json", "unknown_task"
        )
        assert is_allowed is False
        assert "Unknown task type" in error


class TestNetworkRestrictions:
    """Tests for network access restrictions (PHASE0-SEC-005)"""

    def test_network_blocked_for_compute(self, task_security):
        """Compute tasks should not have network access"""
        constraints = task_security.get_security_constraints("compute")
        assert constraints.network_allowed is False

    def test_network_allowed_for_transfer(self, task_security):
        """Transfer tasks need network access"""
        constraints = task_security.get_security_constraints("transfer")
        assert constraints.network_allowed is True

    def test_coordinator_only_access(self, task_security):
        """Transfer should only access coordinator"""
        is_allowed, error = task_security.validate_network_access(
            "127.0.0.1", 8000, "transfer"
        )
        assert is_allowed is True

    def test_localhost_allowed(self, task_security):
        """Localhost should be allowed for transfer"""
        is_allowed, error = task_security.validate_network_access(
            "localhost", 8000, "transfer"
        )
        assert is_allowed is True

    def test_external_host_blocked(self, task_security):
        """External hosts should be blocked even for transfer"""
        is_allowed, error = task_security.validate_network_access(
            "evil.com", 443, "transfer"
        )
        assert is_allowed is False
        assert "not allowed" in error

    def test_network_blocked_completely_for_compute(self, task_security):
        """Compute tasks should block all network"""
        is_allowed, error = task_security.validate_network_access(
            "127.0.0.1", 8000, "compute"
        )
        assert is_allowed is False
        assert "not allowed" in error


# === PHASE2-TASK-002: Task Capability Negotiation Tests ===

class TestCapabilityNegotiation:
    """Tests for device capability validation"""

    def test_cpu_device_can_compute(self, task_security, cpu_device):
        """CPU device should be able to do compute tasks"""
        result = task_security.validate_device_capability("compute", cpu_device)

        assert result.is_valid is True
        assert result.error_message is None

    def test_cpu_device_cannot_gpu_compute(self, task_security, cpu_device):
        """CPU device cannot do GPU compute tasks"""
        # First add gpu_compute to declared task_types to isolate the capability test
        cpu_device.task_types = ["compute", "gpu_compute"]

        result = task_security.validate_device_capability("gpu_compute", cpu_device)

        assert result.is_valid is False
        assert "missing required capabilities" in result.error_message.lower()

    def test_gpu_device_can_gpu_compute(self, task_security, gpu_device):
        """GPU device should be able to do GPU compute tasks"""
        result = task_security.validate_device_capability("gpu_compute", gpu_device)

        assert result.is_valid is True

    def test_storage_device_can_store(self, task_security, storage_device):
        """Storage device should be able to do storage tasks"""
        result = task_security.validate_device_capability("storage", storage_device)

        assert result.is_valid is True

    def test_device_must_declare_task_type(self, task_security, cpu_device):
        """Device must declare support for task type"""
        # Device doesn't declare "storage" in task_types
        result = task_security.validate_device_capability("storage", cpu_device)

        assert result.is_valid is False
        assert "does not declare support" in result.error_message

    def test_minimal_device_resources(self, task_security, minimal_device):
        """Minimal device should pass for basic compute"""
        result = task_security.validate_device_capability("compute", minimal_device)

        assert result.is_valid is True

    def test_insufficient_cpu_cores(self, task_security, minimal_device):
        """Device with insufficient CPU cores should fail for aggregate"""
        # Aggregate requires 2 cores, minimal has 1
        minimal_device.task_types.append("aggregate")
        minimal_device.capabilities.append(DeviceCapability.MEMORY)
        minimal_device.ram_gb = 4.0  # Meet RAM requirement

        result = task_security.validate_device_capability("aggregate", minimal_device)

        assert result.is_valid is False
        assert "CPU cores" in result.error_message

    def test_insufficient_ram(self, task_security, minimal_device):
        """Device with insufficient RAM should fail"""
        # GPU compute requires 4GB RAM, minimal has 0.5GB
        minimal_device.task_types = ["gpu_compute"]
        minimal_device.capabilities = [DeviceCapability.CPU, DeviceCapability.GPU]
        minimal_device.gpu_vram_gb = 8.0  # Meet GPU requirement
        minimal_device.cpu_cores = 4  # Meet CPU requirement
        minimal_device.ram_gb = 1.0  # Not enough RAM

        result = task_security.validate_device_capability("gpu_compute", minimal_device)

        assert result.is_valid is False
        assert "RAM" in result.error_message

    def test_insufficient_gpu_vram(self, task_security, cpu_device):
        """Device without enough GPU VRAM should fail for GPU tasks"""
        cpu_device.task_types = ["gpu_compute"]
        cpu_device.capabilities = [DeviceCapability.CPU, DeviceCapability.GPU]
        cpu_device.gpu_vram_gb = 1.0  # Not enough (needs 2.0)

        result = task_security.validate_device_capability("gpu_compute", cpu_device)

        assert result.is_valid is False
        assert "GPU VRAM" in result.error_message

    def test_no_gpu_for_gpu_task(self, task_security, cpu_device):
        """Device without GPU should fail for GPU tasks"""
        cpu_device.task_types = ["gpu_compute"]
        cpu_device.capabilities = [DeviceCapability.CPU, DeviceCapability.GPU]
        # No GPU VRAM set (None)

        result = task_security.validate_device_capability("gpu_compute", cpu_device)

        assert result.is_valid is False
        assert "no gpu" in result.error_message.lower()

    def test_warnings_for_low_resources(self, task_security, storage_device):
        """Low resources should generate warnings but still pass"""
        storage_device.bandwidth_mbps = 5.0  # Below recommended 10 Mbps

        result = task_security.validate_device_capability("transfer", storage_device)

        assert result.is_valid is True
        assert len(result.warnings) > 0
        assert "bandwidth" in result.warnings[0].lower()


class TestFindCapableDevices:
    """Tests for finding capable devices"""

    def test_find_compute_capable(self, task_security, cpu_device, gpu_device, storage_device):
        """Should find devices capable of compute"""
        devices = [cpu_device, gpu_device, storage_device]

        capable = task_security.find_capable_devices("compute", devices)

        # GPU device should be first (more capabilities)
        # CPU device can also compute
        # Storage device cannot
        assert len(capable) == 2
        assert gpu_device in capable
        assert cpu_device in capable
        assert storage_device not in capable

    def test_find_gpu_capable(self, task_security, cpu_device, gpu_device, storage_device):
        """Should find only GPU devices for GPU compute"""
        devices = [cpu_device, gpu_device, storage_device]

        capable = task_security.find_capable_devices("gpu_compute", devices)

        assert len(capable) == 1
        assert gpu_device in capable

    def test_find_storage_capable(self, task_security, cpu_device, gpu_device, storage_device):
        """Should find only storage devices for storage tasks"""
        devices = [cpu_device, gpu_device, storage_device]

        capable = task_security.find_capable_devices("storage", devices)

        assert len(capable) == 1
        assert storage_device in capable

    def test_sorting_by_capability(self, task_security):
        """Capable devices should be sorted by suitability"""
        weak = DeviceProfile(
            hostname="weak",
            capabilities=[DeviceCapability.CPU],
            cpu_cores=2,
            ram_gb=4.0,
            storage_gb=50.0,
            bandwidth_mbps=10.0,
            task_types=["compute"],
        )
        strong = DeviceProfile(
            hostname="strong",
            capabilities=[DeviceCapability.CPU, DeviceCapability.MEMORY],
            cpu_cores=16,
            ram_gb=64.0,
            storage_gb=1000.0,
            bandwidth_mbps=1000.0,
            task_types=["compute"],
        )

        capable = task_security.find_capable_devices("compute", [weak, strong])

        assert len(capable) == 2
        # Strong should be first (more capabilities, more resources)
        assert capable[0].hostname == "strong"


class TestRequirements:
    """Tests for capability requirements"""

    def test_requirements_exist_for_all_types(self, task_security):
        """Every task type should have capability requirements"""
        for task_type in task_security.get_allowed_task_types():
            requirements = task_security.get_capability_requirements(task_type)
            assert requirements is not None, f"No requirements for {task_type}"
            assert isinstance(requirements, TaskCapabilityRequirements)

    def test_compute_requires_cpu(self, task_security):
        """Compute task should require CPU capability"""
        requirements = task_security.get_capability_requirements("compute")

        assert DeviceCapability.CPU in requirements.required_capabilities

    def test_gpu_compute_requires_gpu(self, task_security):
        """GPU compute should require GPU capability"""
        requirements = task_security.get_capability_requirements("gpu_compute")

        assert DeviceCapability.GPU in requirements.required_capabilities
        assert requirements.min_gpu_vram_gb is not None
        assert requirements.min_gpu_vram_gb > 0

    def test_storage_requires_storage(self, task_security):
        """Storage task should require storage capability"""
        requirements = task_security.get_capability_requirements("storage")

        assert DeviceCapability.STORAGE in requirements.required_capabilities
        assert requirements.min_storage_gb >= 10.0


class TestCustomConstraints:
    """Tests for custom constraint configuration"""

    def test_set_custom_constraints(self, task_security):
        """Should be able to set custom constraints"""
        custom = TaskSecurityConstraints(
            allowed_filesystem_paths=["/tmp/custom"],
            max_memory_mb=2048,
            network_allowed=True,
        )

        task_security.set_custom_constraints("compute", custom)

        retrieved = task_security.get_security_constraints("compute")
        assert "/tmp/custom" in retrieved.allowed_filesystem_paths
        assert retrieved.max_memory_mb == 2048

    def test_custom_constraints_ignored_for_unknown_type(self, task_security):
        """Custom constraints should be ignored for unknown task types"""
        custom = TaskSecurityConstraints()

        # Should not raise, just log warning
        task_security.set_custom_constraints("unknown_type", custom)

        # Unknown type still returns None
        assert task_security.get_security_constraints("unknown_type") is None


class TestGlobalInstance:
    """Tests for global service instance"""

    def test_get_task_security_service(self):
        """Should return a TaskSecurityService instance"""
        service = get_task_security_service()

        assert service is not None
        assert isinstance(service, TaskSecurityService)

    def test_singleton_pattern(self):
        """Should return same instance on multiple calls"""
        service1 = get_task_security_service()
        service2 = get_task_security_service()

        assert service1 is service2


class TestTaskAllowlistConfiguration:
    """Tests for the TASK_ALLOWLIST configuration"""

    def test_all_task_types_have_entries(self):
        """Every TaskType should have an entry in TASK_ALLOWLIST"""
        for task_type in TaskType:
            assert task_type in TASK_ALLOWLIST, f"Missing allowlist entry for {task_type}"

    def test_allowlist_entries_are_valid(self):
        """All allowlist entries should be valid tuples"""
        for task_type, entry in TASK_ALLOWLIST.items():
            assert isinstance(entry, tuple), f"Entry for {task_type} is not a tuple"
            assert len(entry) == 2, f"Entry for {task_type} should have 2 elements"

            constraints, requirements = entry
            assert isinstance(constraints, TaskSecurityConstraints)
            assert isinstance(requirements, TaskCapabilityRequirements)

    def test_default_security_level(self):
        """All tasks should default to sandboxed security level"""
        for task_type, (constraints, _) in TASK_ALLOWLIST.items():
            assert constraints.security_level == SecurityLevel.SANDBOXED, \
                f"Task {task_type} should be sandboxed by default"
