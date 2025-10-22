"""
Integration tests for VPN onion routing system.

Tests full circuit creation, data transmission, and hidden service functionality.
"""

import pytest
import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from vpn.onion_routing import (
    OnionRouter,
    NodeType,
    CircuitState,
)


@pytest.fixture
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def onion_router():
    """Create and initialize an onion router with consensus"""
    router = OnionRouter(
        node_id="integration-test-router",
        node_types={NodeType.GUARD, NodeType.MIDDLE},
        enable_hidden_services=True,
        num_guards=3,
        circuit_lifetime_hours=1,
    )

    # Fetch consensus to populate network state
    await router.fetch_consensus()

    return router


class TestIntegration:
    """Integration tests for full onion routing workflows"""

    @pytest.mark.asyncio
    async def test_full_circuit_creation(self, onion_router):
        """Test creating a complete 3-hop circuit and sending data through it"""
        # Build a 3-hop circuit
        circuit = await onion_router.build_circuit(purpose="general", path_length=3)

        # Verify circuit was created
        assert circuit is not None
        assert circuit.state == CircuitState.ESTABLISHED
        assert len(circuit.hops) == 3

        # Verify circuit is registered
        assert circuit.circuit_id in onion_router.circuits

        # Test data transmission through the circuit
        test_data = b"Integration test message through 3-hop circuit"
        success = await onion_router.send_data(circuit.circuit_id, test_data)

        # Verify send was successful
        assert success is True

        # Verify circuit stats were updated
        assert circuit.bytes_sent > 0

        # Verify we can encrypt and decrypt through the full circuit
        encrypted = onion_router._onion_encrypt(circuit, test_data)

        # Decrypt layer by layer
        decrypted = encrypted
        for hop_index in range(len(circuit.hops)):
            decrypted = onion_router._onion_decrypt(circuit, decrypted, hop_index)

        # Remove padding and verify
        final_data = onion_router._unpad_payload(decrypted)
        assert final_data == test_data

        # Clean up
        closed = await onion_router.close_circuit(circuit.circuit_id)
        assert closed is True
        assert circuit.circuit_id not in onion_router.circuits

    @pytest.mark.asyncio
    async def test_multiple_circuits(self, onion_router):
        """Test creating and managing multiple circuits simultaneously"""
        circuits = []

        # Create 5 circuits
        for i in range(5):
            circuit = await onion_router.build_circuit(purpose="general", path_length=3)
            assert circuit is not None
            circuits.append(circuit)

        # Verify all circuits are established
        assert len(circuits) == 5
        for circuit in circuits:
            assert circuit.state == CircuitState.ESTABLISHED
            assert circuit.circuit_id in onion_router.circuits

        # Send data through each circuit
        for i, circuit in enumerate(circuits):
            test_data = f"Message {i} through circuit {circuit.circuit_id}".encode()
            success = await onion_router.send_data(circuit.circuit_id, test_data)
            assert success is True

        # Clean up all circuits
        for circuit in circuits:
            await onion_router.close_circuit(circuit.circuit_id)

        # Verify all circuits are closed
        for circuit in circuits:
            assert circuit.circuit_id not in onion_router.circuits

    @pytest.mark.asyncio
    async def test_hidden_service_creation(self, onion_router):
        """Test creating a hidden service with introduction points"""
        # Create hidden service
        ports = {80: 8080, 443: 8443}
        service = await onion_router.create_hidden_service(ports)

        # Verify service was created
        assert service is not None
        assert service.service_id in onion_router.hidden_services

        # Verify onion address is correctly formatted
        assert service.onion_address.endswith(".fog")
        assert len(service.onion_address) > 10

        # Verify introduction points
        assert len(service.introduction_points) > 0

        # Verify ports configuration
        assert service.ports == ports

        # Verify service has keys
        assert len(service.private_key) > 0
        assert len(service.public_key) > 0

    @pytest.mark.asyncio
    async def test_hidden_service_connection(self, onion_router):
        """Test connecting to a hidden service"""
        # First create a hidden service
        ports = {80: 8080}
        service = await onion_router.create_hidden_service(ports)

        # Now try to connect to it
        circuit = await onion_router.connect_to_hidden_service(service.onion_address)

        # Verify connection was established
        assert circuit is not None
        assert circuit.is_hidden_service is True
        assert circuit.rendezvous_cookie is not None
        assert len(circuit.rendezvous_cookie) == 20

    @pytest.mark.asyncio
    async def test_circuit_statistics(self, onion_router):
        """Test that circuit statistics are tracked correctly"""
        # Build circuit
        circuit = await onion_router.build_circuit(purpose="general", path_length=3)

        # Send some data
        test_messages = [
            b"Message 1",
            b"Message 2" * 10,
            b"Message 3" * 100,
        ]

        for msg in test_messages:
            await onion_router.send_data(circuit.circuit_id, msg)

        # Get stats
        stats = onion_router.get_stats()

        # Verify stats
        assert stats["node_id"] == "integration-test-router"
        assert stats["active_circuits"] >= 1
        assert stats["total_bytes_sent"] > 0

        # Clean up
        await onion_router.close_circuit(circuit.circuit_id)

    @pytest.mark.asyncio
    async def test_circuit_rotation(self, onion_router):
        """Test circuit rotation mechanism"""
        # Build initial circuit
        circuit = await onion_router.build_circuit(purpose="general", path_length=3)
        old_circuit_id = circuit.circuit_id

        # Manually age the circuit by setting created_at to old time
        from datetime import UTC, datetime, timedelta
        circuit.created_at = datetime.now(UTC) - timedelta(hours=2)

        # Trigger rotation
        rotated_count = await onion_router.rotate_circuits()

        # Verify rotation occurred
        assert rotated_count >= 1
        assert old_circuit_id not in onion_router.circuits

    @pytest.mark.asyncio
    async def test_invalid_circuit_send(self, onion_router):
        """Test that sending data through invalid circuit fails gracefully"""
        # Try to send through non-existent circuit
        success = await onion_router.send_data("non-existent-circuit", b"test")
        assert success is False

        # Create circuit but close it
        circuit = await onion_router.build_circuit(purpose="general", path_length=3)
        circuit_id = circuit.circuit_id
        await onion_router.close_circuit(circuit_id)

        # Try to send through closed circuit
        success = await onion_router.send_data(circuit_id, b"test")
        assert success is False

    @pytest.mark.asyncio
    async def test_consensus_fetch(self, onion_router):
        """Test that consensus fetching populates network state"""
        # Verify consensus was fetched in fixture
        assert len(onion_router.consensus) > 0
        assert len(onion_router.guard_nodes) > 0

        # Verify guard nodes are properly selected
        for guard in onion_router.guard_nodes:
            assert NodeType.GUARD in guard.node_types
            assert guard.is_stable is True

        # Verify we have different node types
        node_types = set()
        for node in onion_router.consensus.values():
            node_types.update(node.node_types)

        assert NodeType.MIDDLE in node_types
        assert NodeType.EXIT in node_types or NodeType.GUARD in node_types


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
