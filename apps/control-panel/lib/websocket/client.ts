/**
 * WebSocket Client for Real-time Updates
 * Manages WebSocket connections with automatic reconnection and message handling
 */

export type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'reconnecting' | 'error';

export interface WebSocketMessage {
  type: string;
  data?: any;
  room?: string;
  timestamp?: string;
}

export interface ConnectionOptions {
  url: string;
  token?: string;
  autoReconnect?: boolean;
  maxReconnectAttempts?: number;
  reconnectInterval?: number;
  maxReconnectInterval?: number;
  heartbeatInterval?: number;
}

export interface MessageHandler {
  (message: WebSocketMessage): void;
}

export interface StateChangeHandler {
  (state: ConnectionState): void;
}

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private token?: string;
  private autoReconnect: boolean;
  private maxReconnectAttempts: number;
  private reconnectInterval: number;
  private maxReconnectInterval: number;
  private heartbeatInterval: number;

  private state: ConnectionState = 'disconnected';
  private reconnectAttempts = 0;
  private reconnectTimer?: NodeJS.Timeout;
  private heartbeatTimer?: NodeJS.Timeout;

  private messageHandlers: Map<string, Set<MessageHandler>> = new Map();
  private stateChangeHandlers: Set<StateChangeHandler> = new Set();
  private messageQueue: WebSocketMessage[] = [];

  private isManualDisconnect = false;

  constructor(options: ConnectionOptions) {
    this.url = options.url;
    this.token = options.token;
    this.autoReconnect = options.autoReconnect ?? true;
    this.maxReconnectAttempts = options.maxReconnectAttempts ?? 10;
    this.reconnectInterval = options.reconnectInterval ?? 1000;
    this.maxReconnectInterval = options.maxReconnectInterval ?? 30000;
    this.heartbeatInterval = options.heartbeatInterval ?? 30000;
  }

  /**
   * Connect to WebSocket server
   */
  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN || this.ws?.readyState === WebSocket.CONNECTING) {
      return;
    }

    this.setState('connecting');
    this.isManualDisconnect = false;

    try {
      const url = this.token ? `${this.url}?token=${this.token}` : this.url;
      this.ws = new WebSocket(url);

      this.ws.onopen = this.handleOpen.bind(this);
      this.ws.onclose = this.handleClose.bind(this);
      this.ws.onerror = this.handleError.bind(this);
      this.ws.onmessage = this.handleMessage.bind(this);
    } catch (error) {
      console.error('WebSocket connection error:', error);
      this.setState('error');
      this.scheduleReconnect();
    }
  }

  /**
   * Disconnect from WebSocket server
   */
  disconnect(): void {
    this.isManualDisconnect = true;
    this.clearTimers();

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.setState('disconnected');
  }

  /**
   * Subscribe to rooms
   */
  subscribe(rooms: string[]): void {
    this.send({
      type: 'subscribe',
      rooms
    });
  }

  /**
   * Unsubscribe from rooms
   */
  unsubscribe(rooms: string[]): void {
    this.send({
      type: 'unsubscribe',
      rooms
    });
  }

  /**
   * Send message to server
   */
  send(message: WebSocketMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      // Queue message for later if not connected
      if (message.type !== 'ping') {
        this.messageQueue.push(message);
      }
    }
  }

  /**
   * Register message handler for specific message type
   */
  on(messageType: string, handler: MessageHandler): () => void {
    if (!this.messageHandlers.has(messageType)) {
      this.messageHandlers.set(messageType, new Set());
    }

    this.messageHandlers.get(messageType)!.add(handler);

    // Return unsubscribe function
    return () => {
      const handlers = this.messageHandlers.get(messageType);
      if (handlers) {
        handlers.delete(handler);
        if (handlers.size === 0) {
          this.messageHandlers.delete(messageType);
        }
      }
    };
  }

  /**
   * Register state change handler
   */
  onStateChange(handler: StateChangeHandler): () => void {
    this.stateChangeHandlers.add(handler);

    // Return unsubscribe function
    return () => {
      this.stateChangeHandlers.delete(handler);
    };
  }

  /**
   * Get current connection state
   */
  getState(): ConnectionState {
    return this.state;
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.state === 'connected' && this.ws?.readyState === WebSocket.OPEN;
  }

  private handleOpen(): void {
    console.log('WebSocket connected');
    this.setState('connected');
    this.reconnectAttempts = 0;

    // Send queued messages
    while (this.messageQueue.length > 0) {
      const message = this.messageQueue.shift()!;
      this.send(message);
    }

    // Start heartbeat
    this.startHeartbeat();
  }

  private handleClose(event: CloseEvent): void {
    console.log('WebSocket closed:', event.code, event.reason);
    this.clearTimers();

    if (!this.isManualDisconnect && this.autoReconnect) {
      this.setState('reconnecting');
      this.scheduleReconnect();
    } else {
      this.setState('disconnected');
    }
  }

  private handleError(event: Event): void {
    console.error('WebSocket error:', event);
    this.setState('error');
  }

  private handleMessage(event: MessageEvent): void {
    try {
      const message: WebSocketMessage = JSON.parse(event.data);

      // Handle ping/pong
      if (message.type === 'ping') {
        this.send({ type: 'pong' });
        return;
      }

      if (message.type === 'pong') {
        return;
      }

      // Dispatch to registered handlers
      const handlers = this.messageHandlers.get(message.type);
      if (handlers) {
        handlers.forEach(handler => {
          try {
            handler(message);
          } catch (error) {
            console.error('Error in message handler:', error);
          }
        });
      }

      // Also dispatch to wildcard handlers
      const wildcardHandlers = this.messageHandlers.get('*');
      if (wildcardHandlers) {
        wildcardHandlers.forEach(handler => {
          try {
            handler(message);
          } catch (error) {
            console.error('Error in wildcard handler:', error);
          }
        });
      }
    } catch (error) {
      console.error('Error parsing WebSocket message:', error);
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      this.setState('error');
      return;
    }

    // Exponential backoff with jitter
    const baseDelay = Math.min(
      this.reconnectInterval * Math.pow(2, this.reconnectAttempts),
      this.maxReconnectInterval
    );
    const jitter = Math.random() * 1000;
    const delay = baseDelay + jitter;

    console.log(`Reconnecting in ${(delay / 1000).toFixed(1)}s (attempt ${this.reconnectAttempts + 1}/${this.maxReconnectAttempts})`);

    this.reconnectTimer = setTimeout(() => {
      this.reconnectAttempts++;
      this.connect();
    }, delay);
  }

  private startHeartbeat(): void {
    this.heartbeatTimer = setInterval(() => {
      if (this.isConnected()) {
        this.send({ type: 'ping' });
      }
    }, this.heartbeatInterval);
  }

  private clearTimers(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = undefined;
    }

    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = undefined;
    }
  }

  private setState(newState: ConnectionState): void {
    if (this.state !== newState) {
      this.state = newState;
      this.stateChangeHandlers.forEach(handler => {
        try {
          handler(newState);
        } catch (error) {
          console.error('Error in state change handler:', error);
        }
      });
    }
  }
}

/**
 * Create and manage a singleton WebSocket client instance
 */
let globalClient: WebSocketClient | null = null;

export function createWebSocketClient(options: ConnectionOptions): WebSocketClient {
  if (globalClient) {
    globalClient.disconnect();
  }

  globalClient = new WebSocketClient(options);
  return globalClient;
}

export function getWebSocketClient(): WebSocketClient | null {
  return globalClient;
}
