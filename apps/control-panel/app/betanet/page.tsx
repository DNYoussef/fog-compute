'use client';

import { useEffect, useState } from 'react';
import { BetanetTopology } from '@/components/BetanetTopology';
import { PacketFlowMonitor } from '@/components/PacketFlowMonitor';
import { MixnodeList } from '@/components/MixnodeList';
import { NodeManagementPanel } from '@/components/betanet/NodeManagementPanel';

interface MixnodeInfo {
  id: string;
  address: string;
  status: 'active' | 'inactive' | 'degraded';
  packetsProcessed: number;
  uptime: number;
  latency: number;
  reputation: number;
  position: { x: number; y: number; z: number };
}

export default function BetanetPage() {
  const [mixnodes, setMixnodes] = useState<MixnodeInfo[]>([]);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [networkHealth, setNetworkHealth] = useState<number>(0);

  useEffect(() => {
    document.title = 'Betanet Network | Fog Compute';
  }, []);

  useEffect(() => {
    const fetchBetanetData = async () => {
      try {
        const response = await fetch('/api/betanet/status');
        const data = await response.json();
        setMixnodes(data.mixnodes || []);
        setNetworkHealth(data.health || 0);
      } catch (error) {
        console.error('Failed to fetch betanet data:', error);
      }
    };

    fetchBetanetData();
    const interval = setInterval(fetchBetanetData, 3000);

    return () => clearInterval(interval);
  }, []);

  const activeNodes = mixnodes.filter(n => n.status === 'active').length;
  const avgLatency = mixnodes.reduce((acc, n) => acc + n.latency, 0) / mixnodes.length || 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="glass rounded-xl p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-fog-cyan">Betanet Privacy Network</h1>
            <p className="text-gray-400 mt-2">
              Real-time monitoring of mixnode topology and packet flow
            </p>
          </div>
          <div className="text-right">
            <div className="text-3xl font-bold text-fog-cyan">{networkHealth}%</div>
            <div className="text-sm text-gray-400">Network Health</div>
          </div>
        </div>
      </div>

      {/* Network Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="glass rounded-lg p-4">
          <div className="text-2xl font-bold text-green-400">{activeNodes}</div>
          <div className="text-sm text-gray-400">Active Mixnodes</div>
        </div>
        <div className="glass rounded-lg p-4">
          <div className="text-2xl font-bold text-blue-400">{mixnodes.length}</div>
          <div className="text-sm text-gray-400">Total Mixnodes</div>
        </div>
        <div className="glass rounded-lg p-4">
          <div className="text-2xl font-bold text-purple-400">{avgLatency.toFixed(2)}ms</div>
          <div className="text-sm text-gray-400">Avg Latency</div>
        </div>
        <div className="glass rounded-lg p-4">
          <div className="text-2xl font-bold text-yellow-400">
            {mixnodes.reduce((acc, n) => acc + n.packetsProcessed, 0).toLocaleString()}
          </div>
          <div className="text-sm text-gray-400">Total Packets</div>
        </div>
      </div>
      {/* Node Management Panel */}
      <div className="glass rounded-xl p-6">
        <NodeManagementPanel />
      </div>


      {/* 3D Network Topology */}
      <div className="glass rounded-xl p-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold">Network Topology</h2>
          <div className="flex gap-2" data-testid="topology-controls">
            <button className="px-3 py-1 text-sm bg-white/10 hover:bg-white/20 rounded">
              Reset View
            </button>
            <button className="px-3 py-1 text-sm bg-white/10 hover:bg-white/20 rounded">
              Auto Rotate
            </button>
          </div>
        </div>
        <div className="h-[500px] rounded-lg overflow-hidden">
          <BetanetTopology
            mixnodes={mixnodes}
            selectedNode={selectedNode}
            onNodeSelect={setSelectedNode}
          />
        </div>
      </div>

      {/* Packet Flow and Mixnode List */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="glass rounded-xl p-6">
          <h2 className="text-xl font-semibold mb-4">Packet Flow Monitor</h2>
          <PacketFlowMonitor mixnodes={mixnodes} />
        </div>
        <div className="glass rounded-xl p-6">
          <h2 className="text-xl font-semibold mb-4">Mixnode Details</h2>
          <MixnodeList
            mixnodes={mixnodes}
            selectedNode={selectedNode}
            onNodeSelect={setSelectedNode}
          />
        </div>
      </div>
    </div>
  );
}