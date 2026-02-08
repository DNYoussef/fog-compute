"""
Coordinator Discovery for Desktop Agent
mDNS/Bonjour discovery with manual fallback

PHASE3-AGENT-003: Auto-Discovery + Manual Fallback
- mDNS/Bonjour discovery for coordinator on local network
- Fall back to config file (coordinator_url)
- Retry logic with exponential backoff
"""
import asyncio
import logging
import socket
from dataclasses import dataclass
from datetime import datetime, UTC
from enum import Enum
from typing import Optional, Any, Callable, Awaitable

logger = logging.getLogger(__name__)


class DiscoveryMethod(str, Enum):
    """Method used to discover coordinator"""
    MDNS = "mdns"          # mDNS/Bonjour discovery
    MANUAL = "manual"      # Manual configuration
    CACHED = "cached"      # Previously discovered/configured
    FALLBACK = "fallback"  # Fallback URL


@dataclass
class CoordinatorInfo:
    """Discovered coordinator information"""
    url: str
    host: str
    port: int
    method: DiscoveryMethod
    discovered_at: datetime
    tls_enabled: bool = True
    service_name: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "url": self.url,
            "host": self.host,
            "port": self.port,
            "method": self.method.value,
            "discovered_at": self.discovered_at.isoformat(),
            "tls_enabled": self.tls_enabled,
            "service_name": self.service_name,
        }


class CoordinatorDiscovery:
    """
    Discovers coordinator using mDNS or manual configuration.

    PHASE3-AGENT-003: Auto-Discovery + Manual Fallback.
    Uses exponential backoff for retries.
    """

    def __init__(
        self,
        service_name: str = "_fogburst._tcp.local.",
        default_port: int = 8000,
        manual_url: Optional[str] = None,
        tls_enabled: bool = True,
        discovery_timeout_sec: int = 30,
        max_retries: int = 5,
        base_delay_sec: float = 1.0,
        max_delay_sec: float = 60.0,
    ):
        """
        Initialize coordinator discovery.

        Args:
            service_name: mDNS service name to search for
            default_port: Default coordinator port
            manual_url: Manual coordinator URL override
            tls_enabled: Whether TLS is enabled
            discovery_timeout_sec: mDNS discovery timeout
            max_retries: Maximum retry attempts
            base_delay_sec: Base delay for exponential backoff
            max_delay_sec: Maximum delay between retries
        """
        self.service_name = service_name
        self.default_port = default_port
        self.manual_url = manual_url
        self.tls_enabled = tls_enabled
        self.discovery_timeout_sec = discovery_timeout_sec
        self.max_retries = max_retries
        self.base_delay_sec = base_delay_sec
        self.max_delay_sec = max_delay_sec

        self._current_coordinator: Optional[CoordinatorInfo] = None
        self._zeroconf = None
        self._browser = None

        logger.info(
            f"CoordinatorDiscovery initialized: "
            f"service={service_name}, manual_url={manual_url}"
        )

    async def discover(self) -> Optional[CoordinatorInfo]:
        """
        Discover coordinator with retry logic.

        PHASE3-AGENT-003: Discovery with fallback.

        Returns:
            CoordinatorInfo if found, None otherwise
        """
        # If manual URL is set, use it directly
        if self.manual_url:
            return self._create_manual_coordinator()

        # Try mDNS discovery with retries
        for attempt in range(self.max_retries):
            try:
                coordinator = await self._discover_mdns()
                if coordinator:
                    self._current_coordinator = coordinator
                    logger.info(f"Coordinator discovered via mDNS: {coordinator.url}")
                    return coordinator

            except Exception as e:
                logger.warning(f"mDNS discovery attempt {attempt + 1} failed: {e}")

            # Calculate exponential backoff delay
            delay = min(
                self.base_delay_sec * (2 ** attempt),
                self.max_delay_sec
            )

            logger.info(f"Retrying discovery in {delay:.1f}s...")
            await asyncio.sleep(delay)

        # Fallback: check for cached coordinator
        if self._current_coordinator:
            logger.info("Using cached coordinator")
            return self._current_coordinator

        logger.error("Coordinator discovery failed after all retries")
        return None

    def _create_manual_coordinator(self) -> CoordinatorInfo:
        """Create coordinator info from manual URL."""
        url = self.manual_url
        if not url:
            raise ValueError("Manual URL not set")

        # Parse URL
        if "://" in url:
            protocol, rest = url.split("://", 1)
            tls = protocol == "https"
        else:
            rest = url
            tls = self.tls_enabled

        # Parse host:port
        if ":" in rest:
            host, port_str = rest.rsplit(":", 1)
            # Handle path in URL
            if "/" in port_str:
                port_str = port_str.split("/")[0]
            port = int(port_str)
        else:
            host = rest.split("/")[0]
            port = self.default_port

        # Build full URL
        protocol = "https" if tls else "http"
        full_url = f"{protocol}://{host}:{port}"

        coordinator = CoordinatorInfo(
            url=full_url,
            host=host,
            port=port,
            method=DiscoveryMethod.MANUAL,
            discovered_at=datetime.now(UTC),
            tls_enabled=tls,
        )

        self._current_coordinator = coordinator
        logger.info(f"Using manual coordinator: {full_url}")

        return coordinator

    async def _discover_mdns(self) -> Optional[CoordinatorInfo]:
        """
        Discover coordinator via mDNS/Bonjour.

        PHASE3-AGENT-003: mDNS discovery implementation.
        """
        try:
            from zeroconf.asyncio import AsyncZeroconf, AsyncServiceBrowser
            from zeroconf import ServiceListener, Zeroconf
        except ImportError:
            logger.warning("zeroconf not installed, mDNS discovery unavailable")
            return None

        discovered_services: list[CoordinatorInfo] = []
        discovery_event = asyncio.Event()

        class FogburstListener(ServiceListener):
            """Listener for Fogburst coordinator service."""

            def __init__(self, zc: Zeroconf):
                self.zc = zc

            def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
                """Service discovered."""
                try:
                    info = zc.get_service_info(type_, name)
                    if info:
                        # Get IP address
                        if info.addresses:
                            ip = socket.inet_ntoa(info.addresses[0])
                        else:
                            ip = info.server

                        port = info.port or 8000
                        protocol = "https" if self.parent.tls_enabled else "http"

                        coordinator = CoordinatorInfo(
                            url=f"{protocol}://{ip}:{port}",
                            host=ip,
                            port=port,
                            method=DiscoveryMethod.MDNS,
                            discovered_at=datetime.now(UTC),
                            tls_enabled=self.parent.tls_enabled,
                            service_name=name,
                        )

                        discovered_services.append(coordinator)
                        logger.info(f"mDNS: Found coordinator at {coordinator.url}")

                        discovery_event.set()

                except Exception as e:
                    logger.error(f"Error processing mDNS service: {e}")

            def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
                """Service removed."""
                logger.debug(f"mDNS: Service removed: {name}")

            def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
                """Service updated."""
                logger.debug(f"mDNS: Service updated: {name}")

        try:
            zeroconf = await AsyncZeroconf().__aenter__()
            self._zeroconf = zeroconf

            listener = FogburstListener(zeroconf.zeroconf)
            listener.parent = self

            # Start browsing for service
            browser = AsyncServiceBrowser(
                zeroconf.zeroconf,
                self.service_name,
                listener
            )
            self._browser = browser

            # Wait for discovery or timeout
            try:
                await asyncio.wait_for(
                    discovery_event.wait(),
                    timeout=self.discovery_timeout_sec
                )
            except asyncio.TimeoutError:
                logger.debug(f"mDNS discovery timed out after {self.discovery_timeout_sec}s")

            # Cancel browser
            browser.cancel()

            # Close zeroconf
            await zeroconf.__aexit__(None, None, None)

            if discovered_services:
                return discovered_services[0]

        except Exception as e:
            logger.error(f"mDNS discovery error: {e}")

        return None

    async def verify_coordinator(self, coordinator: CoordinatorInfo) -> bool:
        """
        Verify coordinator is reachable.

        PHASE3-AGENT-003: Health check before use.

        Args:
            coordinator: Coordinator info to verify

        Returns:
            True if reachable
        """
        try:
            import aiohttp

            url = f"{coordinator.url}/health"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        logger.info(f"Coordinator verified: {coordinator.url}")
                        return True
                    else:
                        logger.warning(f"Coordinator health check failed: {response.status}")
                        return False

        except ImportError:
            # aiohttp not available, try basic socket check
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((coordinator.host, coordinator.port))
                sock.close()

                if result == 0:
                    logger.info(f"Coordinator port reachable: {coordinator.url}")
                    return True
                else:
                    logger.warning(f"Coordinator port unreachable")
                    return False

            except Exception as e:
                logger.error(f"Socket check failed: {e}")
                return False

        except Exception as e:
            logger.error(f"Coordinator verification failed: {e}")
            return False

    def set_manual_url(self, url: str) -> None:
        """Set manual coordinator URL."""
        self.manual_url = url
        logger.info(f"Manual coordinator URL set: {url}")

    def get_current_coordinator(self) -> Optional[CoordinatorInfo]:
        """Get currently discovered/configured coordinator."""
        return self._current_coordinator

    def clear_cache(self) -> None:
        """Clear cached coordinator info."""
        self._current_coordinator = None
        logger.info("Coordinator cache cleared")

    async def close(self) -> None:
        """Close discovery resources."""
        if self._browser:
            try:
                self._browser.cancel()
            except Exception:
                pass
            self._browser = None

        if self._zeroconf:
            try:
                await self._zeroconf.__aexit__(None, None, None)
            except Exception:
                pass
            self._zeroconf = None


class RetryWithBackoff:
    """
    Retry helper with exponential backoff.

    PHASE3-AGENT-003: Retry logic with exponential backoff.
    """

    def __init__(
        self,
        max_retries: int = 5,
        base_delay_sec: float = 1.0,
        max_delay_sec: float = 60.0,
        jitter: bool = True,
    ):
        """
        Initialize retry helper.

        Args:
            max_retries: Maximum retry attempts
            base_delay_sec: Base delay between retries
            max_delay_sec: Maximum delay
            jitter: Add random jitter to delays
        """
        self.max_retries = max_retries
        self.base_delay_sec = base_delay_sec
        self.max_delay_sec = max_delay_sec
        self.jitter = jitter
        self._attempt = 0

    def reset(self) -> None:
        """Reset retry counter."""
        self._attempt = 0

    def get_delay(self) -> float:
        """
        Get next delay with exponential backoff.

        Returns:
            Delay in seconds
        """
        import random

        delay = min(
            self.base_delay_sec * (2 ** self._attempt),
            self.max_delay_sec
        )

        if self.jitter:
            delay = delay * (0.5 + random.random())

        self._attempt += 1
        return delay

    def can_retry(self) -> bool:
        """Check if more retries are allowed."""
        return self._attempt < self.max_retries

    @property
    def attempt(self) -> int:
        """Current attempt number (1-indexed)."""
        return self._attempt + 1

    async def execute(
        self,
        func: Callable[..., Awaitable[Any]],
        *args,
        **kwargs
    ) -> Any:
        """
        Execute function with retry logic.

        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Last exception if all retries exhausted
        """
        last_error = None

        while self.can_retry():
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {self.attempt} failed: {e}")

                if not self.can_retry():
                    break

                delay = self.get_delay()
                logger.info(f"Retrying in {delay:.1f}s...")
                await asyncio.sleep(delay)

        raise last_error or RuntimeError("All retries exhausted")
