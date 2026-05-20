'use client';

import { useEffect, useRef, useState } from 'react';
import { RefreshCw, Wifi, WifiOff } from 'lucide-react';

interface WebSocketStatusProps {
  url?: string;
  maxRetries?: number;
  initialReconnectDelay?: number;
  maxReconnectDelay?: number;
  testId?: string;
  offlineTestId?: string;
}

type ConnectionStatus = 'connected' | 'disconnected' | 'connecting' | 'error';
type ConnectionState = 'connected' | 'reconnecting' | 'offline';

function resolveDefaultWebSocketUrl(): string {
  if (process.env.NEXT_PUBLIC_WS_URL) {
    return process.env.NEXT_PUBLIC_WS_URL;
  }

  if (process.env.NEXT_PUBLIC_API_URL) {
    try {
      const apiUrl = new URL(process.env.NEXT_PUBLIC_API_URL);
      apiUrl.protocol = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:';
      apiUrl.pathname = '/ws/metrics';
      apiUrl.search = '';
      apiUrl.hash = '';
      return apiUrl.toString();
    } catch {
      // Fall through to the local development default.
    }
  }

  return 'ws://127.0.0.1:8000/ws/metrics';
}

export function WebSocketStatus({
  url = resolveDefaultWebSocketUrl(),
  maxRetries = 10,
  initialReconnectDelay = 5000,
  maxReconnectDelay = 30000,
  testId = 'ws-status',
  offlineTestId = 'offline-indicator'
}: WebSocketStatusProps) {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [lastMessage, setLastMessage] = useState<string>('');
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [retryCount, setRetryCount] = useState(0);
  const [isBrowserOffline, setIsBrowserOffline] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  const reconnectDelayRef = useRef(initialReconnectDelay);
  const isManualDisconnectRef = useRef(false);
  const retryCountRef = useRef(0);

  useEffect(() => {
    const connect = () => {
      if (retryCountRef.current >= maxRetries) {
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
          retryCountRef.current = 0;
          setRetryCount(0);
          reconnectDelayRef.current = initialReconnectDelay;
          console.log('WebSocket connected');
        };

        wsRef.current.onclose = (event) => {
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
          const nextRetryCount = retryCountRef.current + 1;

          if (retryCountRef.current >= maxRetries) {
            setStatus('error');
            setLastMessage(`Max reconnection attempts (${maxRetries}) exceeded`);
            return;
          }

          setLastMessage(`Reconnecting in ${(delay / 1000).toFixed(1)}s... (attempt ${nextRetryCount}/${maxRetries})`);

          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, maxReconnectDelay);
            retryCountRef.current = nextRetryCount;
            setRetryCount(nextRetryCount);
            connect();
          }, delay);
        };

        wsRef.current.onerror = (error) => {
          setStatus('error');
          setLastMessage('Connection error occurred');
          console.warn('WebSocket error:', error);
        };

        wsRef.current.onmessage = (event) => {
          setLastUpdate(new Date());
          setLastMessage(`Received: ${event.data.substring(0, 50)}${event.data.length > 50 ? '...' : ''}`);
        };
      } catch (error) {
        setStatus('error');
        setLastMessage(`Failed to connect: ${error instanceof Error ? error.message : String(error)}`);

        const delay = Math.min(reconnectDelayRef.current, maxReconnectDelay);
        const nextRetryCount = retryCountRef.current + 1;

        if (retryCountRef.current >= maxRetries) {
          setStatus('error');
          setLastMessage(`Max reconnection attempts (${maxRetries}) exceeded`);
          return;
        }

        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, maxReconnectDelay);
          retryCountRef.current = nextRetryCount;
          setRetryCount(nextRetryCount);
          connect();
        }, delay);
      }
    };

    isManualDisconnectRef.current = false;
    connect();

    return () => {
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

  const handleManualReconnect = (resetRetry = true) => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }

    if (wsRef.current) {
      isManualDisconnectRef.current = true;
      wsRef.current.close();
      wsRef.current = null;
    }

    if (resetRetry) {
      retryCountRef.current = 0;
      setRetryCount(0);
    } else if (retryCountRef.current >= maxRetries) {
      setStatus('error');
      setLastMessage(`Max reconnection attempts (${maxRetries}) exceeded`);
      return;
    }

    reconnectDelayRef.current = initialReconnectDelay;
    setStatus('connecting');
    setLastMessage('Manually reconnecting...');
    isManualDisconnectRef.current = false;

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus('connected');
        setLastMessage('Connected to server');
        setLastUpdate(new Date());
        retryCountRef.current = 0;
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
        const nextRetryCount = retryCountRef.current + 1;

        if (retryCountRef.current >= maxRetries) {
          setStatus('error');
          setLastMessage(`Max reconnection attempts (${maxRetries}) exceeded`);
          return;
        }

        setLastMessage(`Reconnecting in ${(delay / 1000).toFixed(1)}s... (attempt ${nextRetryCount}/${maxRetries})`);

        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, maxReconnectDelay);
          retryCountRef.current = nextRetryCount;
          setRetryCount(nextRetryCount);
          handleManualReconnect(false);
        }, delay);
      };

      ws.onerror = (error) => {
        setStatus('error');
        setLastMessage('Connection error occurred');
        console.warn('WebSocket error:', error);
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

  useEffect(() => {
    const handleOffline = () => {
      setIsBrowserOffline(true);
      setStatus('disconnected');
      setLastMessage('Browser is offline');
    };
    const handleOnline = () => {
      setIsBrowserOffline(false);
      setStatus('connecting');
      setLastMessage('Network restored');
    };

    setIsBrowserOffline(typeof navigator !== 'undefined' && !navigator.onLine);
    window.addEventListener('offline', handleOffline);
    window.addEventListener('online', handleOnline);

    return () => {
      window.removeEventListener('offline', handleOffline);
      window.removeEventListener('online', handleOnline);
    };
  }, []);

  const getConnectionState = (): ConnectionState => {
    if (isBrowserOffline) return 'offline';
    if (status === 'connected') return 'connected';
    return 'reconnecting';
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
          testId,
        };
      case 'reconnecting':
        return {
          icon: RefreshCw,
          text: status === 'error' ? 'Connection Error' : 'Reconnecting...',
          color: 'text-yellow-500',
          bgColor: 'bg-yellow-500',
          testId,
        };
      case 'offline':
        return {
          icon: WifiOff,
          text: 'Offline',
          color: 'text-red-500',
          bgColor: 'bg-red-500',
          testId: offlineTestId,
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
      <div className="relative flex-shrink-0">
        <div className={`w-2 h-2 ${config.bgColor} rounded-full ${state === 'connected' ? 'animate-pulse' : ''}`} />
        {state === 'connected' && (
          <div className={`absolute inset-0 w-2 h-2 ${config.bgColor} rounded-full animate-ping opacity-75`} />
        )}
      </div>

      <Icon className={`w-4 h-4 ${config.color} flex-shrink-0 ${state === 'reconnecting' ? 'animate-spin' : ''}`} />

      <span className={`text-sm font-medium ${config.color}`}>
        {config.text}
      </span>

      {lastUpdate && state === 'connected' && (
        <span className="text-xs text-gray-400 ml-auto" data-testid="last-update-timestamp">
          {formatLastUpdate()}
        </span>
      )}

      {state === 'reconnecting' && retryCount > 0 && (
        <span className="text-xs text-gray-400 ml-auto">
          Attempt {retryCount}/{maxRetries}
        </span>
      )}

      {state === 'offline' && retryCount < maxRetries && (
        <button
          onClick={() => handleManualReconnect()}
          className="ml-auto px-2 py-1 text-xs bg-fog-cyan/20 hover:bg-fog-cyan/30 text-fog-cyan rounded transition-colors"
          data-testid="websocket-reconnect-button"
        >
          Reconnect
        </button>
      )}

      {retryCount >= maxRetries && (
        <div className="ml-auto flex gap-2">
          <button
            onClick={() => handleManualReconnect()}
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
