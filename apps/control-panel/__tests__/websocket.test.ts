/**
 * Frontend WebSocket Client Tests
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { WebSocketClient, createWebSocketClient } from '../lib/websocket/client';

// Mock WebSocket
class MockWebSocket {
  readyState: number = WebSocket.CONNECTING;
  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;

  send = vi.fn();
  close = vi.fn(() => {
    this.readyState = WebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close'));
    }
  });

  simulateOpen() {
    this.readyState = WebSocket.OPEN;
    if (this.onopen) {
      this.onopen(new Event('open'));
    }
  }

  simulateMessage(data: any) {
    if (this.onmessage) {
      this.onmessage(new MessageEvent('message', { data: JSON.stringify(data) }));
    }
  }

  simulateError() {
    if (this.onerror) {
      this.onerror(new Event('error'));
    }
  }
}

describe('WebSocketClient', () => {
  let client: WebSocketClient;
  let mockWs: MockWebSocket;

  beforeEach(() => {
    // Mock global WebSocket
    mockWs = new MockWebSocket();
    global.WebSocket = vi.fn(() => mockWs) as any;

    client = new WebSocketClient({
      url: 'ws://localhost:8000',
      autoReconnect: true,
      maxReconnectAttempts: 3,
      reconnectInterval: 100,
      maxReconnectInterval: 1000,
      heartbeatInterval: 1000
    });
  });

  afterEach(() => {
    if (client) {
      client.disconnect();
    }
  });

  describe('Connection Management', () => {
    it('should connect to WebSocket server', () => {
      client.connect();

      expect(global.WebSocket).toHaveBeenCalledWith('ws://localhost:8000');
      expect(client.getState()).toBe('connecting');
    });

    it('should handle successful connection', () => {
      client.connect();
      mockWs.simulateOpen();

      expect(client.getState()).toBe('connected');
      expect(client.isConnected()).toBe(true);
    });

    it('should handle connection with token', () => {
      const clientWithToken = new WebSocketClient({
        url: 'ws://localhost:8000',
        token: 'test-token'
      });

      clientWithToken.connect();

      expect(global.WebSocket).toHaveBeenCalledWith('ws://localhost:8000?token=test-token');

      clientWithToken.disconnect();
    });

    it('should disconnect cleanly', () => {
      client.connect();
      mockWs.simulateOpen();

      client.disconnect();

      expect(client.getState()).toBe('disconnected');
      expect(mockWs.close).toHaveBeenCalled();
    });

    it('should not reconnect after manual disconnect', () => {
      const reconnectSpy = vi.spyOn(client as any, 'scheduleReconnect');

      client.connect();
      mockWs.simulateOpen();
      client.disconnect();

      expect(reconnectSpy).not.toHaveBeenCalled();
    });
  });

  describe('Message Handling', () => {
    beforeEach(() => {
      client.connect();
      mockWs.simulateOpen();
    });

    it('should send messages when connected', () => {
      const message = { type: 'test', data: 'hello' };

      client.send(message);

      expect(mockWs.send).toHaveBeenCalledWith(JSON.stringify(message));
    });

    it('should queue messages when disconnected', () => {
      client.disconnect();

      const message = { type: 'test', data: 'queued' };
      client.send(message);

      // Should be queued
      expect(mockWs.send).not.toHaveBeenCalled();

      // Reconnect
      client.connect();
      mockWs.simulateOpen();

      // Should send queued message
      expect(mockWs.send).toHaveBeenCalled();
    });

    it('should receive and handle messages', (done) => {
      const testData = { value: 42 };

      client.on('test_message', (message) => {
        expect(message.data).toEqual(testData);
        done();
      });

      mockWs.simulateMessage({
        type: 'test_message',
        data: testData
      });
    });

    it('should handle wildcard message handlers', (done) => {
      client.on('*', (message) => {
        expect(message.type).toBe('any_message');
        done();
      });

      mockWs.simulateMessage({
        type: 'any_message',
        data: {}
      });
    });

    it('should unsubscribe message handlers', () => {
      const handler = vi.fn();
      const unsubscribe = client.on('test', handler);

      mockWs.simulateMessage({ type: 'test', data: {} });
      expect(handler).toHaveBeenCalledTimes(1);

      unsubscribe();

      mockWs.simulateMessage({ type: 'test', data: {} });
      expect(handler).toHaveBeenCalledTimes(1); // Should not be called again
    });
  });

  describe('Room Subscriptions', () => {
    beforeEach(() => {
      client.connect();
      mockWs.simulateOpen();
    });

    it('should subscribe to rooms', () => {
      client.subscribe(['nodes', 'metrics']);

      expect(mockWs.send).toHaveBeenCalledWith(
        JSON.stringify({ type: 'subscribe', rooms: ['nodes', 'metrics'] })
      );
    });

    it('should unsubscribe from rooms', () => {
      client.unsubscribe(['nodes']);

      expect(mockWs.send).toHaveBeenCalledWith(
        JSON.stringify({ type: 'unsubscribe', rooms: ['nodes'] })
      );
    });
  });

  describe('Heartbeat', () => {
    beforeEach(() => {
      client.connect();
      mockWs.simulateOpen();
    });

    it('should respond to ping with pong', () => {
      mockWs.simulateMessage({ type: 'ping' });

      expect(mockWs.send).toHaveBeenCalledWith(
        JSON.stringify({ type: 'pong' })
      );
    });

    it('should ignore pong messages', () => {
      const handler = vi.fn();
      client.on('pong', handler);

      mockWs.simulateMessage({ type: 'pong' });

      expect(handler).not.toHaveBeenCalled();
    });
  });

  describe('State Management', () => {
    it('should track connection state', () => {
      expect(client.getState()).toBe('disconnected');

      client.connect();
      expect(client.getState()).toBe('connecting');

      mockWs.simulateOpen();
      expect(client.getState()).toBe('connected');

      client.disconnect();
      expect(client.getState()).toBe('disconnected');
    });

    it('should notify state change handlers', () => {
      const stateChanges: string[] = [];

      client.onStateChange((state) => {
        stateChanges.push(state);
      });

      client.connect();
      expect(stateChanges).toContain('connecting');

      mockWs.simulateOpen();
      expect(stateChanges).toContain('connected');
    });

    it('should unsubscribe state change handlers', () => {
      const handler = vi.fn();
      const unsubscribe = client.onStateChange(handler);

      client.connect();
      expect(handler).toHaveBeenCalled();

      unsubscribe();
      handler.mockClear();

      mockWs.simulateOpen();
      expect(handler).not.toHaveBeenCalled();
    });
  });

  describe('Reconnection', () => {
    it('should attempt reconnection on disconnect', (done) => {
      client.connect();
      mockWs.simulateOpen();

      // Simulate disconnect
      mockWs.close();

      setTimeout(() => {
        expect(client.getState()).toBe('reconnecting');
        done();
      }, 150);
    });

    it('should use exponential backoff for reconnection', (done) => {
      const delays: number[] = [];
      const originalSetTimeout = global.setTimeout;

      global.setTimeout = ((callback: Function, delay: number) => {
        delays.push(delay);
        return originalSetTimeout(callback as any, 0);
      }) as any;

      client.connect();
      mockWs.simulateOpen();

      // Force multiple disconnections
      for (let i = 0; i < 3; i++) {
        mockWs.close();
        mockWs = new MockWebSocket();
      }

      setTimeout(() => {
        // Delays should increase
        expect(delays[1]).toBeGreaterThan(delays[0]);
        expect(delays[2]).toBeGreaterThan(delays[1]);

        global.setTimeout = originalSetTimeout;
        done();
      }, 100);
    });

    it('should stop reconnecting after max attempts', () => {
      client.connect();

      for (let i = 0; i <= 3; i++) {
        mockWs.close();
        mockWs = new MockWebSocket();
      }

      expect(client.getState()).toBe('error');
    });
  });

  describe('Error Handling', () => {
    it('should handle connection errors', () => {
      client.connect();
      mockWs.simulateError();

      expect(client.getState()).toBe('error');
    });

    it('should handle invalid JSON messages', () => {
      const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      client.connect();
      mockWs.simulateOpen();

      // Simulate invalid JSON
      if (mockWs.onmessage) {
        mockWs.onmessage(new MessageEvent('message', { data: 'invalid json' }));
      }

      expect(errorSpy).toHaveBeenCalled();
      errorSpy.mockRestore();
    });

    it('should handle errors in message handlers', () => {
      const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      client.connect();
      mockWs.simulateOpen();

      client.on('error_test', () => {
        throw new Error('Handler error');
      });

      mockWs.simulateMessage({ type: 'error_test', data: {} });

      expect(errorSpy).toHaveBeenCalled();
      errorSpy.mockRestore();
    });
  });

  describe('Singleton Pattern', () => {
    it('should create singleton instance', () => {
      const client1 = createWebSocketClient({ url: 'ws://test1' });
      const client2 = createWebSocketClient({ url: 'ws://test2' });

      // Second call should replace first
      expect(client1).not.toBe(client2);

      client2.disconnect();
    });
  });
});

describe('Performance Tests', () => {
  it('should handle high message throughput', () => {
    const mockWs = new MockWebSocket();
    global.WebSocket = vi.fn(() => mockWs) as any;

    const client = new WebSocketClient({ url: 'ws://localhost:8000' });
    client.connect();
    mockWs.simulateOpen();

    const receivedMessages: number[] = [];
    client.on('perf_test', (message) => {
      receivedMessages.push(message.data);
    });

    // Send 1000 messages
    for (let i = 0; i < 1000; i++) {
      mockWs.simulateMessage({ type: 'perf_test', data: i });
    }

    expect(receivedMessages).toHaveLength(1000);

    client.disconnect();
  });

  it('should handle multiple subscriptions efficiently', () => {
    const mockWs = new MockWebSocket();
    global.WebSocket = vi.fn(() => mockWs) as any;

    const client = new WebSocketClient({ url: 'ws://localhost:8000' });
    client.connect();
    mockWs.simulateOpen();

    // Subscribe to 10 rooms
    client.subscribe(Array.from({ length: 10 }, (_, i) => `room-${i}`));

    expect(mockWs.send).toHaveBeenCalledTimes(1);

    client.disconnect();
  });
});
