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

        # VPN/Onion DISABLED: cryptography library causes Rust panic (pyo3_runtime.PanicException)
        # This is a system-level issue with cryptography package + Rust bindings
        # TODO: Fix in Week 2 by reinstalling cryptography or using alternative crypto library
        logger.warning("⚠️  VPN/Onion services disabled (cryptography dependency issue)")
        self.services['onion'] = None
        self.services['vpn_coordinator'] = None
        # await self._init_vpn_onion()  # Commented out until cryptography fixed

        await self._init_p2p()
        await self._init_betanet_client()

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
            config.database_path = "./backend/data/dao_tokenomics.db"

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
            from vpn.fog_onion_coordinator import FogOnionCoordinator

            self.services['onion'] = OnionCircuitService()
            self.services['vpn_coordinator'] = FogOnionCoordinator()
            logger.info("✓ VPN/Onion routing services initialized")
        except ImportError as e:
            # cryptography library issue - skip for now
            logger.warning(f"VPN/Onion services skipped (cryptography dependency issue): {e}")
            self.services['onion'] = None
            self.services['vpn_coordinator'] = None
        except Exception as e:
            logger.error(f"Failed to initialize VPN/Onion: {e}")
            self.services['onion'] = None
            self.services['vpn_coordinator'] = None

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

    async def shutdown(self) -> None:
        """Gracefully shutdown all services"""
        logger.info("Shutting down services...")

        # Cleanup services that need it
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
