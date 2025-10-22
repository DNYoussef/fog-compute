'use client';

import { useEffect, useState, useRef } from 'react';

interface WebSocketStatusProps {
  url?: string;
  maxRetries?: number;
  initialReconnectDelay?: number;
  maxReconnectDelay?: number;
}

type ConnectionStatus = 'connected' | 'disconnected' | 'connecting' | 'error';

export function WebSocketStatus({
  url = 'ws://localhost:8080',
  maxRetries = 10,
  initialReconnectDelay = 1000,
  maxReconnectDelay = 30000
}: WebSocketStatusProps) {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [lastMessage, setLastMessage] = useState<string>('');
  const [retryCount, setRetryCount] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  const reconnectDelayRef = useRef(initialReconnectDelay);
  const isManualDisconnectRef = useRef(false);

  useEffect(() => {
    const connect = () => {
      // Don't reconnect if we've exceeded max retries
      if (retryCount >= maxRetries) {
        setStatus('error');
        setLastMessage(`Max reconnection attempts (${maxRetries}) exceeded`);
        return;
      }

      try {
        setStatus('connecting');
        wsRef.current = new WebSocket(url);

        wsRef.current.onopen = () => {
          setStatus('connected');
          setLastMessage('Connected to server');
          setRetryCount(0);
          reconnectDelayRef.current = initialReconnectDelay; // Reset backoff
        };

        wsRef.current.onclose = (event) => {
          wsRef.current = null;

          // Don't reconnect if this was a manual disconnect
          if (isManualDisconnectRef.current) {
            setStatus('disconnected');
            setLastMessage('Manually disconnected');
            return;
          }

          setStatus('disconnected');
          const reason = event.reason || 'Unknown reason';
          setLastMessage(`Disconnected: ${reason}`);

          // Exponential backoff with jitter
          const jitter = Math.random() * 1000;
          const delay = Math.min(reconnectDelayRef.current + jitter, maxReconnectDelay);

          setLastMessage(`Reconnecting in ${(delay / 1000).toFixed(1)}s... (attempt ${retryCount + 1}/${maxRetries})`);

          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, maxReconnectDelay);
            setRetryCount(prev => prev + 1);
            connect();
          }, delay);
        };

        wsRef.current.onerror = (error) => {
          setStatus('error');
          setLastMessage('Connection error occurred');
          console.error('WebSocket error:', error);
        };

        wsRef.current.onmessage = (event) => {
          setLastMessage(`Received: ${event.data.substring(0, 50)}${event.data.length > 50 ? '...' : ''}`);
        };
      } catch (error) {
        setStatus('error');
        setLastMessage(`Failed to connect: ${error instanceof Error ? error.message : String(error)}`);

        // Retry with backoff
        const delay = Math.min(reconnectDelayRef.current, maxReconnectDelay);
        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, maxReconnectDelay);
          setRetryCount(prev => prev + 1);
          connect();
        }, delay);
      }
    };

    // Start initial connection
    isManualDisconnectRef.current = false;
    connect();

    return () => {
      // Mark as manual disconnect to prevent reconnection
      isManualDisconnectRef.current = true;

      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [url, maxRetries, initialReconnectDelay, maxReconnectDelay]);

  const handleManualReconnect = () => {
    // Clear any pending reconnection
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }

    // Close existing connection
    if (wsRef.current) {
      isManualDisconnectRef.current = true;
      wsRef.current.close();
      wsRef.current = null;
    }

    // Reset state and reconnect
    setRetryCount(0);
    reconnectDelayRef.current = initialReconnectDelay;
    isManualDisconnectRef.current = false;

    // Trigger reconnection
    setStatus('connecting');
    setTimeout(() => {
      // Force re-mount of useEffect by changing a dependency
      window.location.reload();
    }, 100);
  };

  const statusConfig = {
    connected: {
      color: 'bg-green-500',
      text: 'Connected',
      icon: '●',
    },
    disconnected: {
      color: 'bg-gray-500',
      text: 'Disconnected',
      icon: '●',
    },
    connecting: {
      color: 'bg-yellow-500',
      text: 'Connecting...',
      icon: '◐',
    },
    error: {
      color: 'bg-red-500',
      text: 'Error',
      icon: '●',
    },
  };

  const config = statusConfig[status];

  return (
    <div
      className="flex items-center gap-2 px-3 py-1.5 bg-white/5 rounded-lg"
      data-testid="websocket-status"
    >
      <span className={`w-2 h-2 rounded-full ${config.color} ${status === 'connecting' ? 'animate-pulse' : ''}`} />
      <span className="text-sm text-gray-300">{config.text}</span>
      {lastMessage && (
        <span className="text-xs text-gray-500 ml-2 max-w-[200px] truncate" title={lastMessage}>
          {lastMessage}
        </span>
      )}
      {(status === 'disconnected' || status === 'error') && retryCount < maxRetries && (
        <button
          onClick={handleManualReconnect}
          className="ml-2 px-2 py-0.5 text-xs bg-fog-cyan/20 hover:bg-fog-cyan/30 text-fog-cyan rounded transition-colors"
          data-testid="websocket-reconnect-button"
        >
          Reconnect
        </button>
      )}
      {retryCount >= maxRetries && (
        <button
          onClick={() => window.location.reload()}
          className="ml-2 px-2 py-0.5 text-xs bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded transition-colors"
          data-testid="websocket-reload-button"
        >
          Reload Page
        </button>
      )}
    </div>
  );
}
