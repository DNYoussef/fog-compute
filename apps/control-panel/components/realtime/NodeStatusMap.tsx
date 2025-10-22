'use client';

import { useNodeStatus } from '@/lib/websocket/hooks';
import { WebSocketClient } from '@/lib/websocket/client';

interface NodeData {
  betanet: {
    active_nodes: number;
    connections: number;
    avg_latency_ms: number;
    packets_processed: number;
  };
  p2p: {
    connected_peers: number;
    messages_sent: number;
    messages_received: number;
  };
}

interface NodeStatusMapProps {
  client: WebSocketClient | null;
}

export function NodeStatusMap({ client }: NodeStatusMapProps) {
  const { data: nodeData, lastUpdate, isLoading } = useNodeStatus(client);

  if (isLoading) {
    return (
      <div className="bg-white/5 rounded-lg p-6 border border-white/10">
        <h3 className="text-lg font-semibold text-white mb-4">Node Status</h3>
        <div className="flex items-center justify-center h-64">
          <div className="animate-pulse text-gray-400">Loading node status...</div>
        </div>
      </div>
    );
  }

  const data = nodeData as NodeData;

  return (
    <div className="bg-white/5 rounded-lg p-6 border border-white/10">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold text-white">Node Status</h3>
        {lastUpdate && (
          <span className="text-xs text-gray-400">
            Updated {lastUpdate.toLocaleTimeString()}
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Betanet Status */}
        <div className="space-y-4">
          <h4 className="text-sm font-medium text-fog-cyan uppercase tracking-wide">Betanet Network</h4>

          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 bg-white/5 rounded">
              <span className="text-gray-400">Active Nodes</span>
              <span className="text-2xl font-bold text-white">{data.betanet.active_nodes}</span>
            </div>

            <div className="flex items-center justify-between p-3 bg-white/5 rounded">
              <span className="text-gray-400">Connections</span>
              <span className="text-2xl font-bold text-white">{data.betanet.connections}</span>
            </div>

            <div className="flex items-center justify-between p-3 bg-white/5 rounded">
              <span className="text-gray-400">Avg Latency</span>
              <span className="text-2xl font-bold text-white">
                {data.betanet.avg_latency_ms.toFixed(1)}
                <span className="text-sm text-gray-400 ml-1">ms</span>
              </span>
            </div>

            <div className="flex items-center justify-between p-3 bg-white/5 rounded">
              <span className="text-gray-400">Packets Processed</span>
              <span className="text-2xl font-bold text-white">
                {data.betanet.packets_processed.toLocaleString()}
              </span>
            </div>
          </div>
        </div>

        {/* P2P Status */}
        <div className="space-y-4">
          <h4 className="text-sm font-medium text-fog-green uppercase tracking-wide">P2P Network</h4>

          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 bg-white/5 rounded">
              <span className="text-gray-400">Connected Peers</span>
              <span className="text-2xl font-bold text-white">{data.p2p.connected_peers}</span>
            </div>

            <div className="flex items-center justify-between p-3 bg-white/5 rounded">
              <span className="text-gray-400">Messages Sent</span>
              <span className="text-2xl font-bold text-white">
                {data.p2p.messages_sent.toLocaleString()}
              </span>
            </div>

            <div className="flex items-center justify-between p-3 bg-white/5 rounded">
              <span className="text-gray-400">Messages Received</span>
              <span className="text-2xl font-bold text-white">
                {data.p2p.messages_received.toLocaleString()}
              </span>
            </div>

            <div className="flex items-center justify-between p-3 bg-white/5 rounded">
              <span className="text-gray-400">Message Rate</span>
              <span className="text-2xl font-bold text-white">
                {((data.p2p.messages_sent + data.p2p.messages_received) / 60).toFixed(1)}
                <span className="text-sm text-gray-400 ml-1">/sec</span>
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Network Visualization */}
      <div className="mt-6 p-4 bg-white/5 rounded">
        <div className="flex items-center justify-center gap-8">
          <div className="flex flex-col items-center">
            <div className="w-16 h-16 rounded-full bg-fog-cyan/20 border-2 border-fog-cyan flex items-center justify-center">
              <span className="text-2xl font-bold text-fog-cyan">{data.betanet.active_nodes}</span>
            </div>
            <span className="text-xs text-gray-400 mt-2">Betanet</span>
          </div>

          <div className="flex-1 h-0.5 bg-gradient-to-r from-fog-cyan via-white to-fog-green" />

          <div className="flex flex-col items-center">
            <div className="w-16 h-16 rounded-full bg-fog-green/20 border-2 border-fog-green flex items-center justify-center">
              <span className="text-2xl font-bold text-fog-green">{data.p2p.connected_peers}</span>
            </div>
            <span className="text-xs text-gray-400 mt-2">P2P Peers</span>
          </div>
        </div>
      </div>
    </div>
  );
}
