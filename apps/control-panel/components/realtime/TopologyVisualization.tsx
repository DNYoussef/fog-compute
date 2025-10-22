'use client';

import { useTopology } from '@/lib/websocket/hooks';
import { WebSocketClient } from '@/lib/websocket/client';
import { useEffect, useState } from 'react';

interface TopologyData {
  active_nodes: number;
  connections: number;
  network_map: Record<string, any>;
}

interface TopologyVisualizationProps {
  client: WebSocketClient | null;
}

export function TopologyVisualization({ client }: TopologyVisualizationProps) {
  const { data: topologyData, lastUpdate, isLoading } = useTopology(client);
  const [changeIndicator, setChangeIndicator] = useState(false);

  useEffect(() => {
    if (lastUpdate) {
      setChangeIndicator(true);
      const timer = setTimeout(() => setChangeIndicator(false), 2000);
      return () => clearTimeout(timer);
    }
  }, [lastUpdate]);

  if (isLoading) {
    return (
      <div className="bg-white/5 rounded-lg p-6 border border-white/10">
        <h3 className="text-lg font-semibold text-white mb-4">Network Topology</h3>
        <div className="flex items-center justify-center h-48">
          <div className="animate-pulse text-gray-400">Loading topology...</div>
        </div>
      </div>
    );
  }

  const data = topologyData as TopologyData;

  return (
    <div className="bg-white/5 rounded-lg p-6 border border-white/10">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <h3 className="text-lg font-semibold text-white">Network Topology</h3>
          {changeIndicator && (
            <span className="px-2 py-1 bg-fog-cyan/20 text-fog-cyan text-xs rounded animate-pulse">
              Updated
            </span>
          )}
        </div>
        {lastUpdate && (
          <span className="text-xs text-gray-400">
            {lastUpdate.toLocaleTimeString()}
          </span>
        )}
      </div>

      {/* Stats Summary */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="p-4 bg-white/5 rounded border border-white/10 text-center">
          <div className="text-4xl font-bold text-fog-cyan mb-1">{data.active_nodes}</div>
          <div className="text-sm text-gray-400">Active Nodes</div>
        </div>

        <div className="p-4 bg-white/5 rounded border border-white/10 text-center">
          <div className="text-4xl font-bold text-fog-green mb-1">{data.connections}</div>
          <div className="text-sm text-gray-400">Connections</div>
        </div>
      </div>

      {/* Topology Visualization */}
      <div className="relative h-64 bg-white/5 rounded border border-white/10 p-4">
        <div className="absolute inset-0 flex items-center justify-center">
          {/* Central Hub */}
          <div className="relative">
            <div className="w-20 h-20 rounded-full bg-gradient-to-br from-fog-cyan to-fog-green flex items-center justify-center animate-pulse">
              <span className="text-2xl font-bold text-white">{data.active_nodes}</span>
            </div>

            {/* Connection Lines */}
            {Array.from({ length: Math.min(data.connections, 8) }).map((_, i) => {
              const angle = (360 / Math.min(data.connections, 8)) * i;
              const radians = (angle * Math.PI) / 180;
              const distance = 100;
              const x = Math.cos(radians) * distance;
              const y = Math.sin(radians) * distance;

              return (
                <div
                  key={i}
                  className="absolute top-1/2 left-1/2 origin-left"
                  style={{
                    transform: `translate(-50%, -50%) rotate(${angle}deg)`,
                    width: `${distance}px`,
                    height: '2px'
                  }}
                >
                  <div className="w-full h-full bg-gradient-to-r from-white/50 to-transparent animate-pulse" />

                  {/* Node */}
                  <div
                    className="absolute right-0 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-fog-cyan/50 border-2 border-fog-cyan flex items-center justify-center"
                    style={{
                      animation: `pulse ${2 + (i * 0.2)}s ease-in-out infinite`
                    }}
                  >
                    <div className="w-2 h-2 rounded-full bg-fog-cyan" />
                  </div>
                </div>
              );
            })}

            {data.connections > 8 && (
              <div className="absolute -bottom-8 left-1/2 -translate-x-1/2 text-xs text-gray-400 whitespace-nowrap">
                +{data.connections - 8} more connections
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Network Map Details */}
      {Object.keys(data.network_map).length > 0 && (
        <div className="mt-6">
          <h4 className="text-sm font-medium text-gray-400 uppercase tracking-wide mb-3">
            Network Map
          </h4>
          <div className="max-h-32 overflow-y-auto">
            <pre className="text-xs text-gray-400 font-mono bg-black/20 p-3 rounded">
              {JSON.stringify(data.network_map, null, 2)}
            </pre>
          </div>
        </div>
      )}

      {/* Connection Quality */}
      <div className="mt-4 p-3 bg-white/5 rounded">
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-400">Connection Density</span>
          <span className="font-bold text-white">
            {data.active_nodes > 0
              ? (data.connections / data.active_nodes).toFixed(2)
              : '0.00'} connections/node
          </span>
        </div>
      </div>
    </div>
  );
}
