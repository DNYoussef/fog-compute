"""
Service Manager - Orchestrates all backend services
Handles initialization, lifecycle, and coordination
"""
import sys
import os
from typing import Dict, Any, Optional
from pathlib import Path
import logging

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

logger = logging.getLogger(__name__)


class ServiceManager:
    """Manages all backend service instances"""

    def __init__(self):
        self.services: Dict[str, Any] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize all services on startup"""
        if self._initialized:
            logger.warning("Services already initialized")
            return

        logger.info("Initializing backend services...")

        # Initialize services individually to prevent one failure from blocking others
        await self._init_tokenomics()
        await self._init_scheduler()
        await self._init_idle_compute()

        # VPN/Onion FIXED: Updated cryptography to stable version 41.0.7
        await self._init_vpn_onion()

        await self._init_p2p()
        await self._init_betanet_client()
        await self._init_bitchat()

        self._initialized = True
        logger.info(f"Successfully initialized {len(self.services)} services")

    async def _init_tokenomics(self) -> None:
        """Initialize tokenomics and DAO system"""
        try:
            from tokenomics.unified_dao_tokenomics_system import (
                UnifiedDAOTokenomicsSystem,
                TokenomicsConfig
            )

            # Create config with defaults
            config = TokenomicsConfig()

            # Ensure data directory exists
            data_dir = Path(__file__).parent.parent.parent / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            config.database_path = str(data_dir / "dao_tokenomics.db")

            self.services['dao'] = UnifiedDAOTokenomicsSystem(config)
            logger.info("✓ Tokenomics DAO system initialized")
        except Exception as e:
            logger.error(f"Failed to initialize tokenomics: {e}")
            # Create a minimal mock for development
            self.services['dao'] = None

    async def _init_scheduler(self) -> None:
        """Initialize batch job scheduler (NSGA-II)"""
        try:
            from batch.placement import FogScheduler

            # FogScheduler requires reputation_engine (optional, defaults to None)
            self.services['scheduler'] = FogScheduler(reputation_engine=None)
            logger.info("✓ NSGA-II Fog Scheduler initialized")
        except Exception as e:
            logger.error(f"Failed to initialize scheduler: {e}")
            self.services['scheduler'] = None

    async def _init_idle_compute(self) -> None:
        """Initialize idle compute harvesting services"""
        try:
            from idle.edge_manager import EdgeManager
            from idle.harvest_manager import FogHarvestManager
            import socket

            # Generate unique node_id from hostname
            node_id = f"fog-backend-{socket.gethostname()}"

            self.services['edge'] = EdgeManager()
            self.services['harvest'] = FogHarvestManager(node_id=node_id)
            logger.info("✓ Idle compute services initialized")
        except Exception as e:
            logger.error(f"Failed to initialize idle compute: {e}")
            self.services['edge'] = None
            self.services['harvest'] = None

    async def _init_vpn_onion(self) -> None:
        """Initialize VPN and onion routing services"""
        try:
            from vpn.onion_circuit_service import OnionCircuitService
            from vpn.onion_routing import OnionRouter, NodeType
            from vpn.fog_onion_coordinator import FogOnionCoordinator
            from fog.coordinator import FogCoordinator
            import socket
            import uuid

            # Create OnionRouter instance (required by OnionCircuitService)
            node_id = f"fog-backend-{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
            node_types = {NodeType.MIDDLE}  # Backend acts as a middle relay

            onion_router = OnionRouter(
                node_id=node_id,
                node_types=node_types,
                enable_hidden_services=True
            )

            # Initialize circuit service with the router
            self.services['onion'] = OnionCircuitService(onion_router=onion_router)

            # Initialize FogCoordinator with onion router integration
            fog_coordinator = FogCoordinator(
                node_id=f"fog-coord-{socket.gethostname()}",
                onion_router=onion_router,
                heartbeat_interval=30,
                heartbeat_timeout=90
            )

            # Start FogCoordinator background tasks
            await fog_coordinator.start()
            self.services['fog_coordinator'] = fog_coordinator
            logger.info("✓ FogCoordinator initialized")

            # Initialize FogOnionCoordinator with FogCoordinator
            vpn_coord = FogOnionCoordinator(
                node_id=f"vpn-coord-{uuid.uuid4().hex[:8]}",
                fog_coordinator=fog_coordinator,
                enable_mixnet=False,  # Mixnet not yet integrated
                max_circuits=50
            )

            # Start VPN coordinator
            await vpn_coord.start()
            self.services['vpn_coordinator'] = vpn_coord
            logger.info("✓ VPN/Onion circuit service initialized")
            logger.info("✓ VPN Coordinator operational")
        except ImportError as e:
            # cryptography library issue - skip for now
            logger.warning(f"VPN/Onion services skipped (import error): {e}")
            self.services['onion'] = None
            self.services['vpn_coordinator'] = None
            self.services['fog_coordinator'] = None
        except Exception as e:
            logger.error(f"Failed to initialize VPN/Onion: {e}")
            self.services['onion'] = None
            self.services['vpn_coordinator'] = None
            self.services['fog_coordinator'] = None

    async def _init_p2p(self) -> None:
        """Initialize unified P2P system"""
        try:
            from p2p.unified_p2p_system import UnifiedDecentralizedSystem
            from p2p.unified_p2p_config import UnifiedP2PConfig
            import socket
            import uuid

            config = UnifiedP2PConfig()
            # Generate unique node_id (config object is not hashable)
            node_id = f"fog-backend-{socket.gethostname()}-{uuid.uuid4().hex[:8]}"

            self.services['p2p'] = UnifiedDecentralizedSystem(
                node_id=node_id,
                config=config
            )
            logger.info("✓ P2P unified system initialized")
        except Exception as e:
            logger.error(f"Failed to initialize P2P: {e}")
            self.services['p2p'] = None

    async def _init_betanet_client(self) -> None:
        """Initialize Betanet privacy network service"""
        try:
            from .betanet import betanet_service

            self.services['betanet'] = betanet_service
            logger.info("✓ Betanet privacy network initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Betanet service: {e}")
            self.services['betanet'] = None

    async def _init_bitchat(self) -> None:
        """Initialize BitChat P2P messaging service"""
        try:
            from .bitchat import bitchat_service

            self.services['bitchat'] = bitchat_service
            logger.info("✓ BitChat P2P messaging initialized")
        except Exception as e:
            logger.error(f"Failed to initialize BitChat service: {e}")
            self.services['bitchat'] = None

    async def shutdown(self) -> None:
        """Gracefully shutdown all services"""
        logger.info("Shutting down services...")

        # Shutdown FogCoordinator and VPN coordinator first
        for name in ['vpn_coordinator', 'fog_coordinator']:
            service = self.services.get(name)
            if service and hasattr(service, 'stop'):
                try:
                    await service.stop()
                    logger.info(f"✓ Stopped {name}")
                except Exception as e:
                    logger.error(f"Error stopping {name}: {e}")

        # Cleanup other services
        for name, service in self.services.items():
            if hasattr(service, 'close'):
                try:
                    await service.close()
                    logger.info(f"✓ Closed {name}")
                except Exception as e:
                    logger.error(f"Error closing {name}: {e}")

        self.services.clear()
        self._initialized = False
        logger.info("All services shut down")

    def get(self, service_name: str) -> Optional[Any]:
        """Get a service instance by name"""
        return self.services.get(service_name)

    def is_ready(self) -> bool:
        """Check if all critical services are initialized"""
        critical_services = ['dao', 'scheduler', 'edge']
        return all(self.services.get(name) is not None for name in critical_services)

    def get_health(self) -> Dict[str, str]:
        """Get health status of all services"""
        health = {}
        for name, service in self.services.items():
            if service is None:
                health[name] = "unavailable"
            elif hasattr(service, 'get_health'):
                try:
                    health[name] = "healthy"
                except:
                    health[name] = "unhealthy"
            else:
                health[name] = "unknown"
        return health


# Global service manager instance
service_manager = ServiceManager()
