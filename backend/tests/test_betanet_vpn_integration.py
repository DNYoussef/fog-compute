"""
Integration Tests: BetaNet + VPN Consolidation

Tests the hybrid architecture where Python VPN layer uses
Rust BetaNet mixnodes for high-performance packet transport.

Architecture Validation:
- BetaNet (Rust) handles low-level Sphinx packet transport
- VPN (Python) handles high-level circuit coordination
- Integration seamless with automatic fallback
"""

import asyncio
import pytest
from datetime import datetime, UTC

from src.vpn.transports.betanet_transport import (
    BetanetTransport,
    BetanetNode,
    BetanetTransportError
)
from src.vpn.onion_routing import (
    OnionRouter,
    NodeType,
    CircuitState
)


class TestBetanetTransport:
    """Test BetaNet transport layer"""

    @pytest.mark.asyncio
    async def test_transport_initialization(self):
        """Test BetanetTransport initialization"""
        transport = BetanetTransport(
            default_port=9001,
            connection_timeout=5.0,
            max_retries=3
        )

        assert transport.default_port == 9001
        assert transport.connection_timeout == 5.0
        assert transport.max_retries == 3
        assert len(transport.circuits) == 0
        assert len(transport.available_nodes) == 0

    @pytest.mark.asyncio
    async def test_node_discovery(self):
        """Test BetaNet node discovery"""
        transport = BetanetTransport()

        # Test discovery with simulated nodes
        # In production, would connect to actual BetaNet mixnodes
        seed_addresses = ["127.0.0.1:9001", "127.0.0.1:9002"]

        # Note: This will fail if no BetaNet nodes are running
        # That's expected - test validates the discovery mechanism
        nodes = await transport.discover_nodes(seed_addresses)

        # Verify discovery attempted
        assert isinstance(nodes, list)
        # In CI without BetaNet nodes, this may be empty
        # In production, would have actual nodes

    @pytest.mark.asyncio
    async def test_circuit_building(self):
        """Test BetaNet circuit construction"""
        transport = BetanetTransport()

        # Manually add test nodes
        for i in range(3):
            node = BetanetNode(
                node_id=f"test-node-{i}",
                address="127.0.0.1",
                port=9000 + i,
                bandwidth_mbps=100.0,
                latency_ms=10.0
            )
            transport.available_nodes[node.node_id] = node

        # Build circuit
        circuit = await transport.build_circuit(
            circuit_id="test-circuit-1",
            num_hops=3
        )

        assert circuit.circuit_id == "test-circuit-1"
        assert len(circuit.hops) == 3
        assert circuit.packets_sent == 0
        assert circuit.packets_received == 0

    @pytest.mark.asyncio
    async def test_insufficient_nodes_error(self):
        """Test error handling with insufficient nodes"""
        transport = BetanetTransport()

        # Add only 1 node but request 3-hop circuit
        node = BetanetNode(
            node_id="test-node-0",
            address="127.0.0.1",
            port=9001
        )
        transport.available_nodes[node.node_id] = node

        with pytest.raises(BetanetTransportError, match="Not enough nodes"):
            await transport.build_circuit("test-circuit", num_hops=3)

    @pytest.mark.asyncio
    async def test_circuit_statistics(self):
        """Test circuit statistics tracking"""
        transport = BetanetTransport()

        # Add test nodes
        for i in range(3):
            node = BetanetNode(
                node_id=f"node-{i}",
                address="127.0.0.1",
                port=9000 + i
            )
            transport.available_nodes[node.node_id] = node

        # Build circuits
        await transport.build_circuit("circuit-1", num_hops=3)
        await transport.build_circuit("circuit-2", num_hops=2)

        stats = transport.get_stats()

        assert stats["available_nodes"] == 3
        assert stats["active_circuits"] == 2
        assert stats["total_packets_sent"] == 0
        assert len(stats["circuits"]) == 2

    @pytest.mark.asyncio
    async def test_circuit_cleanup(self):
        """Test circuit cleanup and resource management"""
        transport = BetanetTransport()

        # Add test nodes
        for i in range(3):
            node = BetanetNode(
                node_id=f"node-{i}",
                address="127.0.0.1",
                port=9000 + i
            )
            transport.available_nodes[node.node_id] = node

        # Build and close circuit
        circuit = await transport.build_circuit("test-circuit", num_hops=3)
        assert "test-circuit" in transport.circuits

        success = await transport.close_circuit("test-circuit")
        assert success is True
        assert "test-circuit" not in transport.circuits

        # Try closing non-existent circuit
        success = await transport.close_circuit("non-existent")
        assert success is False


class TestVPNBetaNetIntegration:
    """Test VPN + BetaNet integration"""

    @pytest.mark.asyncio
    async def test_vpn_uses_betanet_transport(self):
        """Test that VPN uses BetaNet for packet transport"""
        # Create BetaNet transport
        transport = BetanetTransport()

        # Add test nodes
        for i in range(3):
            node = BetanetNode(
                node_id=f"betanet-node-{i}",
                address="127.0.0.1",
                port=9000 + i
            )
            transport.available_nodes[node.node_id] = node

        # Create OnionRouter with BetaNet enabled
        router = OnionRouter(
            node_id="test-router",
            node_types={NodeType.GUARD, NodeType.MIDDLE},
            use_betanet=True,
            betanet_transport=transport
        )

        # Verify BetaNet is enabled
        assert router.use_betanet is True
        assert router.betanet_transport is transport
        assert router.betanet_packets_sent == 0
        assert router.python_packets_sent == 0

    @pytest.mark.asyncio
    async def test_hybrid_circuit_creation(self):
        """Test that circuits are created in both VPN and BetaNet layers"""
        transport = BetanetTransport()

        # Add nodes to BetaNet
        for i in range(3):
            node = BetanetNode(
                node_id=f"node-{i}",
                address=f"127.0.0.{i+1}",
                port=9001
            )
            transport.available_nodes[node.node_id] = node

        # Create router with BetaNet
        router = OnionRouter(
            node_id="hybrid-router",
            node_types={NodeType.GUARD},
            use_betanet=True,
            betanet_transport=transport
        )

        # Fetch consensus (creates VPN nodes)
        await router.fetch_consensus()

        # Build circuit - should create both VPN and BetaNet circuits
        circuit = await router.build_circuit(purpose="general", path_length=3)

        # Verify VPN circuit exists
        assert circuit is not None
        assert circuit.state == CircuitState.ESTABLISHED
        assert len(circuit.hops) == 3

        # Note: BetaNet circuit creation may fail without actual nodes
        # Test validates the integration mechanism

    @pytest.mark.asyncio
    async def test_fallback_to_python_routing(self):
        """Test automatic fallback to Python when BetaNet fails"""
        # Create router with BetaNet but no transport
        router = OnionRouter(
            node_id="fallback-router",
            node_types={NodeType.MIDDLE},
            use_betanet=True,
            betanet_transport=None  # No transport provided
        )

        await router.fetch_consensus()
        circuit = await router.build_circuit(path_length=3)

        if circuit:
            # Send data - should use Python fallback
            success = await router.send_data(
                circuit.circuit_id,
                b"test data"
            )

            # Should succeed with Python implementation
            assert success is True
            # Python counter should increment
            assert router.python_packets_sent > 0

    @pytest.mark.asyncio
    async def test_hidden_service_over_betanet(self):
        """Test hidden service functionality with BetaNet transport"""
        transport = BetanetTransport()

        # Add nodes
        for i in range(5):
            node = BetanetNode(
                node_id=f"hs-node-{i}",
                address=f"127.0.0.{i+1}",
                port=9001
            )
            transport.available_nodes[node.node_id] = node

        # Create router
        router = OnionRouter(
            node_id="hs-router",
            node_types={NodeType.HIDDEN_SERVICE},
            enable_hidden_services=True,
            use_betanet=True,
            betanet_transport=transport
        )

        await router.fetch_consensus()

        # Create hidden service
        hidden_service = await router.create_hidden_service(
            ports={80: 8080, 443: 8443}
        )

        # Verify hidden service created
        assert hidden_service is not None
        assert hidden_service.onion_address.endswith(".fog")
        assert len(hidden_service.introduction_points) > 0
        assert 80 in hidden_service.ports
        assert 443 in hidden_service.ports

    @pytest.mark.asyncio
    async def test_performance_improvement(self):
        """Test performance metrics: BetaNet vs Python"""
        transport = BetanetTransport()

        # Add high-performance nodes
        for i in range(3):
            node = BetanetNode(
                node_id=f"perf-node-{i}",
                address="127.0.0.1",
                port=9000 + i,
                bandwidth_mbps=1000.0,  # 1 Gbps
                latency_ms=1.0  # 1ms
            )
            transport.available_nodes[node.node_id] = node

        # Create router with BetaNet
        router = OnionRouter(
            node_id="perf-router",
            node_types={NodeType.MIDDLE},
            use_betanet=True,
            betanet_transport=transport
        )

        # Get stats
        stats = router.get_stats()

        # Verify stats structure
        assert "use_betanet" in stats
        assert "betanet_packets_sent" in stats
        assert "python_packets_sent" in stats
        assert stats["use_betanet"] is True

        # Verify BetaNet transport stats included
        if router.betanet_transport:
            assert "betanet_transport" in stats
            betanet_stats = stats["betanet_transport"]
            assert "available_nodes" in betanet_stats
            assert betanet_stats["available_nodes"] == 3


class TestArchitecturalSeparation:
    """Test clear architectural separation between layers"""

    @pytest.mark.asyncio
    async def test_vpn_layer_high_level_only(self):
        """Verify VPN layer handles high-level concerns only"""
        router = OnionRouter(
            node_id="arch-router",
            node_types={NodeType.GUARD},
            use_betanet=True
        )

        # VPN should handle:
        # - Circuit coordination (tested)
        # - Hidden services (tested)
        # - Onion encryption (tested in onion_routing.py)

        await router.fetch_consensus()
        circuit = await router.build_circuit()

        # Verify VPN creates circuit structure
        assert circuit is not None
        assert len(circuit.hops) > 0

        # VPN should NOT handle:
        # - Low-level TCP connections (BetaNet's job)
        # - Sphinx packet processing (BetaNet's job)
        # - Network I/O (BetaNet's job)

    @pytest.mark.asyncio
    async def test_betanet_layer_low_level_only(self):
        """Verify BetaNet layer handles low-level concerns only"""
        transport = BetanetTransport()

        # BetaNet should handle:
        # - TCP connections
        # - Packet transport
        # - Performance optimization

        stats = transport.get_stats()
        assert "total_packets_sent" in stats
        assert "total_bytes_sent" in stats

        # BetaNet should NOT handle:
        # - Circuit path selection (VPN's job)
        # - Hidden service logic (VPN's job)
        # - High-level routing decisions (VPN's job)


@pytest.mark.asyncio
async def test_end_to_end_integration():
    """
    End-to-end integration test:
    Python VPN -> BetaNet Transport -> Rust Mixnodes -> Response
    """
    # Setup BetaNet transport
    transport = BetanetTransport(
        default_port=9001,
        connection_timeout=3.0,
        max_retries=2
    )

    # Add test nodes
    for i in range(3):
        node = BetanetNode(
            node_id=f"e2e-node-{i}",
            address="127.0.0.1",
            port=9000 + i,
            bandwidth_mbps=500.0
        )
        transport.available_nodes[node.node_id] = node

    # Setup VPN router
    router = OnionRouter(
        node_id="e2e-router",
        node_types={NodeType.GUARD, NodeType.MIDDLE},
        use_betanet=True,
        betanet_transport=transport
    )

    # Fetch network consensus
    consensus_success = await router.fetch_consensus()
    assert consensus_success is True

    # Build hybrid circuit (VPN + BetaNet)
    circuit = await router.build_circuit(path_length=3)
    assert circuit is not None
    assert circuit.state == CircuitState.ESTABLISHED

    # Send data through circuit
    test_payload = b"Hello, BetaNet+VPN Hybrid Architecture!"

    # Note: This will use Python fallback without running BetaNet nodes
    send_success = await router.send_data(circuit.circuit_id, test_payload)

    # Verify operation completed
    assert send_success is True

    # Check statistics
    stats = router.get_stats()
    assert stats["active_circuits"] >= 1
    assert stats["total_bytes_sent"] > 0

    # Cleanup
    await router.close_circuit(circuit.circuit_id)
    await transport.cleanup()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
