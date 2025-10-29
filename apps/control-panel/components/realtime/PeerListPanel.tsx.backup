'use client';

import { useState, useEffect } from 'react';
import { User, Signal } from 'lucide-react';

interface Peer {
  id: string;
  name?: string;
  address: string;
  connected_at: string;
  messages_exchanged: number;
  latency_ms: number;
}

export function PeerListPanel() {
  const [peers, setPeers] = useState<Peer[]>([]);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    const websocket = new WebSocket('ws://localhost:8000/ws/nodes');

    websocket.onopen = () => {
      setIsConnected(true);
    };

    websocket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);

        if (message.type === 'peer_list_update' || message.type === 'node_status_update') {
          const peerData = message.data?.peers || message.data?.bitchat?.peers || [];
          setPeers(peerData);
        }
      } catch (err) {
        console.error('Failed to parse peer list:', err);
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
    <div data-testid="peer-list" className="bg-gray-900 border border-gray-800 rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">Active Peers</h3>
        <span className="text-sm text-gray-400">{peers.length} connected</span>
      </div>

      {peers.length === 0 ? (
        <div className="text-center py-8 text-gray-400">
          <User className="w-12 h-12 mx-auto mb-2 text-gray-600" />
          <p>No peers connected</p>
        </div>
      ) : (
        <div className="space-y-2">
          {peers.map((peer) => (
            <div
              key={peer.id}
              data-testid={`peer-${peer.id}`}
              className="flex items-center justify-between p-3 bg-gray-800 rounded-lg hover:bg-gray-750 transition-colors"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-blue-600 rounded-full flex items-center justify-center">
                  <User className="w-5 h-5 text-white" />
                </div>
                <div>
                  <p className="text-white font-medium">{peer.name || peer.id.slice(0, 8)}</p>
                  <p className="text-sm text-gray-400">{peer.address}</p>
                </div>
              </div>

              <div className="flex items-center gap-4">
                <div className="text-right">
                  <p className="text-sm text-gray-400">Messages</p>
                  <p className="text-white font-medium">{peer.messages_exchanged}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm text-gray-400">Latency</p>
                  <p className="text-white font-medium">{peer.latency_ms}ms</p>
                </div>
                <Signal className="w-4 h-4 text-green-500" />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
