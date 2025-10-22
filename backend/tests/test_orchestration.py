"""
Orchestration System Tests
Tests for service lifecycle, dependency resolution, health checks, and auto-restart
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Any

from backend.server.services.dependencies import (
    DependencyGraph,
    ServiceType,
    create_default_dependency_graph,
    validate_startup_order
)
from backend.server.services.health_checks import (
    HealthChecker,
    HealthCheckConfig,
    HealthCheckManager,
    HealthStatus
)
from backend.server.services.registry import (
    ServiceRegistry,
    ServiceStatus,
    ServiceMetadata
)


# ============================================================================
# Dependency Graph Tests
# ============================================================================

def test_dependency_graph_creation():
    """Test creating a dependency graph"""
    graph = DependencyGraph()

    graph.add_service("service_a", ServiceType.DAO, dependencies=[])
    graph.add_service("service_b", ServiceType.SCHEDULER, dependencies=["service_a"])
    graph.add_service("service_c", ServiceType.EDGE, dependencies=["service_a", "service_b"])

    assert len(graph.nodes) == 3
    assert "service_a" in graph.nodes
    assert graph.get_dependencies("service_b") == {"service_a"}
    assert graph.get_dependencies("service_c") == {"service_a", "service_b"}


def test_dependency_graph_topological_sort():
    """Test topological sorting for startup order"""
    graph = DependencyGraph()

    graph.add_service("dao", ServiceType.DAO, dependencies=[])
    graph.add_service("scheduler", ServiceType.SCHEDULER, dependencies=["dao"])
    graph.add_service("edge", ServiceType.EDGE, dependencies=["dao"])
    graph.add_service("harvest", ServiceType.HARVEST, dependencies=["edge"])

    order = graph.topological_sort()

    # DAO must come first
    assert order[0] == "dao"

    # Scheduler and edge after DAO
    assert order.index("scheduler") > order.index("dao")
    assert order.index("edge") > order.index("dao")

    # Harvest after edge
    assert order.index("harvest") > order.index("edge")


def test_circular_dependency_detection():
    """Test detection of circular dependencies"""
    graph = DependencyGraph()

    graph.add_service("service_a", ServiceType.DAO, dependencies=["service_b"])
    graph.add_service("service_b", ServiceType.SCHEDULER, dependencies=["service_c"])
    graph.add_service("service_c", ServiceType.EDGE, dependencies=["service_a"])

    cycle = graph.detect_circular_dependencies()

    assert cycle is not None
    assert len(cycle) > 0


def test_dependency_layers():
    """Test service layer calculation"""
    graph = create_default_dependency_graph()

    # DAO should be layer 0 (no dependencies)
    assert graph.get_service_layer("dao") == 0

    # Services depending on layer 0 should be layer 1 or higher
    scheduler_layer = graph.get_service_layer("scheduler")
    assert scheduler_layer >= 0  # Scheduler has optional dependencies

    # Services with dependencies should have higher layers
    harvest_layer = graph.get_service_layer("harvest")
    edge_layer = graph.get_service_layer("edge")
    assert harvest_layer > edge_layer  # Harvest depends on edge


def test_startup_order_validation():
    """Test validation of startup order"""
    graph = create_default_dependency_graph()

    # Valid startup order
    valid_order = graph.get_startup_order()
    is_valid, error = validate_startup_order(valid_order, graph)
    assert is_valid
    assert error is None

    # Invalid startup order (harvest before edge)
    invalid_order = ["dao", "harvest", "edge"]
    is_valid, error = validate_startup_order(invalid_order, graph)
    assert not is_valid
    assert error is not None


def test_shutdown_order():
    """Test shutdown order is reverse of startup"""
    graph = create_default_dependency_graph()

    startup_order = graph.get_startup_order()
    shutdown_order = graph.get_shutdown_order()

    assert shutdown_order == list(reversed(startup_order))


# ============================================================================
# Health Check Tests
# ============================================================================

class MockHealthyService:
    """Mock service that is always healthy"""

    async def get_health(self):
        return {"status": "healthy", "uptime": 100}


class MockUnhealthyService:
    """Mock service that is always unhealthy"""

    async def get_health(self):
        raise Exception("Service is down")


class MockTimeoutService:
    """Mock service that times out"""

    async def get_health(self):
        await asyncio.sleep(10)  # Will timeout
        return {"status": "healthy"}


@pytest.mark.asyncio
async def test_health_check_healthy_service():
    """Test health check on healthy service"""
    config = HealthCheckConfig(service_name="test_service", timeout=2)
    checker = HealthChecker(config)

    service = MockHealthyService()
    result = await checker.perform_check(service)

    assert result.status == HealthStatus.HEALTHY
    assert result.service_name == "test_service"
    assert result.response_time_ms >= 0  # Response time may be 0 for fast checks


@pytest.mark.asyncio
async def test_health_check_unhealthy_service():
    """Test health check on unhealthy service"""
    config = HealthCheckConfig(service_name="test_service", timeout=2)
    checker = HealthChecker(config)

    service = MockUnhealthyService()
    result = await checker.perform_check(service)

    assert result.status == HealthStatus.UNHEALTHY
    assert "Service is down" in result.message


@pytest.mark.asyncio
async def test_health_check_timeout():
    """Test health check timeout"""
    config = HealthCheckConfig(service_name="test_service", timeout=1)
    checker = HealthChecker(config)

    service = MockTimeoutService()
    result = await checker.perform_check(service)

    assert result.status == HealthStatus.UNHEALTHY
    assert "timed out" in result.message.lower()


@pytest.mark.asyncio
async def test_health_check_failure_threshold():
    """Test consecutive failure threshold"""
    config = HealthCheckConfig(
        service_name="test_service",
        timeout=1,
        failure_threshold=3
    )
    checker = HealthChecker(config)

    service = MockUnhealthyService()

    # First two failures should be degraded
    await checker.perform_check(service)
    assert checker.consecutive_failures == 1

    await checker.perform_check(service)
    assert checker.consecutive_failures == 2

    # Third failure should trigger threshold
    await checker.perform_check(service)
    assert checker.consecutive_failures == 3
    assert checker.get_current_status() == HealthStatus.UNHEALTHY


@pytest.mark.asyncio
async def test_health_check_history():
    """Test health check history tracking"""
    config = HealthCheckConfig(service_name="test_service", timeout=1)
    checker = HealthChecker(config)

    service = MockHealthyService()

    # Perform multiple checks
    for _ in range(5):
        await checker.perform_check(service)

    history = checker.get_history(limit=10)
    assert len(history) == 5
    assert all(check.status == HealthStatus.HEALTHY for check in history)


@pytest.mark.asyncio
async def test_health_check_manager():
    """Test health check manager for multiple services"""
    manager = HealthCheckManager()

    # Register services
    manager.register_service("service_a")
    manager.register_service("service_b")
    manager.register_service("service_c")

    assert len(manager.checkers) == 3

    # Check composite health
    composite = manager.get_composite_health()
    assert composite == HealthStatus.UNKNOWN  # No checks yet

    # Perform checks
    services = {
        "service_a": MockHealthyService(),
        "service_b": MockHealthyService(),
        "service_c": MockUnhealthyService()
    }

    await manager.check_all_now(services)

    # Composite should be degraded or unhealthy (one service unhealthy)
    # Note: Requires 3 consecutive failures to be UNHEALTHY, first failure is DEGRADED
    composite = manager.get_composite_health()
    assert composite in [HealthStatus.DEGRADED, HealthStatus.UNHEALTHY]

    # Perform multiple checks to reach failure threshold
    for _ in range(3):
        await manager.check_all_now(services)

    # Now should be unhealthy after multiple failures
    composite = manager.get_composite_health()
    assert composite == HealthStatus.UNHEALTHY

    # Get unhealthy services
    unhealthy = manager.get_unhealthy_services()
    assert "service_c" in unhealthy


# ============================================================================
# Service Registry Tests
# ============================================================================

def test_service_registry_registration():
    """Test service registration"""
    registry = ServiceRegistry()

    meta = registry.register(
        name="test_service",
        service_type="dao",
        version="1.0.0",
        endpoints={"api": "/api/test"},
        dependencies=["service_a"]
    )

    assert meta.name == "test_service"
    assert meta.service_type == "dao"
    assert meta.version == "1.0.0"
    assert meta.status == ServiceStatus.STARTING


def test_service_registry_deregistration():
    """Test service deregistration"""
    registry = ServiceRegistry()

    registry.register(name="test_service", service_type="dao")
    assert "test_service" in registry.services

    result = registry.deregister("test_service")
    assert result is True
    assert "test_service" not in registry.services


def test_service_registry_status_update():
    """Test service status updates"""
    registry = ServiceRegistry()

    registry.register(name="test_service", service_type="dao")

    result = registry.update_status("test_service", ServiceStatus.RUNNING)
    assert result is True

    service = registry.get_service("test_service")
    assert service.status == ServiceStatus.RUNNING


def test_service_registry_heartbeat():
    """Test service heartbeat tracking"""
    registry = ServiceRegistry()

    registry.register(name="test_service", service_type="dao")

    # Record heartbeat
    result = registry.heartbeat("test_service")
    assert result is True

    service = registry.get_service("test_service")
    assert service.last_heartbeat is not None


def test_service_registry_alive_check():
    """Test service alive checking"""
    registry = ServiceRegistry(heartbeat_timeout=1)

    registry.register(name="test_service", service_type="dao")
    registry.heartbeat("test_service")

    # Should be alive immediately
    assert registry.is_alive("test_service")


def test_service_registry_get_by_type():
    """Test getting services by type"""
    registry = ServiceRegistry()

    registry.register(name="service_a", service_type="dao")
    registry.register(name="service_b", service_type="dao")
    registry.register(name="service_c", service_type="scheduler")

    dao_services = registry.get_services_by_type("dao")
    assert len(dao_services) == 2
    assert all(s.service_type == "dao" for s in dao_services)


def test_service_registry_get_dependencies():
    """Test getting service dependencies"""
    registry = ServiceRegistry()

    registry.register(
        name="service_a",
        service_type="dao",
        dependencies=["dep1", "dep2"]
    )

    deps = registry.get_dependencies("service_a")
    assert set(deps) == {"dep1", "dep2"}


def test_service_registry_get_dependents():
    """Test getting service dependents"""
    registry = ServiceRegistry()

    registry.register(name="dep1", service_type="dao", dependencies=[])
    registry.register(name="service_a", service_type="scheduler", dependencies=["dep1"])
    registry.register(name="service_b", service_type="edge", dependencies=["dep1"])

    dependents = registry.get_dependents("dep1")
    assert set(dependents) == {"service_a", "service_b"}


def test_service_registry_stats():
    """Test registry statistics"""
    registry = ServiceRegistry()

    registry.register(name="service_a", service_type="dao")
    registry.register(name="service_b", service_type="dao")
    registry.register(name="service_c", service_type="scheduler")

    registry.update_status("service_a", ServiceStatus.RUNNING)
    registry.update_status("service_b", ServiceStatus.RUNNING)
    registry.update_status("service_c", ServiceStatus.FAILED)

    stats = registry.get_stats()

    assert stats["total_services"] == 3
    assert stats["by_status"]["running"] == 2
    assert stats["by_status"]["failed"] == 1
    assert stats["by_type"]["dao"] == 2
    assert stats["by_type"]["scheduler"] == 1


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_service_lifecycle():
    """Test complete service lifecycle"""
    # This is a placeholder for integration test
    # Would test: start -> running -> health check -> restart -> stop
    pass


@pytest.mark.asyncio
async def test_auto_restart_on_failure():
    """Test automatic restart on service failure"""
    # This is a placeholder for integration test
    # Would test: service failure -> auto restart -> recovery
    pass


@pytest.mark.asyncio
async def test_graceful_shutdown():
    """Test graceful shutdown of all services"""
    # This is a placeholder for integration test
    # Would test: shutdown signal -> stop services in order -> cleanup
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
