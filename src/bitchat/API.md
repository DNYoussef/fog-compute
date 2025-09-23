# BitChat Public API Reference

## Table of Contents

1. [Components](#components)
2. [Hooks](#hooks)
3. [Protocols](#protocols)
4. [Encryption](#encryption)
5. [Types](#types)

---

## Components

### BitChatInterface

Main UI component for P2P mesh messaging.

```typescript
import { BitChatInterface } from '@/bitchat';

<BitChatInterface
  userId: string
  onPeerConnect?: (peer: BitChatPeer) => void
  onMessageReceived?: (message: P2PMessage) => void
/>
```

**Props:**
- `userId` (required): Unique identifier for the current user
- `onPeerConnect` (optional): Callback when a new peer connects
- `onMessageReceived` (optional): Callback when a message is received

### PeerList

Display list of connected peers.

```typescript
import { PeerList } from '@/bitchat';

<PeerList
  peers: BitChatPeer[]
  selectedPeer: string | null
  onPeerSelect: (peerId: string) => void
  onPeerConnect: (peerId: string) => Promise<void>
  onPeerDisconnect: (peerId: string) => Promise<void>
  conversations: Record<string, P2PMessage[]>
/>
```

### ConversationView

Display message thread for a selected peer.

```typescript
import { ConversationView } from '@/bitchat';

<ConversationView
  peer: BitChatPeer
  messages: P2PMessage[]
  onSendMessage: (content: string) => void
  encryptionEnabled: boolean
/>
```

### NetworkStatus

Display mesh network health metrics.

```typescript
import { NetworkStatus } from '@/bitchat';

<NetworkStatus
  status: MeshStatus
  peerCount: number
  isDiscovering: boolean
/>
```

---

## Hooks

### useBitChatService

Main service hook for BitChat functionality.

```typescript
import { useBitChatService } from '@/bitchat';

const {
  messagingState,
  sendMessage,
  discoverPeers,
  connectToPeer,
  disconnectFromPeer,
  meshStatus,
  encryptionStatus,
  isInitialized
} = useBitChatService(userId: string);
```

**Returns:**
- `messagingState: MessagingState` - Current messaging state
- `sendMessage: (message: P2PMessage) => Promise<boolean>` - Send a message
- `discoverPeers: () => Promise<void>` - Scan for nearby peers
- `connectToPeer: (peerId: string) => Promise<boolean>` - Connect to a peer
- `disconnectFromPeer: (peerId: string) => Promise<boolean>` - Disconnect from a peer
- `meshStatus: MeshStatus` - Network health metrics
- `encryptionStatus: EncryptionStatus` - Encryption configuration
- `isInitialized: boolean` - Service initialization status

---

## Protocols

### WebRTCProtocol

WebRTC mesh networking implementation.

```typescript
import { WebRTCProtocol } from '@/bitchat';

const webrtc = new WebRTCProtocol();

// Methods
await webrtc.setupWebRTCStack(): Promise<void>
await webrtc.createPeerConnection(peerId: string, onMessage: (data: any) => void): Promise<RTCPeerConnection>
await webrtc.sendMessage(peerId: string, data: any): Promise<boolean>
await webrtc.closePeerConnection(peerId: string): Promise<void>
webrtc.getConnectionStatus(peerId: string): string
webrtc.cleanup(): void
```

### BluetoothProtocol

Bluetooth Low Energy peer discovery.

```typescript
import { BluetoothProtocol } from '@/bitchat';

const bluetooth = new BluetoothProtocol();

// Methods
await bluetooth.initializeBluetoothLEDiscovery(): Promise<void>
await bluetooth.discoverPeers(): Promise<BitChatPeer[]>
bluetooth.isBluetoothAvailable(): boolean
bluetooth.getDeviceInfo(): { name?: string; id?: string } | null
```

---

## Encryption

### ChaCha20Encryption

ChaCha20-Poly1305 authenticated encryption.

```typescript
import { ChaCha20Encryption } from '@/bitchat';

const crypto = new ChaCha20Encryption(keyRotationInterval?: number);

// Methods
await crypto.encryptMessage(message: P2PMessage): Promise<P2PMessage>
await crypto.decryptMessage(message: P2PMessage): Promise<P2PMessage>
await crypto.rotateKey(): Promise<void>
await crypto.exportPublicKey(): Promise<string>
await crypto.importPeerKey(publicKey: string): Promise<void>
```

---

## Types

### BitChatPeer

```typescript
interface BitChatPeer {
  id: string;
  name: string;
  avatar?: string;
  status: 'online' | 'offline' | 'away';
  lastSeen: Date;
  publicKey: string;
}
```

### P2PMessage

```typescript
interface P2PMessage extends Message {
  encrypted: boolean;
  recipient: string;
  deliveryStatus: 'sent' | 'delivered' | 'read';
}

interface Message {
  id: string;
  sender: string;
  content: string;
  timestamp: Date;
  type: 'user' | 'ai' | 'system';
  metadata?: Record<string, any>;
}
```

### MessagingState

```typescript
interface MessagingState {
  peers: BitChatPeer[];
  conversations: Record<string, P2PMessage[]>;
  activeChat?: string;
  isDiscovering: boolean;
}
```

### MeshStatus

```typescript
interface MeshStatus {
  health: 'good' | 'fair' | 'poor';
  connectivity: number;
  latency: number;
  redundancy: number;
}
```

### EncryptionStatus

```typescript
interface EncryptionStatus {
  enabled: boolean;
  protocol: string;
  keyRotationInterval: number;
}
```

### WebRTCConnection

```typescript
interface WebRTCConnection {
  peerId: string;
  connection: RTCPeerConnection;
  dataChannel?: RTCDataChannel;
  status: 'connecting' | 'connected' | 'disconnected' | 'failed';
}
```

### BitChatServiceHook

```typescript
interface BitChatServiceHook {
  messagingState: MessagingState;
  sendMessage: (message: P2PMessage) => Promise<boolean>;
  discoverPeers: () => Promise<void>;
  connectToPeer: (peerId: string) => Promise<boolean>;
  disconnectFromPeer: (peerId: string) => Promise<boolean>;
  meshStatus: MeshStatus;
  encryptionStatus: EncryptionStatus;
  isInitialized: boolean;
}
```

---

## Import Patterns

### Named Imports

```typescript
import {
  // Components
  BitChatInterface,
  PeerList,
  ConversationView,
  NetworkStatus,

  // Hooks
  useBitChatService,

  // Protocols
  WebRTCProtocol,
  BluetoothProtocol,

  // Encryption
  ChaCha20Encryption,

  // Types
  BitChatPeer,
  P2PMessage,
  MessagingState,
  MeshStatus,
  EncryptionStatus
} from '@/bitchat';
```

### Default Import

```typescript
import BitChatInterface from '@/bitchat';
```

### Wildcard Import

```typescript
import * as BitChat from '@/bitchat';

// Usage
<BitChat.BitChatInterface userId="user-123" />
const webrtc = new BitChat.WebRTCProtocol();
```

---

## Examples

### Complete Integration

```typescript
import { BitChatInterface, useBitChatService } from '@/bitchat';
import type { BitChatPeer, P2PMessage } from '@/bitchat';

function App() {
  const handlePeerConnect = (peer: BitChatPeer) => {
    console.log(`Connected to ${peer.name}`);
  };

  const handleMessage = (message: P2PMessage) => {
    console.log(`Message from ${message.sender}: ${message.content}`);
  };

  return (
    <BitChatInterface
      userId="user-123"
      onPeerConnect={handlePeerConnect}
      onMessageReceived={handleMessage}
    />
  );
}
```

### Custom Hook Usage

```typescript
import { useBitChatService } from '@/bitchat';

function CustomMessaging() {
  const {
    messagingState,
    sendMessage,
    meshStatus
  } = useBitChatService('user-123');

  return (
    <div>
      <p>Peers: {messagingState.peers.length}</p>
      <p>Health: {meshStatus.health}</p>
    </div>
  );
}
```

### Protocol-Level Usage

```typescript
import { WebRTCProtocol, BluetoothProtocol } from '@/bitchat';

async function setupP2P() {
  const webrtc = new WebRTCProtocol();
  const bluetooth = new BluetoothProtocol();

  await webrtc.setupWebRTCStack();
  const peers = await bluetooth.discoverPeers();

  for (const peer of peers) {
    await webrtc.createPeerConnection(
      peer.id,
      (data) => console.log('Message:', data)
    );
  }
}
```

---

## Error Handling

All async methods may throw errors. Wrap in try-catch:

```typescript
try {
  const success = await sendMessage(message);
  if (!success) {
    console.error('Failed to send message');
  }
} catch (error) {
  console.error('Error sending message:', error);
}
```

## Browser Compatibility

- **WebRTC**: All modern browsers
- **Bluetooth**: Chrome, Edge only (Web Bluetooth API)
- **Encryption**: All modern browsers (Crypto.subtle API)

## Performance Tips

- Keep message size under 1KB for best latency
- Limit mesh to 2-10 peers for optimal performance
- Monitor `meshStatus.health` for quality indicators
- Use encryption (minimal overhead ~5-10ms)

---

*Last Updated: 2025-09-23*