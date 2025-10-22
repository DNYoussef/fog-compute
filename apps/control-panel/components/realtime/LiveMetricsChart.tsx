'use client';

import { useEffect, useState } from 'react';
import { WebSocketClient } from '@/lib/websocket/client';
import { useRealtimeMetrics } from '@/lib/websocket/hooks';

interface MetricsData {
  composite_health: string;
  services: Record<string, any>;
  timestamp: string;
}

interface LiveMetricsChartProps {
  client: WebSocketClient | null;
}

export function LiveMetricsChart({ client }: LiveMetricsChartProps) {
  const { data: metrics, lastUpdate } = useRealtimeMetrics(client);
  const [history, setHistory] = useState<MetricsData[]>([]);

  useEffect(() => {
    if (metrics) {
      setHistory(prev => [...prev.slice(-59), metrics as MetricsData]); // Keep last 60 data points
    }
  }, [metrics]);

  const getHealthColor = (health: string) => {
    switch (health) {
      case 'healthy':
        return 'bg-green-500';
      case 'degraded':
        return 'bg-yellow-500';
      case 'critical':
        return 'bg-red-500';
      default:
        return 'bg-gray-500';
    }
  };

  const getHealthText = (health: string) => {
    return health.charAt(0).toUpperCase() + health.slice(1);
  };

  if (!metrics) {
    return (
      <div className="bg-white/5 rounded-lg p-6 border border-white/10">
        <h3 className="text-lg font-semibold text-white mb-4">Live Metrics</h3>
        <div className="flex items-center justify-center h-48">
          <div className="animate-pulse text-gray-400">Waiting for metrics...</div>
        </div>
      </div>
    );
  }

  const metricsData = metrics as MetricsData;
  const healthColor = getHealthColor(metricsData.composite_health);

  return (
    <div className="bg-white/5 rounded-lg p-6 border border-white/10">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">Live Metrics</h3>
        {lastUpdate && (
          <span className="text-xs text-gray-400">
            Updated {lastUpdate.toLocaleTimeString()}
          </span>
        )}
      </div>

      {/* System Health */}
      <div className="mb-6">
        <div className="flex items-center gap-3">
          <div className={`w-3 h-3 rounded-full ${healthColor} animate-pulse`} />
          <span className="text-white font-medium">
            System Health: {getHealthText(metricsData.composite_health)}
          </span>
        </div>
      </div>

      {/* Service Status */}
      <div className="space-y-3">
        <h4 className="text-sm font-medium text-gray-400 uppercase tracking-wide">Services</h4>
        {Object.entries(metricsData.services).map(([service, status]) => (
          <div key={service} className="flex items-center justify-between p-3 bg-white/5 rounded border border-white/5">
            <span className="text-gray-300 capitalize">{service}</span>
            <div className="flex items-center gap-2">
              <div
                className={`w-2 h-2 rounded-full ${
                  status === 'healthy' ? 'bg-green-500' :
                  status === 'degraded' ? 'bg-yellow-500' :
                  'bg-red-500'
                }`}
              />
              <span className="text-sm text-gray-400 capitalize">{String(status)}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Mini Chart */}
      <div className="mt-6">
        <h4 className="text-sm font-medium text-gray-400 uppercase tracking-wide mb-3">
          Health History (Last {history.length} updates)
        </h4>
        <div className="flex items-end gap-1 h-20">
          {history.map((item, index) => {
            const height = item.composite_health === 'healthy' ? 100 :
                          item.composite_health === 'degraded' ? 66 : 33;
            const color = getHealthColor(item.composite_health);

            return (
              <div
                key={index}
                className={`flex-1 ${color} rounded-t transition-all duration-300`}
                style={{ height: `${height}%` }}
                title={`${new Date(item.timestamp).toLocaleTimeString()}: ${item.composite_health}`}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}
