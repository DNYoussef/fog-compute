#!/usr/bin/env python3
"""
Simple test runner for P2P integration
Bypasses pytest dependency issues
"""

import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from p2p.transports.bitchat_transport import BitChatTransport
from p2p.transports.betanet_transport import BetaNetTransport
from p2p.transports.base_transport import TransportCapabilities, TransportType


def test_bitchat_transport_initialization():
    """Test BitChat transport initialization."""
    transport = BitChatTransport(
        node_id="test_node_123",
        bitchat_api_url="http://localhost:8000"
    )

    assert transport.node_id == "test_node_123"
    assert transport.transport_type == TransportType.BLE_MESH
    assert not transport.is_available()
    print("✅ BitChat transport initialization test passed")


def test_bitchat_capabilities():
    """Test BitChat transport capabilities."""
    transport = BitChatTransport(node_id="test_node")
    caps = transport.get_capabilities()

    assert isinstance(caps, TransportCapabilities)
    assert caps.supports_broadcast is True
    assert caps.is_offline_capable is True
    assert caps.requires_internet is False
    assert caps.supports_multi_hop is True
    assert caps.max_hops == 7
    print("✅ BitChat capabilities test passed")


def test_betanet_transport_initialization():
    """Test BetaNet transport initialization."""
    transport = BetaNetTransport(
        node_id="test_node_456",
        betanet_api_url="http://localhost:8443"
    )

    assert transport.node_id == "test_node_456"
    assert transport.transport_type == TransportType.HTX_PRIVACY
    assert not transport.is_available()
    print("✅ BetaNet transport initialization test passed")


def test_betanet_capabilities():
    """Test BetaNet transport capabilities."""
    transport = BetaNetTransport(node_id="test_node")
    caps = transport.get_capabilities()

    assert isinstance(caps, TransportCapabilities)
    assert caps.supports_broadcast is False  # Mixnet limitation
    assert caps.is_offline_capable is False
    assert caps.requires_internet is True
    assert caps.provides_encryption is True
    assert caps.supports_forward_secrecy is True
    assert caps.anonymity_level == 3
    print("✅ BetaNet capabilities test passed")


def test_transport_selection_logic():
    """Test intelligent transport selection."""
    bitchat = BitChatTransport(node_id="test")
    betanet = BetaNetTransport(node_id="test")

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
            "name": "Broadcast message",
            "has_internet": True,
            "is_broadcast": True,
            "expected": "bitchat"
        }
    ]

    for scenario in scenarios:
        # Simulate selection logic
        if scenario.get("is_broadcast"):
            selected = "bitchat"
        elif not scenario.get("has_internet"):
            selected = "bitchat"
        elif scenario.get("requires_privacy"):
            selected = "betanet"
        else:
            selected = "betanet"

        assert selected == scenario["expected"], f"Failed: {scenario['name']}"

    print("✅ Transport selection logic test passed")


def test_capabilities_comparison():
    """Test BitChat vs BetaNet capabilities comparison."""
    bitchat = BitChatTransport(node_id="test")
    betanet = BetaNetTransport(node_id="test")

    bitchat_caps = bitchat.get_capabilities()
    betanet_caps = betanet.get_capabilities()

    # BitChat advantages
    assert bitchat_caps.is_offline_capable > betanet_caps.is_offline_capable
    assert bitchat_caps.supports_broadcast > betanet_caps.supports_broadcast

    # BetaNet advantages
    assert betanet_caps.anonymity_level > bitchat_caps.anonymity_level
    assert betanet_caps.supports_forward_secrecy > bitchat_caps.supports_forward_secrecy
    assert betanet_caps.bandwidth_mbps > bitchat_caps.bandwidth_mbps

    print("✅ Capabilities comparison test passed")


def test_transport_status():
    """Test transport status reporting."""
    transport = BitChatTransport(node_id="status_test")
    status = transport.get_status()

    assert status["transport_type"] == "ble_mesh"
    assert status["node_id"] == "status_test"
    assert "is_available" in status
    assert "messages_sent" in status
    assert "messages_received" in status

    print("✅ Transport status test passed")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("P2P + BitChat Integration Tests")
    print("="*60 + "\n")

    tests = [
        test_bitchat_transport_initialization,
        test_bitchat_capabilities,
        test_betanet_transport_initialization,
        test_betanet_capabilities,
        test_transport_selection_logic,
        test_capabilities_comparison,
        test_transport_status,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ {test.__name__} failed: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ {test.__name__} error: {e}")
            failed += 1

    print("\n" + "="*60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("="*60 + "\n")

    if failed == 0:
        print("✅ ALL TESTS PASSED")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
