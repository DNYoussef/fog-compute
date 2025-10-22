'use client';

import { useResourceMonitor } from '@/lib/websocket/hooks';
import { WebSocketClient } from '@/lib/websocket/client';

interface ResourceData {
  devices: number;
  avg_cpu_usage: number;
  avg_memory_usage: number;
  total_storage_used: number;
  devices_details: Array<{
    id: string;
    cpu: number;
    memory: number;
    storage: number;
    status: string;
  }>;
}

interface ResourceMonitorProps {
  client: WebSocketClient | null;
}

export function ResourceMonitor({ client }: ResourceMonitorProps) {
  const { data: resourceData, lastUpdate, isLoading } = useResourceMonitor(client);

  if (isLoading) {
    return (
      <div className="bg-white/5 rounded-lg p-6 border border-white/10">
        <h3 className="text-lg font-semibold text-white mb-4">Resource Monitor</h3>
        <div className="flex items-center justify-center h-48">
          <div className="animate-pulse text-gray-400">Loading resources...</div>
        </div>
      </div>
    );
  }

  const data = resourceData as ResourceData;

  const getUsageColor = (usage: number) => {
    if (usage >= 90) return 'text-red-400';
    if (usage >= 70) return 'text-yellow-400';
    return 'text-green-400';
  };

  const getUsageBarColor = (usage: number) => {
    if (usage >= 90) return 'from-red-500 to-red-600';
    if (usage >= 70) return 'from-yellow-500 to-yellow-600';
    return 'from-green-500 to-green-600';
  };

  const formatStorage = (bytes: number) => {
    const gb = bytes / (1024 * 1024 * 1024);
    return gb.toFixed(2) + ' GB';
  };

  return (
    <div className="bg-white/5 rounded-lg p-6 border border-white/10">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold text-white">Resource Monitor</h3>
        {lastUpdate && (
          <span className="text-xs text-gray-400">
            Updated {lastUpdate.toLocaleTimeString()}
          </span>
        )}
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="p-4 bg-white/5 rounded border border-white/10">
          <div className="text-sm text-gray-400 mb-1">Total Devices</div>
          <div className="text-3xl font-bold text-white">{data.devices}</div>
        </div>

        <div className="p-4 bg-white/5 rounded border border-white/10">
          <div className="text-sm text-gray-400 mb-1">Avg CPU</div>
          <div className={`text-3xl font-bold ${getUsageColor(data.avg_cpu_usage)}`}>
            {data.avg_cpu_usage.toFixed(1)}%
          </div>
        </div>

        <div className="p-4 bg-white/5 rounded border border-white/10">
          <div className="text-sm text-gray-400 mb-1">Avg Memory</div>
          <div className={`text-3xl font-bold ${getUsageColor(data.avg_memory_usage)}`}>
            {data.avg_memory_usage.toFixed(1)}%
          </div>
        </div>

        <div className="p-4 bg-white/5 rounded border border-white/10">
          <div className="text-sm text-gray-400 mb-1">Total Storage</div>
          <div className="text-3xl font-bold text-white">
            {formatStorage(data.total_storage_used)}
          </div>
        </div>
      </div>

      {/* Average Usage Bars */}
      <div className="space-y-4 mb-6">
        <div>
          <div className="flex items-center justify-between text-sm mb-2">
            <span className="text-gray-400">Average CPU Usage</span>
            <span className={`font-bold ${getUsageColor(data.avg_cpu_usage)}`}>
              {data.avg_cpu_usage.toFixed(1)}%
            </span>
          </div>
          <div className="w-full h-3 bg-white/10 rounded-full overflow-hidden">
            <div
              className={`h-full bg-gradient-to-r ${getUsageBarColor(data.avg_cpu_usage)} transition-all duration-500`}
              style={{ width: `${data.avg_cpu_usage}%` }}
            />
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between text-sm mb-2">
            <span className="text-gray-400">Average Memory Usage</span>
            <span className={`font-bold ${getUsageColor(data.avg_memory_usage)}`}>
              {data.avg_memory_usage.toFixed(1)}%
            </span>
          </div>
          <div className="w-full h-3 bg-white/10 rounded-full overflow-hidden">
            <div
              className={`h-full bg-gradient-to-r ${getUsageBarColor(data.avg_memory_usage)} transition-all duration-500`}
              style={{ width: `${data.avg_memory_usage}%` }}
            />
          </div>
        </div>
      </div>

      {/* Device Details */}
      <div>
        <h4 className="text-sm font-medium text-gray-400 uppercase tracking-wide mb-3">
          Device Details (Top 10)
        </h4>
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {data.devices_details.map((device) => (
            <div
              key={device.id}
              className="p-3 bg-white/5 rounded border border-white/10 hover:bg-white/10 transition-colors"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-mono text-gray-300">{device.id}</span>
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                  device.status === 'active' ? 'bg-green-500/20 text-green-400' :
                  device.status === 'idle' ? 'bg-yellow-500/20 text-yellow-400' :
                  'bg-gray-500/20 text-gray-400'
                }`}>
                  {device.status}
                </span>
              </div>

              <div className="grid grid-cols-3 gap-2 text-xs">
                <div>
                  <div className="text-gray-400 mb-1">CPU</div>
                  <div className={`font-bold ${getUsageColor(device.cpu)}`}>
                    {device.cpu.toFixed(1)}%
                  </div>
                </div>
                <div>
                  <div className="text-gray-400 mb-1">Memory</div>
                  <div className={`font-bold ${getUsageColor(device.memory)}`}>
                    {device.memory.toFixed(1)}%
                  </div>
                </div>
                <div>
                  <div className="text-gray-400 mb-1">Storage</div>
                  <div className="font-bold text-white">
                    {formatStorage(device.storage)}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
