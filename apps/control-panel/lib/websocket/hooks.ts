/**
 * React Hooks for WebSocket Integration
 */
import { useEffect, useState, useCallback, useRef } from 'react';
import { WebSocketClient, ConnectionState, WebSocketMessage, createWebSocketClient } from './client';

/**
 * Hook to manage WebSocket connection
 */
export function useWebSocket(url: string, token?: string) {
  const [state, setState] = useState<ConnectionState>('disconnected');
  const clientRef = useRef<WebSocketClient | null>(null);

  useEffect(() => {
    const client = createWebSocketClient({
      url,
      token,
      autoReconnect: true,
      maxReconnectAttempts: 10,
      reconnectInterval: 1000,
      maxReconnectInterval: 30000,
      heartbeatInterval: 30000
    });

    clientRef.current = client;

    // Subscribe to state changes
    const unsubscribe = client.onStateChange(setState);

    // Connect
    client.connect();

    // Cleanup
    return () => {
      unsubscribe();
      client.disconnect();
      clientRef.current = null;
    };
  }, [url, token]);

  const subscribe = useCallback((rooms: string[]) => {
    clientRef.current?.subscribe(rooms);
  }, []);

  const unsubscribe = useCallback((rooms: string[]) => {
    clientRef.current?.unsubscribe(rooms);
  }, []);

  const send = useCallback((message: WebSocketMessage) => {
    clientRef.current?.send(message);
  }, []);

  return {
    state,
    isConnected: state === 'connected',
    subscribe,
    unsubscribe,
    send,
    client: clientRef.current
  };
}

/**
 * Hook to subscribe to WebSocket messages
 */
export function useWebSocketMessage<T = any>(
  client: WebSocketClient | null,
  messageType: string,
  handler: (data: T) => void
) {
  useEffect(() => {
    if (!client) return;

    const unsubscribe = client.on(messageType, (message: WebSocketMessage) => {
      handler(message.data as T);
    });

    return unsubscribe;
  }, [client, messageType, handler]);
}

/**
 * Hook to manage subscriptions with automatic cleanup
 */
export function useWebSocketSubscription(
  client: WebSocketClient | null,
  rooms: string[],
  enabled: boolean = true
) {
  useEffect(() => {
    if (!client || !enabled || rooms.length === 0) return;

    // Subscribe when connected
    if (client.isConnected()) {
      client.subscribe(rooms);
    }

    // Subscribe on reconnection
    const unsubscribe = client.onStateChange((state) => {
      if (state === 'connected') {
        client.subscribe(rooms);
      }
    });

    // Cleanup: unsubscribe
    return () => {
      unsubscribe();
      if (client.isConnected()) {
        client.unsubscribe(rooms);
      }
    };
  }, [client, rooms, enabled]);
}

/**
 * Hook to receive and manage data from a WebSocket room
 */
export function useWebSocketData<T = any>(
  client: WebSocketClient | null,
  room: string,
  messageType: string,
  initialData?: T
) {
  const [data, setData] = useState<T | undefined>(initialData);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  // Subscribe to room
  useWebSocketSubscription(client, [room]);

  // Handle messages
  useWebSocketMessage(client, messageType, useCallback((newData: T) => {
    setData(newData);
    setLastUpdate(new Date());
  }, []));

  return {
    data,
    lastUpdate,
    isLoading: data === undefined
  };
}

/**
 * Hook for real-time metrics
 */
export function useRealtimeMetrics(client: WebSocketClient | null) {
  return useWebSocketData(
    client,
    'metrics',
    'metrics_update'
  );
}

/**
 * Hook for node status
 */
export function useNodeStatus(client: WebSocketClient | null) {
  return useWebSocketData(
    client,
    'nodes',
    'node_status_update'
  );
}

/**
 * Hook for task progress
 */
export function useTaskProgress(client: WebSocketClient | null) {
  return useWebSocketData(
    client,
    'tasks',
    'task_progress_update'
  );
}

/**
 * Hook for alerts
 */
export function useAlerts(client: WebSocketClient | null) {
  const [alerts, setAlerts] = useState<any[]>([]);

  useWebSocketSubscription(client, ['alerts']);

  useWebSocketMessage(client, 'alert', useCallback((alert: any) => {
    setAlerts(prev => [alert, ...prev].slice(0, 100)); // Keep last 100 alerts
  }, []));

  const clearAlerts = useCallback(() => {
    setAlerts([]);
  }, []);

  return {
    alerts,
    clearAlerts
  };
}

/**
 * Hook for resource monitoring
 */
export function useResourceMonitor(client: WebSocketClient | null) {
  return useWebSocketData(
    client,
    'resources',
    'resource_update'
  );
}

/**
 * Hook for topology changes
 */
export function useTopology(client: WebSocketClient | null) {
  return useWebSocketData(
    client,
    'topology',
    'topology_change'
  );
}
