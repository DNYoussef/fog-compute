# BitChat Quick Start Guide

## Installation

The BitChat module is already included in the fog-compute project at `src/bitchat/`.

## Basic Usage

### 1. Import the Component

```typescript
import BitChatInterface from '@/bitchat';
// or
import { BitChatInterface } from '@/bitchat';
```

### 2. Add to Your App

```tsx
function App() {
  return (
    <BitChatInterface
      userId="your-user-id"
      onPeerConnect={(peer) => {
        console.log('New peer connected:', peer.name);
      }}
      onMessageReceived={(message) => {
        console.log('Message received:', message.content);
      }}
    />
  );
}
```

## Advanced Usage

### Using the Service Hook

```typescript
import { useBitChatService } from '@/bitchat';

function CustomChat() {
  const {
    messagingState,      // Current state (peers, conversations)
    sendMessage,         // Send a message
    discoverPeers,       // Scan for peers
    connectToPeer,       // Connect to a peer
    disconnectFromPeer,  // Disconnect
    meshStatus,          // Network health
    encryptionStatus,    // Encryption info
    isInitialized        // Ready state
  } = useBitChatService('user-123');

  return (
    <div>
      <h3>Connected Peers: {messagingState.peers.length}</h3>
      <button onClick={discoverPeers}>Find Peers</button>
    </div>
  );
}
```

### Protocol-Level Access

```typescript
import { WebRTCProtocol, BluetoothProtocol, ChaCha20Encryption } from '@/bitchat';

// WebRTC mesh networking
const webrtc = new WebRTCProtocol();
await webrtc.setupWebRTCStack();
await webrtc.createPeerConnection('peer-id', onMessage);

// Bluetooth discovery
const bluetooth = new BluetoothProtocol();
const peers = await bluetooth.discoverPeers();

// Encryption
const crypto = new ChaCha20Encryption();
const encrypted = await crypto.encryptMessage(message);
```

## Type Definitions

```typescript
import type {
  BitChatPeer,
  P2PMessage,
  MessagingState,
  MeshStatus,
  EncryptionStatus
} from '@/bitchat';

// Example peer
const peer: BitChatPeer = {
  id: 'peer-123',
  name: 'Alice',
  status: 'online',
  lastSeen: new Date(),
  publicKey: 'key-abc'
};

// Example message
const message: P2PMessage = {
  id: 'msg-456',
  sender: 'user-123',
  recipient: 'peer-123',
  content: 'Hello!',
  timestamp: new Date(),
  type: 'user',
  encrypted: true,
  deliveryStatus: 'sent'
};
```

## Available Imports

### Components
- `BitChatInterface` - Main chat UI
- `PeerList` - Peer list component
- `ConversationView` - Message thread view
- `NetworkStatus` - Network health display

### Hooks
- `useBitChatService` - Main service hook

### Protocols
- `WebRTCProtocol` - WebRTC networking
- `BluetoothProtocol` - BLE discovery

### Encryption
- `ChaCha20Encryption` - Message encryption

### Types
- `BitChatPeer` - Peer interface
- `P2PMessage` - Message interface
- `MessagingState` - State interface
- `MeshStatus` - Network metrics
- `EncryptionStatus` - Crypto config

## Features

### Automatic Features
- ✅ Peer discovery every 30 seconds
- ✅ End-to-end encryption (ChaCha20-Poly1305)
- ✅ Mesh network health monitoring
- ✅ Automatic key rotation (hourly)
- ✅ WebRTC data channels

### Manual Controls
- 🔍 Trigger peer discovery
- 🔗 Connect/disconnect peers
- 💬 Send encrypted messages
- 📊 View network metrics

## Network Requirements

### Browser Support
- Chrome/Edge: Full support (WebRTC + Bluetooth)
- Firefox/Safari: WebRTC only (no Bluetooth)

### Protocols Used
- WebRTC for P2P data channels
- Bluetooth LE for local discovery
- STUN servers for NAT traversal
- ChaCha20-Poly1305 for encryption

## Testing

Run the test suite:

```bash
npm test src/bitchat/ui/BitChatInterface.test.tsx
```

## Troubleshooting

### No Peers Found
- Enable Bluetooth on device
- Grant Bluetooth permissions in browser
- Ensure peers are within ~100m range

### Messages Not Sending
- Check peer connection status
- Verify encryption is enabled
- Check network connectivity

### Poor Mesh Health
- Reduce distance between peers
- Check for network interference
- Verify STUN server accessibility

## Performance Tips

- Mesh works best with 2-10 peers
- Keep message size under 1KB for best latency
- Use encryption (minimal overhead ~5-10ms)
- Monitor `meshStatus.health` for quality

## Security Notes

- All messages encrypted by default
- Keys rotated every hour
- No central server (fully P2P)
- Public key exchange on connection
- ChaCha20-Poly1305 authenticated encryption

## Next Steps

1. **Styling**: Add CSS for BitChat components
2. **Persistence**: Store conversation history
3. **File Sharing**: Add file transfer support
4. **Voice/Video**: Integrate WebRTC media streams
5. **Offline**: Add offline message queue

For detailed documentation, see [README.md](./README.md)