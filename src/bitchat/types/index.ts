/**
 * BitChat Type Definitions
 * P2P Messaging with Bluetooth Low Energy and WebRTC
 */

export interface Message {
  id: string;
  sender: string;
  content: string;
  timestamp: Date;
  type: 'user' | 'ai' | 'system';
  metadata?: Record<string, any>;
}

export interface BitChatPeer {
  id: string;
  name: string;
  avatar?: string;
  status: 'online' | 'offline' | 'away';
  lastSeen: Date;
  publicKey: string;
}

export interface P2PMessage extends Message {
  encrypted: boolean;
  recipient: string;
  deliveryStatus: 'sent' | 'delivered' | 'read';
}

export interface MessagingState {
  peers: BitChatPeer[];
  conversations: Record<string, P2PMessage[]>;
  activeChat?: string;
  isDiscovering: boolean;
}

export interface WebRTCConnection {
  peerId: string;
  connection: RTCPeerConnection;
  dataChannel?: RTCDataChannel;
  status: 'connecting' | 'connected' | 'disconnected' | 'failed';
}

export interface EncryptionStatus {
  enabled: boolean;
  protocol: string;
  keyRotationInterval: number;
}

export interface MeshStatus {
  health: 'good' | 'fair' | 'poor';
  connectivity: number;
  latency: number;
  redundancy: number;
}

export interface BitChatServiceHook {
  messagingState: MessagingState;
  sendMessage: (message: P2PMessage) => Promise<boolean>;
  discoverPeers: () => Promise<void>;
  connectToPeer: (peerId: string) => Promise<boolean>;
  disconnectFromPeer: (peerId: string) => Promise<boolean>;
  meshStatus: MeshStatus;
  encryptionStatus: EncryptionStatus;
  isInitialized: boolean;
}