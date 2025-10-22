"""
Standalone integration test runner for VPN onion routing system.
Tests full circuit creation and data transmission.
"""

import sys
import io
import asyncio
from pathlib import Path
import traceback

# Fix Windows console encoding for emojis
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from vpn.onion_routing import (
    OnionRouter,
    NodeType,
    CircuitState,
)


async def test_full_circuit_creation():
    """Test creating a complete 3-hop circuit and sending data through it"""
    print("TEST: Full Circuit Creation")

    router = OnionRouter(
        node_id="integration-test-router",
        node_types={NodeType.GUARD, NodeType.MIDDLE},
        enable_hidden_services=True,
        num_guards=5,  # Increase guard nodes
        circuit_lifetime_hours=1,
    )

    # Fetch consensus to populate network state
    consensus_ok = await router.fetch_consensus()
    assert consensus_ok, "Failed to fetch consensus"

    # Verify we have enough nodes
    print(f"  Network state: {len(router.consensus)} nodes, {len(router.guard_nodes)} guards")
    assert len(router.guard_nodes) > 0, "No guard nodes available"

    # Build a 3-hop circuit
    circuit = await router.build_circuit(purpose="general", path_length=3)

    # Verify circuit was created
    assert circuit is not None, "Circuit creation failed"
    assert circuit.state == CircuitState.ESTABLISHED, "Circuit not established"
    assert len(circuit.hops) == 3, "Circuit should have 3 hops"

    # Verify circuit is registered
    assert circuit.circuit_id in router.circuits, "Circuit not registered"

    # Test data transmission through the circuit
    test_data = b"Integration test message through 3-hop circuit"
    success = await router.send_data(circuit.circuit_id, test_data)

    # Verify send was successful
    assert success is True, "Data send failed"

    # Verify circuit stats were updated
    assert circuit.bytes_sent > 0, "Circuit bytes_sent not updated"

    # Verify we can encrypt and decrypt through the full circuit
    encrypted = router._onion_encrypt(circuit, test_data)

    # Decrypt layer by layer
    decrypted = encrypted
    for hop_index in range(len(circuit.hops)):
        decrypted = router._onion_decrypt(circuit, decrypted, hop_index)

    # Remove padding and verify
    final_data = router._unpad_payload(decrypted)
    assert final_data == test_data, "Decrypted data doesn't match original"

    # Clean up
    closed = await router.close_circuit(circuit.circuit_id)
    assert closed is True, "Circuit close failed"
    assert circuit.circuit_id not in router.circuits, "Circuit still registered after close"

    print("  ✅ PASS: Full circuit creation and data transmission successful")
    return True


async def test_hidden_service_creation():
    """Test creating a hidden service with introduction points"""
    print("TEST: Hidden Service Creation")

    router = OnionRouter(
        node_id="hidden-service-test-router",
        node_types={NodeType.GUARD, NodeType.MIDDLE},
        enable_hidden_services=True,
    )

    # Fetch consensus
    await router.fetch_consensus()

    # Create hidden service
    ports = {80: 8080, 443: 8443}
    service = await router.create_hidden_service(ports)

    # Verify service was created
    assert service is not None, "Hidden service creation failed"
    assert service.service_id in router.hidden_services, "Service not registered"

    # Verify onion address is correctly formatted
    assert service.onion_address.endswith(".fog"), "Invalid onion address suffix"
    assert len(service.onion_address) > 10, "Onion address too short"

    # Verify introduction points
    assert len(service.introduction_points) > 0, "No introduction points"

    # Verify ports configuration
    assert service.ports == ports, "Ports configuration mismatch"

    # Verify service has keys
    assert len(service.private_key) > 0, "No private key"
    assert len(service.public_key) > 0, "No public key"

    print("  ✅ PASS: Hidden service created successfully")
    return True


async def test_consensus_fetch():
    """Test that consensus fetching populates network state"""
    print("TEST: Consensus Fetch")

    router = OnionRouter(
        node_id="consensus-test-router",
        node_types={NodeType.GUARD, NodeType.MIDDLE},
    )

    # Fetch consensus
    success = await router.fetch_consensus()
    assert success, "Consensus fetch failed"

    # Verify consensus was fetched
    assert len(router.consensus) > 0, "No consensus nodes"
    assert len(router.guard_nodes) > 0, "No guard nodes"

    # Verify guard nodes are properly selected
    for guard in router.guard_nodes:
        assert NodeType.GUARD in guard.node_types, "Guard node doesn't have GUARD type"
        assert guard.is_stable is True, "Guard node not stable"

    # Verify we have different node types
    node_types = set()
    for node in router.consensus.values():
        node_types.update(node.node_types)

    assert NodeType.MIDDLE in node_types, "No MIDDLE nodes"
    assert NodeType.EXIT in node_types or NodeType.GUARD in node_types, "No EXIT or GUARD nodes"

    print("  ✅ PASS: Consensus fetch successful")
    return True


async def main():
    """Run all integration tests"""
    print("="*60)
    print("VPN Integration Tests - Full System Validation")
    print("="*60)
    print()

    tests = [
        test_full_circuit_creation,
        test_hidden_service_creation,
        test_consensus_fetch,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            if await test_func():
                passed += 1
            else:
                failed += 1
                print(f"  ❌ FAIL: Test returned False")
        except Exception as e:
            failed += 1
            print(f"  ❌ FAIL: {e}")
            traceback.print_exc()

        print()

    print("="*60)
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("="*60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
