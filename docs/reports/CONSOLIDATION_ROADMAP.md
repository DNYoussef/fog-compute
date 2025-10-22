# Consolidation Roadmap
## Step-by-Step Migration Plan for Fog Compute Infrastructure

**Date**: 2025-10-21
**Timeline**: 8 weeks to production-ready
**Engineers Required**: 4 (1 Rust, 1 Python, 1 Full-stack, 1 DevOps)

---

## Executive Summary

This roadmap provides a **detailed, phase-by-phase migration plan** to consolidate the fog-compute infrastructure from its current **72% completeness** to **100% production-ready** status.

**Key Consolidations**:
1. **BetaNet + VPN** → Unified privacy layer (Rust transport + Python services)
2. **P2P + BitChat** → Integrated messaging (P2P coordinator + BitChat transport)
3. **Docker Configs** → Single base + environment overrides

**Critical Path**: Fix security bugs → Consolidate overlaps → Complete features → Production deploy

---

## Phase 1: Critical Security Fixes (Week 1)

### Priority 0: VPN Crypto Bug Fix

**Issue**: Random nonce breaks AES-CTR decryption
**File**: `src/vpn/onion_routing.py:396`
**Severity**: 🔴 **CRITICAL** - 100% packet decryption failure
**Timeline**: **4 hours**

#### Step 1.1: Fix Decryption Function (30 min)

```python
# File: src/vpn/onion_routing.py
# Line: ~410

def _decrypt_layer(self, ciphertext: bytes, layer_key: bytes) -> bytes:
    """
    Decrypt data with layer key using AES-CTR.

    FIX: Extract nonce from ciphertext (prepended during encryption)
    """
    # Extract the nonce (first 16 bytes)
    if len(ciphertext) < 16:
        raise ValueError("Ciphertext too short - missing nonce")

    nonce = ciphertext[:16]
    actual_ciphertext = ciphertext[16:]

    cipher = Cipher(
        algorithms.AES(layer_key),
        modes.CTR(nonce),  # Use extracted nonce
        backend=default_backend()
    )
    decryptor = cipher.decryptor()
    plaintext = decryptor.update(actual_ciphertext) + decryptor.finalize()

    return plaintext
```

#### Step 1.2: Add Unit Tests (1 hour)

```python
# File: backend/tests/test_vpn_crypto.py (NEW)

import pytest
from src.vpn.onion_routing import OnionRouter

def test_encrypt_decrypt_round_trip():
    """Test that encryption + decryption returns original plaintext"""
    router = OnionRouter()

    plaintext = b"Hello, privacy world!"
    layer_key = os.urandom(32)  # 256-bit key

    # Encrypt
    ciphertext = router._encrypt_layer(plaintext, layer_key)

    # Decrypt
    recovered = router._decrypt_layer(ciphertext, layer_key)

    assert recovered == plaintext, "Decryption failed to recover plaintext"

def test_multi_hop_circuit():
    """Test 3-hop circuit encryption/decryption"""
    router = OnionRouter()

    plaintext = b"Secret message"
    keys = [os.urandom(32) for _ in range(3)]  # 3 layer keys

    # Wrap in 3 layers (onion)
    onion = plaintext
    for key in reversed(keys):
        onion = router._encrypt_layer(onion, key)

    # Unwrap 3 layers (peel onion)
    for key in keys:
        onion = router._decrypt_layer(onion, key)

    assert onion == plaintext, "Multi-hop decryption failed"
```

**Run tests**:
```bash
cd backend
python -m pytest tests/test_vpn_crypto.py -v
```

#### Step 1.3: Integration Test (1 hour)

```python
# File: backend/tests/test_vpn_integration.py (NEW)

async def test_full_circuit_creation():
    """Test complete circuit: build → encrypt → route → decrypt"""

    # Initialize service
    circuit_service = OnionCircuitService(db_session)

    # Create 3-hop circuit
    circuit = await circuit_service.create_circuit(num_hops=3)

    assert circuit is not None
    assert len(circuit.hops) == 3

    # Send test message through circuit
    plaintext = b"Test message through circuit"
    encrypted = circuit_service.encrypt_for_circuit(plaintext, circuit)

    # Simulate each hop decrypting one layer
    current = encrypted
    for hop in circuit.hops:
        current = hop.decrypt_layer(current)

    assert current == plaintext, "Full circuit test failed"
```

#### Step 1.4: Verify & Deploy (1.5 hours)

**Verification**:
```bash
# Run all VPN tests
python -m pytest tests/test_vpn*.py -v

# Start backend with VPN enabled
cd backend
python -m uvicorn server.main:app --reload

# Test via API
curl -X POST http://localhost:8000/api/privacy/circuits \
  -H "Content-Type: application/json" \
  -d '{"num_hops": 3}'

# Verify circuit creation succeeds
```

**Success Criteria**:
- ✅ All unit tests pass
- ✅ Integration test passes
- ✅ API returns valid circuit
- ✅ No decryption errors in logs

**Deliverables**:
- Fixed `onion_routing.py`
- 2 new test files (`test_vpn_crypto.py`, `test_vpn_integration.py`)
- Verification report

---

### Priority 0: BetaNet Network I/O

**Issue**: Mixnode processes packets but doesn't send over network
**Location**: `src/betanet/server/`, `src/betanet/core/mixnode.rs`
**Severity**: 🔴 **CRITICAL** - No actual networking
**Timeline**: **2 days**

#### Step 2.1: Add Tokio TCP Server (Day 1, 4 hours)

```rust
// File: src/betanet/server/tcp.rs (NEW)

use tokio::net::{TcpListener, TcpStream};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use std::sync::Arc;
use crate::core::mixnode::Mixnode;
use crate::pipeline::PacketPipeline;

pub struct TcpServer {
    listener: TcpListener,
    mixnode: Arc<Mixnode>,
    pipeline: Arc<PacketPipeline>,
}

impl TcpServer {
    pub async fn new(addr: &str, mixnode: Mixnode) -> Result<Self, std::io::Error> {
        let listener = TcpListener::bind(addr).await?;

        Ok(Self {
            listener,
            mixnode: Arc::new(mixnode),
            pipeline: Arc::new(PacketPipeline::new(1024, 128)),
        })
    }

    pub async fn run(&self) -> Result<(), std::io::Error> {
        println!("Betanet mixnode listening on {}", self.listener.local_addr()?);

        loop {
            let (socket, addr) = self.listener.accept().await?;
            let mixnode = Arc::clone(&self.mixnode);
            let pipeline = Arc::clone(&self.pipeline);

            // Spawn task for each connection
            tokio::spawn(async move {
                if let Err(e) = handle_connection(socket, mixnode, pipeline).await {
                    eprintln!("Connection error from {}: {}", addr, e);
                }
            });
        }
    }
}

async fn handle_connection(
    mut socket: TcpStream,
    mixnode: Arc<Mixnode>,
    pipeline: Arc<PacketPipeline>,
) -> Result<(), std::io::Error> {
    let mut buffer = vec![0u8; 4096];

    loop {
        let n = socket.read(&mut buffer).await?;
        if n == 0 {
            break; // Connection closed
        }

        let packet = &buffer[..n];

        // Process through pipeline (existing code)
        let processed = pipeline.process_packet(packet).await;

        // Send processed packet (if any)
        if let Some(output) = processed {
            socket.write_all(&output).await?;
        }
    }

    Ok(())
}
```

#### Step 2.2: Update Mixnode Main (Day 1, 2 hours)

```rust
// File: src/betanet/server/mod.rs

mod tcp;
mod http;

use tcp::TcpServer;
use crate::core::mixnode::Mixnode;
use crate::core::config::MixnodeConfig;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Load config
    let config = MixnodeConfig::from_env()?;

    // Create mixnode
    let mixnode = Mixnode::new(config)?;

    // Start TCP server
    let tcp_server = TcpServer::new("0.0.0.0:9001", mixnode).await?;

    // Run server
    tcp_server.run().await?;

    Ok(())
}
```

#### Step 2.3: Test Networking (Day 1, 2 hours)

```rust
// File: src/betanet/tests/test_networking.rs (NEW)

#[tokio::test]
async fn test_tcp_send_receive() {
    // Start mixnode server in background
    let mixnode = Mixnode::new(test_config())?;
    let server = TcpServer::new("127.0.0.1:9001", mixnode).await?;

    tokio::spawn(async move {
        server.run().await
    });

    // Give server time to start
    tokio::time::sleep(Duration::from_millis(100)).await;

    // Connect as client
    let mut client = TcpStream::connect("127.0.0.1:9001").await?;

    // Send test packet
    let test_packet = b"test sphinx packet";
    client.write_all(test_packet).await?;

    // Receive processed packet
    let mut buffer = vec![0u8; 4096];
    let n = client.read(&mut buffer).await?;

    assert!(n > 0, "No response from mixnode");
    println!("Received {} bytes from mixnode", n);
}
```

#### Step 2.4: Integration with Backend (Day 2, 4 hours)

```python
# File: backend/server/services/betanet_client.py (UPDATE)

import asyncio
import struct

class BetanetTcpClient:
    """Client for connecting to Betanet mixnode over TCP"""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.reader = None
        self.writer = None

    async def connect(self):
        """Connect to mixnode"""
        self.reader, self.writer = await asyncio.open_connection(
            self.host, self.port
        )
        print(f"Connected to Betanet mixnode at {self.host}:{self.port}")

    async def send_packet(self, packet: bytes) -> bytes:
        """Send packet to mixnode and receive processed packet"""
        # Send length prefix + packet
        length = struct.pack('>I', len(packet))
        self.writer.write(length + packet)
        await self.writer.drain()

        # Receive response length
        resp_length_data = await self.reader.readexactly(4)
        resp_length = struct.unpack('>I', resp_length_data)[0]

        # Receive response packet
        response = await self.reader.readexactly(resp_length)

        return response

    async def close(self):
        """Close connection"""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
```

#### Step 2.5: End-to-End Test (Day 2, 4 hours)

```python
# File: backend/tests/test_betanet_e2e.py (NEW)

import pytest

@pytest.mark.asyncio
async def test_betanet_full_circuit():
    """Test complete flow: Backend → Betanet mixnode → Backend"""

    # Start 3 mixnodes (Docker)
    subprocess.run([
        "docker-compose", "-f", "docker-compose.betanet.yml", "up", "-d"
    ])

    # Wait for nodes to start
    await asyncio.sleep(5)

    # Connect to entry node
    client = BetanetTcpClient("localhost", 9001)
    await client.connect()

    # Create Sphinx packet
    from src.betanet import SphinxPacket
    packet = SphinxPacket.create(
        message=b"Secret message",
        path=["mixnode-1", "mixnode-2", "mixnode-3"]
    )

    # Send through circuit
    result = await client.send_packet(packet.serialize())

    # Verify packet was processed
    assert result is not None
    assert len(result) > 0

    # Cleanup
    await client.close()
    subprocess.run(["docker-compose", "-f", "docker-compose.betanet.yml", "down"])
```

**Success Criteria**:
- ✅ TCP server accepts connections
- ✅ Packets sent over network
- ✅ 3-node circuit works end-to-end
- ✅ Backend can communicate with Rust mixnodes
- ✅ 25k pps throughput (benchmark)

---

### Priority 0: BitChat Backend Service

**Issue**: BitChat is TypeScript-only, no backend bridge
**Location**: `src/bitchat/` (frontend only)
**Severity**: 🔴 **CRITICAL** - No persistence, no API
**Timeline**: **3 days**

#### Step 3.1: Database Models (Day 1, 3 hours)

```python
# File: backend/server/models/database.py (UPDATE)

class Peer(Base):
    """P2P network peer"""
    __tablename__ = 'peers'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    peer_id = Column(String(255), unique=True, nullable=False)  # Public key hash
    display_name = Column(String(100))
    public_key = Column(Text, nullable=False)  # Ed25519 public key

    # Connection info
    last_seen = Column(DateTime, default=datetime.utcnow)
    connection_type = Column(String(50))  # 'ble', 'webrtc', 'http'
    is_online = Column(Boolean, default=False)

    # Trust
    trust_score = Column(Float, default=0.5)  # 0-1
    is_blocked = Column(Boolean, default=False)

    # Stats
    messages_sent = Column(Integer, default=0)
    messages_received = Column(Integer, default=0)
    bytes_transferred = Column(BigInteger, default=0)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)

class Message(Base):
    """P2P message (BitChat, P2P Unified)"""
    __tablename__ = 'messages'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(String(255), unique=True, nullable=False)  # Content hash

    # Routing
    from_peer_id = Column(UUID(as_uuid=True), ForeignKey('peers.id'))
    to_peer_id = Column(UUID(as_uuid=True), ForeignKey('peers.id'), nullable=True)  # Null for broadcast
    group_id = Column(String(255), nullable=True)  # For group messages

    # Content
    message_type = Column(String(50), default='text')  # 'text', 'file', 'voice', 'video'
    content = Column(Text)  # Encrypted content
    content_hash = Column(String(64))  # SHA-256 for integrity

    # Encryption
    encryption_algorithm = Column(String(50), default='chacha20-poly1305')
    nonce = Column(String(64))

    # Delivery
    status = Column(String(50), default='pending')  # 'pending', 'sent', 'delivered', 'read', 'failed'
    sent_at = Column(DateTime, default=datetime.utcnow)
    delivered_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)

    # Store-and-forward
    ttl = Column(Integer, default=86400)  # 24 hours
    hop_count = Column(Integer, default=0)
    max_hops = Column(Integer, default=5)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
```

#### Step 3.2: Alembic Migration (Day 1, 1 hour)

```bash
cd backend
python -m alembic revision -m "add_peer_and_message_models"
```

```python
# File: backend/alembic/versions/XXXX_add_peer_and_message_models.py

def upgrade():
    # Create peers table
    op.create_table(
        'peers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('peer_id', sa.String(255), nullable=False),
        sa.Column('display_name', sa.String(100)),
        sa.Column('public_key', sa.Text(), nullable=False),
        sa.Column('last_seen', sa.DateTime(), nullable=True),
        sa.Column('connection_type', sa.String(50)),
        sa.Column('is_online', sa.Boolean(), default=False),
        sa.Column('trust_score', sa.Float(), default=0.5),
        sa.Column('is_blocked', sa.Boolean(), default=False),
        sa.Column('messages_sent', sa.Integer(), default=0),
        sa.Column('messages_received', sa.Integer(), default=0),
        sa.Column('bytes_transferred', sa.BigInteger(), default=0),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('peer_id')
    )

    # Create messages table
    op.create_table(
        'messages',
        # ... (similar structure)
    )

    # Create indexes
    op.create_index('ix_peers_peer_id', 'peers', ['peer_id'])
    op.create_index('ix_messages_message_id', 'messages', ['message_id'])
    op.create_index('ix_messages_from_peer', 'messages', ['from_peer_id'])
    op.create_index('ix_messages_to_peer', 'messages', ['to_peer_id'])
    op.create_index('ix_messages_status', 'messages', ['status'])

def downgrade():
    op.drop_table('messages')
    op.drop_table('peers')
```

**Run migration**:
```bash
python -m alembic upgrade head
```

#### Step 3.3: BitChat Service (Day 1-2, 4 hours)

```python
# File: backend/server/services/bitchat.py (NEW)

from typing import List, Optional
import asyncio
import hashlib
from sqlalchemy.ext.asyncio import AsyncSession
from server.models.database import Peer, Message

class BitChatService:
    """Backend service for BitChat P2P messaging"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.active_connections = {}  # peer_id -> WebSocket

    async def register_peer(
        self,
        peer_id: str,
        public_key: str,
        display_name: Optional[str] = None
    ) -> Peer:
        """Register a new peer in the network"""

        # Check if peer exists
        existing = await self.db.query(Peer).filter(
            Peer.peer_id == peer_id
        ).first()

        if existing:
            # Update last seen
            existing.last_seen = datetime.utcnow()
            existing.is_online = True
            await self.db.commit()
            return existing

        # Create new peer
        peer = Peer(
            peer_id=peer_id,
            public_key=public_key,
            display_name=display_name or f"Peer-{peer_id[:8]}",
            is_online=True,
            last_seen=datetime.utcnow()
        )

        self.db.add(peer)
        await self.db.commit()

        return peer

    async def send_message(
        self,
        from_peer_id: str,
        to_peer_id: Optional[str],
        content: str,
        message_type: str = 'text',
        group_id: Optional[str] = None
    ) -> Message:
        """Send a message to a peer or group"""

        # Generate message ID (hash of content + timestamp)
        message_id = hashlib.sha256(
            f"{content}{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:32]

        # Create message record
        message = Message(
            message_id=message_id,
            from_peer_id=from_peer_id,
            to_peer_id=to_peer_id,
            group_id=group_id,
            message_type=message_type,
            content=content,
            content_hash=hashlib.sha256(content.encode()).hexdigest(),
            status='sent',
            sent_at=datetime.utcnow()
        )

        self.db.add(message)
        await self.db.commit()

        # Forward to recipient if online
        if to_peer_id and to_peer_id in self.active_connections:
            ws = self.active_connections[to_peer_id]
            await ws.send_json({
                'type': 'message',
                'message_id': message_id,
                'from': from_peer_id,
                'content': content,
                'timestamp': message.sent_at.isoformat()
            })

            # Mark as delivered
            message.status = 'delivered'
            message.delivered_at = datetime.utcnow()
            await self.db.commit()

        return message

    async def get_conversation(
        self,
        peer_id_1: str,
        peer_id_2: str,
        limit: int = 100
    ) -> List[Message]:
        """Get message history between two peers"""

        messages = await self.db.query(Message).filter(
            or_(
                and_(
                    Message.from_peer_id == peer_id_1,
                    Message.to_peer_id == peer_id_2
                ),
                and_(
                    Message.from_peer_id == peer_id_2,
                    Message.to_peer_id == peer_id_1
                )
            )
        ).order_by(Message.created_at.desc()).limit(limit).all()

        return list(reversed(messages))
```

#### Step 3.4: API Routes (Day 2, 4 hours)

```python
# File: backend/server/routes/bitchat.py (NEW)

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from server.services.bitchat import BitChatService
from server.database import get_db
from server.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/bitchat", tags=["bitchat"])

@router.post("/peers/register")
async def register_peer(
    peer_data: dict,
    db: AsyncSession = Depends(get_db)
):
    """Register a peer in the BitChat network"""
    service = BitChatService(db)

    peer = await service.register_peer(
        peer_id=peer_data['peer_id'],
        public_key=peer_data['public_key'],
        display_name=peer_data.get('display_name')
    )

    return {
        'peer_id': peer.peer_id,
        'display_name': peer.display_name,
        'registered_at': peer.created_at.isoformat()
    }

@router.get("/peers")
async def list_peers(
    db: AsyncSession = Depends(get_db)
):
    """List all peers in the network"""
    peers = await db.query(Peer).filter(
        Peer.is_blocked == False
    ).order_by(Peer.last_seen.desc()).all()

    return {
        'peers': [
            {
                'peer_id': p.peer_id,
                'display_name': p.display_name,
                'is_online': p.is_online,
                'last_seen': p.last_seen.isoformat() if p.last_seen else None
            }
            for p in peers
        ]
    }

@router.post("/messages/send")
async def send_message(
    message_data: dict,
    db: AsyncSession = Depends(get_db)
):
    """Send a message to a peer"""
    service = BitChatService(db)

    message = await service.send_message(
        from_peer_id=message_data['from_peer_id'],
        to_peer_id=message_data.get('to_peer_id'),
        content=message_data['content'],
        message_type=message_data.get('type', 'text'),
        group_id=message_data.get('group_id')
    )

    return {
        'message_id': message.message_id,
        'status': message.status,
        'sent_at': message.sent_at.isoformat()
    }

@router.get("/messages/conversation/{peer_id}")
async def get_conversation(
    peer_id: str,
    my_peer_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get conversation history with a peer"""
    service = BitChatService(db)

    messages = await service.get_conversation(my_peer_id, peer_id)

    return {
        'messages': [
            {
                'message_id': m.message_id,
                'from': m.from_peer_id,
                'to': m.to_peer_id,
                'content': m.content,
                'type': m.message_type,
                'status': m.status,
                'sent_at': m.sent_at.isoformat()
            }
            for m in messages
        ]
    }

@router.websocket("/ws/{peer_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    peer_id: str,
    db: AsyncSession = Depends(get_db)
):
    """WebSocket connection for real-time messaging"""
    await websocket.accept()

    service = BitChatService(db)
    service.active_connections[peer_id] = websocket

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()

            # Send message
            if data.get('type') == 'send':
                await service.send_message(
                    from_peer_id=peer_id,
                    to_peer_id=data.get('to'),
                    content=data['content'],
                    message_type=data.get('message_type', 'text')
                )

    except WebSocketDisconnect:
        # Remove from active connections
        del service.active_connections[peer_id]

        # Mark peer as offline
        peer = await db.query(Peer).filter(Peer.peer_id == peer_id).first()
        if peer:
            peer.is_online = False
            await db.commit()
```

#### Step 3.5: Integration (Day 3, 4 hours)

```python
# File: backend/server/main.py (UPDATE)

from server.routes import bitchat

# Add BitChat router
app.include_router(bitchat.router)
```

```typescript
// File: apps/control-panel/lib/api/bitchat.ts (NEW)

export async function registerPeer(peerId: string, publicKey: string, displayName?: string) {
  const response = await fetch('/api/bitchat/peers/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ peer_id: peerId, public_key: publicKey, display_name: displayName })
  });
  return response.json();
}

export async function listPeers() {
  const response = await fetch('/api/bitchat/peers');
  return response.json();
}

export async function sendMessage(fromPeerId: string, toPeerId: string, content: string) {
  const response = await fetch('/api/bitchat/messages/send', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ from_peer_id: fromPeerId, to_peer_id: toPeerId, content })
  });
  return response.json();
}

// WebSocket connection
export function connectBitChatWebSocket(peerId: string) {
  const ws = new WebSocket(`ws://localhost:8000/api/bitchat/ws/${peerId}`);

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'message') {
      // Handle incoming message
      console.log('New message:', data);
    }
  };

  return ws;
}
```

**Success Criteria**:
- ✅ Peer registration works
- ✅ Message sending persists to database
- ✅ WebSocket delivers real-time messages
- ✅ Frontend can list peers and send messages
- ✅ Conversation history retrieved correctly

---

## Phase 2: Strategic Consolidations (Week 2-3)

### Consolidation 1: BetaNet + VPN Hybrid (Week 2)

**Goal**: Unified privacy layer with Rust transport + Python services

#### Step 4.1: Architecture Design (Day 1)

**Decision**:
- **BetaNet (Rust)**: Low-level packet transport (TCP/UDP, Sphinx, VRF)
- **VPN (Python)**: High-level services (hidden services, circuits, fog coordination)

**Interface**:
```python
# VPN calls BetaNet for transport
class BetanetTransport:
    """Python wrapper for Rust BetaNet transport"""

    async def send_packet(self, packet: SphinxPacket) -> bool:
        """Send packet through BetaNet mixnet"""
        # Call Rust via TCP
        result = await betanet_client.send_packet(packet.serialize())
        return result.success
```

#### Step 4.2: Update VPN to Use BetaNet (Day 2-3)

```python
# File: src/vpn/onion_routing.py (UPDATE)

class OnionRouter:
    def __init__(self, use_betanet: bool = True):
        self.use_betanet = use_betanet
        if use_betanet:
            self.betanet = BetanetTransport(host="localhost", port=9001)

    async def send_through_circuit(self, circuit_id: str, data: bytes) -> bytes:
        """Send data through onion circuit"""

        if self.use_betanet:
            # Use Rust BetaNet for transport (HIGH PERFORMANCE)
            sphinx_packet = self._wrap_in_sphinx(data, circuit_id)
            return await self.betanet.send_packet(sphinx_packet)
        else:
            # Fallback to Python implementation (SLOW, for testing only)
            return await self._python_onion_route(data, circuit_id)
```

#### Step 4.3: Deprecate Redundant Code (Day 4-5)

- Mark Python onion routing as @deprecated
- Update all callers to use BetaNet transport
- Remove duplicate Sphinx implementation (keep VPN's for fallback)
- Update documentation

**Success Criteria**:
- ✅ VPN uses BetaNet for transport
- ✅ Performance: 25k pps throughput
- ✅ All tests pass
- ✅ No regression in functionality

---

### Consolidation 2: P2P + BitChat Integration (Week 3)

**Goal**: BitChat as P2P transport module

#### Step 5.1: Refactor BitChat as Transport (Day 1-2)

```python
# File: src/p2p/transports/bitchat_transport.py (NEW)

from src.p2p.unified_p2p_config import TransportConfig

class BitChatTransport:
    """BLE mesh transport for P2P Unified System"""

    def __init__(self, config: TransportConfig):
        self.config = config
        # Bridge to TypeScript BitChat implementation
        self.bitchat_bridge = BitChatBridge()

    async def send(self, peer_id: str, message: bytes) -> bool:
        """Send message via BLE mesh"""
        return await self.bitchat_bridge.send_ble(peer_id, message)

    async def receive(self) -> Optional[bytes]:
        """Receive message from BLE mesh"""
        return await self.bitchat_bridge.receive_ble()
```

#### Step 5.2: Update P2P to Use BitChat Transport (Day 3-4)

```python
# File: src/p2p/unified_p2p_system.py (UPDATE)

from src.p2p.transports.bitchat_transport import BitChatTransport
from src.p2p.transports.betanet_transport import BetanetTransport

class UnifiedP2PSystem:
    def __init__(self):
        self.transports = {
            'ble': BitChatTransport(config),
            'htx': BetanetTransport(config),
            'mesh': MeshTransport(config)
        }

    async def send_message(self, peer_id: str, message: bytes, protocol: str = 'auto'):
        """Send message using best available transport"""

        if protocol == 'auto':
            # Choose best transport (online vs offline)
            transport = self._select_transport(peer_id)
        else:
            transport = self.transports[protocol]

        return await transport.send(peer_id, message)
```

#### Step 5.3: Testing (Day 5)

- Test BLE transport via BitChat
- Test HTX transport via BetaNet
- Test protocol switching
- Test store-and-forward

**Success Criteria**:
- ✅ P2P can use BitChat for BLE
- ✅ P2P can use BetaNet for HTX
- ✅ Seamless protocol switching
- ✅ No code duplication

---

## Phase 3: Docker Consolidation (Week 3, Days 6-7)

### Step 6: Unified Docker Configuration

**Goal**: Single base + environment overrides

#### Step 6.1: Create New Base (2 hours)

```yaml
# File: docker-compose.yml (REPLACE)

version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: fog_user
      POSTGRES_PASSWORD: fog_password
      POSTGRES_DB: fog_compute
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U fog_user"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - fog-network

  redis:
    image: redis:7-alpine
    networks:
      - fog-network

  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
      target: production
    environment:
      DATABASE_URL: postgresql+asyncpg://fog_user:fog_password@postgres:5432/fog_compute
      API_HOST: 0.0.0.0
      API_PORT: 8000
      PYTHONPATH: /app
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - fog-network
      - betanet-network  # Multi-network attachment
    command: python -m uvicorn server.main:app --host 0.0.0.0 --port 8000

  frontend:
    build:
      context: ./apps/control-panel
      dockerfile: Dockerfile
      target: production
    environment:
      NEXT_PUBLIC_API_URL: http://backend:8000
      NODE_ENV: production
    depends_on:
      - backend
    networks:
      - fog-network

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./monitoring/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    networks:
      - fog-network
      - betanet-network

  grafana:
    image: grafana/grafana:latest
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources
      - grafana_data:/var/lib/grafana
    depends_on:
      - prometheus
    networks:
      - fog-network
      - betanet-network

  loki:
    image: grafana/loki:latest
    command: -config.file=/etc/loki/local-config.yaml
    networks:
      - fog-network

volumes:
  postgres_data:
  prometheus_data:
  grafana_data:

networks:
  fog-network:
    driver: bridge
  betanet-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.30.0.0/16
```

#### Step 6.2: Create Dev Overrides (1 hour)

```yaml
# File: docker-compose.dev.yml (REPLACE)

version: '3.8'

services:
  backend:
    build:
      target: development
    environment:
      LOG_LEVEL: DEBUG
      RELOAD: "true"
    volumes:
      - ./backend:/app/backend
      - ./src:/app/src
    ports:
      - "8000:8000"
    command: python -m uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build:
      dockerfile: Dockerfile.dev
    environment:
      NODE_ENV: development
    volumes:
      - ./apps/control-panel:/app
      - /app/node_modules
      - /app/.next
    ports:
      - "3000:3000"

  postgres:
    ports:
      - "5432:5432"

  redis:
    ports:
      - "6379:6379"

  prometheus:
    ports:
      - "9090:9090"

  grafana:
    ports:
      - "3001:3000"

  loki:
    ports:
      - "3100:3100"
```

#### Step 6.3: Update Betanet Config (1 hour)

```yaml
# File: docker-compose.betanet.yml (UPDATE)

version: '3.8'

services:
  betanet-mixnode-1:
    build:
      context: .
      dockerfile: Dockerfile.betanet
    container_name: betanet-mixnode-1
    environment:
      - NODE_TYPE=entry
      - NODE_PORT=9001
      - RUST_LOG=info
      - DATABASE_URL=postgresql://fog_user:fog_password@postgres:5432/fog_compute
    networks:
      - betanet-network
      - fog-network  # Multi-network: can access DB
    # ... rest of config

  betanet-mixnode-2:
    # Similar with fog-network access

  betanet-mixnode-3:
    # Similar with fog-network access
```

#### Step 6.4: Testing (4 hours)

```bash
# Test dev environment
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
# Verify hot-reload works

# Test production
docker-compose up -d
# Verify all services start

# Test betanet
docker-compose -f docker-compose.yml -f docker-compose.betanet.yml up -d
# Verify 3-node network + database access

# Cleanup
docker-compose down
```

**Success Criteria**:
- ✅ No duplicate services
- ✅ Single monitoring stack
- ✅ Betanet can access database
- ✅ No port conflicts
- ✅ ~300MB RAM savings

---

## Phase 4: Feature Completeness (Week 4-6)

### Step 7: BitChat Advanced Features

#### Week 4: Group Messaging (5 days)

**Implementation**:
- Group creation and management
- Multi-peer message broadcasting
- Group member sync via gossip protocol
- Encrypted group messages (shared key)

#### Week 5: File Sharing (5 days)

**Implementation**:
- File chunking (1MB chunks)
- Chunk transfer over BLE
- Reassembly and integrity verification
- Progress tracking

#### Week 6: Voice/Video (5 days)

**Implementation**:
- WebRTC signaling over BitChat
- STUN/TURN for NAT traversal
- Voice encoding (Opus)
- Video encoding (VP8/VP9)

---

### Step 8: Real-time WebSocket Updates (Week 4, 3 days)

```python
# File: backend/server/routes/websocket.py (NEW)

from fastapi import WebSocket, WebSocketDisconnect

@router.websocket("/ws/updates")
async def websocket_updates(websocket: WebSocket):
    """Real-time updates for dashboard"""
    await websocket.accept()

    try:
        while True:
            # Push updates every second
            updates = {
                'jobs': await get_job_stats(),
                'devices': await get_device_stats(),
                'circuits': await get_circuit_stats(),
                'timestamp': datetime.utcnow().isoformat()
            }

            await websocket.send_json(updates)
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        pass
```

---

## Phase 5: Testing & Quality (Week 7)

### Step 9: Comprehensive Test Suite

**Unit Tests** (80%+ coverage):
- All layers tested individually
- Crypto functions verified
- Database models tested

**Integration Tests**:
- Layer interactions tested
- API endpoints verified
- WebSocket connections tested

**E2E Tests**:
- Full user workflows
- Multi-hop circuits end-to-end
- File transfer complete flow

**Load Tests**:
- 25k pps BetaNet throughput
- 1000 concurrent users
- Database query performance

---

## Phase 6: Production Deployment (Week 8)

### Step 10: Production Readiness

1. **Security Audit** (2 days)
2. **Performance Optimization** (2 days)
3. **CI/CD Pipeline** (1 day)
4. **Monitoring & Alerting** (1 day)
5. **Documentation** (2 days)

---

## Summary

**Total Timeline**: **8 weeks**
**Engineers**: **4** (Rust, Python, Full-stack, DevOps)
**Completion**: **72% → 100%**

**Critical Path**:
Week 1 → Fix bugs
Week 2-3 → Consolidate overlaps
Week 4-6 → Complete features
Week 7 → Test thoroughly
Week 8 → Production deploy

**ROI**: **High** - Eliminates redundancy, improves performance, enables production use

**Risk**: **LOW** - Clear path, simple fixes, strong foundation

---

**Next Step**: Begin Week 1 with VPN crypto bug fix (4 hours)