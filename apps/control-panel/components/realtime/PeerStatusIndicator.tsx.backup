'use client';

import { useState, useEffect } from 'react';
import { Users, Wifi, WifiOff } from 'lucide-react';

interface PeerStats {
  connected_peers: number;
  messages_sent: number;
  messages_received: number;
  mesh_health: string;
}

export function PeerStatusIndicator() {
  const [stats, setStats] = useState<PeerStats>({
    connected_peers: 0,
    messages_sent: 0,
    messages_received: 0,
    mesh_health: 'unknown',
  });
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    const websocket = new WebSocket('ws://localhost:8000/ws/nodes');

    websocket.onopen = () => {
      setIsConnected(true);
    };

    websocket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);

        if (message.type === 'node_status_update' && message.data?.bitchat) {
          setStats({
            connected_peers: message.data.bitchat.connected_peers || 0,
            messages_sent: message.data.bitchat.messages_sent || 0,
            messages_received: message.data.bitchat.messages_received || 0,
            mesh_health: message.data.bitchat.mesh_health || 'unknown',
          });
        }
      } catch (err) {
        console.error('Failed to parse peer status:', err);
      }
    };

    websocket.onclose = () => {
      setIsConnected(false);
    };

    return () => {
      websocket.close();
    };
  }, []);

  return (
    <div data-testid="peer-status" className="bg-gray-900 border border-gray-800 rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">BitChat Peer Status</h3>
        {isConnected ? (
          <Wifi className="w-5 h-5 text-green-500" />
        ) : (
          <WifiOff className="w-5 h-5 text-red-500" />
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-gray-800 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <Users className="w-4 h-4 text-blue-400" />
            <span className="text-sm text-gray-400">Connected Peers</span>
          </div>
          <p className="text-2xl font-bold text-white">{stats.connected_peers}</p>
        </div>

        <div className="bg-gray-800 rounded-lg p-4">
          <span className="text-sm text-gray-400 block mb-2">Mesh Health</span>
          <span
            className={`px-3 py-1 rounded-full text-sm font-medium ${
              stats.mesh_health === 'healthy'
                ? 'bg-green-900/30 text-green-400'
                : stats.mesh_health === 'degraded'
                ? 'bg-yellow-900/30 text-yellow-400'
                : 'bg-gray-700 text-gray-400'
            }`}
          >
            {stats.mesh_health}
          </span>
        </div>

        <div className="bg-gray-800 rounded-lg p-4">
          <span className="text-sm text-gray-400 block mb-2">Messages Sent</span>
          <p className="text-xl font-semibold text-white">{stats.messages_sent.toLocaleString()}</p>
        </div>

        <div className="bg-gray-800 rounded-lg p-4">
          <span className="text-sm text-gray-400 block mb-2">Messages Received</span>
          <p className="text-xl font-semibold text-white">{stats.messages_received.toLocaleString()}</p>
        </div>
      </div>
    </div>
  );
}
