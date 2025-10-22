"""
BitChat Integration Test Script
Quick test to verify BitChat API functionality
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from httpx import AsyncClient


async def test_bitchat_integration():
    """Test complete BitChat workflow"""
    base_url = "http://localhost:8000"

    async with AsyncClient(base_url=base_url) as client:
        print("🧪 Testing BitChat Integration...")
        print("=" * 60)

        # Test 1: Health check
        print("\n1️⃣ Testing health check...")
        try:
            response = await client.get("/health")
            if response.status_code == 200:
                print("   ✅ Health check passed")
            else:
                print(f"   ❌ Health check failed: {response.status_code}")
        except Exception as e:
            print(f"   ⚠️  Server may not be running: {e}")
            return

        # Test 2: Get stats (before any peers)
        print("\n2️⃣ Testing BitChat stats...")
        try:
            response = await client.get("/api/bitchat/stats")
            if response.status_code == 200:
                stats = response.json()
                print(f"   ✅ Stats retrieved: {stats}")
            else:
                print(f"   ❌ Stats failed: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Test 3: Register first peer
        print("\n3️⃣ Registering first peer...")
        peer1_data = {
            "peer_id": "test-peer-alice",
            "public_key": "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...",
            "display_name": "Alice"
        }
        try:
            response = await client.post("/api/bitchat/peers/register", json=peer1_data)
            if response.status_code == 201:
                peer1 = response.json()
                print(f"   ✅ Peer registered: {peer1['display_name']} ({peer1['peer_id']})")
                print(f"      Trust score: {peer1['trust_score']}")
            else:
                print(f"   ❌ Registration failed: {response.status_code}")
                print(f"      {response.text}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Test 4: Register second peer
        print("\n4️⃣ Registering second peer...")
        peer2_data = {
            "peer_id": "test-peer-bob",
            "public_key": "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEB...",
            "display_name": "Bob"
        }
        try:
            response = await client.post("/api/bitchat/peers/register", json=peer2_data)
            if response.status_code == 201:
                peer2 = response.json()
                print(f"   ✅ Peer registered: {peer2['display_name']} ({peer2['peer_id']})")
            else:
                print(f"   ❌ Registration failed: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Test 5: List all peers
        print("\n5️⃣ Listing all peers...")
        try:
            response = await client.get("/api/bitchat/peers")
            if response.status_code == 200:
                peers = response.json()
                print(f"   ✅ Found {len(peers)} peer(s)")
                for peer in peers:
                    print(f"      - {peer['display_name']} (online: {peer['is_online']})")
            else:
                print(f"   ❌ List failed: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Test 6: Send a message
        print("\n6️⃣ Sending encrypted message...")
        message_data = {
            "from_peer_id": peer1_data["peer_id"],
            "to_peer_id": peer2_data["peer_id"],
            "content": "U2FsdGVkX1+encrypted_message_content_here",
            "encryption_algorithm": "AES-256-GCM",
            "nonce": "random-nonce-abc123"
        }
        try:
            response = await client.post("/api/bitchat/messages/send", json=message_data)
            if response.status_code == 201:
                message = response.json()
                print(f"   ✅ Message sent: {message['message_id']}")
                print(f"      Status: {message['status']}")
                print(f"      Hop count: {message['hop_count']}")
            else:
                print(f"   ❌ Send failed: {response.status_code}")
                print(f"      {response.text}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Test 7: Send another message (reverse direction)
        print("\n7️⃣ Sending reply message...")
        reply_data = {
            "from_peer_id": peer2_data["peer_id"],
            "to_peer_id": peer1_data["peer_id"],
            "content": "U2FsdGVkX1+reply_encrypted_content",
            "encryption_algorithm": "AES-256-GCM"
        }
        try:
            response = await client.post("/api/bitchat/messages/send", json=reply_data)
            if response.status_code == 201:
                print(f"   ✅ Reply sent")
            else:
                print(f"   ❌ Reply failed: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Test 8: Get conversation history
        print("\n8️⃣ Retrieving conversation history...")
        try:
            response = await client.get(
                f"/api/bitchat/messages/conversation/{peer1_data['peer_id']}/{peer2_data['peer_id']}"
            )
            if response.status_code == 200:
                messages = response.json()
                print(f"   ✅ Retrieved {len(messages)} message(s)")
                for i, msg in enumerate(messages, 1):
                    print(f"      {i}. From {msg['from_peer_id']}: {msg['status']}")
            else:
                print(f"   ❌ Conversation failed: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Test 9: Update peer stats
        print("\n9️⃣ Checking updated peer stats...")
        try:
            response = await client.get(f"/api/bitchat/peers/{peer1_data['peer_id']}")
            if response.status_code == 200:
                peer = response.json()
                print(f"   ✅ {peer['display_name']} stats:")
                print(f"      Messages sent: {peer['messages_sent']}")
                print(f"      Messages received: {peer['messages_received']}")
            else:
                print(f"   ❌ Stats failed: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Test 10: Final statistics
        print("\n🔟 Final BitChat statistics...")
        try:
            response = await client.get("/api/bitchat/stats")
            if response.status_code == 200:
                stats = response.json()
                print(f"   ✅ Service status: {stats['status']}")
                print(f"      Total peers: {stats['total_peers']}")
                print(f"      Online peers: {stats['online_peers']}")
                print(f"      Total messages: {stats['total_messages']}")
                print(f"      Messages (24h): {stats['messages_24h']}")
            else:
                print(f"   ❌ Stats failed: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        print("\n" + "=" * 60)
        print("✅ BitChat Integration Test Complete!")


if __name__ == "__main__":
    print("🚀 Starting BitChat Integration Test")
    print("📝 Make sure the backend server is running:")
    print("   cd backend && python -m server.main\n")

    asyncio.run(test_bitchat_integration())
