'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { SystemMetrics } from '@/components/SystemMetrics';
import { QuickActions } from '@/components/QuickActions';
import { FogMap } from '@/components/FogMap';

interface DashboardStats {
  betanet: {
    mixnodes: number;
    activeConnections: number;
    packetsProcessed: number;
    status: 'online' | 'offline' | 'degraded';
  };
  bitchat: {
    activePeers: number;
    messagesDelivered: number;
    encryptionStatus: boolean;
    meshHealth: 'good' | 'fair' | 'poor';
  };
  benchmarks: {
    avgLatency: number;
    throughput: number;
    cpuUsage: number;
    memoryUsage: number;
  };
}

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await fetch('/api/dashboard/stats');
        const data = await response.json();
        setStats(data);
      } catch (error) {
        console.error('Failed to fetch dashboard stats:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
    const interval = setInterval(fetchStats, 5000); // Update every 5 seconds

    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]" data-testid="loading">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-fog-cyan mx-auto mb-4"></div>
          <p className="text-gray-400">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="glass rounded-xl p-6">
        <h1 className="text-3xl font-bold bg-gradient-to-r from-fog-cyan to-fog-purple bg-clip-text text-transparent">
          Fog Compute Dashboard
        </h1>
        <p className="text-gray-400 mt-2">
          Unified monitoring and control for privacy networking, P2P messaging, and performance benchmarks
        </p>
      </div>

      {/* System Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Betanet Status */}
        <Link href="/betanet">
          <div className="glass glass-hover rounded-xl p-6 cursor-pointer transition-all duration-300 hover:scale-105">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xl font-semibold text-fog-cyan">Betanet Privacy Network</h3>
              <div className={`w-3 h-3 rounded-full status-${stats?.betanet.status === 'online' ? 'online' : stats?.betanet.status === 'degraded' ? 'warning' : 'offline'}`} />
            </div>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-400">Active Mixnodes</span>
                <span className="font-semibold">{stats?.betanet.mixnodes || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Connections</span>
                <span className="font-semibold">{stats?.betanet.activeConnections || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Packets Processed</span>
                <span className="font-semibold">{stats?.betanet.packetsProcessed?.toLocaleString() || 0}</span>
              </div>
            </div>
          </div>
        </Link>

        {/* BitChat Status */}
        <Link href="/bitchat">
          <div className="glass glass-hover rounded-xl p-6 cursor-pointer transition-all duration-300 hover:scale-105">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xl font-semibold text-fog-purple">BitChat Mesh Network</h3>
              <div className={`w-3 h-3 rounded-full status-${stats?.bitchat.encryptionStatus ? 'online' : 'offline'}`} />
            </div>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-400">Active Peers</span>
                <span className="font-semibold">{stats?.bitchat.activePeers || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Messages Delivered</span>
                <span className="font-semibold">{stats?.bitchat.messagesDelivered?.toLocaleString() || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Mesh Health</span>
                <span className={`font-semibold ${
                  stats?.bitchat.meshHealth === 'good' ? 'text-green-400' :
                  stats?.bitchat.meshHealth === 'fair' ? 'text-yellow-400' :
                  'text-red-400'
                }`}>
                  {stats?.bitchat.meshHealth?.toUpperCase() || 'UNKNOWN'}
                </span>
              </div>
            </div>
          </div>
        </Link>

        {/* Benchmarks Status */}
        <Link href="/benchmarks">
          <div className="glass glass-hover rounded-xl p-6 cursor-pointer transition-all duration-300 hover:scale-105">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xl font-semibold text-green-400">Performance Benchmarks</h3>
              <div className={`w-3 h-3 rounded-full status-${(stats?.benchmarks.cpuUsage || 0) < 80 ? 'online' : 'warning'}`} />
            </div>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-400">Avg Latency</span>
                <span className="font-semibold">{stats?.benchmarks.avgLatency?.toFixed(2) || 0}ms</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Throughput</span>
                <span className="font-semibold" data-testid="throughput-value">{stats?.benchmarks.throughput?.toFixed(2) || 0} MB/s</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">CPU Usage</span>
                <span className="font-semibold">{stats?.benchmarks.cpuUsage?.toFixed(1) || 0}%</span>
              </div>
            </div>
          </div>
        </Link>
      </div>

      {/* Fog Map and Metrics */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <FogMap />
        </div>
        <div>
          <SystemMetrics stats={stats} />
        </div>
      </div>

      {/* Quick Actions */}
      <QuickActions />
    </div>
  );
}