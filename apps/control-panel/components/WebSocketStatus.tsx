'use client';

import { useEffect, useState } from 'react';

interface WebSocketStatusProps {
  url?: string;
}

type ConnectionStatus = 'connected' | 'disconnected' | 'connecting' | 'error';

export function WebSocketStatus({ url = 'ws://localhost:8080' }: WebSocketStatusProps) {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [lastMessage, setLastMessage] = useState<string>('');

  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimeout: NodeJS.Timeout;

    const connect = () => {
      try {
        setStatus('connecting');
        ws = new WebSocket(url);

        ws.onopen = () => {
          setStatus('connected');
          setLastMessage('Connected to server');
        };

        ws.onclose = () => {
          setStatus('disconnected');
          setLastMessage('Disconnected from server');
          // Attempt to reconnect after 5 seconds
          reconnectTimeout = setTimeout(connect, 5000);
        };

        ws.onerror = () => {
          setStatus('error');
          setLastMessage('Connection error');
        };

        ws.onmessage = (event) => {
          setLastMessage(`Received: ${event.data}`);
        };
      } catch (error) {
        setStatus('error');
        setLastMessage(`Failed to connect: ${error}`);
      }
    };

    connect();

    return () => {
      if (ws) {
        ws.close();
      }
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
      }
    };
  }, [url]);

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
      <span className={`w-2 h-2 rounded-full ${config.color} animate-pulse`} />
      <span className="text-sm text-gray-300">{config.text}</span>
      {lastMessage && (
        <span className="text-xs text-gray-500 ml-2 max-w-[200px] truncate" title={lastMessage}>
          {lastMessage}
        </span>
      )}
    </div>
  );
}
