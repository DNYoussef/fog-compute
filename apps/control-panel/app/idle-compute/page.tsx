'use client';

import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/Card';
import { DeviceList } from '@/components/DeviceList';

interface HarvestStats {
  devices: {
    total: number;
    active: number;
    charging: number;
    thermal_throttle: number;
  };
  compute: {
    totalCPU: number;
    totalGPU: number;
    totalMemory: number;
    utilizationRate: number;
  };
  harvest: {
    tasksCompleted: number;
    computeHoursCollected: number;
    energyEfficiency: number;
  };
  mobile: {
    android: number;
    ios: number;
    batteryHealthAvg: number;
  };
}

export default function IdleComputePage() {
  const [stats, setStats] = useState<HarvestStats | null>(null);
  const [harvestMode, setHarvestMode] = useState<'conservative' | 'balanced' | 'aggressive'>('balanced');

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await fetch('/api/idle-compute/stats');
        const data = await response.json();
        setStats(data);
      } catch (error) {
        console.error('Failed to fetch harvest stats:', error);
      }
    };

    fetchStats();
    const interval = setInterval(fetchStats, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="glass rounded-xl p-6">
        <h1 className="text-3xl font-bold bg-gradient-to-r from-green-400 to-fog-cyan bg-clip-text text-transparent">
          Idle Compute Harvesting
        </h1>
        <p className="text-gray-400 mt-2">
          Collect spare compute from mobile devices during charging with battery-safe optimization
        </p>
      </div>

      {/* Harvest Mode Selector */}
      <div className="glass rounded-xl p-6">
        <h3 className="text-xl font-semibold mb-4">Harvest Mode</h3>
        <div className="flex gap-4">
          {[
            { mode: 'conservative', desc: 'Minimal impact, 5% battery drain max' },
            { mode: 'balanced', desc: 'Optimized performance, 10% battery drain max' },
            { mode: 'aggressive', desc: 'Maximum compute, 15% battery drain max' },
          ].map(({ mode, desc }) => (
            <button
              key={mode}
              onClick={() => setHarvestMode(mode as any)}
              className={`flex-1 p-4 rounded-lg transition-all ${
                harvestMode === mode
                  ? 'bg-gradient-to-r from-green-400 to-fog-cyan text-dark-bg'
                  : 'glass hover:border-green-400'
              }`}
            >
              <div className="font-semibold capitalize">{mode}</div>
              <div className="text-sm mt-1 opacity-80">{desc}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Device Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <Card title="Total Devices" className="border-l-4 border-green-400">
          <div className="text-4xl font-bold text-green-400">
            {stats?.devices.total || 0}
          </div>
          <div className="text-gray-400 mt-2">Registered Edge Devices</div>
        </Card>

        <Card title="Active Harvest" className="border-l-4 border-fog-cyan">
          <div className="text-4xl font-bold text-fog-cyan">
            {stats?.devices.active || 0}
          </div>
          <div className="text-gray-400 mt-2">Currently Harvesting</div>
        </Card>

        <Card title="Charging" className="border-l-4 border-yellow-400">
          <div className="text-4xl font-bold text-yellow-400">
            {stats?.devices.charging || 0}
          </div>
          <div className="text-gray-400 mt-2">Devices Charging</div>
        </Card>

        <Card title="Thermal Throttle" className="border-l-4 border-red-400">
          <div className="text-4xl font-bold text-red-400">
            {stats?.devices.thermal_throttle || 0}
          </div>
          <div className="text-gray-400 mt-2">Heat Limited</div>
        </Card>
      </div>

      {/* Compute Resources */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card title="Total CPU Power">
          <div className="text-3xl font-bold text-fog-cyan">
            {stats?.compute.totalCPU?.toFixed(1) || 0} GHz
          </div>
          <div className="mt-4 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-gray-400">Utilization</span>
              <span>{stats?.compute.utilizationRate || 0}%</span>
            </div>
            <div className="w-full bg-dark-bg-lighter rounded-full h-2">
              <div
                className="bg-fog-cyan h-2 rounded-full transition-all"
                style={{ width: `${stats?.compute.utilizationRate || 0}%` }}
              />
            </div>
          </div>
        </Card>

        <Card title="Total GPU Power">
          <div className="text-3xl font-bold text-fog-purple">
            {stats?.compute.totalGPU?.toFixed(1) || 0} TFLOPS
          </div>
          <div className="mt-4 text-sm text-gray-400">
            Available for AI/ML workloads
          </div>
        </Card>

        <Card title="Total Memory">
          <div className="text-3xl font-bold text-green-400">
            {stats?.compute.totalMemory?.toFixed(1) || 0} GB
          </div>
          <div className="mt-4 text-sm text-gray-400">
            Distributed across devices
          </div>
        </Card>
      </div>

      {/* Harvest Performance */}
      <Card title="Harvest Performance">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="text-center p-4 glass rounded-lg">
            <div className="text-3xl font-bold text-green-400">
              {stats?.harvest.tasksCompleted?.toLocaleString() || 0}
            </div>
            <div className="text-gray-400 mt-2">Tasks Completed</div>
          </div>
          <div className="text-center p-4 glass rounded-lg">
            <div className="text-3xl font-bold text-fog-cyan">
              {stats?.harvest.computeHoursCollected?.toFixed(1) || 0}
            </div>
            <div className="text-gray-400 mt-2">Compute Hours</div>
          </div>
          <div className="text-center p-4 glass rounded-lg">
            <div className="text-3xl font-bold text-fog-purple">
              {stats?.harvest.energyEfficiency?.toFixed(1) || 0}%
            </div>
            <div className="text-gray-400 mt-2">Energy Efficiency</div>
          </div>
        </div>
      </Card>

      {/* Mobile Platform Distribution */}
      <Card title="Mobile Platform Distribution">
        <div className="grid grid-cols-2 gap-4">
          <div className="text-center p-6 glass rounded-lg">
            <div className="text-4xl font-bold text-green-400">
              {stats?.mobile.android || 0}
            </div>
            <div className="text-gray-400 mt-2">Android Devices</div>
          </div>
          <div className="text-center p-6 glass rounded-lg">
            <div className="text-4xl font-bold text-fog-cyan">
              {stats?.mobile.ios || 0}
            </div>
            <div className="text-gray-400 mt-2">iOS Devices</div>
          </div>
        </div>
        <div className="mt-4 p-4 bg-dark-bg-lighter rounded-lg">
          <div className="flex justify-between items-center">
            <span className="text-gray-400">Average Battery Health</span>
            <span className="text-2xl font-bold text-green-400">
              {stats?.mobile.batteryHealthAvg?.toFixed(1) || 0}%
            </span>
          </div>
        </div>
      </Card>

      {/* Device List */}
      <DeviceList />

      {/* Safety Controls */}
      <Card title="Safety & Thermal Controls">
        <div className="space-y-4">
          <div className="flex items-center justify-between p-4 glass rounded-lg">
            <div>
              <div className="font-semibold">Battery Temperature Limit</div>
              <div className="text-sm text-gray-400">Stop harvest if device exceeds 40°C</div>
            </div>
            <input
              type="range"
              min="35"
              max="45"
              defaultValue="40"
              className="w-32"
            />
          </div>
          <div className="flex items-center justify-between p-4 glass rounded-lg">
            <div>
              <div className="font-semibold">Minimum Battery Level</div>
              <div className="text-sm text-gray-400">Only harvest when battery above 20%</div>
            </div>
            <input
              type="range"
              min="10"
              max="50"
              defaultValue="20"
              className="w-32"
            />
          </div>
          <div className="flex items-center justify-between p-4 glass rounded-lg">
            <div>
              <div className="font-semibold">Charging Only Mode</div>
              <div className="text-sm text-gray-400">Only harvest from devices while charging</div>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" className="sr-only peer" defaultChecked />
              <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-400"></div>
            </label>
          </div>
        </div>
      </Card>
    </div>
  );
}