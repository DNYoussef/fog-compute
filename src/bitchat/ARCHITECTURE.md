# BitChat Module Architecture

## Directory Structure

```
src/bitchat/
├── types/                          # Type Definitions
│   └── index.ts                   # All TypeScript interfaces
│
├── protocol/                       # P2P Communication Protocols
│   ├── webrtc.ts                  # WebRTC mesh networking
│   └── bluetooth.ts               # BLE peer discovery
│
├── encryption/                     # Cryptography Layer
│   └── chacha20.ts                # ChaCha20-Poly1305 E2E encryption
│
├── hooks/                          # React State Management
│   └── useBitChatService.ts       # Main service hook
│
├── ui/                             # React Components
│   ├── BitChatInterface.tsx       # Main chat interface
│   ├── PeerList.tsx               # Peer list display
│   ├── ConversationView.tsx       # Message thread view
│   ├── NetworkStatus.tsx          # Network health monitor
│   └── BitChatInterface.test.tsx  # Component tests
│
├── index.ts                        # Public API exports
├── API.md                          # API reference
├── README.md                       # Module documentation
├── QUICK-START.md                 # Developer guide
└── ARCHITECTURE.md                # This file
```

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     BitChatInterface (UI)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  PeerList    │  │ Conversation │  │   Network    │      │
│  │              │  │     View     │  │    Status    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              useBitChatService (State Hook)                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  MessagingState, MeshStatus, EncryptionStatus        │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
          │                    │                    │
          ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  WebRTC         │  │  Bluetooth      │  │  ChaCha20       │
│  Protocol       │  │  Protocol       │  │  Encryption     │
│                 │  │                 │  │                 │
│ • Mesh network  │  │ • BLE discovery │  │ • E2E encrypt   │
│ • Data channels │  │ • Peer scan     │  │ • Key rotation  │
│ • STUN/TURN     │  │ • Device pairing│  │ • Auth crypto   │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

## Module Layers

### Layer 1: Types (Foundation)
- **Purpose**: Type definitions and interfaces
- **Dependencies**: None
- **Exports**: All TypeScript types

```typescript
types/
└── index.ts  (BitChatPeer, P2PMessage, MessagingState, etc.)
```

### Layer 2: Protocol (Communication)
- **Purpose**: P2P networking and discovery
- **Dependencies**: Types
- **Exports**: WebRTCProtocol, BluetoothProtocol

```typescript
protocol/
├── webrtc.ts      (Mesh networking, data channels)
└── bluetooth.ts   (BLE discovery, device pairing)
```

### Layer 3: Encryption (Security)
- **Purpose**: Message encryption/decryption
- **Dependencies**: Types
- **Exports**: ChaCha20Encryption

```typescript
encryption/
└── chacha20.ts    (E2E encryption, key management)
```

### Layer 4: Hooks (Business Logic)
- **Purpose**: State management and orchestration
- **Dependencies**: Types, Protocol, Encryption
- **Exports**: useBitChatService

```typescript
hooks/
└── useBitChatService.ts  (Main service hook)
```

### Layer 5: UI (Presentation)
- **Purpose**: React components
- **Dependencies**: Types, Hooks
- **Exports**: All UI components

```typescript
ui/
├── BitChatInterface.tsx   (Main component)
├── PeerList.tsx           (Peer display)
├── ConversationView.tsx   (Message thread)
└── NetworkStatus.tsx      (Health monitor)
```

## Component Interaction Flow

### 1. Initialization Flow
```
User Component
    │
    ├─> BitChatInterface (userId)
    │       │
    │       ├─> useBitChatService(userId)
    │       │       │
    │       │       ├─> WebRTCProtocol.setupWebRTCStack()
    │       │       ├─> BluetoothProtocol.initializeBluetoothLEDiscovery()
    │       │       └─> ChaCha20Encryption (key generation)
    │       │
    │       ├─> Auto-start peer discovery (30s interval)
    │       └─> Render UI components
    │
    └─> Ready for messaging
```

### 2. Peer Discovery Flow
```
User clicks "Scan for Peers"
    │
    ├─> BitChatInterface.discoverPeers()
    │       │
    │       ├─> BluetoothProtocol.discoverPeers()
    │       │       │
    │       │       └─> Returns: BitChatPeer[]
    │       │
    │       ├─> Update MessagingState.peers
    │       └─> Update MeshStatus
    │
    └─> PeerList displays new peers
```

### 3. Message Sending Flow
```
User types message and clicks "Send"
    │
    ├─> ConversationView.handleSendMessage(content)
    │       │
    │       ├─> Create P2PMessage object
    │       │
    │       ├─> useBitChatService.sendMessage(message)
    │       │       │
    │       │       ├─> ChaCha20Encryption.encryptMessage(message)
    │       │       │       │
    │       │       │       └─> Encrypted P2PMessage
    │       │       │
    │       │       ├─> WebRTCProtocol.sendMessage(recipient, data)
    │       │       │       │
    │       │       │       └─> Via RTCDataChannel
    │       │       │
    │       │       └─> Update MessagingState.conversations
    │       │
    │       └─> ConversationView displays message
    │
    └─> Callback: onMessageReceived(message)
```

### 4. Message Receiving Flow
```
RTCDataChannel receives data
    │
    ├─> WebRTCProtocol.dataChannel.onmessage(event)
    │       │
    │       ├─> Parse JSON data
    │       │
    │       ├─> useBitChatService.handleIncomingMessage(message)
    │       │       │
    │       │       ├─> If encrypted: ChaCha20Encryption.decryptMessage()
    │       │       │
    │       │       └─> Update MessagingState.conversations
    │       │
    │       └─> ConversationView displays new message
    │
    └─> Callback: onMessageReceived(message)
```

## Design Patterns

### 1. MECE Architecture
- **Mutually Exclusive**: Each module has distinct responsibility
- **Collectively Exhaustive**: All functionality is covered

### 2. Separation of Concerns
- Types: Data structures
- Protocol: Communication
- Encryption: Security
- Hooks: Logic
- UI: Presentation

### 3. Dependency Injection
```typescript
// Protocol classes are injected into hooks
const webrtcProtocol = useRef<WebRTCProtocol>(new WebRTCProtocol());
const bluetoothProtocol = useRef<BluetoothProtocol>(new BluetoothProtocol());
```

### 4. Observer Pattern
```typescript
// UI observes state changes via React hooks
const { messagingState, meshStatus } = useBitChatService(userId);
```

### 5. Strategy Pattern
```typescript
// Different protocols for different scenarios
if (bluetoothAvailable) {
  await bluetoothProtocol.discoverPeers();
} else {
  await webrtcOnlyDiscovery();
}
```

## State Management

### MessagingState
```typescript
{
  peers: BitChatPeer[],           // Connected peers
  conversations: {                 // Message history
    [peerId]: P2PMessage[]
  },
  activeChat?: string,             // Selected peer
  isDiscovering: boolean           // Discovery status
}
```

### MeshStatus
```typescript
{
  health: 'good' | 'fair' | 'poor',  // Network quality
  connectivity: number,               // Percentage (0-100)
  latency: number,                    // ms
  redundancy: number                  // Backup paths (0-3)
}
```

### EncryptionStatus
```typescript
{
  enabled: boolean,                   // Encryption on/off
  protocol: 'ChaCha20-Poly1305',     // Algorithm
  keyRotationInterval: 3600000        // 1 hour in ms
}
```

## Security Model

### End-to-End Encryption
1. Each peer generates ChaCha20-Poly1305 key pair
2. Public keys exchanged on connection
3. Messages encrypted before transmission
4. Messages decrypted after reception
5. Keys rotated every hour

### Trust Model
- No central authority
- Peer-to-peer trust
- Public key verification
- Authenticated encryption

## Performance Considerations

### Optimization Strategies
1. **Lazy Loading**: Protocols initialized on demand
2. **Memoization**: State updates optimized with React hooks
3. **Batching**: Multiple state updates batched
4. **Throttling**: Peer discovery throttled to 30s intervals
5. **Cleanup**: Resources cleaned on unmount

### Bottlenecks
- WebRTC signaling (requires STUN/TURN)
- Bluetooth LE range (~100m)
- Message size (optimal <1KB)
- Peer limit (optimal 2-10)

## Testing Strategy

### Unit Tests
- Component rendering
- Peer interactions
- Message flow
- Network status

### Integration Tests
- Protocol integration
- Encryption pipeline
- State management
- UI workflows

### E2E Tests
- Full messaging flow
- Multi-peer scenarios
- Network degradation
- Security verification

## Extension Points

### Adding New Features
1. **File Transfer**: Extend P2PMessage with file metadata
2. **Voice/Video**: Add MediaStream to WebRTCProtocol
3. **Group Chat**: Extend mesh topology for multicast
4. **Offline Mode**: Add message queue and sync

### Custom Protocols
```typescript
// Create custom protocol
export class CustomProtocol {
  async discover(): Promise<BitChatPeer[]> {
    // Custom implementation
  }
}

// Use in hook
const customProtocol = useRef<CustomProtocol>(new CustomProtocol());
```

## Browser API Dependencies

- **WebRTC API**: All modern browsers
- **Bluetooth Web API**: Chrome, Edge only
- **Crypto.subtle API**: All modern browsers
- **Navigator API**: All modern browsers

## Future Enhancements

1. **Protocol Adapters**: Support more P2P protocols
2. **Persistence**: IndexedDB for message history
3. **Sync**: Multi-device synchronization
4. **Advanced Crypto**: Quantum-resistant algorithms
5. **Federation**: Cross-network messaging

---

*Architecture Version: 1.0*
*Last Updated: 2025-09-23*