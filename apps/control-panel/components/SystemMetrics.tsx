'use client';

interface SystemMetricsProps {
  stats: any;
}

export function SystemMetrics({ stats }: SystemMetricsProps) {
  return (
    <div className="glass rounded-xl p-6 h-full" data-testid="system-metrics">
      <h2 className="text-xl font-semibold mb-4">System Metrics</h2>

      <div className="space-y-4">
        <div>
          <div className="flex justify-between text-sm mb-2">
            <span className="text-gray-400">Overall Health</span>
            <span className="font-semibold">
              {stats ? Math.round((
                (stats.betanet.status === 'online' ? 100 : 0) +
                (stats.bitchat.meshHealth === 'good' ? 100 : stats.bitchat.meshHealth === 'fair' ? 60 : 20) +
                (stats.benchmarks.cpuUsage < 80 ? 100 : 50)
              ) / 3) : 0}%
            </span>
          </div>
          <div className="w-full bg-white/10 rounded-full h-2">
            <div
              className="bg-gradient-to-r from-green-400 to-fog-cyan h-2 rounded-full transition-all duration-500"
              style={{
                width: `${stats ? Math.round((
                  (stats.betanet.status === 'online' ? 100 : 0) +
                  (stats.bitchat.meshHealth === 'good' ? 100 : stats.bitchat.meshHealth === 'fair' ? 60 : 20) +
                  (stats.benchmarks.cpuUsage < 80 ? 100 : 50)
                ) / 3) : 0}%`
              }}
            />
          </div>
        </div>

        <div>
          <div className="flex justify-between text-sm mb-2">
            <span className="text-gray-400">Network Utilization</span>
            <span className="font-semibold">{stats?.benchmarks.networkUtilization?.toFixed(1) || 0}%</span>
          </div>
          <div className="w-full bg-white/10 rounded-full h-2">
            <div
              className="bg-fog-purple h-2 rounded-full transition-all duration-500"
              style={{ width: `${stats?.benchmarks.networkUtilization || 0}%` }}
            />
          </div>
        </div>

        <div>
          <div className="flex justify-between text-sm mb-2">
            <span className="text-gray-400">CPU Usage</span>
            <span className="font-semibold">{stats?.benchmarks.cpuUsage?.toFixed(1) || 0}%</span>
          </div>
          <div className="w-full bg-white/10 rounded-full h-2">
            <div
              className={`h-2 rounded-full transition-all duration-500 ${
                (stats?.benchmarks.cpuUsage || 0) > 80 ? 'bg-red-400' :
                (stats?.benchmarks.cpuUsage || 0) > 60 ? 'bg-yellow-400' : 'bg-green-400'
              }`}
              style={{ width: `${stats?.benchmarks.cpuUsage || 0}%` }}
            />
          </div>
        </div>

        <div>
          <div className="flex justify-between text-sm mb-2">
            <span className="text-gray-400">Memory Usage</span>
            <span className="font-semibold">{stats?.benchmarks.memoryUsage?.toFixed(1) || 0}%</span>
          </div>
          <div className="w-full bg-white/10 rounded-full h-2">
            <div
              className={`h-2 rounded-full transition-all duration-500 ${
                (stats?.benchmarks.memoryUsage || 0) > 80 ? 'bg-red-400' :
                (stats?.benchmarks.memoryUsage || 0) > 60 ? 'bg-yellow-400' : 'bg-green-400'
              }`}
              style={{ width: `${stats?.benchmarks.memoryUsage || 0}%` }}
            />
          </div>
        </div>

        <div className="pt-4 border-t border-white/10">
          <h3 className="text-sm font-semibold mb-3">Active Services</h3>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <div className={`w-2 h-2 rounded-full status-${stats?.betanet.status === 'online' ? 'online' : 'offline'}`} />
                <span className="text-sm text-gray-400">Betanet</span>
              </div>
              <span className="text-xs text-gray-500">{stats?.betanet.mixnodes || 0} nodes</span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <div className={`w-2 h-2 rounded-full status-${stats?.bitchat.encryptionStatus ? 'online' : 'offline'}`} />
                <span className="text-sm text-gray-400">BitChat</span>
              </div>
              <span className="text-xs text-gray-500">{stats?.bitchat.activePeers || 0} peers</span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <div className={`w-2 h-2 rounded-full status-${(stats?.benchmarks.cpuUsage || 0) < 80 ? 'online' : 'warning'}`} />
                <span className="text-sm text-gray-400">Benchmarks</span>
              </div>
              <span className="text-xs text-gray-500">Active</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}