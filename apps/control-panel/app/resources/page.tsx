'use client';

import { useState } from 'react';

interface ResourceLimits {
  cpu: { limit: number; reserve: number };
  memory: { limit: number; reserve: number };
}

export default function ResourcesPage() {
  const [activeTab, setActiveTab] = useState<'overview' | 'limits' | 'auto-scaling'>('overview');
  const [limits, setLimits] = useState<ResourceLimits>({
    cpu: { limit: 80, reserve: 20 },
    memory: { limit: 8192, reserve: 2048 }
  });
  const [autoScalingEnabled, setAutoScalingEnabled] = useState(false);
  const [autoScalingConfig, setAutoScalingConfig] = useState({
    scaleUpThreshold: 80,
    scaleDownThreshold: 30,
    minInstances: 2,
    maxInstances: 10
  });

  const handleApplyLimits = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    setLimits({
      cpu: {
        limit: parseInt(formData.get('cpu-limit') as string),
        reserve: parseInt(formData.get('cpu-reserve') as string)
      },
      memory: {
        limit: parseInt(formData.get('memory-limit') as string),
        reserve: parseInt(formData.get('memory-reserve') as string)
      }
    });
    // Show success notification (stub)
    alert('Resource limits updated successfully!');
  };

  const handleSaveAutoScaling = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);

  useEffect(() => {
    document.title = 'Resources | Fog Compute';
  }, []);
    setAutoScalingConfig({
      scaleUpThreshold: parseInt(formData.get('scale-up-threshold') as string),
      scaleDownThreshold: parseInt(formData.get('scale-down-threshold') as string),
      minInstances: parseInt(formData.get('min-instances') as string),
      maxInstances: parseInt(formData.get('max-instances') as string)
    });
    alert('Auto-scaling configuration saved!');
  };

  return (
    <div className="space-y-6" data-testid="resource-dashboard">
      {/* Header */}
      <div className="glass rounded-xl p-6">
        <h1 className="text-3xl font-bold bg-gradient-to-r from-fog-cyan to-fog-purple bg-clip-text text-transparent">
          Resource Management
        </h1>
        <p className="text-gray-400 mt-2">
          Monitor and optimize resource allocation across your fog network
        </p>
      </div>

      {/* Tab Navigation */}
      <div className="glass rounded-xl p-2">
        <div className="flex space-x-2">
          <button
            onClick={() => setActiveTab('overview')}
            className={`flex-1 px-4 py-2 rounded-lg transition-colors ${
              activeTab === 'overview' ? 'bg-fog-cyan text-white' : 'hover:bg-white/5'
            }`}
          >
            Overview
          </button>
          <button
            data-testid="resource-limits-tab"
            onClick={() => setActiveTab('limits')}
            className={`flex-1 px-4 py-2 rounded-lg transition-colors ${
              activeTab === 'limits' ? 'bg-fog-cyan text-white' : 'hover:bg-white/5'
            }`}
          >
            Resource Limits
          </button>
          <button
            data-testid="auto-scaling-tab"
            onClick={() => setActiveTab('auto-scaling')}
            className={`flex-1 px-4 py-2 rounded-lg transition-colors ${
              activeTab === 'auto-scaling' ? 'bg-fog-cyan text-white' : 'hover:bg-white/5'
            }`}
          >
            Auto-Scaling
          </button>
        </div>
      </div>

      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* Utilization Chart */}
          <div className="glass rounded-xl p-6" data-testid="utilization-chart">
            <h2 className="text-xl font-semibold mb-4">Resource Utilization</h2>
            <div className="h-64 bg-white/5 rounded-lg flex items-center justify-center text-gray-500">
              [Chart Placeholder - Resource Utilization Over Time]
            </div>
          </div>

          {/* Resource Breakdown */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="glass rounded-xl p-6" data-testid="cpu-allocation">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-lg font-semibold">CPU Allocation</h3>
                <span className="text-2xl">💻</span>
              </div>
              <div className="mt-4">
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-gray-400">Used</span>
                  <span className="font-semibold">65%</span>
                </div>
                <div className="w-full bg-white/10 rounded-full h-2">
                  <div className="bg-fog-cyan h-2 rounded-full" style={{ width: '65%' }}></div>
                </div>
              </div>
            </div>

            <div className="glass rounded-xl p-6" data-testid="memory-allocation">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-lg font-semibold">Memory Allocation</h3>
                <span className="text-2xl">🧠</span>
              </div>
              <div className="mt-4">
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-gray-400">Used</span>
                  <span className="font-semibold">72%</span>
                </div>
                <div className="w-full bg-white/10 rounded-full h-2">
                  <div className="bg-fog-purple h-2 rounded-full" style={{ width: '72%' }}></div>
                </div>
              </div>
            </div>

            <div className="glass rounded-xl p-6" data-testid="storage-allocation">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-lg font-semibold">Storage Allocation</h3>
                <span className="text-2xl">💾</span>
              </div>
              <div className="mt-4">
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-gray-400">Used</span>
                  <span className="font-semibold">48%</span>
                </div>
                <div className="w-full bg-white/10 rounded-full h-2">
                  <div className="bg-green-400 h-2 rounded-full" style={{ width: '48%' }}></div>
                </div>
              </div>
            </div>

            <div className="glass rounded-xl p-6" data-testid="network-allocation">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-lg font-semibold">Network Allocation</h3>
                <span className="text-2xl">🌐</span>
              </div>
              <div className="mt-4">
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-gray-400">Used</span>
                  <span className="font-semibold">54%</span>
                </div>
                <div className="w-full bg-white/10 rounded-full h-2">
                  <div className="bg-yellow-400 h-2 rounded-full" style={{ width: '54%' }}></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Resource Limits Tab */}
      {activeTab === 'limits' && (
        <div className="glass rounded-xl p-6">
          <h2 className="text-2xl font-semibold mb-6">Configure Resource Limits</h2>
          <form onSubmit={handleApplyLimits} className="space-y-6">
            {/* CPU Limits */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-fog-cyan">CPU Limits</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">
                    CPU Limit (%)
                  </label>
                  <input
                    name="cpu-limit"
                    data-testid="cpu-limit-input"
                    type="number"
                    min="0"
                    max="100"
                    defaultValue={limits.cpu.limit}
                    className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-fog-cyan"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">
                    CPU Reserve (%)
                  </label>
                  <input
                    name="cpu-reserve"
                    data-testid="cpu-reserve-input"
                    type="number"
                    min="0"
                    max="100"
                    defaultValue={limits.cpu.reserve}
                    className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-fog-cyan"
                  />
                </div>
              </div>
            </div>

            {/* Memory Limits */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-fog-purple">Memory Limits</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">
                    Memory Limit (MB)
                  </label>
                  <input
                    name="memory-limit"
                    data-testid="memory-limit-input"
                    type="number"
                    min="0"
                    defaultValue={limits.memory.limit}
                    className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-fog-cyan"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">
                    Memory Reserve (MB)
                  </label>
                  <input
                    name="memory-reserve"
                    data-testid="memory-reserve-input"
                    type="number"
                    min="0"
                    defaultValue={limits.memory.reserve}
                    className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-fog-cyan"
                  />
                </div>
              </div>
            </div>

            <button
              type="submit"
              data-testid="apply-limits-button"
              className="w-full px-6 py-3 bg-fog-cyan text-white rounded-lg hover:bg-fog-cyan/80 transition-colors"
            >
              Apply Limits
            </button>
          </form>
        </div>
      )}

      {/* Auto-Scaling Tab */}
      {activeTab === 'auto-scaling' && (
        <div className="glass rounded-xl p-6">
          <h2 className="text-2xl font-semibold mb-6">Auto-Scaling Configuration</h2>
          <form onSubmit={handleSaveAutoScaling} className="space-y-6">
            <div className="flex items-center space-x-3">
              <input
                data-testid="enable-auto-scaling-checkbox"
                type="checkbox"
                checked={autoScalingEnabled}
                onChange={(e) => setAutoScalingEnabled(e.target.checked)}
                className="w-5 h-5"
              />
              <label className="text-lg font-medium">Enable Auto-Scaling</label>
            </div>

            {autoScalingEnabled && (
              <div className="space-y-4 pt-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">
                      Scale Up Threshold (%)
                    </label>
                    <input
                      name="scale-up-threshold"
                      data-testid="scale-up-threshold-input"
                      type="number"
                      min="0"
                      max="100"
                      defaultValue={autoScalingConfig.scaleUpThreshold}
                      className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-fog-cyan"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">
                      Scale Down Threshold (%)
                    </label>
                    <input
                      name="scale-down-threshold"
                      data-testid="scale-down-threshold-input"
                      type="number"
                      min="0"
                      max="100"
                      defaultValue={autoScalingConfig.scaleDownThreshold}
                      className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-fog-cyan"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">
                      Minimum Instances
                    </label>
                    <input
                      name="min-instances"
                      data-testid="min-instances-input"
                      type="number"
                      min="1"
                      defaultValue={autoScalingConfig.minInstances}
                      className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-fog-cyan"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">
                      Maximum Instances
                    </label>
                    <input
                      name="max-instances"
                      data-testid="max-instances-input"
                      type="number"
                      min="1"
                      defaultValue={autoScalingConfig.maxInstances}
                      className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-fog-cyan"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  data-testid="save-auto-scaling-button"
                  className="w-full px-6 py-3 bg-fog-cyan text-white rounded-lg hover:bg-fog-cyan/80 transition-colors"
                >
                  Save Auto-Scaling Configuration
                </button>

                <div className="mt-4 p-4 bg-green-500/10 border border-green-500/20 rounded-lg">
                  <div className="flex items-center space-x-2">
                    <span className="text-green-400" data-testid="auto-scaling-status">Enabled</span>
                  </div>
                </div>
              </div>
            )}

            {!autoScalingEnabled && (
              <div className="p-4 bg-gray-500/10 border border-gray-500/20 rounded-lg">
                <div className="flex items-center space-x-2">
                  <span className="text-gray-400" data-testid="auto-scaling-status">Disabled</span>
                </div>
              </div>
            )}
          </form>
        </div>
      )}
    </div>
  );
}
