'use client';

import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/Card';
import { NetworkGraph } from '@/components/NetworkGraph';

interface P2PStats {
  bitchat: {
    bleConnections: number;
    offlinePeers: number;
    meshTopology: 'star' | 'mesh' | 'hybrid';
  };
  betanet: {
    htxCircuits: number;
    onlineNodes: number;
    throughput: number;
  };
  unified: {
    totalPeers: number;
    protocolDistribution: { ble: number; htx: number; mesh: number };
    messageQueue: number;
    activeRoutes: number;
  };
}

export default function P2PNetworkPage() {
  const [stats, setStats] = useState<P2PStats | null>(null);
  const [selectedProtocol, setSelectedProtocol] = useState<'all' | 'ble' | 'htx' | 'mesh'>('all');

  useEffect(() => {
    document.title = 'P2P Network | Fog Compute';
  }, []);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await fetch('/api/p2p/stats');
        const data = await response.json();
        setStats(data);
      } catch (error) {
        console.error('Failed to fetch P2P stats:', error);
      }
    };

    fetchStats();
    const interval = setInterval(fetchStats, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="glass rounded-xl p-6">
        <h1 className="text-3xl font-bold bg-gradient-to-r from-fog-cyan to-fog-purple bg-clip-text text-transparent">
          Unified P2P Network
        </h1>
        <p className="text-gray-400 mt-2">
          Monitor and control BLE (offline), HTX (online), and Mesh protocols
        </p>
      </div>

      {/* Protocol Selector */}
      <div className="flex gap-4">
        {['all', 'ble', 'htx', 'mesh'].map((protocol) => (
          <button
            key={protocol}
            onClick={() => setSelectedProtocol(protocol as any)}
            className={`px-6 py-3 rounded-lg font-semibold transition-all ${
              selectedProtocol === protocol
                ? 'bg-fog-cyan text-dark-bg'
                : 'glass text-gray-400 hover:text-white'
            }`}
          >
            {protocol.toUpperCase()}
          </button>
        ))}
      </div>

      {/* Protocol Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card
          title="BitChat (BLE)"
          subtitle="Offline P2P Messaging"
          className="border-l-4 border-fog-purple"
        >
          <div className="space-y-3">
            <div className="flex justify-between">
              <span className="text-gray-400">BLE Connections</span>
              <span className="font-semibold text-fog-purple">
                {stats?.bitchat.bleConnections || 0}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Offline Peers</span>
              <span className="font-semibold">{stats?.bitchat.offlinePeers || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Mesh Topology</span>
              <span className="font-semibold uppercase">
                {stats?.bitchat.meshTopology || 'Unknown'}
              </span>
            </div>
          </div>
        </Card>

        <Card
          title="BetaNet (HTX)"
          subtitle="Internet P2P Network"
          className="border-l-4 border-fog-cyan"
        >
          <div className="space-y-3">
            <div className="flex justify-between">
              <span className="text-gray-400">HTX Circuits</span>
              <span className="font-semibold text-fog-cyan">
                {stats?.betanet.htxCircuits || 0}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Online Nodes</span>
              <span className="font-semibold">{stats?.betanet.onlineNodes || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Throughput</span>
              <span className="font-semibold">
                {stats?.betanet.throughput?.toFixed(2) || 0} MB/s
              </span>
            </div>
          </div>
        </Card>

        <Card
          title="Unified System"
          subtitle="Cross-Protocol Coordination"
          className="border-l-4 border-green-400"
        >
          <div className="space-y-3">
            <div className="flex justify-between">
              <span className="text-gray-400">Total Peers</span>
              <span className="font-semibold text-green-400">
                {stats?.unified.totalPeers || 0}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Active Routes</span>
              <span className="font-semibold">{stats?.unified.activeRoutes || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Message Queue</span>
              <span className="font-semibold">{stats?.unified.messageQueue || 0}</span>
            </div>
          </div>
        </Card>
      </div>

      {/* Network Visualization */}
      <Card title="P2P Network Topology" className="min-h-[500px]">
        <NetworkGraph protocol={selectedProtocol} stats={stats} />
      </Card>

      {/* Protocol Distribution */}
      <Card title="Protocol Distribution">
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center p-4 glass rounded-lg">
            <div className="text-3xl font-bold text-fog-purple">
              {stats?.unified.protocolDistribution.ble || 0}
            </div>
            <div className="text-gray-400 mt-2">BLE Connections</div>
          </div>
          <div className="text-center p-4 glass rounded-lg">
            <div className="text-3xl font-bold text-fog-cyan">
              {stats?.unified.protocolDistribution.htx || 0}
            </div>
            <div className="text-gray-400 mt-2">HTX Circuits</div>
          </div>
          <div className="text-center p-4 glass rounded-lg">
            <div className="text-3xl font-bold text-green-400">
              {stats?.unified.protocolDistribution.mesh || 0}
            </div>
            <div className="text-gray-400 mt-2">Mesh Links</div>
          </div>
        </div>
      </Card>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <button className="btn-primary p-4 rounded-lg">
          <span className="text-lg">Switch Protocol</span>
          <p className="text-sm text-gray-400 mt-1">
            Automatically switch between BLE/HTX based on connectivity
          </p>
        </button>
        <button className="btn-secondary p-4 rounded-lg">
          <span className="text-lg">Create Circuit</span>
          <p className="text-sm text-gray-400 mt-1">
            Establish new HTX circuit for privacy routing
          </p>
        </button>
      </div>
    </div>
  );
}