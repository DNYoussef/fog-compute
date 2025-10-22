/**
 * BitChat API Client
 * TypeScript client for BitChat P2P messaging service
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ============================================================================
// Type Definitions
// ============================================================================

export interface Peer {
  id: string;
  peer_id: string;
  public_key: string;
  display_name?: string;
  last_seen: string;
  is_online: boolean;
  trust_score: number;
  messages_sent: number;
  messages_received: number;
  created_at: string;
}

export interface Message {
  id: string;
  message_id: string;
  from_peer_id: string;
  to_peer_id?: string;
  group_id?: string;
  content: string;
  encryption_algorithm: string;
  nonce?: string;
  status: 'pending' | 'sent' | 'delivered' | 'read' | 'failed';
  sent_at: string;
  delivered_at?: string;
  ttl: number;
  hop_count: number;
}

export interface PeerRegisterRequest {
  peer_id: string;
  public_key: string;
  display_name?: string;
}

export interface MessageSendRequest {
  from_peer_id: string;
  to_peer_id?: string;
  group_id?: string;
  content: string;
  encryption_algorithm?: string;
  nonce?: string;
  ttl?: number;
}

export interface ConversationRequest {
  peer_id: string;
  other_peer_id: string;
  limit?: number;
  offset?: number;
}

export interface BitChatStats {
  total_peers: number;
  online_peers: number;
  active_connections: number;
  total_messages: number;
  messages_24h: number;
  status: string;
}

// ============================================================================
// Peer Management
// ============================================================================

/**
 * Register a new peer in the BitChat network
 */
export async function registerPeer(request: PeerRegisterRequest): Promise<Peer> {
  const response = await fetch(`${API_BASE_URL}/api/bitchat/peers/register`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Failed to register peer: ${response.statusText}`);
  }

  return response.json();
}

/**
 * List all peers in the network
 */
export async function listPeers(onlineOnly: boolean = false): Promise<Peer[]> {
  const url = new URL(`${API_BASE_URL}/api/bitchat/peers`);
  if (onlineOnly) {
    url.searchParams.set('online_only', 'true');
  }

  const response = await fetch(url.toString());

  if (!response.ok) {
    throw new Error(`Failed to list peers: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get information about a specific peer
 */
export async function getPeer(peerId: string): Promise<Peer> {
  const response = await fetch(`${API_BASE_URL}/api/bitchat/peers/${peerId}`);

  if (!response.ok) {
    throw new Error(`Failed to get peer: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Update peer online status
 */
export async function updatePeerStatus(
  peerId: string,
  isOnline: boolean
): Promise<{ message: string; is_online: boolean }> {
  const response = await fetch(`${API_BASE_URL}/api/bitchat/peers/${peerId}/status`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ is_online: isOnline }),
  });

  if (!response.ok) {
    throw new Error(`Failed to update peer status: ${response.statusText}`);
  }

  return response.json();
}

// ============================================================================
// Messaging
// ============================================================================

/**
 * Send an encrypted message
 */
export async function sendMessage(request: MessageSendRequest): Promise<Message> {
  const response = await fetch(`${API_BASE_URL}/api/bitchat/messages/send`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      ...request,
      encryption_algorithm: request.encryption_algorithm || 'AES-256-GCM',
      ttl: request.ttl || 3600,
    }),
  });

  if (!response.ok) {
    throw new Error(`Failed to send message: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get conversation history between two peers
 */
export async function getConversation(
  peerId: string,
  otherPeerId: string,
  limit: number = 50,
  offset: number = 0
): Promise<Message[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/bitchat/messages/conversation/${peerId}/${otherPeerId}?limit=${limit}&offset=${offset}`
  );

  if (!response.ok) {
    throw new Error(`Failed to get conversation: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get messages for a group chat
 */
export async function getGroupMessages(
  groupId: string,
  limit: number = 50,
  offset: number = 0
): Promise<Message[]> {
  const response = await fetch(`${API_BASE_URL}/api/bitchat/messages/group`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ group_id: groupId, limit, offset }),
  });

  if (!response.ok) {
    throw new Error(`Failed to get group messages: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Mark a message as delivered
 */
export async function markMessageDelivered(messageId: string): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE_URL}/api/bitchat/messages/${messageId}/delivered`, {
    method: 'PUT',
  });

  if (!response.ok) {
    throw new Error(`Failed to mark message delivered: ${response.statusText}`);
  }

  return response.json();
}

// ============================================================================
// Statistics
// ============================================================================

/**
 * Get BitChat service statistics
 */
export async function getBitChatStats(): Promise<BitChatStats> {
  const response = await fetch(`${API_BASE_URL}/api/bitchat/stats`);

  if (!response.ok) {
    throw new Error(`Failed to get BitChat stats: ${response.statusText}`);
  }

  return response.json();
}

// ============================================================================
// WebSocket Connection
// ============================================================================

export type MessageHandler = (message: Message) => void;
export type GroupMessageHandler = (groupId: string, message: Message) => void;

export interface BitChatWebSocketOptions {
  onMessage?: MessageHandler;
  onGroupMessage?: GroupMessageHandler;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
}

/**
 * WebSocket connection for real-time messaging
 */
export class BitChatWebSocket {
  private ws: WebSocket | null = null;
  private peerId: string;
  private options: BitChatWebSocketOptions;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private pingInterval: NodeJS.Timeout | null = null;

  constructor(peerId: string, options: BitChatWebSocketOptions = {}) {
    this.peerId = peerId;
    this.options = options;
  }

  /**
   * Connect to WebSocket server
   */
  connect(): void {
    const wsUrl = API_BASE_URL.replace('http', 'ws');
    this.ws = new WebSocket(`${wsUrl}/api/bitchat/ws/${this.peerId}`);

    this.ws.onopen = () => {
      console.log(`BitChat WebSocket connected for peer: ${this.peerId}`);
      this.reconnectAttempts = 0;
      this.options.onConnect?.();

      // Start ping/pong heartbeat
      this.pingInterval = setInterval(() => {
        this.send({ type: 'ping' });
      }, 30000); // Every 30 seconds
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'message') {
          this.options.onMessage?.(data.data as Message);
          // Auto-acknowledge receipt
          this.send({ type: 'ack', message_id: data.data.message_id });
        } else if (data.type === 'group_message') {
          this.options.onGroupMessage?.(data.group_id, data.data as Message);
          this.send({ type: 'ack', message_id: data.data.message_id });
        } else if (data.type === 'pong') {
          // Heartbeat response
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    this.ws.onerror = (error) => {
      console.error('BitChat WebSocket error:', error);
      this.options.onError?.(error);
    };

    this.ws.onclose = () => {
      console.log('BitChat WebSocket disconnected');
      this.options.onDisconnect?.();

      // Clear ping interval
      if (this.pingInterval) {
        clearInterval(this.pingInterval);
        this.pingInterval = null;
      }

      // Attempt reconnection
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
        console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
        setTimeout(() => this.connect(), delay);
      }
    };
  }

  /**
   * Send data to WebSocket server
   */
  private send(data: any): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  /**
   * Disconnect from WebSocket server
   */
  disconnect(): void {
    this.reconnectAttempts = this.maxReconnectAttempts; // Prevent auto-reconnect
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  /**
   * Check if WebSocket is connected
   */
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }
}

/**
 * Create a WebSocket connection for real-time messaging
 */
export function createBitChatWebSocket(
  peerId: string,
  options: BitChatWebSocketOptions = {}
): BitChatWebSocket {
  const socket = new BitChatWebSocket(peerId, options);
  socket.connect();
  return socket;
}
