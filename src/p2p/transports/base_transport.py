#!/usr/bin/env python3
"""
Base Transport Interface
Defines the common interface that all P2P transports must implement
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
import logging

logger = logging.getLogger(__name__)


class TransportType(Enum):
    """Transport type identifiers."""

    BLE_MESH = "ble_mesh"  # BitChat BLE mesh
    HTX_PRIVACY = "htx_privacy"  # BetaNet HTX with Sphinx
    TCP_DIRECT = "tcp_direct"  # Direct TCP connections
    MESH_RELAY = "mesh_relay"  # Mesh relay protocol
    FOG_BRIDGE = "fog_bridge"  # Fog computing bridge


@dataclass
class TransportCapabilities:
    """
    Transport capabilities descriptor.

    Describes what a transport can do, used for intelligent
    transport selection by the P2P Unified System.
    """

    # Basic capabilities
    supports_unicast: bool = True
    supports_broadcast: bool = False
    supports_multicast: bool = False

    # Size and performance
    max_message_size: int = 65536  # 64KB default
    typical_latency_ms: float = 1000.0
    bandwidth_mbps: float = 1.0

    # Network requirements
    is_offline_capable: bool = False
    requires_internet: bool = True
    works_on_cellular: bool = True
    works_on_wifi: bool = True

    # Security features
    provides_encryption: bool = False
    supports_forward_secrecy: bool = False
    anonymity_level: int = 0  # 0=none, 1=basic, 2=onion routing, 3=full privacy

    # Resource impact
    battery_impact: str = "medium"  # low, medium, high
    data_cost_impact: str = "medium"  # low, medium, high

    # Availability
    is_available: bool = True
    is_connected: bool = False
    connection_quality: float = 1.0  # 0.0 to 1.0

    # Advanced features
    supports_store_and_forward: bool = False
    supports_multi_hop: bool = False
    max_hops: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "supports_unicast": self.supports_unicast,
            "supports_broadcast": self.supports_broadcast,
            "supports_multicast": self.supports_multicast,
            "max_message_size": self.max_message_size,
            "typical_latency_ms": self.typical_latency_ms,
            "bandwidth_mbps": self.bandwidth_mbps,
            "is_offline_capable": self.is_offline_capable,
            "requires_internet": self.requires_internet,
            "provides_encryption": self.provides_encryption,
            "supports_forward_secrecy": self.supports_forward_secrecy,
            "anonymity_level": self.anonymity_level,
            "battery_impact": self.battery_impact,
            "data_cost_impact": self.data_cost_impact,
            "is_available": self.is_available,
            "is_connected": self.is_connected,
            "connection_quality": self.connection_quality,
            "supports_store_and_forward": self.supports_store_and_forward,
            "supports_multi_hop": self.supports_multi_hop,
            "max_hops": self.max_hops,
        }


class TransportInterface(ABC):
    """
    Abstract base interface for all P2P transports.

    All transport implementations must inherit from this class
    and implement its abstract methods to integrate with the
    P2P Unified System.
    """

    @abstractmethod
    async def start(self) -> bool:
        """
        Start the transport.

        Initialize connections, start background tasks, and
        prepare the transport for sending/receiving messages.

        Returns:
            True if started successfully, False otherwise
        """
        pass

    @abstractmethod
    async def stop(self) -> bool:
        """
        Stop the transport.

        Close connections, cleanup resources, and stop
        all background tasks gracefully.

        Returns:
            True if stopped successfully, False otherwise
        """
        pass

    @abstractmethod
    async def send(self, message: dict[str, Any]) -> bool:
        """
        Send a message through this transport.

        Args:
            message: Message dictionary with standard P2P format:
                - sender_id: str
                - receiver_id: str (or "broadcast")
                - payload: bytes
                - message_type: str
                - priority: int
                - metadata: dict

        Returns:
            True if message was sent successfully, False otherwise
        """
        pass

    @abstractmethod
    async def receive(self) -> Optional[dict[str, Any]]:
        """
        Receive a message from this transport.

        This is called periodically by the P2P system to poll
        for incoming messages. For event-driven transports,
        this may return None and use message handlers instead.

        Returns:
            Message dictionary or None if no messages available
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> TransportCapabilities:
        """
        Get transport capabilities.

        Returns descriptor of what this transport can do,
        used for intelligent transport selection.

        Returns:
            TransportCapabilities object
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if transport is available.

        Returns:
            True if transport can be used right now, False otherwise
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check if transport is connected.

        Returns:
            True if transport has active connections, False otherwise
        """
        pass

    @abstractmethod
    def get_status(self) -> dict[str, Any]:
        """
        Get transport status information.

        Returns:
            Dictionary with status details:
                - transport_type: str
                - is_available: bool
                - is_connected: bool
                - peer_count: int
                - messages_sent: int
                - messages_received: int
                - last_activity: float (timestamp)
                - errors: list[str]
        """
        pass

    def register_message_handler(self, handler: Callable) -> None:
        """
        Register a callback for incoming messages.

        Optional method for event-driven transports that want
        to push messages instead of being polled.

        Args:
            handler: Async callable that accepts message dict
        """
        pass


class BaseTransport(TransportInterface):
    """
    Base implementation of transport interface.

    Provides common functionality and default implementations
    that specific transports can inherit from.
    """

    def __init__(self, transport_type: TransportType, node_id: str):
        self.transport_type = transport_type
        self.node_id = node_id
        self._running = False
        self._message_handlers: list[Callable] = []

        # Metrics
        self.messages_sent = 0
        self.messages_received = 0
        self.last_activity = 0.0
        self.errors: list[str] = []

        logger.info(f"Base transport initialized: {transport_type.value} for node {node_id}")

    def register_message_handler(self, handler: Callable) -> None:
        """Register message handler callback."""
        self._message_handlers.append(handler)
        logger.debug(f"Message handler registered for {self.transport_type.value}")

    async def _notify_handlers(self, message: dict[str, Any]):
        """Notify all registered message handlers."""
        for handler in self._message_handlers:
            try:
                if hasattr(handler, "__call__"):
                    if hasattr(handler, "__self__"):  # Bound method
                        await handler(message)
                    else:  # Regular async function
                        await handler(message)
            except Exception as e:
                logger.warning(f"Message handler error in {self.transport_type.value}: {e}")
                self.errors.append(f"Handler error: {str(e)}")

    def get_status(self) -> dict[str, Any]:
        """Get transport status."""
        return {
            "transport_type": self.transport_type.value,
            "node_id": self.node_id,
            "is_available": self.is_available(),
            "is_connected": self.is_connected(),
            "is_running": self._running,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "last_activity": self.last_activity,
            "errors": self.errors[-10:],  # Last 10 errors
        }

    def is_available(self) -> bool:
        """Default availability check."""
        return self._running

    def is_connected(self) -> bool:
        """Default connection check."""
        return self._running
