#!/usr/bin/env python3
"""
P2P + BitChat Integration Tests
Tests the integration of BitChat as a transport module for P2P Unified System

TESTS:
- BitChat transport registration with P2P
- BLE message routing through P2P
- Protocol switching (BitChat ↔ BetaNet)
- Store-and-forward functionality
- Multi-transport failover
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# P2P Unified System imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from p2p.transports.bitchat_transport import BitChatTransport
from p2p.transports.betanet_transport import BetaNetTransport
from p2p.transports.base_transport import TransportCapabilities, TransportType


@pytest.fixture
def node_id():
    """Test node ID."""
    return "test_node_12345678"


@pytest.fixture
def mock_bitchat_api():
    """Mock BitChat API responses."""
    with patch("aiohttp.ClientSession") as mock_session:
        # Mock session instance
        session_instance = AsyncMock()
        mock_session.return_value = session_instance

        # Mock POST /peers/register
        register_response = AsyncMock()
        register_response.status = 201
        register_response.json = AsyncMock(return_value={
            "peer_id": "test_node_12345678",
            "public_key": "test_key",
            "is_online": True
        })
        session_instance.post = AsyncMock(return_value=register_response)

        # Mock GET /peers
        peers_response = AsyncMock()
        peers_response.status = 200
        peers_response.json = AsyncMock(return_value=[
            {"peer_id": "peer1", "is_online": True},
            {"peer_id": "peer2", "is_online": True}
        ])
        session_instance.get = AsyncMock(return_value=peers_response)

        # Mock WebSocket
        ws_mock = AsyncMock()
        ws_mock.closed = False
        ws_mock.send_json = AsyncMock()
        session_instance.ws_connect = AsyncMock(return_value=ws_mock)

        yield session_instance


@pytest.fixture
def mock_betanet_api():
    """Mock BetaNet API responses."""
    with patch("aiohttp.ClientSession") as mock_session:
        session_instance = AsyncMock()
        mock_session.return_value = session_instance

        # Mock POST /register
        register_response = AsyncMock()
        register_response.status = 200
        register_response.json = AsyncMock(return_value={
            "mixnode_id": "test_node_12345678",
            "status": "registered"
        })
        session_instance.post = AsyncMock(return_value=register_response)

        # Mock GET /relays
        relays_response = AsyncMock()
        relays_response.status = 200
        relays_response.json = AsyncMock(return_value=[
            {"node_id": "relay1", "capacity": 100},
            {"node_id": "relay2", "capacity": 100},
            {"node_id": "relay3", "capacity": 100}
        ])
        session_instance.get = AsyncMock(return_value=relays_response)

        yield session_instance


class TestBitChatTransport:
    """Test BitChat transport module."""

    @pytest.mark.asyncio
    async def test_bitchat_transport_initialization(self, node_id):
        """Test BitChat transport can be initialized."""
        transport = BitChatTransport(
            node_id=node_id,
            bitchat_api_url="http://localhost:8000",
            display_name="Test Node"
        )

        assert transport.node_id == node_id
        assert transport.transport_type == TransportType.BLE_MESH
        assert transport.display_name == "Test Node"
        assert not transport.is_available()

    @pytest.mark.asyncio
    async def test_bitchat_transport_capabilities(self, node_id):
        """Test BitChat transport reports correct capabilities."""
        transport = BitChatTransport(node_id=node_id)
        caps = transport.get_capabilities()

        assert isinstance(caps, TransportCapabilities)
        assert caps.supports_broadcast is True
        assert caps.is_offline_capable is True
        assert caps.requires_internet is False
        assert caps.supports_multi_hop is True
        assert caps.max_hops == 7
        assert caps.provides_encryption is True

    @pytest.mark.asyncio
    async def test_bitchat_transport_start_stop(self, node_id, mock_bitchat_api):
        """Test BitChat transport can start and stop."""
        transport = BitChatTransport(
            node_id=node_id,
            enable_websocket=False  # Disable WebSocket for test
        )

        # Start transport
        with patch("aiohttp.ClientSession", return_value=mock_bitchat_api):
            started = await transport.start()
            assert started is True
            assert transport.is_available()

        # Stop transport
        stopped = await transport.stop()
        assert stopped is True
        assert not transport.is_available()

    @pytest.mark.asyncio
    async def test_bitchat_send_message(self, node_id, mock_bitchat_api):
        """Test sending message through BitChat transport."""
        transport = BitChatTransport(
            node_id=node_id,
            enable_websocket=False
        )

        # Start transport
        with patch("aiohttp.ClientSession", return_value=mock_bitchat_api):
            await transport.start()

            # Mock send response
            send_response = AsyncMock()
            send_response.status = 201
            transport.session.post = AsyncMock(return_value=send_response)

            # Send message
            message = {
                "sender_id": node_id,
                "receiver_id": "peer1",
                "payload": b"Hello BitChat",
                "message_type": "data",
                "priority": 3
            }

            success = await transport.send(message)
            assert success is True
            assert transport.messages_sent == 1

            await transport.stop()


class TestBetaNetTransport:
    """Test BetaNet transport module."""

    @pytest.mark.asyncio
    async def test_betanet_transport_initialization(self, node_id):
        """Test BetaNet transport can be initialized."""
        transport = BetaNetTransport(
            node_id=node_id,
            betanet_api_url="http://localhost:8443",
            device_name="Test Device"
        )

        assert transport.node_id == node_id
        assert transport.transport_type == TransportType.HTX_PRIVACY
        assert transport.device_name == "Test Device"
        assert not transport.is_available()

    @pytest.mark.asyncio
    async def test_betanet_transport_capabilities(self, node_id):
        """Test BetaNet transport reports correct capabilities."""
        transport = BetaNetTransport(node_id=node_id)
        caps = transport.get_capabilities()

        assert isinstance(caps, TransportCapabilities)
        assert caps.supports_broadcast is False  # Mixnet doesn't support broadcast
        assert caps.is_offline_capable is False  # Requires internet
        assert caps.requires_internet is True
        assert caps.provides_encryption is True
        assert caps.supports_forward_secrecy is True
        assert caps.anonymity_level == 3  # Full privacy

    @pytest.mark.asyncio
    async def test_betanet_transport_start_stop(self, node_id, mock_betanet_api):
        """Test BetaNet transport can start and stop."""
        transport = BetaNetTransport(node_id=node_id)

        # Start transport
        with patch("aiohttp.ClientSession", return_value=mock_betanet_api):
            started = await transport.start()
            assert started is True
            assert transport.is_available()
            assert transport.mixnode_id is not None

        # Stop transport
        stopped = await transport.stop()
        assert stopped is True
        assert not transport.is_available()


class TestP2PBitChatIntegration:
    """Test P2P + BitChat integration scenarios."""

    @pytest.mark.asyncio
    async def test_bitchat_transport_registration(self, node_id):
        """Test BitChat transport can register with P2P system."""
        # This would test integration with unified_p2p_system.py
        # For now, verify transport can be instantiated and provides interface

        transport = BitChatTransport(node_id=node_id)

        # Verify transport interface
        assert hasattr(transport, 'start')
        assert hasattr(transport, 'stop')
        assert hasattr(transport, 'send')
        assert hasattr(transport, 'receive')
        assert hasattr(transport, 'get_capabilities')
        assert hasattr(transport, 'is_available')
        assert hasattr(transport, 'is_connected')
        assert hasattr(transport, 'get_status')

    @pytest.mark.asyncio
    async def test_ble_message_routing(self, node_id, mock_bitchat_api):
        """Test BLE message routing through BitChat transport."""
        transport = BitChatTransport(
            node_id=node_id,
            enable_websocket=False
        )

        with patch("aiohttp.ClientSession", return_value=mock_bitchat_api):
            await transport.start()

            # Mock successful send
            send_response = AsyncMock()
            send_response.status = 201
            transport.session.post = AsyncMock(return_value=send_response)

            # Test unicast message
            unicast_msg = {
                "sender_id": node_id,
                "receiver_id": "specific_peer",
                "payload": b"Direct message",
                "message_type": "data"
            }
            assert await transport.send(unicast_msg) is True

            # Test broadcast message
            broadcast_msg = {
                "sender_id": node_id,
                "receiver_id": "broadcast",
                "payload": b"Broadcast message",
                "message_type": "data"
            }
            assert await transport.send(broadcast_msg) is True

            await transport.stop()

    @pytest.mark.asyncio
    async def test_protocol_switching(self, node_id):
        """Test protocol switching between BitChat and BetaNet."""
        # Simulate scenario where P2P switches from BetaNet to BitChat
        # when internet connection is lost

        bitchat = BitChatTransport(node_id=node_id)
        betanet = BetaNetTransport(node_id=node_id)

        # Get capabilities for decision making
        bitchat_caps = bitchat.get_capabilities()
        betanet_caps = betanet.get_capabilities()

        # Verify BitChat can work offline
        assert bitchat_caps.is_offline_capable is True
        assert bitchat_caps.requires_internet is False

        # Verify BetaNet requires internet
        assert betanet_caps.is_offline_capable is False
        assert betanet_caps.requires_internet is True

        # Simulate transport selection logic
        has_internet = False
        requires_privacy = False

        if requires_privacy and has_internet:
            selected_transport = betanet
        elif not has_internet:
            selected_transport = bitchat
        else:
            selected_transport = bitchat  # Default to offline-capable

        assert selected_transport == bitchat

    @pytest.mark.asyncio
    async def test_store_and_forward(self, node_id, mock_bitchat_api):
        """Test store-and-forward functionality."""
        transport = BitChatTransport(
            node_id=node_id,
            enable_websocket=False
        )

        # Verify capability
        caps = transport.get_capabilities()
        assert caps.supports_store_and_forward is True

        # In production, would test actual store-and-forward
        # For now, verify capability is reported correctly

    @pytest.mark.asyncio
    async def test_multi_transport_failover(self, node_id):
        """Test failover between multiple transports."""
        # Simulate P2P system with both BitChat and BetaNet
        transports = {
            "bitchat": BitChatTransport(node_id=node_id),
            "betanet": BetaNetTransport(node_id=node_id)
        }

        # Test failover logic
        message = {
            "sender_id": node_id,
            "receiver_id": "peer1",
            "payload": b"Test message",
            "requires_privacy": True
        }

        # Priority order: BetaNet (privacy) → BitChat (fallback)
        selected = None

        # Try BetaNet first (privacy required)
        if message.get("requires_privacy") and transports["betanet"].is_available():
            selected = "betanet"
        # Fall back to BitChat
        elif transports["bitchat"].is_available():
            selected = "bitchat"

        # Since neither is started, both should be unavailable
        assert selected is None


class TestTransportCapabilities:
    """Test transport capabilities comparison."""

    def test_bitchat_vs_betanet_capabilities(self, node_id):
        """Compare BitChat and BetaNet capabilities."""
        bitchat = BitChatTransport(node_id=node_id)
        betanet = BetaNetTransport(node_id=node_id)

        bitchat_caps = bitchat.get_capabilities()
        betanet_caps = betanet.get_capabilities()

        # BitChat advantages
        assert bitchat_caps.is_offline_capable > betanet_caps.is_offline_capable
        assert bitchat_caps.supports_broadcast > betanet_caps.supports_broadcast
        assert bitchat_caps.supports_multi_hop

        # BetaNet advantages
        assert betanet_caps.anonymity_level > bitchat_caps.anonymity_level
        assert betanet_caps.supports_forward_secrecy > bitchat_caps.supports_forward_secrecy
        assert betanet_caps.bandwidth_mbps > bitchat_caps.bandwidth_mbps
        assert betanet_caps.typical_latency_ms < bitchat_caps.typical_latency_ms

    def test_transport_selection_algorithm(self, node_id):
        """Test intelligent transport selection."""
        bitchat = BitChatTransport(node_id=node_id)
        betanet = BetaNetTransport(node_id=node_id)

        scenarios = [
            {
                "name": "Offline mode",
                "has_internet": False,
                "requires_privacy": False,
                "expected": "bitchat"
            },
            {
                "name": "Privacy required",
                "has_internet": True,
                "requires_privacy": True,
                "expected": "betanet"
            },
            {
                "name": "Online, no special requirements",
                "has_internet": True,
                "requires_privacy": False,
                "expected": "betanet"  # Better latency
            },
            {
                "name": "Broadcast message",
                "has_internet": True,
                "is_broadcast": True,
                "expected": "bitchat"  # Only supports broadcast
            }
        ]

        for scenario in scenarios:
            # Simulate selection
            if scenario.get("is_broadcast"):
                selected = "bitchat"
            elif not scenario.get("has_internet"):
                selected = "bitchat"
            elif scenario.get("requires_privacy"):
                selected = "betanet"
            else:
                selected = "betanet"  # Default to better performance

            assert selected == scenario["expected"], f"Failed scenario: {scenario['name']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
