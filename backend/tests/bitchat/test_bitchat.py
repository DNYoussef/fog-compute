"""
BitChat Service Integration Tests
Tests for P2P messaging functionality
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from ..main import app
from ..database import get_db
from ..models.database import Peer, Message


@pytest.fixture
async def test_peer_data():
    """Sample peer data for testing"""
    return {
        "peer_id": f"test-peer-{uuid.uuid4()}",
        "public_key": "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...",
        "display_name": "Test Peer"
    }


@pytest.fixture
async def test_peer_data_2():
    """Second sample peer for conversation testing"""
    return {
        "peer_id": f"test-peer-{uuid.uuid4()}",
        "public_key": "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEB...",
        "display_name": "Test Peer 2"
    }


class TestPeerManagement:
    """Test peer registration and management"""

    @pytest.mark.asyncio
    async def test_register_peer(self, test_peer_data):
        """Test registering a new peer"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/bitchat/peers/register",
                json=test_peer_data
            )

            assert response.status_code == 201
            data = response.json()
            assert data["peer_id"] == test_peer_data["peer_id"]
            assert data["public_key"] == test_peer_data["public_key"]
            assert data["display_name"] == test_peer_data["display_name"]
            assert data["is_online"] is True
            assert data["trust_score"] == 0.5
            assert data["messages_sent"] == 0
            assert data["messages_received"] == 0

    @pytest.mark.asyncio
    async def test_register_duplicate_peer(self, test_peer_data):
        """Test updating existing peer"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Register first time
            response1 = await client.post(
                "/api/bitchat/peers/register",
                json=test_peer_data
            )
            assert response1.status_code == 201

            # Register again with updated info
            updated_data = test_peer_data.copy()
            updated_data["display_name"] = "Updated Name"
            response2 = await client.post(
                "/api/bitchat/peers/register",
                json=updated_data
            )

            assert response2.status_code == 201
            data = response2.json()
            assert data["display_name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_list_peers(self, test_peer_data):
        """Test listing all peers"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Register a peer
            await client.post("/api/bitchat/peers/register", json=test_peer_data)

            # List all peers
            response = await client.get("/api/bitchat/peers")
            assert response.status_code == 200

            peers = response.json()
            assert isinstance(peers, list)
            assert len(peers) > 0
            assert any(p["peer_id"] == test_peer_data["peer_id"] for p in peers)

    @pytest.mark.asyncio
    async def test_list_online_peers_only(self, test_peer_data):
        """Test filtering online peers"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Register a peer
            await client.post("/api/bitchat/peers/register", json=test_peer_data)

            # List online peers only
            response = await client.get("/api/bitchat/peers?online_only=true")
            assert response.status_code == 200

            peers = response.json()
            assert all(p["is_online"] for p in peers)

    @pytest.mark.asyncio
    async def test_get_peer(self, test_peer_data):
        """Test getting specific peer"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Register a peer
            await client.post("/api/bitchat/peers/register", json=test_peer_data)

            # Get peer by ID
            response = await client.get(f"/api/bitchat/peers/{test_peer_data['peer_id']}")
            assert response.status_code == 200

            peer = response.json()
            assert peer["peer_id"] == test_peer_data["peer_id"]

    @pytest.mark.asyncio
    async def test_get_nonexistent_peer(self):
        """Test getting peer that doesn't exist"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/bitchat/peers/nonexistent-peer")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_peer_status(self, test_peer_data):
        """Test updating peer online status"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Register a peer
            await client.post("/api/bitchat/peers/register", json=test_peer_data)

            # Update status to offline
            response = await client.put(
                f"/api/bitchat/peers/{test_peer_data['peer_id']}/status",
                params={"is_online": False}
            )
            assert response.status_code == 200

            # Verify status was updated
            get_response = await client.get(f"/api/bitchat/peers/{test_peer_data['peer_id']}")
            peer = get_response.json()
            assert peer["is_online"] is False


class TestMessaging:
    """Test message sending and retrieval"""

    @pytest.mark.asyncio
    async def test_send_message(self, test_peer_data, test_peer_data_2):
        """Test sending a message"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Register two peers
            await client.post("/api/bitchat/peers/register", json=test_peer_data)
            await client.post("/api/bitchat/peers/register", json=test_peer_data_2)

            # Send message
            message_data = {
                "from_peer_id": test_peer_data["peer_id"],
                "to_peer_id": test_peer_data_2["peer_id"],
                "content": "encrypted-message-content-here",
                "encryption_algorithm": "AES-256-GCM",
                "nonce": "random-nonce-123",
                "ttl": 3600
            }

            response = await client.post("/api/bitchat/messages/send", json=message_data)
            assert response.status_code == 201

            message = response.json()
            assert message["from_peer_id"] == test_peer_data["peer_id"]
            assert message["to_peer_id"] == test_peer_data_2["peer_id"]
            assert message["content"] == "encrypted-message-content-here"
            assert message["status"] == "sent"
            assert message["hop_count"] == 0

    @pytest.mark.asyncio
    async def test_send_group_message(self, test_peer_data):
        """Test sending a group message"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Register peer
            await client.post("/api/bitchat/peers/register", json=test_peer_data)

            # Send group message
            message_data = {
                "from_peer_id": test_peer_data["peer_id"],
                "group_id": "test-group-123",
                "content": "encrypted-group-message",
                "encryption_algorithm": "AES-256-GCM"
            }

            response = await client.post("/api/bitchat/messages/send", json=message_data)
            assert response.status_code == 201

            message = response.json()
            assert message["group_id"] == "test-group-123"
            assert message["to_peer_id"] is None

    @pytest.mark.asyncio
    async def test_get_conversation(self, test_peer_data, test_peer_data_2):
        """Test retrieving conversation history"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Register peers
            await client.post("/api/bitchat/peers/register", json=test_peer_data)
            await client.post("/api/bitchat/peers/register", json=test_peer_data_2)

            # Send messages
            for i in range(3):
                await client.post("/api/bitchat/messages/send", json={
                    "from_peer_id": test_peer_data["peer_id"],
                    "to_peer_id": test_peer_data_2["peer_id"],
                    "content": f"message-{i}"
                })

            # Get conversation
            response = await client.get(
                f"/api/bitchat/messages/conversation/{test_peer_data['peer_id']}/{test_peer_data_2['peer_id']}"
            )
            assert response.status_code == 200

            messages = response.json()
            assert len(messages) == 3
            # Messages should be in chronological order
            assert messages[0]["content"] == "message-0"
            assert messages[2]["content"] == "message-2"

    @pytest.mark.asyncio
    async def test_get_conversation_pagination(self, test_peer_data, test_peer_data_2):
        """Test conversation pagination"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Register peers
            await client.post("/api/bitchat/peers/register", json=test_peer_data)
            await client.post("/api/bitchat/peers/register", json=test_peer_data_2)

            # Send 10 messages
            for i in range(10):
                await client.post("/api/bitchat/messages/send", json={
                    "from_peer_id": test_peer_data["peer_id"],
                    "to_peer_id": test_peer_data_2["peer_id"],
                    "content": f"message-{i}"
                })

            # Get first page
            response1 = await client.get(
                f"/api/bitchat/messages/conversation/{test_peer_data['peer_id']}/{test_peer_data_2['peer_id']}?limit=5&offset=0"
            )
            assert response1.status_code == 200
            messages1 = response1.json()
            assert len(messages1) == 5

            # Get second page
            response2 = await client.get(
                f"/api/bitchat/messages/conversation/{test_peer_data['peer_id']}/{test_peer_data_2['peer_id']}?limit=5&offset=5"
            )
            assert response2.status_code == 200
            messages2 = response2.json()
            assert len(messages2) == 5

            # Ensure no overlap
            message_ids_1 = {m["message_id"] for m in messages1}
            message_ids_2 = {m["message_id"] for m in messages2}
            assert len(message_ids_1.intersection(message_ids_2)) == 0

    @pytest.mark.asyncio
    async def test_mark_message_delivered(self, test_peer_data, test_peer_data_2):
        """Test marking message as delivered"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Register peers and send message
            await client.post("/api/bitchat/peers/register", json=test_peer_data)
            await client.post("/api/bitchat/peers/register", json=test_peer_data_2)

            send_response = await client.post("/api/bitchat/messages/send", json={
                "from_peer_id": test_peer_data["peer_id"],
                "to_peer_id": test_peer_data_2["peer_id"],
                "content": "test-message"
            })
            message = send_response.json()
            message_id = message["message_id"]

            # Mark as delivered
            response = await client.put(f"/api/bitchat/messages/{message_id}/delivered")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_message_stats_update(self, test_peer_data, test_peer_data_2):
        """Test that message stats are updated correctly"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Register peers
            reg1 = await client.post("/api/bitchat/peers/register", json=test_peer_data)
            reg2 = await client.post("/api/bitchat/peers/register", json=test_peer_data_2)

            peer1_before = reg1.json()
            peer2_before = reg2.json()

            # Send message
            await client.post("/api/bitchat/messages/send", json={
                "from_peer_id": test_peer_data["peer_id"],
                "to_peer_id": test_peer_data_2["peer_id"],
                "content": "test-message"
            })

            # Check updated stats
            peer1_response = await client.get(f"/api/bitchat/peers/{test_peer_data['peer_id']}")
            peer1_after = peer1_response.json()
            assert peer1_after["messages_sent"] == peer1_before["messages_sent"] + 1

            peer2_response = await client.get(f"/api/bitchat/peers/{test_peer_data_2['peer_id']}")
            peer2_after = peer2_response.json()
            assert peer2_after["messages_received"] == peer2_before["messages_received"] + 1


class TestStatistics:
    """Test BitChat statistics"""

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test getting service statistics"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/bitchat/stats")
            assert response.status_code == 200

            stats = response.json()
            assert "total_peers" in stats
            assert "online_peers" in stats
            assert "active_connections" in stats
            assert "total_messages" in stats
            assert "messages_24h" in stats
            assert "status" in stats
            assert stats["status"] in ["operational", "error"]

    @pytest.mark.asyncio
    async def test_stats_accuracy(self, test_peer_data):
        """Test that statistics are accurate"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Get initial stats
            initial_stats = (await client.get("/api/bitchat/stats")).json()

            # Register a peer
            await client.post("/api/bitchat/peers/register", json=test_peer_data)

            # Get updated stats
            updated_stats = (await client.get("/api/bitchat/stats")).json()

            # Verify peer count increased
            assert updated_stats["total_peers"] >= initial_stats["total_peers"] + 1
            assert updated_stats["online_peers"] >= initial_stats["online_peers"] + 1
