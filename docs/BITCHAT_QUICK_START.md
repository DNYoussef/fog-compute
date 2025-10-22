# BitChat Backend - Quick Start Guide

## Overview
BitChat is now a fully functional P2P messaging backend with database persistence, REST APIs, and WebSocket support.

---

## 🚀 Quick Setup

### 1. Database Migration
```bash
cd backend
python -m alembic upgrade head
```

### 2. Start Server
```bash
cd backend
python -m server.main
```

Server runs at: `http://localhost:8000`

### 3. Test API
```bash
cd backend
python -m tests.test_bitchat_integration
```

---

## 📡 API Endpoints

### Base URL
```
http://localhost:8000/api/bitchat
```

### Peer Management

#### Register Peer
```bash
POST /peers/register
Content-Type: application/json

{
  "peer_id": "alice-123",
  "public_key": "MIIBIjANBg...",
  "display_name": "Alice"
}
```

#### List Peers
```bash
GET /peers?online_only=true
```

#### Get Peer
```bash
GET /peers/{peer_id}
```

### Messaging

#### Send Message
```bash
POST /messages/send
Content-Type: application/json

{
  "from_peer_id": "alice-123",
  "to_peer_id": "bob-456",
  "content": "encrypted_content_here",
  "encryption_algorithm": "AES-256-GCM",
  "nonce": "abc123"
}
```

#### Get Conversation
```bash
GET /messages/conversation/{peer_id}/{other_peer_id}?limit=50&offset=0
```

### Statistics
```bash
GET /stats
```

### WebSocket
```
WS /ws/{peer_id}
```

---

## 💻 Frontend Integration

### Install Types
```typescript
import {
  registerPeer,
  sendMessage,
  getConversation,
  createBitChatWebSocket,
  type Peer,
  type Message
} from '@/lib/api/bitchat';
```

### Register Peer
```typescript
const peer = await registerPeer({
  peer_id: 'alice-123',
  public_key: 'MIIBIjAN...',
  display_name: 'Alice'
});
```

### Send Message
```typescript
const message = await sendMessage({
  from_peer_id: 'alice-123',
  to_peer_id: 'bob-456',
  content: encryptedContent
});
```

### WebSocket Connection
```typescript
const ws = createBitChatWebSocket('alice-123', {
  onMessage: (msg) => {
    console.log('New message:', msg);
  },
  onConnect: () => {
    console.log('Connected to BitChat');
  }
});

// Later: disconnect
ws.disconnect();
```

---

## 🗄️ Database Schema

### Peers Table
| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| peer_id | String | Unique identifier (indexed) |
| public_key | Text | Encryption public key |
| display_name | String | Optional display name |
| is_online | Boolean | Online status |
| trust_score | Float | Reputation (0.0-1.0) |
| messages_sent | Integer | Total sent |
| messages_received | Integer | Total received |

### Messages Table
| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| message_id | String | Unique identifier (indexed) |
| from_peer_id | String | Sender (FK to peers) |
| to_peer_id | String | Recipient (FK to peers) |
| group_id | String | Group chat ID (optional) |
| content | Text | Encrypted content |
| status | String | pending/sent/delivered/read |
| sent_at | DateTime | Timestamp |

---

## 🧪 Testing

### Run Unit Tests
```bash
cd backend
pytest server/tests/test_bitchat.py -v
```

### Run Integration Test
```bash
cd backend
python -m tests.test_bitchat_integration
```

### Manual Testing with cURL
```bash
# Health check
curl http://localhost:8000/health

# Register peer
curl -X POST http://localhost:8000/api/bitchat/peers/register \
  -H "Content-Type: application/json" \
  -d '{"peer_id":"alice","public_key":"key123","display_name":"Alice"}'

# List peers
curl http://localhost:8000/api/bitchat/peers

# Send message
curl -X POST http://localhost:8000/api/bitchat/messages/send \
  -H "Content-Type: application/json" \
  -d '{"from_peer_id":"alice","to_peer_id":"bob","content":"encrypted"}'

# Stats
curl http://localhost:8000/api/bitchat/stats
```

---

## 🔒 Security Notes

1. **Encryption**: Messages are stored encrypted in the database
2. **Public Keys**: Each peer has a public key for E2E encryption
3. **Validation**: All inputs validated via Pydantic schemas
4. **SQL Injection**: Protected by SQLAlchemy ORM
5. **CORS**: Configured for frontend access

---

## 🐛 Troubleshooting

### Database Connection Issues
```bash
# Check PostgreSQL is running
# Verify DATABASE_URL in .env
# Run migration: python -m alembic upgrade head
```

### WebSocket Connection Fails
```bash
# Ensure server is running
# Check WebSocket URL: ws://localhost:8000/api/bitchat/ws/{peer_id}
# Verify CORS settings in backend/server/main.py
```

### Import Errors
```bash
# Ensure dependencies installed
cd backend
pip install -r requirements.txt
```

---

## 📊 Statistics Response

```json
{
  "total_peers": 42,
  "online_peers": 15,
  "active_connections": 15,
  "total_messages": 1234,
  "messages_24h": 567,
  "status": "operational"
}
```

---

## 🔗 Related Files

- **Service**: `backend/server/services/bitchat.py`
- **Routes**: `backend/server/routes/bitchat.py`
- **Models**: `backend/server/models/database.py`
- **Schemas**: `backend/server/schemas/bitchat.py`
- **Frontend Client**: `apps/control-panel/lib/api/bitchat.ts`
- **Tests**: `backend/server/tests/test_bitchat.py`
- **Migration**: `backend/alembic/versions/8c1adce3f0c1_*.py`

---

## 📚 Documentation

- Full implementation: [BITCHAT_BACKEND_IMPLEMENTATION.md](./BITCHAT_BACKEND_IMPLEMENTATION.md)
- API Docs (Swagger): `http://localhost:8000/docs`
- API Docs (ReDoc): `http://localhost:8000/redoc`

---

**Need Help?** Check the comprehensive documentation or run the integration test to verify everything is working.
