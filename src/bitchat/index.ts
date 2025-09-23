/**
 * BitChat - P2P Mesh Messaging Module
 * Consolidated exports for all BitChat components
 */

// Types
export * from './types';

// Protocol
export { WebRTCProtocol } from './protocol/webrtc';
export { BluetoothProtocol } from './protocol/bluetooth';

// Encryption
export { ChaCha20Encryption } from './encryption/chacha20';

// Hooks
export { useBitChatService } from './hooks/useBitChatService';

// UI Components
export { BitChatInterface } from './ui/BitChatInterface';
export { PeerList } from './ui/PeerList';
export { ConversationView } from './ui/ConversationView';
export { NetworkStatus } from './ui/NetworkStatus';

// Default export
export { BitChatInterface as default } from './ui/BitChatInterface';