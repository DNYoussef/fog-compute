'use client';

import { useEffect, useState, useRef } from 'react';
import { Wifi, WifiOff, RefreshCw } from 'lucide-react';

interface WebSocketStatusProps {
  url?: string;
  maxRetries?: number;
  initialReconnectDelay?: number;
  maxReconnectDelay?: number;
}

type ConnectionStatus = 'connected' | 'disconnected' | 'connecting' | 'error';
type ConnectionState = 'connected' | 'reconnecting' | 'offline';

export function WebSocketStatus({
  url = 'ws://localhost:8000/ws/metrics',
  maxRetries = 10,
  initialReconnectDelay = 5000,
  maxReconnectDelay = 30000
}: WebSocketStatusProps) {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [lastMessage, setLastMessage] = useState<string>('');
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
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
          setLastUpdate(new Date());
          setRetryCount(0);
          reconnectDelayRef.current = initialReconnectDelay; // Reset backoff
          console.log('✅ WebSocket connected');
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
          setLastUpdate(new Date());
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
    setStatus('connecting');
    setLastMessage('Manually reconnecting...');
    isManualDisconnectRef.current = false;

    // Trigger reconnection by creating new connection
    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus('connected');
        setLastMessage('Connected to server');
        setLastUpdate(new Date());
        setRetryCount(0);
        reconnectDelayRef.current = initialReconnectDelay;
        console.log('Manual reconnect successful');
      };

      ws.onclose = (event) => {
        wsRef.current = null;

        if (isManualDisconnectRef.current) {
          setStatus('disconnected');
          setLastMessage('Manually disconnected');
          return;
        }

        setStatus('disconnected');
        const reason = event.reason || 'Unknown reason';
        setLastMessage(`Disconnected: ${reason}`);

        const jitter = Math.random() * 1000;
        const delay = Math.min(reconnectDelayRef.current + jitter, maxReconnectDelay);

        setLastMessage(`Reconnecting in ${(delay / 1000).toFixed(1)}s... (attempt ${retryCount + 1}/${maxRetries})`);

        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, maxReconnectDelay);
          setRetryCount(prev => prev + 1);
          handleManualReconnect();
        }, delay);
      };

      ws.onerror = (error) => {
        setStatus('error');
        setLastMessage('Connection error occurred');
        console.error('WebSocket error:', error);
      };

      ws.onmessage = (event) => {
        setLastUpdate(new Date());
        setLastMessage(`Received: ${event.data.substring(0, 50)}${event.data.length > 50 ? '...' : ''}`);
      };
    } catch (error) {
      setStatus('error');
      setLastMessage(`Failed to reconnect: ${error instanceof Error ? error.message : String(error)}`);
    }
  };

  const getConnectionState = (): ConnectionState => {
    if (status === 'connected') return 'connected';
    if (status === 'connecting') return 'reconnecting';
    return 'offline';
  };

  const state = getConnectionState();

  const getStatusConfig = () => {
    switch (state) {
      case 'connected':
        return {
          icon: Wifi,
          text: 'Connected',
          color: 'text-green-500',
          bgColor: 'bg-green-500',
          testId: 'ws-status',
        };
      case 'reconnecting':
        return {
          icon: RefreshCw,
          text: status === 'error' ? 'Connection Error' : 'Reconnecting...',
          color: 'text-yellow-500',
          bgColor: 'bg-yellow-500',
          testId: 'ws-status',
        };
      case 'offline':
        return {
          icon: WifiOff,
          text: 'Offline',
          color: 'text-red-500',
          bgColor: 'bg-red-500',
          testId: 'offline-indicator',
        };
    }
  };

  const config = getStatusConfig();
  const Icon = config.icon;

  const formatLastUpdate = () => {
    if (!lastUpdate) return 'Never';
    const seconds = Math.floor((new Date().getTime() - lastUpdate.getTime()) / 1000);
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h ago`;
  };

  return (
    <div
      data-testid={config.testId}
      data-status={state}
      className="flex items-center gap-3 px-3 py-2 bg-gray-900 border border-gray-800 rounded-lg"
    >
      {/* Animated Status Dot */}
      <div className="relative flex-shrink-0">
        <div className={`w-2 h-2 ${config.bgColor} rounded-full ${state === 'connected' ? 'animate-pulse' : ''}`} />
        {state === 'connected' && (
          <div className={`absolute inset-0 w-2 h-2 ${config.bgColor} rounded-full animate-ping opacity-75`} />
        )}
      </div>

      {/* Icon */}
      <Icon className={`w-4 h-4 ${config.color} flex-shrink-0 ${state === 'reconnecting' ? 'animate-spin' : ''}`} />

      {/* Status Text */}
      <span className={`text-sm font-medium ${config.color}`}>
        {config.text}
      </span>

      {/* Last Update Timestamp */}
      {lastUpdate && state === 'connected' && (
        <span className="text-xs text-gray-500 ml-auto" data-testid="last-update-timestamp">
          {formatLastUpdate()}
        </span>
      )}

      {/* Reconnection Info */}
      {state === 'reconnecting' && retryCount > 0 && (
        <span className="text-xs text-gray-500 ml-auto">
          Attempt {retryCount}/{maxRetries}
        </span>
      )}

      {/* Manual Reconnect Button */}
      {state === 'offline' && retryCount < maxRetries && (
        <button
          onClick={handleManualReconnect}
          className="ml-auto px-2 py-1 text-xs bg-fog-cyan/20 hover:bg-fog-cyan/30 text-fog-cyan rounded transition-colors"
          data-testid="websocket-reconnect-button"
        >
          Reconnect
        </button>
      )}

      {/* Error State - Try Again or Reload */}
      {retryCount >= maxRetries && (
        <div className="ml-auto flex gap-2">
          <button
            onClick={handleManualReconnect}
            className="px-2 py-1 text-xs bg-yellow-500/20 hover:bg-yellow-500/30 text-yellow-400 rounded transition-colors"
            data-testid="websocket-retry-button"
          >
            Try Again
          </button>
          <button
            onClick={() => window.location.reload()}
            className="px-2 py-1 text-xs bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded transition-colors"
            data-testid="websocket-reload-button"
            title="Last resort: Reload entire page"
          >
            Reload
          </button>
        </div>
      )}
    </div>
  );
}
