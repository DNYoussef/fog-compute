'use client';

import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/Card';
import { CircuitVisualization } from '@/components/CircuitVisualization';

interface PrivacyStats {
  circuits: {
    active: number;
    total: number;
    avgLatency: number;
    throughput: number;
  };
  onion: {
    layers: number;
    nodes: number;
    encryption: 'AES-256' | 'ChaCha20';
    mixnets: number;
  };
  vpn: {
    tunnels: number;
    bandwidth: number;
    connectedUsers: number;
    protocols: string[];
  };
  privacy: {
    anonymityScore: number;
    fingerprintResistance: number;
    trafficObfuscation: number;
  };
}

export default function PrivacyPage() {
  const [stats, setStats] = useState<PrivacyStats | null>(null);
  const [selectedCircuit, setSelectedCircuit] = useState<string | null>(null);

  useEffect(() => {
    document.title = 'Privacy | Fog Compute';
  }, []);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await fetch('/api/privacy/stats');
        const data = await response.json();
        setStats(data);
      } catch (error) {
        console.error('Failed to fetch privacy stats:', error);
      }
    };

    fetchStats();
    const interval = setInterval(fetchStats, 4000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="glass rounded-xl p-6">
        <h1 className="text-3xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
          Privacy & Onion Routing
        </h1>
        <p className="text-gray-400 mt-2">
          Multi-layer encryption, VPN tunneling, and anonymity preservation
        </p>
      </div>

      {/* Privacy Score Dashboard */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card title="Anonymity Score" className="border-l-4 border-purple-400">
          <div className="relative pt-1">
            <div className="flex mb-2 items-center justify-between">
              <div>
                <span className="text-4xl font-bold text-purple-400">
                  {stats?.privacy.anonymityScore || 0}
                </span>
                <span className="text-gray-400">/100</span>
              </div>
            </div>
            <div className="overflow-hidden h-4 text-xs flex rounded-full bg-dark-bg-lighter">
              <div
                style={{ width: `${stats?.privacy.anonymityScore || 0}%` }}
                className="shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center bg-gradient-to-r from-purple-400 to-pink-400 transition-all"
              />
            </div>
          </div>
        </Card>

        <Card title="Fingerprint Resistance" className="border-l-4 border-fog-cyan">
          <div className="relative pt-1">
            <div className="flex mb-2 items-center justify-between">
              <div>
                <span className="text-4xl font-bold text-fog-cyan">
                  {stats?.privacy.fingerprintResistance || 0}
                </span>
                <span className="text-gray-400">/100</span>
              </div>
            </div>
            <div className="overflow-hidden h-4 text-xs flex rounded-full bg-dark-bg-lighter">
              <div
                style={{ width: `${stats?.privacy.fingerprintResistance || 0}%` }}
                className="shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center bg-fog-cyan transition-all"
              />
            </div>
          </div>
        </Card>

        <Card title="Traffic Obfuscation" className="border-l-4 border-green-400">
          <div className="relative pt-1">
            <div className="flex mb-2 items-center justify-between">
              <div>
                <span className="text-4xl font-bold text-green-400">
                  {stats?.privacy.trafficObfuscation || 0}
                </span>
                <span className="text-gray-400">/100</span>
              </div>
            </div>
            <div className="overflow-hidden h-4 text-xs flex rounded-full bg-dark-bg-lighter">
              <div
                style={{ width: `${stats?.privacy.trafficObfuscation || 0}%` }}
                className="shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center bg-green-400 transition-all"
              />
            </div>
          </div>
        </Card>
      </div>

      {/* Circuit Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card title="Onion Routing Circuits">
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 glass rounded-lg">
              <div>
                <div className="text-sm text-gray-400">Active Circuits</div>
                <div className="text-2xl font-bold text-purple-400">
                  {stats?.circuits.active || 0}
                </div>
              </div>
              <div>
                <div className="text-sm text-gray-400">Total Circuits</div>
                <div className="text-2xl font-bold">
                  {stats?.circuits.total || 0}
                </div>
              </div>
            </div>
            <div className="flex items-center justify-between p-4 glass rounded-lg">
              <div>
                <div className="text-sm text-gray-400">Avg Latency</div>
                <div className="text-2xl font-bold text-fog-cyan">
                  {stats?.circuits.avgLatency || 0}ms
                </div>
              </div>
              <div>
                <div className="text-sm text-gray-400">Throughput</div>
                <div className="text-2xl font-bold">
                  {stats?.circuits.throughput?.toFixed(1) || 0} MB/s
                </div>
              </div>
            </div>
          </div>
        </Card>

        <Card title="Onion Routing Configuration">
          <div className="space-y-4">
            <div className="flex justify-between items-center p-4 glass rounded-lg">
              <span className="text-gray-400">Encryption Layers</span>
              <span className="text-2xl font-bold text-purple-400">
                {stats?.onion.layers || 0}
              </span>
            </div>
            <div className="flex justify-between items-center p-4 glass rounded-lg">
              <span className="text-gray-400">Relay Nodes</span>
              <span className="text-2xl font-bold">
                {stats?.onion.nodes || 0}
              </span>
            </div>
            <div className="flex justify-between items-center p-4 glass rounded-lg">
              <span className="text-gray-400">Encryption Algorithm</span>
              <span className="text-xl font-bold text-fog-cyan">
                {stats?.onion.encryption || 'N/A'}
              </span>
            </div>
            <div className="flex justify-between items-center p-4 glass rounded-lg">
              <span className="text-gray-400">Mixnets</span>
              <span className="text-2xl font-bold text-green-400">
                {stats?.onion.mixnets || 0}
              </span>
            </div>
          </div>
        </Card>
      </div>

      {/* Circuit Visualization */}
      <Card title="Circuit Topology Visualization" className="min-h-[600px]">
        <CircuitVisualization selectedCircuit={selectedCircuit} stats={stats} />
      </Card>

      {/* VPN Tunnels */}
      <Card title="VPN Tunnel Statistics">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="text-center p-6 glass rounded-lg">
            <div className="text-4xl font-bold text-purple-400">
              {stats?.vpn.tunnels || 0}
            </div>
            <div className="text-gray-400 mt-2">Active Tunnels</div>
          </div>
          <div className="text-center p-6 glass rounded-lg">
            <div className="text-4xl font-bold text-fog-cyan">
              {stats?.vpn.bandwidth?.toFixed(1) || 0} MB/s
            </div>
            <div className="text-gray-400 mt-2">Total Bandwidth</div>
          </div>
          <div className="text-center p-6 glass rounded-lg">
            <div className="text-4xl font-bold text-green-400">
              {stats?.vpn.connectedUsers || 0}
            </div>
            <div className="text-gray-400 mt-2">Connected Users</div>
          </div>
        </div>
        <div className="mt-6 p-4 glass rounded-lg">
          <div className="text-sm text-gray-400 mb-2">Supported Protocols</div>
          <div className="flex gap-2 flex-wrap">
            {stats?.vpn.protocols?.map((protocol) => (
              <span
                key={protocol}
                className="px-3 py-1 bg-dark-bg-lighter rounded-full text-sm font-semibold"
              >
                {protocol}
              </span>
            )) || <span className="text-gray-400">Loading...</span>}
          </div>
        </div>
      </Card>

      {/* Privacy Controls */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <button className="btn-primary p-6 rounded-lg text-left">
          <div className="text-xl font-semibold">Create New Circuit</div>
          <p className="text-sm text-gray-400 mt-2">
            Establish a new onion routing circuit with 3+ hops
          </p>
        </button>
        <button className="btn-secondary p-6 rounded-lg text-left">
          <div className="text-xl font-semibold">Rotate Circuits</div>
          <p className="text-sm text-gray-400 mt-2">
            Rotate all active circuits for enhanced privacy
          </p>
        </button>
      </div>

      {/* Advanced Settings */}
      <Card title="Advanced Privacy Settings">
        <div className="space-y-4">
          <div className="flex items-center justify-between p-4 glass rounded-lg">
            <div>
              <div className="font-semibold">Circuit Rotation Interval</div>
              <div className="text-sm text-gray-400">Automatically rotate circuits every N minutes</div>
            </div>
            <select className="bg-dark-bg-lighter border border-gray-700 rounded-lg px-4 py-2">
              <option>5 minutes</option>
              <option>10 minutes</option>
              <option>15 minutes</option>
              <option>30 minutes</option>
            </select>
          </div>
          <div className="flex items-center justify-between p-4 glass rounded-lg">
            <div>
              <div className="font-semibold">Minimum Circuit Hops</div>
              <div className="text-sm text-gray-400">Minimum number of relay nodes per circuit</div>
            </div>
            <select className="bg-dark-bg-lighter border border-gray-700 rounded-lg px-4 py-2">
              <option>3 hops</option>
              <option>4 hops</option>
              <option>5 hops</option>
              <option>6 hops</option>
            </select>
          </div>
          <div className="flex items-center justify-between p-4 glass rounded-lg">
            <div>
              <div className="font-semibold">Guard Node Pinning</div>
              <div className="text-sm text-gray-400">Use same entry guard for consistency</div>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" className="sr-only peer" defaultChecked />
              <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-purple-400"></div>
            </label>
          </div>
        </div>
      </Card>
    </div>
  );
}