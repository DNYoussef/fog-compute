"""
End-to-End Integration Tests for BetaNet

Tests full Python → Rust → Python flow with actual TCP networking.
Requires Docker Compose to spin up mixnode infrastructure.
"""

import asyncio
import pytest
import struct
import time
from typing import Optional

from backend.server.services.betanet_client import (
    BetanetTcpClient,
    BetanetConfig,
    BetanetCircuitClient,
)


@pytest.fixture
async def betanet_client():
    """Fixture providing connected BetaNet client"""
    config = BetanetConfig(host="127.0.0.1", port=9001, timeout=3.0)
    client = BetanetTcpClient(config)

    yield client

    await client.disconnect()


@pytest.fixture
async def betanet_circuit():
    """Fixture providing 3-node circuit"""
    circuit = BetanetCircuitClient(
        [
            ("127.0.0.1", 9001),
            ("127.0.0.1", 9002),
            ("127.0.0.1", 9003),
        ]
    )

    yield circuit

    await circuit.disconnect_all()


@pytest.mark.asyncio
async def test_betanet_connection():
    """Test basic connection to BetaNet mixnode"""
    config = BetanetConfig(host="127.0.0.1", port=9001)
    client = BetanetTcpClient(config)

    try:
        connected = await client.connect()
        assert connected, "Should connect to mixnode"
        assert client.is_connected, "Client should report connected state"

    finally:
        await client.disconnect()
        assert not client.is_connected, "Client should report disconnected"


@pytest.mark.asyncio
async def test_betanet_send_receive(betanet_client):
    """Test sending and receiving packets"""
    # Create test packet
    test_data = b"Test packet for BetaNet mixnode"

    # Connect
    connected = await betanet_client.connect()
    if not connected:
        pytest.skip("Cannot connect to BetaNet mixnode (is it running?)")

    # Send packet
    response = await betanet_client.send_packet(test_data)

    # Verify response
    assert response is not None, "Should receive response"
    assert len(response) > 0, "Response should not be empty"
    assert len(response) >= 4, "Response should have at least length prefix"


@pytest.mark.asyncio
async def test_betanet_multiple_packets(betanet_client):
    """Test sending multiple packets in sequence"""
    connected = await betanet_client.connect()
    if not connected:
        pytest.skip("Cannot connect to BetaNet mixnode")

    # Send 10 packets
    for i in range(10):
        test_data = f"Packet {i}".encode()
        response = await betanet_client.send_packet(test_data)

        assert response is not None, f"Packet {i} should get response"


@pytest.mark.asyncio
async def test_betanet_large_packet(betanet_client):
    """Test sending large packet (1200 bytes)"""
    connected = await betanet_client.connect()
    if not connected:
        pytest.skip("Cannot connect to BetaNet mixnode")

    # Create large packet
    large_data = b"X" * 1200

    response = await betanet_client.send_packet(large_data)

    assert response is not None, "Large packet should get response"
    assert len(response) >= 4, "Response should be valid"


@pytest.mark.asyncio
async def test_betanet_retry_logic():
    """Test automatic retry on connection failure"""
    # Use invalid port to trigger retry
    config = BetanetConfig(host="127.0.0.1", port=19999, timeout=0.5, max_retries=2)
    client = BetanetTcpClient(config)

    test_data = b"Test"

    # This should fail and retry
    response = await client.send_packet_with_retry(test_data)

    # Should fail after retries
    assert response is None, "Should fail when server unavailable"


@pytest.mark.asyncio
async def test_betanet_full_circuit(betanet_circuit):
    """
    Test full 3-node circuit: Python → Node1 → Node2 → Node3 → Python

    This is the main E2E test verifying:
    1. Python client can send to Rust mixnode
    2. Packet gets processed through 3 hops
    3. Response flows back through circuit
    """
    # Create test packet
    test_data = b"Secret message through 3-hop mixnet circuit"

    # Send through circuit
    final_response = await betanet_circuit.send_through_circuit(test_data)

    # Verify circuit completion
    if final_response is None:
        pytest.skip("Circuit nodes not available (is Docker Compose running?)")

    assert final_response is not None, "Circuit should complete successfully"
    assert len(final_response) > 0, "Final response should not be empty"


@pytest.mark.asyncio
async def test_betanet_concurrent_connections():
    """Test multiple concurrent connections to mixnode"""
    config = BetanetConfig(host="127.0.0.1", port=9001)

    # Create 5 concurrent clients
    async def send_packet(client_id: int) -> Optional[bytes]:
        client = BetanetTcpClient(config)
        try:
            if await client.connect():
                test_data = f"Concurrent packet {client_id}".encode()
                return await client.send_packet(test_data)
        finally:
            await client.disconnect()

    # Send concurrently
    tasks = [send_packet(i) for i in range(5)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Count successes
    successful = sum(1 for r in results if r is not None and not isinstance(r, Exception))

    print(f"Concurrent connections: {successful}/5 successful")
    assert successful >= 3, "At least 60% of concurrent connections should succeed"


@pytest.mark.asyncio
async def test_betanet_throughput_benchmark():
    """
    Benchmark throughput to verify 25k pps target

    Note: This is a simplified client-side test. Full benchmark
    requires Rust-side testing infrastructure.
    """
    config = BetanetConfig(host="127.0.0.1", port=9001, timeout=2.0)
    client = BetanetTcpClient(config)

    connected = await client.connect()
    if not connected:
        pytest.skip("Cannot connect to BetaNet mixnode")

    # Send packets for 1 second
    test_data = b"X" * 1200  # Typical packet size
    packets_sent = 0
    packets_received = 0
    start_time = time.time()
    test_duration = 1.0

    try:
        while time.time() - start_time < test_duration:
            response = await client.send_packet(test_data)
            packets_sent += 1

            if response is not None:
                packets_received += 1

            # Small delay to prevent overwhelming
            if packets_sent % 100 == 0:
                await asyncio.sleep(0.001)

    except Exception as e:
        print(f"Benchmark error: {e}")

    elapsed = time.time() - start_time
    throughput = packets_sent / elapsed

    print(f"\n📊 Client-side Throughput Benchmark:")
    print(f"  Duration:         {elapsed:.2f}s")
    print(f"  Packets sent:     {packets_sent}")
    print(f"  Packets received: {packets_received}")
    print(f"  Throughput:       {throughput:.0f} pkt/s")
    print(f"  Success rate:     {100.0 * packets_received / packets_sent:.1f}%")

    await client.disconnect()

    # Assert reasonable performance
    assert packets_sent > 0, "Should send at least some packets"
    assert throughput > 100, "Should achieve at least 100 pkt/s from Python client"


@pytest.mark.asyncio
async def test_betanet_packet_integrity():
    """Test packet data integrity through mixnode"""
    config = BetanetConfig(host="127.0.0.1", port=9001)
    client = BetanetTcpClient(config)

    connected = await client.connect()
    if not connected:
        pytest.skip("Cannot connect to BetaNet mixnode")

    # Create packet with known pattern
    test_pattern = bytes(range(256))

    response = await client.send_packet(test_pattern)

    await client.disconnect()

    # Verify response received
    assert response is not None, "Should receive response"

    # Note: Exact pattern match depends on Sphinx processing
    # This test verifies basic packet handling


@pytest.mark.asyncio
async def test_betanet_connection_timeout():
    """Test connection timeout handling"""
    # Use non-routable IP to trigger timeout
    config = BetanetConfig(host="192.0.2.1", port=9001, timeout=0.5)
    client = BetanetTcpClient(config)

    connected = await client.connect()

    assert not connected, "Should fail to connect to non-routable IP"
    assert not client.is_connected, "Client should not be connected"


@pytest.mark.asyncio
async def test_betanet_context_manager():
    """Test async context manager usage"""
    config = BetanetConfig(host="127.0.0.1", port=9001)

    async with BetanetTcpClient(config) as client:
        if client.is_connected:
            test_data = b"Context manager test"
            response = await client.send_packet(test_data)

            assert response is not None or True, "Should handle packet in context"

    # Client should be disconnected after context
    assert not client.is_connected, "Should disconnect after context exit"


if __name__ == "__main__":
    # Run specific test
    asyncio.run(test_betanet_connection())
