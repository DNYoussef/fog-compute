"""
BetaNet Transport Layer

Integrates Rust-based BetaNet mixnode network with Python VPN layer.
Provides high-performance packet transport through Sphinx-encrypted mixnet.

Architecture:
- Python VPN layer: High-level circuit coordination, hidden services
- Rust BetaNet layer: Low-level packet transport, Sphinx processing
- This module: Bridge between the two layers

Performance Target: 25,000 packets per second
"""

import asyncio
import json
import logging
import socket
import struct
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class BetanetNode:
    """Represents a BetaNet mixnode"""

    node_id: str
    address: str  # IP:port
    port: int
    public_key: bytes | None = None
    bandwidth_mbps: float = 10.0
    latency_ms: float = 50.0
    is_active: bool = True


@dataclass
class BetanetCircuit:
    """Circuit through BetaNet mixnodes"""

    circuit_id: str
    hops: list[BetanetNode]
    created_at: datetime
    last_used: datetime
    bytes_sent: int = 0
    bytes_received: int = 0
    packets_sent: int = 0
    packets_received: int = 0


class BetanetTransportError(Exception):
    """BetaNet transport layer errors"""

    pass


class BetanetTransport:
    """
    High-performance transport layer using BetaNet Rust mixnodes.

    Provides:
    - Circuit building through BetaNet topology
    - Sphinx packet transmission
    - Connection pooling and retry logic
    - Performance metrics and monitoring
    """

    def __init__(
        self,
        default_port: int = 9001,
        connection_timeout: float = 5.0,
        max_retries: int = 3,
        circuit_lifetime_hours: int = 1,
        enable_connection_pooling: bool = True,
    ):
        self.default_port = default_port
        self.connection_timeout = connection_timeout
        self.max_retries = max_retries
        self.circuit_lifetime = timedelta(hours=circuit_lifetime_hours)
        self.enable_connection_pooling = enable_connection_pooling

        # State management
        self.circuits: dict[str, BetanetCircuit] = {}
        self.available_nodes: dict[str, BetanetNode] = {}
        self.connection_pool: dict[str, tuple[socket.socket, datetime]] = {}

        # Performance tracking
        self.total_packets_sent = 0
        self.total_packets_received = 0
        self.total_bytes_sent = 0
        self.total_bytes_received = 0
        self.failed_sends = 0
        self.retry_count = 0

        logger.info(
            "BetanetTransport initialized: "
            f"port={default_port}, timeout={connection_timeout}s, "
            f"retries={max_retries}, pooling={enable_connection_pooling}"
        )

    async def discover_nodes(self, seed_addresses: list[str] | None = None) -> list[BetanetNode]:
        """
        Discover available BetaNet mixnodes.

        In production, this would query:
        - Directory authorities
        - DHT network
        - Bootstrap nodes

        Args:
            seed_addresses: Optional seed node addresses

        Returns:
            List of discovered nodes
        """
        if seed_addresses is None:
            seed_addresses = ["127.0.0.1:9001", "127.0.0.1:9002", "127.0.0.1:9003"]

        discovered_nodes = []

        for addr_str in seed_addresses:
            try:
                # Parse address
                if ":" in addr_str:
                    host, port = addr_str.rsplit(":", 1)
                    port = int(port)
                else:
                    host = addr_str
                    port = self.default_port

                # Test connectivity
                node = BetanetNode(
                    node_id=f"betanet-{host}:{port}",
                    address=host,
                    port=port,
                    bandwidth_mbps=100.0,  # Would be queried from node
                    latency_ms=10.0,  # Would be measured
                )

                # Verify node is reachable
                if await self._ping_node(node):
                    discovered_nodes.append(node)
                    self.available_nodes[node.node_id] = node
                    logger.debug(f"Discovered BetaNet node: {node.node_id}")
                else:
                    logger.warning(f"Node unreachable: {addr_str}")

            except Exception as e:
                logger.error(f"Failed to discover node {addr_str}: {e}")

        logger.info(f"Discovered {len(discovered_nodes)} BetaNet nodes")
        return discovered_nodes

    async def _ping_node(self, node: BetanetNode) -> bool:
        """
        Ping a BetaNet node to verify connectivity.

        Args:
            node: Node to ping

        Returns:
            True if node is reachable
        """
        try:
            # Create simple TCP connection test
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(node.address, node.port), timeout=self.connection_timeout
            )

            # Send stats request (control packet)
            stats_request = b"stats"
            length = len(stats_request)
            message = struct.pack("!I", length) + stats_request

            writer.write(message)
            await writer.drain()

            # Read response with timeout
            response_length_bytes = await asyncio.wait_for(reader.read(4), timeout=self.connection_timeout)

            if len(response_length_bytes) == 4:
                response_length = struct.unpack("!I", response_length_bytes)[0]
                response_data = await asyncio.wait_for(reader.read(response_length), timeout=self.connection_timeout)

                if response_data:
                    logger.debug(f"Node {node.node_id} responded: {len(response_data)} bytes")
                    writer.close()
                    await writer.wait_closed()
                    return True

            writer.close()
            await writer.wait_closed()
            return False

        except Exception as e:
            logger.debug(f"Ping failed for {node.node_id}: {e}")
            return False

    async def build_circuit(
        self, circuit_id: str, num_hops: int = 3, preferred_nodes: list[str] | None = None
    ) -> BetanetCircuit:
        """
        Build a circuit through BetaNet mixnodes.

        Args:
            circuit_id: Unique circuit identifier
            num_hops: Number of hops (default: 3)
            preferred_nodes: Optional list of preferred node IDs

        Returns:
            BetanetCircuit object

        Raises:
            BetanetTransportError: If circuit building fails
        """
        if num_hops < 1:
            raise BetanetTransportError("Circuit requires at least 1 hop")

        if num_hops > len(self.available_nodes):
            raise BetanetTransportError(f"Not enough nodes for {num_hops}-hop circuit")

        # Select nodes for circuit
        selected_nodes = []

        if preferred_nodes:
            # Use preferred nodes
            for node_id in preferred_nodes[:num_hops]:
                if node_id in self.available_nodes:
                    selected_nodes.append(self.available_nodes[node_id])
        else:
            # Select nodes based on performance
            sorted_nodes = sorted(
                self.available_nodes.values(),
                key=lambda n: (n.bandwidth_mbps / (n.latency_ms + 1)),
                reverse=True,
            )
            selected_nodes = sorted_nodes[:num_hops]

        if len(selected_nodes) < num_hops:
            raise BetanetTransportError(f"Could not select {num_hops} nodes for circuit")

        # Create circuit
        circuit = BetanetCircuit(
            circuit_id=circuit_id,
            hops=selected_nodes,
            created_at=datetime.now(UTC),
            last_used=datetime.now(UTC),
        )

        # Store circuit
        self.circuits[circuit_id] = circuit

        logger.info(
            f"Built BetaNet circuit {circuit_id}: " f"{' -> '.join([h.node_id for h in selected_nodes])}"
        )

        return circuit

    async def send_packet(
        self, circuit_id: str, payload: bytes, timeout: float | None = None
    ) -> tuple[bool, bytes | None]:
        """
        Send packet through BetaNet circuit.

        This implements the core transport functionality:
        1. Lookup circuit
        2. Send through first hop (entry node)
        3. BetaNet mixnodes handle Sphinx processing
        4. Receive response from exit node

        Args:
            circuit_id: Circuit to use
            payload: Packet payload (will be Sphinx-encrypted by caller)
            timeout: Optional timeout override

        Returns:
            (success, response_data) tuple

        Raises:
            BetanetTransportError: On transport failures
        """
        if circuit_id not in self.circuits:
            raise BetanetTransportError(f"Unknown circuit: {circuit_id}")

        circuit = self.circuits[circuit_id]
        timeout = timeout or self.connection_timeout

        # Get entry node (first hop)
        entry_node = circuit.hops[0]

        # Send packet with retries
        for attempt in range(self.max_retries):
            try:
                # Send through BetaNet TCP interface
                response = await self._send_to_node(entry_node, payload, timeout)

                # Update statistics
                circuit.bytes_sent += len(payload)
                circuit.packets_sent += 1
                circuit.last_used = datetime.now(UTC)
                self.total_packets_sent += 1
                self.total_bytes_sent += len(payload)

                if response:
                    circuit.bytes_received += len(response)
                    circuit.packets_received += 1
                    self.total_packets_received += 1
                    self.total_bytes_received += len(response)

                logger.debug(
                    f"Sent {len(payload)} bytes through circuit {circuit_id}, "
                    f"received {len(response) if response else 0} bytes"
                )

                return (True, response)

            except Exception as e:
                logger.warning(f"Send attempt {attempt + 1}/{self.max_retries} failed: {e}")
                self.retry_count += 1

                if attempt < self.max_retries - 1:
                    await asyncio.sleep(0.1 * (attempt + 1))  # Exponential backoff
                else:
                    self.failed_sends += 1
                    raise BetanetTransportError(f"Failed to send packet after {self.max_retries} attempts: {e}")

        return (False, None)

    async def _send_to_node(self, node: BetanetNode, payload: bytes, timeout: float) -> bytes | None:
        """
        Send payload to specific BetaNet node via TCP.

        Uses length-prefixed framing:
        - 4 bytes: payload length (big-endian)
        - N bytes: payload data

        Args:
            node: Target node
            payload: Data to send
            timeout: Send timeout

        Returns:
            Response data or None
        """
        try:
            # Get or create connection
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(node.address, node.port), timeout=timeout
            )

            # Send length-prefixed packet
            length = len(payload)
            message = struct.pack("!I", length) + payload

            writer.write(message)
            await writer.drain()

            # Read response (length-prefixed)
            response_length_bytes = await asyncio.wait_for(reader.read(4), timeout=timeout)

            if len(response_length_bytes) != 4:
                raise BetanetTransportError("Invalid response length prefix")

            response_length = struct.unpack("!I", response_length_bytes)[0]

            if response_length > 0:
                response_data = await asyncio.wait_for(reader.read(response_length), timeout=timeout)

                if len(response_data) != response_length:
                    raise BetanetTransportError(f"Incomplete response: {len(response_data)}/{response_length}")

                writer.close()
                await writer.wait_closed()
                return response_data

            writer.close()
            await writer.wait_closed()
            return None

        except asyncio.TimeoutError as e:
            raise BetanetTransportError(f"Send timeout to {node.node_id}") from e
        except Exception as e:
            raise BetanetTransportError(f"Send failed to {node.node_id}: {e}") from e

    async def close_circuit(self, circuit_id: str) -> bool:
        """
        Close a BetaNet circuit.

        Args:
            circuit_id: Circuit to close

        Returns:
            True if closed successfully
        """
        if circuit_id not in self.circuits:
            return False

        circuit = self.circuits[circuit_id]
        logger.info(
            f"Closing circuit {circuit_id}: "
            f"{circuit.packets_sent} packets sent, "
            f"{circuit.packets_received} packets received"
        )

        del self.circuits[circuit_id]
        return True

    async def rotate_circuits(self) -> int:
        """
        Rotate old circuits for security.

        Returns:
            Number of circuits rotated
        """
        now = datetime.now(UTC)
        rotated = 0

        for circuit_id, circuit in list(self.circuits.items()):
            age = now - circuit.created_at

            if age > self.circuit_lifetime:
                await self.close_circuit(circuit_id)
                rotated += 1

        if rotated > 0:
            logger.info(f"Rotated {rotated} circuits")

        return rotated

    def get_stats(self) -> dict[str, Any]:
        """
        Get transport statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "available_nodes": len(self.available_nodes),
            "active_circuits": len(self.circuits),
            "total_packets_sent": self.total_packets_sent,
            "total_packets_received": self.total_packets_received,
            "total_bytes_sent": self.total_bytes_sent,
            "total_bytes_received": self.total_bytes_received,
            "failed_sends": self.failed_sends,
            "retry_count": self.retry_count,
            "circuits": [
                {
                    "circuit_id": c.circuit_id,
                    "hops": len(c.hops),
                    "packets_sent": c.packets_sent,
                    "packets_received": c.packets_received,
                    "age_seconds": (datetime.now(UTC) - c.created_at).total_seconds(),
                }
                for c in self.circuits.values()
            ],
        }

    async def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up BetanetTransport")

        # Close all circuits
        for circuit_id in list(self.circuits.keys()):
            await self.close_circuit(circuit_id)

        # Clear state
        self.available_nodes.clear()
        self.connection_pool.clear()
