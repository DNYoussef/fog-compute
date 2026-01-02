"""
Enhanced Service Manager - Orchestrates all backend services
Handles lifecycle, health checks, auto-restart, and dependency management
"""
import sys
import os
from typing import Dict, Any, Optional, Set
from pathlib import Path
import logging
import asyncio
from datetime import datetime

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from .dependencies import (
    DependencyGraph,
    create_default_dependency_graph,
    validate_startup_order
)
from .health_checks import (
    HealthCheckManager,
    HealthCheckConfig,
    HealthStatus,
    HealthCheckResult
)
from .registry import ServiceRegistry, ServiceStatus, ServiceMetadata

logger = logging.getLogger(__name__)


class ServiceState:
    """Tracks state for a service"""

    def __init__(self, name: str):
        self.name = name
        self.instance: Optional[Any] = None
        self.status = ServiceStatus.STOPPED
        self.restart_count = 0
        self.last_restart: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self.is_critical = True  # Critical services block startup if failed


class EnhancedServiceManager:
    """
    Enhanced Service Manager with:
    - Service lifecycle management (start, stop, restart)
    - Dependency graph resolution
    - Auto-restart on failure (max 3 retries, exponential backoff)
    - Graceful shutdown (30s timeout, force kill)
    - Health check monitoring (every 30s)
    - Service status tracking
    """

    def __init__(
        self,
        max_restart_attempts: int = 3,
        restart_backoff_base: float = 2.0,
        shutdown_timeout: int = 30,
        health_check_interval: int = 30
    ):
        """
        Initialize Enhanced Service Manager

        Args:
            max_restart_attempts: Maximum restart attempts before giving up
            restart_backoff_base: Base for exponential backoff (seconds)
            shutdown_timeout: Timeout for graceful shutdown (seconds)
            health_check_interval: Health check interval (seconds)
        """
        self.services: Dict[str, ServiceState] = {}
        self._initialized = False

        # Configuration
        self.max_restart_attempts = max_restart_attempts
        self.restart_backoff_base = restart_backoff_base
        self.shutdown_timeout = shutdown_timeout
        self.health_check_interval = health_check_interval

        # Dependency management
        self.dependency_graph = create_default_dependency_graph()

        # Health check system
        self.health_manager = HealthCheckManager()

        # Service registry
        self.registry = ServiceRegistry(
            heartbeat_interval=60,
            heartbeat_timeout=180
        )

        # Shutdown event
        self._shutdown_event = asyncio.Event()
        self._health_monitor_task: Optional[asyncio.Task] = None

        # Initialize service states
        self._init_service_states()

    def _init_service_states(self) -> None:
        """Initialize service states from dependency graph"""
        for service_name in self.dependency_graph.nodes.keys():
            self.services[service_name] = ServiceState(service_name)

            # Register health checker
            config = HealthCheckConfig(
                service_name=service_name,
                check_interval=self.health_check_interval,
                failure_threshold=3,
                recovery_threshold=2,
                auto_recovery=True
            )
            checker = self.health_manager.register_service(service_name, config)

            # Set up failure callback for auto-restart
            checker.on_failure_callback = self._handle_service_failure

    async def _handle_service_failure(self, result: HealthCheckResult) -> None:
        """Handle service failure with auto-restart"""
        service_name = result.service_name
        state = self.services.get(service_name)

        if not state:
            return

        logger.warning(
            f"Service {service_name} failed health check: {result.message}"
        )

        # Check if we should auto-restart
        if state.restart_count >= self.max_restart_attempts:
            logger.error(
                f"Service {service_name} exceeded max restart attempts "
                f"({self.max_restart_attempts}), giving up"
            )
            state.status = ServiceStatus.FAILED
            self.registry.update_status(service_name, ServiceStatus.FAILED)
            return

        # Attempt restart with exponential backoff
        backoff_time = self.restart_backoff_base ** state.restart_count
        logger.info(
            f"Attempting restart of {service_name} in {backoff_time}s "
            f"(attempt {state.restart_count + 1}/{self.max_restart_attempts})"
        )

        await asyncio.sleep(backoff_time)

        try:
            await self.restart_service(service_name)
        except Exception as e:
            logger.error(f"Failed to restart {service_name}: {e}")
            state.last_error = str(e)

    async def initialize(self) -> None:
        """Initialize all services in dependency order"""
        if self._initialized:
            logger.warning("Services already initialized")
            return

        is_ci = os.getenv('CI') == 'true'
        skip_external = os.getenv('SKIP_EXTERNAL_SERVICES', '').lower() == 'true' or is_ci
        init_timeout = int(os.getenv('SERVICE_INIT_TIMEOUT', '30'))

        skip_services: Set[str] = set()
        if skip_external:
            skip_services.update({
                "p2p",
                "betanet",
                "bitchat",
                "vpn_coordinator",
                "onion"
            })

        logger.info("=" * 60)
        logger.info("Enhanced Service Manager - Initializing Services")
        logger.info("=" * 60)

        # Get startup order from dependency graph
        startup_order = self.dependency_graph.get_startup_order()

        logger.info("\nStartup Order:")
        for i, service_name in enumerate(startup_order, 1):
            layer = self.dependency_graph.get_service_layer(service_name)
            logger.info(f"  {i}. {service_name} (Layer {layer})")

        # Validate startup order
        is_valid, error = validate_startup_order(startup_order, self.dependency_graph)
        if not is_valid:
            raise RuntimeError(f"Invalid startup order: {error}")

        logger.info("\nInitializing services...")

        # Start registry monitoring
        await self.registry.start_monitoring()

        # Initialize services in order
        for service_name in startup_order:
            if service_name in skip_services:
                logger.info(f"  Skipping {service_name} (non-essential in CI)")
                state = self.services[service_name]
                state.status = ServiceStatus.STOPPED
                state.is_critical = False
                self.registry.update_status(service_name, ServiceStatus.STOPPED)
                continue

            try:
                await asyncio.wait_for(
                    self._initialize_service(service_name),
                    timeout=init_timeout
                )
            except Exception as e:
                logger.error(f"Failed to initialize {service_name}: {e}")
                state = self.services[service_name]
                state.status = ServiceStatus.FAILED
                state.last_error = str(e)
                self.registry.update_status(service_name, ServiceStatus.FAILED)

                if isinstance(e, asyncio.TimeoutError):
                    state.last_error = f"Initialization timed out after {init_timeout}s"

                # Stop if critical service failed
                if state.is_critical:
                    logger.error(f"Critical service {service_name} failed, aborting initialization")
                    raise

        # Start health monitoring
        service_instances = {
            name: state.instance
            for name, state in self.services.items()
            if state.instance is not None
        }
        await self.health_manager.start_all(service_instances)

        self._initialized = True

        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info("Service Initialization Summary")
        logger.info("=" * 60)

        running_count = sum(1 for s in self.services.values() if s.status == ServiceStatus.RUNNING)
        failed_count = sum(1 for s in self.services.values() if s.status == ServiceStatus.FAILED)

        logger.info(f"✓ Running: {running_count}/{len(self.services)}")
        if failed_count > 0:
            logger.warning(f"✗ Failed: {failed_count}/{len(self.services)}")

        logger.info("\nDependency Graph:")
        logger.info(self.dependency_graph.visualize())

    async def _initialize_service(self, service_name: str) -> None:
        """Initialize a single service"""
        state = self.services[service_name]
        state.status = ServiceStatus.STARTING

        # Register in service registry
        service_type = self.dependency_graph.nodes[service_name].service_type.value
        dependencies = list(self.dependency_graph.get_dependencies(service_name))
        optional_deps = list(self.dependency_graph.get_optional_dependencies(service_name))

        self.registry.register(
            name=service_name,
            service_type=service_type,
            dependencies=dependencies,
            optional_dependencies=optional_deps
        )

        logger.info(f"  Initializing {service_name}...")

        # Service-specific initialization
        try:
            if service_name == "dao":
                await self._init_tokenomics()
            elif service_name == "scheduler":
                await self._init_scheduler()
            elif service_name == "edge":
                await self._init_edge()
            elif service_name == "harvest":
                await self._init_harvest()
            elif service_name == "fog_coordinator":
                await self._init_fog_coordinator()
            elif service_name == "onion":
                await self._init_onion()
            elif service_name == "vpn_coordinator":
                await self._init_vpn_coordinator()
            elif service_name == "p2p":
                await self._init_p2p()
            elif service_name == "betanet":
                await self._init_betanet()
            elif service_name == "bitchat":
                await self._init_bitchat()

            state.status = ServiceStatus.RUNNING
            self.registry.update_status(service_name, ServiceStatus.RUNNING)
            self.registry.heartbeat(service_name)

            logger.info(f"    ✓ {service_name} initialized successfully")

        except Exception as e:
            state.status = ServiceStatus.FAILED
            state.last_error = str(e)
            self.registry.update_status(service_name, ServiceStatus.FAILED)
            logger.error(f"    ✗ {service_name} initialization failed: {e}")
            raise

    # Service initialization methods (from original service_manager.py)
    async def _init_tokenomics(self) -> None:
        """Initialize tokenomics and DAO system"""
        try:
            from tokenomics.unified_dao_tokenomics_system import (
                UnifiedDAOTokenomicsSystem,
                TokenomicsConfig
            )

            config = TokenomicsConfig()
            data_dir = Path(__file__).parent.parent.parent / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            config.database_path = str(data_dir / "dao_tokenomics.db")

            # Instantiate the system
            system = UnifiedDAOTokenomicsSystem(config)

            # CRITICAL: Await the initialize() coroutine to open SQLite connections
            initialization_success = await system.initialize()

            if not initialization_success:
                raise RuntimeError("Tokenomics system initialization returned False")

            # Only set instance after successful initialization
            self.services['dao'].instance = system
            logger.info("Tokenomics system initialized successfully with database connections")

        except Exception as e:
            logger.error(f"Failed to initialize tokenomics: {e}")
            self.services['dao'].instance = None
            # Fail fast: Mark as critical and re-raise to stop initialization
            self.services['dao'].is_critical = True
            raise RuntimeError(f"Critical service 'dao' failed to initialize: {e}") from e

    async def _init_scheduler(self) -> None:
        """Initialize batch job scheduler (NSGA-II)"""
        try:
            from batch.placement import FogScheduler
            self.services['scheduler'].instance = FogScheduler(reputation_engine=None)
        except Exception as e:
            logger.error(f"Failed to initialize scheduler: {e}")
            self.services['scheduler'].instance = None

    async def _init_edge(self) -> None:
        """Initialize edge manager"""
        try:
            from idle.edge_manager import EdgeManager
            self.services['edge'].instance = EdgeManager()
        except Exception as e:
            logger.error(f"Failed to initialize edge manager: {e}")
            self.services['edge'].instance = None

    async def _init_harvest(self) -> None:
        """Initialize harvest manager"""
        try:
            from idle.harvest_manager import FogHarvestManager
            import socket

            node_id = f"fog-backend-{socket.gethostname()}"
            self.services['harvest'].instance = FogHarvestManager(node_id=node_id)
        except Exception as e:
            logger.error(f"Failed to initialize harvest manager: {e}")
            self.services['harvest'].instance = None

    async def _init_fog_coordinator(self) -> None:
        """Initialize FOG coordinator"""
        try:
            from fog.coordinator import FogCoordinator
            import socket

            node_id = f"fog-coord-{socket.gethostname()}"

            # Get onion router if available
            onion_router = None
            if 'onion' in self.services and self.services['onion'].instance:
                onion_router = getattr(self.services['onion'].instance, 'onion_router', None)

            coordinator = FogCoordinator(
                node_id=node_id,
                onion_router=onion_router,
                heartbeat_interval=30,
                heartbeat_timeout=90
            )

            await coordinator.start()
            self.services['fog_coordinator'].instance = coordinator
        except Exception as e:
            logger.error(f"Failed to initialize fog coordinator: {e}")
            self.services['fog_coordinator'].instance = None

    async def _init_onion(self) -> None:
        """Initialize onion routing"""
        try:
            from vpn.onion_circuit_service import OnionCircuitService
            from vpn.onion_routing import OnionRouter, NodeType
            import socket
            import uuid

            node_id = f"fog-backend-{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
            node_types = {NodeType.MIDDLE}

            onion_router = OnionRouter(
                node_id=node_id,
                node_types=node_types,
                enable_hidden_services=True
            )

            self.services['onion'].instance = OnionCircuitService(onion_router=onion_router)
        except ImportError as e:
            logger.warning(f"Onion routing skipped (import error): {e}")
            self.services['onion'].instance = None
            self.services['onion'].is_critical = False

    async def _init_vpn_coordinator(self) -> None:
        """Initialize VPN coordinator"""
        try:
            from vpn.fog_onion_coordinator import FogOnionCoordinator
            import uuid

            # Get fog coordinator
            fog_coordinator = self.services.get('fog_coordinator')
            if not fog_coordinator or not fog_coordinator.instance:
                raise RuntimeError("FOG coordinator not available")

            vpn_coord = FogOnionCoordinator(
                node_id=f"vpn-coord-{uuid.uuid4().hex[:8]}",
                fog_coordinator=fog_coordinator.instance,
                enable_mixnet=False,
                max_circuits=50
            )

            await vpn_coord.start()
            self.services['vpn_coordinator'].instance = vpn_coord
        except Exception as e:
            logger.warning(f"VPN coordinator initialization failed: {e}")
            self.services['vpn_coordinator'].instance = None
            self.services['vpn_coordinator'].is_critical = False

    async def _init_p2p(self) -> None:
        """Initialize unified P2P system"""
        try:
            from p2p.unified_p2p_system import UnifiedDecentralizedSystem
            import socket
            import uuid

            timeout_seconds = int(os.getenv('P2P_TIMEOUT', '30'))

            node_id = f"fog-backend-{socket.gethostname()}-{uuid.uuid4().hex[:8]}"

            # Create P2P system instance
            p2p_system = UnifiedDecentralizedSystem(
                node_id=node_id,
                device_name=f"fog-backend-{socket.gethostname()}",
                enable_bitchat=True,
                enable_betanet=True,
                enable_mobile_bridge=False,
                enable_fog_bridge=True
            )

            # Start the P2P system
            started = await asyncio.wait_for(
                p2p_system.start(),
                timeout=timeout_seconds
            )
            if not started:
                logger.warning("P2P system failed to start, but continuing with limited functionality")

            self.services['p2p'].instance = p2p_system
            logger.info(f"P2P system initialized and started for node {node_id}")

        except Exception as e:
            logger.error(f"Failed to initialize P2P: {e}")
            self.services['p2p'].instance = None

            state = self.services.get('p2p')
            if state:
                state.is_critical = False

    async def _init_betanet(self) -> None:
        """Initialize Betanet privacy network"""
        try:
            from .betanet_client import BetanetClient
            betanet_client = BetanetClient(url="http://localhost:9000", timeout=5)
            self.services['betanet'].instance = betanet_client
        except Exception as e:
            logger.error(f"Failed to initialize Betanet: {e}")
            self.services['betanet'].instance = None
            self.services['betanet'].is_critical = False

    async def _init_bitchat(self) -> None:
        """Initialize BitChat P2P messaging"""
        try:
            from .bitchat import bitchat_service
            self.services['bitchat'].instance = bitchat_service
        except Exception as e:
            logger.error(f"Failed to initialize BitChat: {e}")
            self.services['bitchat'].instance = None
            self.services['bitchat'].is_critical = False

    async def restart_service(self, service_name: str) -> None:
        """Restart a specific service"""
        if service_name not in self.services:
            raise ValueError(f"Unknown service: {service_name}")

        state = self.services[service_name]
        logger.info(f"Restarting service: {service_name}")

        # Stop service
        await self._stop_service(service_name)

        # Wait a bit
        await asyncio.sleep(1)

        # Start service
        await self._initialize_service(service_name)

        # Update restart tracking
        state.restart_count += 1
        state.last_restart = datetime.now()

        logger.info(f"Service {service_name} restarted (attempt {state.restart_count})")

    async def _stop_service(self, service_name: str) -> None:
        """Stop a single service"""
        state = self.services.get(service_name)
        if not state or not state.instance:
            return

        state.status = ServiceStatus.STOPPING
        self.registry.update_status(service_name, ServiceStatus.STOPPING)

        try:
            # Try graceful shutdown methods
            if hasattr(state.instance, 'stop'):
                await asyncio.wait_for(
                    state.instance.stop(),
                    timeout=self.shutdown_timeout
                )
            elif hasattr(state.instance, 'close'):
                await asyncio.wait_for(
                    state.instance.close(),
                    timeout=self.shutdown_timeout
                )

            state.status = ServiceStatus.STOPPED
            self.registry.update_status(service_name, ServiceStatus.STOPPED)

        except asyncio.TimeoutError:
            logger.warning(f"Service {service_name} shutdown timed out, forcing stop")
            state.status = ServiceStatus.STOPPED
            self.registry.update_status(service_name, ServiceStatus.STOPPED)
        except Exception as e:
            logger.error(f"Error stopping {service_name}: {e}")
            state.status = ServiceStatus.FAILED
            self.registry.update_status(service_name, ServiceStatus.FAILED)

    async def shutdown(self) -> None:
        """Gracefully shutdown all services in reverse dependency order"""
        logger.info("\n" + "=" * 60)
        logger.info("Enhanced Service Manager - Graceful Shutdown")
        logger.info("=" * 60)

        # Set shutdown event
        self._shutdown_event.set()

        # Stop health monitoring
        await self.health_manager.stop_all()

        # Get shutdown order (reverse of startup)
        shutdown_order = self.dependency_graph.get_shutdown_order()

        logger.info("\nShutdown Order:")
        for i, service_name in enumerate(shutdown_order, 1):
            logger.info(f"  {i}. {service_name}")

        # Shutdown services
        for service_name in shutdown_order:
            try:
                logger.info(f"  Stopping {service_name}...")
                await self._stop_service(service_name)
                logger.info(f"    ✓ {service_name} stopped")
            except Exception as e:
                logger.error(f"    ✗ Error stopping {service_name}: {e}")

        # Stop registry monitoring
        await self.registry.stop_monitoring()

        # Clear service instances
        for state in self.services.values():
            state.instance = None
            state.status = ServiceStatus.STOPPED

        self._initialized = False

        logger.info("\n" + "=" * 60)
        logger.info("All services shut down gracefully")
        logger.info("=" * 60)

    def get(self, service_name: str) -> Optional[Any]:
        """Get a service instance by name"""
        state = self.services.get(service_name)
        return state.instance if state else None

    @property
    def betanet_client(self) -> Optional[Any]:
        """Get Betanet client instance"""
        return self.get('betanet')

    def is_ready(self) -> bool:
        """Check if all critical services are running"""
        critical_services = [
            name for name, state in self.services.items()
            if state.is_critical
        ]

        return all(
            self.services[name].status == ServiceStatus.RUNNING
            for name in critical_services
        )

    def get_health(self) -> Dict[str, str]:
        """Get health status of all services"""
        return self.health_manager.get_all_statuses()

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status of all services"""
        return {
            "services": {
                name: {
                    "status": state.status.value,
                    "restart_count": state.restart_count,
                    "last_restart": state.last_restart.isoformat() if state.last_restart else None,
                    "last_error": state.last_error,
                    "is_critical": state.is_critical
                }
                for name, state in self.services.items()
            },
            "health": self.get_health(),
            "registry": self.registry.get_stats(),
            "is_ready": self.is_ready(),
            "initialized": self._initialized
        }

    def get_readiness_summary(self) -> Dict[str, Any]:
        """Return readiness including skipped and failed optional services."""
        critical_services = {
            name for name, state in self.services.items()
            if state.is_critical
        }

        non_critical_failed = []
        skipped_services = []

        for name, state in self.services.items():
            if not state.is_critical and state.status == ServiceStatus.STOPPED and state.instance is None:
                skipped_services.append(name)
            if not state.is_critical and state.status == ServiceStatus.FAILED:
                non_critical_failed.append(name)

        ready = all(
            self.services[name].status == ServiceStatus.RUNNING
            for name in critical_services
        )

        return {
            "ready": ready,
            "critical": sorted(critical_services),
            "non_critical_failed": sorted(non_critical_failed),
            "skipped": sorted(skipped_services)
        }


# Global enhanced service manager instance
enhanced_service_manager = EnhancedServiceManager()
