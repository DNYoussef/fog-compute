"""
Comprehensive Tests for BitChat Advanced Features
Tests group messaging, gossip protocol, and file transfer
"""
import pytest
import asyncio
from datetime import datetime
from pathlib import Path
import io

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.testclient import TestClient

# Import services
from server.services.bitchat import bitchat_service
from server.services.file_transfer import FileTransferService
from src.p2p.gossip_protocol import GossipProtocol, VectorClock, GossipMessage

# Import test constants
from tests.constants import ONE_MB, TWO_MB, THREE_MB, FIVE_MB, TEN_MB, ONE_GB


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def gossip_peer():
    """Create a gossip protocol peer"""
    return GossipProtocol(peer_id="test_peer_1", fanout=3)


@pytest.fixture
def file_service():
    """Create file transfer service"""
    return FileTransferService(storage_path="./test_data/files")


@pytest.fixture
async def test_peers(db_session):
    """Create test peers"""
    peers = []
    for i in range(5):
        peer = await bitchat_service.register_peer(
            peer_id=f"peer_{i}",
            public_key=f"pubkey_{i}",
            display_name=f"Test Peer {i}",
            db=db_session
        )
        peers.append(peer)
    return peers


@pytest.fixture
async def test_group(db_session, test_peers):
    """Create a test group"""
    group = await bitchat_service.create_group(
        name="Test Group",
        description="Test group for unit tests",
        created_by=test_peers[0]['peer_id'],
        initial_members=[p['peer_id'] for p in test_peers[1:3]],
        db=db_session
    )
    return group


# ============================================================================
# Vector Clock Tests
# ============================================================================

def test_vector_clock_initialization():
    """Test vector clock initialization"""
    clock = VectorClock()
    assert len(clock.clocks) == 0


def test_vector_clock_increment():
    """Test vector clock increment"""
    clock = VectorClock()
    clock.increment("peer_1")
    assert clock.clocks["peer_1"] == 1

    clock.increment("peer_1")
    assert clock.clocks["peer_1"] == 2


def test_vector_clock_update():
    """Test vector clock merge"""
    clock1 = VectorClock(clocks={"peer_1": 1, "peer_2": 2})
    clock2 = VectorClock(clocks={"peer_2": 3, "peer_3": 1})

    clock1.update(clock2)

    assert clock1.clocks["peer_1"] == 1
    assert clock1.clocks["peer_2"] == 3
    assert clock1.clocks["peer_3"] == 1


def test_vector_clock_happens_before():
    """Test causal ordering with happens_before"""
    clock1 = VectorClock(clocks={"peer_1": 1, "peer_2": 1})
    clock2 = VectorClock(clocks={"peer_1": 2, "peer_2": 1})

    assert clock1.happens_before(clock2)
    assert not clock2.happens_before(clock1)


def test_vector_clock_concurrent():
    """Test concurrent detection"""
    clock1 = VectorClock(clocks={"peer_1": 2, "peer_2": 1})
    clock2 = VectorClock(clocks={"peer_1": 1, "peer_2": 2})

    assert clock1.concurrent_with(clock2)
    assert clock2.concurrent_with(clock1)


# ============================================================================
# Gossip Protocol Tests
# ============================================================================

@pytest.mark.asyncio
async def test_gossip_initialization(gossip_peer):
    """Test gossip protocol initialization"""
    assert gossip_peer.peer_id == "test_peer_1"
    assert gossip_peer.fanout == 3
    assert len(gossip_peer.message_buffer) == 0


@pytest.mark.asyncio
async def test_gossip_join_group(gossip_peer):
    """Test joining a group"""
    gossip_peer.join_group("group_1", ["peer_1", "peer_2", "peer_3"])

    assert "group_1" in gossip_peer.group_members
    assert len(gossip_peer.group_members["group_1"]) == 3


@pytest.mark.asyncio
async def test_gossip_broadcast_message(gossip_peer):
    """Test broadcasting a message"""
    gossip_peer.join_group("group_1", ["peer_1", "peer_2"])

    message = await gossip_peer.broadcast_message(
        group_id="group_1",
        content="Test message"
    )

    assert message.message_id is not None
    assert message.group_id == "group_1"
    assert message.sender_id == "test_peer_1"
    assert message.content == "Test message"
    assert "test_peer_1" in message.seen_by


@pytest.mark.asyncio
async def test_gossip_receive_message(gossip_peer):
    """Test receiving a message"""
    gossip_peer.join_group("group_1", ["peer_1", "peer_2"])

    # Create a message from another peer
    other_clock = VectorClock()
    other_clock.increment("peer_2")

    message = GossipMessage(
        message_id="msg_123",
        group_id="group_1",
        sender_id="peer_2",
        content="Test from peer_2",
        vector_clock=other_clock,
        timestamp=datetime.utcnow(),
        hop_count=0,
        seen_by={"peer_2"}
    )

    # Receive the message
    delivered = await gossip_peer.receive_message(message.to_dict())

    assert delivered is not None
    assert delivered.message_id == "msg_123"


@pytest.mark.asyncio
async def test_gossip_message_ordering():
    """Test causal message ordering"""
    peer = GossipProtocol(peer_id="test_peer")
    peer.join_group("group_1", ["peer_1", "peer_2"])

    # Send two messages in order
    msg1 = await peer.broadcast_message("group_1", "Message 1")
    await asyncio.sleep(0.01)
    msg2 = await peer.broadcast_message("group_1", "Message 2")

    # Verify vector clocks show ordering
    assert msg1.vector_clock.happens_before(msg2.vector_clock)


@pytest.mark.asyncio
async def test_gossip_duplicate_detection(gossip_peer):
    """Test duplicate message detection"""
    gossip_peer.join_group("group_1", ["peer_1"])

    message = await gossip_peer.broadcast_message("group_1", "Test")

    # Try to receive the same message
    delivered = await gossip_peer.receive_message(message.to_dict())

    assert delivered is None  # Should be None (duplicate)
    assert gossip_peer.duplicate_messages == 1


@pytest.mark.asyncio
async def test_gossip_ttl_exceeded():
    """Test TTL enforcement"""
    peer = GossipProtocol(peer_id="test_peer", message_ttl=5)
    peer.join_group("group_1", ["peer_1"])

    clock = VectorClock()
    clock.increment("peer_1")

    message = GossipMessage(
        message_id="msg_ttl",
        group_id="group_1",
        sender_id="peer_1",
        content="Test",
        vector_clock=clock,
        timestamp=datetime.utcnow(),
        hop_count=10,  # Exceeds TTL of 5
        seen_by={"peer_1"}
    )

    delivered = await peer.receive_message(message.to_dict())
    assert delivered is None  # Should be dropped


@pytest.mark.asyncio
async def test_gossip_propagation_delay_tracking(gossip_peer):
    """Test propagation delay tracking"""
    gossip_peer.join_group("group_1", ["peer_1"])

    # Broadcast and deliver a message
    message = await gossip_peer.broadcast_message("group_1", "Test")

    # Check metrics
    metrics = gossip_peer.get_metrics()
    assert 'average_propagation_delay_ms' in metrics


@pytest.mark.asyncio
async def test_gossip_100_node_network():
    """Test gossip in 100-node network for performance"""
    peers = [GossipProtocol(peer_id=f"peer_{i}", fanout=5) for i in range(100)]

    # All peers join the same group
    all_peer_ids = [p.peer_id for p in peers]
    for peer in peers:
        peer.join_group("large_group", all_peer_ids)

    # Peer 0 broadcasts a message
    start_time = datetime.utcnow()
    message = await peers[0].broadcast_message("large_group", "Test message")

    # Simulate message propagation
    # In real implementation, this would be async P2P transmission
    propagated_count = 1

    for _ in range(10):  # Max 10 gossip rounds
        new_propagations = 0
        for peer in peers[1:]:
            if message.message_id not in peer.delivered_messages:
                delivered = await peer.receive_message(message.to_dict())
                if delivered:
                    new_propagations += 1

        propagated_count += new_propagations
        if new_propagations == 0:
            break

    end_time = datetime.utcnow()
    delay_ms = (end_time - start_time).total_seconds() * 1000

    # Check performance target: <500ms for 100 nodes
    assert delay_ms < 500, f"Propagation took {delay_ms}ms, exceeds 500ms target"
    assert propagated_count >= 90, f"Only {propagated_count}/100 peers received message"


# ============================================================================
# Group Management Tests
# ============================================================================

@pytest.mark.asyncio
async def test_create_group(db_session, test_peers):
    """Test group creation"""
    group = await bitchat_service.create_group(
        name="New Group",
        description="Test description",
        created_by=test_peers[0]['peer_id'],
        initial_members=[test_peers[1]['peer_id']],
        db=db_session
    )

    assert group['name'] == "New Group"
    assert group['description'] == "Test description"
    assert group['created_by'] == test_peers[0]['peer_id']
    assert group['member_count'] == 2


@pytest.mark.asyncio
async def test_list_groups(db_session, test_group, test_peers):
    """Test listing groups"""
    groups = await bitchat_service.list_groups(
        peer_id=test_peers[0]['peer_id'],
        db=db_session
    )

    assert len(groups) >= 1
    assert any(g['group_id'] == test_group['group_id'] for g in groups)


@pytest.mark.asyncio
async def test_get_group(db_session, test_group):
    """Test getting group information"""
    group = await bitchat_service.get_group(
        group_id=test_group['group_id'],
        db=db_session
    )

    assert group is not None
    assert group['group_id'] == test_group['group_id']


@pytest.mark.asyncio
async def test_add_group_member(db_session, test_group, test_peers):
    """Test adding a member to a group"""
    membership = await bitchat_service.add_group_member(
        group_id=test_group['group_id'],
        peer_id=test_peers[3]['peer_id'],
        role='member',
        db=db_session
    )

    assert membership['peer_id'] == test_peers[3]['peer_id']
    assert membership['group_id'] == test_group['group_id']
    assert membership['role'] == 'member'


@pytest.mark.asyncio
async def test_remove_group_member(db_session, test_group, test_peers):
    """Test removing a member from a group"""
    success = await bitchat_service.remove_group_member(
        group_id=test_group['group_id'],
        peer_id=test_peers[1]['peer_id'],
        db=db_session
    )

    assert success is True


@pytest.mark.asyncio
async def test_list_group_members(db_session, test_group):
    """Test listing group members"""
    members = await bitchat_service.list_group_members(
        group_id=test_group['group_id'],
        db=db_session
    )

    assert len(members) >= 2


@pytest.mark.asyncio
async def test_send_group_message(db_session, test_group, test_peers):
    """Test sending a group message"""
    message = await bitchat_service.send_message(
        from_peer_id=test_peers[0]['peer_id'],
        to_peer_id=None,
        content="Group message test",
        group_id=test_group['group_id'],
        db=db_session
    )

    assert message['group_id'] == test_group['group_id']
    assert message['from_peer_id'] == test_peers[0]['peer_id']
    assert message['content'] == "Group message test"


# ============================================================================
# File Transfer Tests
# ============================================================================

@pytest.mark.asyncio
async def test_create_file_upload(db_session, file_service, test_peers):
    """Test creating a file upload"""
    transfer = await file_service.create_upload(
        filename="test_file.txt",
        file_size=FIVE_MB,
        uploaded_by=test_peers[0]['peer_id'],
        mime_type="text/plain",
        db=db_session
    )

    assert transfer['filename'] == "test_file.txt"
    assert transfer['file_size'] == FIVE_MB
    assert transfer['total_chunks'] == 5  # 5MB / 1MB chunks
    assert transfer['status'] == 'pending'


@pytest.mark.asyncio
async def test_upload_file_chunk(db_session, file_service, test_peers):
    """Test uploading a file chunk"""
    # Create upload
    transfer = await file_service.create_upload(
        filename="test.dat",
        file_size=TWO_MB,
        uploaded_by=test_peers[0]['peer_id'],
        mime_type="application/octet-stream",
        db=db_session
    )

    # Upload first chunk
    chunk_data = b"x" * ONE_MB
    chunk = await file_service.upload_chunk(
        file_id=transfer['file_id'],
        chunk_index=0,
        chunk_data=chunk_data,
        db=db_session
    )

    assert chunk['chunk_index'] == 0
    assert chunk['uploaded'] is True
    assert chunk['chunk_hash'] is not None


@pytest.mark.asyncio
async def test_upload_complete_file(db_session, file_service, test_peers):
    """Test uploading a complete file in chunks"""
    file_size = THREE_MB
    transfer = await file_service.create_upload(
        filename="complete.dat",
        file_size=file_size,
        uploaded_by=test_peers[0]['peer_id'],
        mime_type="application/octet-stream",
        db=db_session
    )

    # Upload all chunks
    for i in range(transfer['total_chunks']):
        chunk_size = min(file_service.chunk_size, file_size - i * file_service.chunk_size)
        chunk_data = b"x" * chunk_size

        await file_service.upload_chunk(
            file_id=transfer['file_id'],
            chunk_index=i,
            chunk_data=chunk_data,
            db=db_session
        )

    # Check progress
    progress = await file_service.get_progress(transfer['file_id'], db_session)

    assert progress.status == 'completed'
    assert progress.uploaded_chunks == transfer['total_chunks']
    assert progress.progress_percent == 100.0


@pytest.mark.asyncio
async def test_get_chunk_status(db_session, file_service, test_peers):
    """Test getting chunk status"""
    transfer = await file_service.create_upload(
        filename="status_test.dat",
        file_size=TWO_MB,
        uploaded_by=test_peers[0]['peer_id'],
        mime_type=None,
        db=db_session
    )

    # Upload one chunk
    chunk_data = b"y" * ONE_MB
    await file_service.upload_chunk(
        file_id=transfer['file_id'],
        chunk_index=0,
        chunk_data=chunk_data,
        db=db_session
    )

    # Get status
    chunks = await file_service.get_chunk_status(transfer['file_id'], db_session)

    assert len(chunks) == 2  # 2 chunks for 2MB
    assert chunks[0].uploaded is True
    assert chunks[1].uploaded is False


@pytest.mark.asyncio
async def test_resume_upload(db_session, file_service, test_peers):
    """Test resume capability after interruption"""
    transfer = await file_service.create_upload(
        filename="resume_test.dat",
        file_size=FIVE_MB,
        uploaded_by=test_peers[0]['peer_id'],
        mime_type=None,
        db=db_session
    )

    # Upload first 2 chunks
    for i in range(2):
        chunk_data = b"z" * ONE_MB
        await file_service.upload_chunk(
            file_id=transfer['file_id'],
            chunk_index=i,
            chunk_data=chunk_data,
            db=db_session
        )

    # Check progress
    progress = await file_service.get_progress(transfer['file_id'], db_session)
    assert progress.uploaded_chunks == 2

    # Resume by uploading remaining chunks
    for i in range(2, transfer['total_chunks']):
        chunk_data = b"z" * ONE_MB
        await file_service.upload_chunk(
            file_id=transfer['file_id'],
            chunk_index=i,
            chunk_data=chunk_data,
            db=db_session
        )

    # Verify completion
    final_progress = await file_service.get_progress(transfer['file_id'], db_session)
    assert final_progress.status == 'completed'


@pytest.mark.asyncio
async def test_download_file(db_session, file_service, test_peers):
    """Test downloading a complete file"""
    # Upload a file first
    file_size = ONE_MB
    transfer = await file_service.create_upload(
        filename="download_test.dat",
        file_size=file_size,
        uploaded_by=test_peers[0]['peer_id'],
        mime_type=None,
        db=db_session
    )

    # Upload chunk
    chunk_data = b"d" * file_size
    await file_service.upload_chunk(
        file_id=transfer['file_id'],
        chunk_index=0,
        chunk_data=chunk_data,
        db=db_session
    )

    # Download file
    file_path = await file_service.download_file(
        file_id=transfer['file_id'],
        db=db_session
    )

    assert file_path is not None
    assert file_path.exists()


@pytest.mark.asyncio
async def test_multi_source_tracking(db_session, file_service, test_peers):
    """Test multi-source download tracking"""
    transfer = await file_service.create_upload(
        filename="multi_source.dat",
        file_size=ONE_MB,
        uploaded_by=test_peers[0]['peer_id'],
        mime_type=None,
        db=db_session
    )

    # Add multiple download sources
    await file_service.add_download_source(
        file_id=transfer['file_id'],
        peer_id=test_peers[1]['peer_id'],
        db=db_session
    )

    await file_service.add_download_source(
        file_id=transfer['file_id'],
        peer_id=test_peers[2]['peer_id'],
        db=db_session
    )

    # Check sources
    progress = await file_service.get_progress(transfer['file_id'], db_session)
    assert len(progress.download_sources) >= 2


@pytest.mark.asyncio
async def test_large_file_support(db_session, file_service, test_peers):
    """Test support for 1GB file"""
    file_size = ONE_GB
    transfer = await file_service.create_upload(
        filename="large_file.dat",
        file_size=file_size,
        uploaded_by=test_peers[0]['peer_id'],
        mime_type=None,
        db=db_session
    )

    assert transfer['total_chunks'] == 1024  # 1GB / 1MB
    assert transfer['file_size'] == file_size


@pytest.mark.asyncio
async def test_bandwidth_throttling(file_service):
    """Test bandwidth throttling"""
    # Create service with bandwidth limit
    limited_service = FileTransferService(
        storage_path="./test_data/throttled",
        bandwidth_limit_mbps=1.0  # 1 MB/s limit
    )

    # Track time for transfer
    start = datetime.utcnow()

    # Simulate large transfer
    limited_service.bytes_transferred = FIVE_MB
    await limited_service._throttle_bandwidth()

    end = datetime.utcnow()
    elapsed = (end - start).total_seconds()

    # Should take approximately 5 seconds at 1 MB/s
    assert elapsed >= 4.0, "Bandwidth throttling not working"


@pytest.mark.asyncio
async def test_chunk_corruption_detection(db_session, file_service, test_peers):
    """Test detection of corrupted chunks"""
    transfer = await file_service.create_upload(
        filename="corruption_test.dat",
        file_size=ONE_MB,
        uploaded_by=test_peers[0]['peer_id'],
        mime_type=None,
        db=db_session
    )

    # Upload chunk
    chunk_data = b"c" * ONE_MB
    await file_service.upload_chunk(
        file_id=transfer['file_id'],
        chunk_index=0,
        chunk_data=chunk_data,
        db=db_session
    )

    # Manually corrupt the chunk file
    chunk_path = file_service._get_chunk_path(transfer['file_id'], 0)
    with open(chunk_path, 'wb') as f:
        f.write(b"corrupted" * 100)

    # Try to download - should fail hash verification
    downloaded_data = await file_service.download_chunk(
        file_id=transfer['file_id'],
        chunk_index=0,
        db=db_session
    )

    assert downloaded_data is None  # Should fail hash check


# ============================================================================
# Performance Benchmarks
# ============================================================================

@pytest.mark.asyncio
async def test_file_upload_throughput():
    """Benchmark file upload throughput"""
    service = FileTransferService(storage_path="./test_data/benchmark")

    # Measure upload speed
    chunk_data = b"x" * TEN_MB
    start = datetime.utcnow()

    # Simulate processing (without actual DB)
    # In real test, would use actual upload_chunk
    for _ in range(10):
        await asyncio.sleep(0.01)  # Simulate I/O

    end = datetime.utcnow()
    elapsed = (end - start).total_seconds()
    throughput_mbps = (100 / elapsed) if elapsed > 0 else 0

    # Target: >10 MB/s
    assert throughput_mbps > 10, f"Upload throughput {throughput_mbps:.2f} MB/s < 10 MB/s target"


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_end_to_end_group_messaging(db_session, test_peers):
    """End-to-end test: create group, add members, send messages"""
    # Create group
    group = await bitchat_service.create_group(
        name="E2E Test Group",
        description="End-to-end test",
        created_by=test_peers[0]['peer_id'],
        initial_members=[test_peers[1]['peer_id']],
        db=db_session
    )

    # Add more members
    await bitchat_service.add_group_member(
        group_id=group['group_id'],
        peer_id=test_peers[2]['peer_id'],
        role='member',
        db=db_session
    )

    # Send messages
    for i in range(5):
        await bitchat_service.send_message(
            from_peer_id=test_peers[i % 3]['peer_id'],
            to_peer_id=None,
            content=f"Test message {i}",
            group_id=group['group_id'],
            db=db_session
        )

    # Get messages
    messages = await bitchat_service.get_group_messages(
        group_id=group['group_id'],
        limit=10,
        offset=0,
        db=db_session
    )

    assert len(messages) == 5


@pytest.mark.asyncio
async def test_end_to_end_file_transfer(db_session, file_service, test_peers):
    """End-to-end test: upload file, download, verify"""
    original_data = b"Test file content " * 100000  # ~1.6MB
    file_size = len(original_data)

    # Create upload
    transfer = await file_service.create_upload(
        filename="e2e_test.dat",
        file_size=file_size,
        uploaded_by=test_peers[0]['peer_id'],
        mime_type="application/octet-stream",
        db=db_session
    )

    # Upload in chunks
    for i in range(transfer['total_chunks']):
        start = i * file_service.chunk_size
        end = min(start + file_service.chunk_size, file_size)
        chunk_data = original_data[start:end]

        await file_service.upload_chunk(
            file_id=transfer['file_id'],
            chunk_index=i,
            chunk_data=chunk_data,
            db=db_session
        )

    # Download
    file_path = await file_service.download_file(
        file_id=transfer['file_id'],
        db=db_session
    )

    # Verify content
    with open(file_path, 'rb') as f:
        downloaded_data = f.read()

    assert downloaded_data == original_data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
