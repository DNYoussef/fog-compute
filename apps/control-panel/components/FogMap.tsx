'use client';

import { useEffect, useState } from 'react';

interface FogNode {
  id: string;
  lat: number;
  lng: number;
  type: 'betanet' | 'bitchat' | 'benchmark';
  status: 'online' | 'offline';
}

/**
 * SIN-027: FogMap fetches from topology API instead of hardcoded nodes.
 * Falls back to empty state with stale-data indicator when backend is unavailable.
 */
export function FogMap() {
  const [nodes, setNodes] = useState<FogNode[]>([]);
  const [dataSource, setDataSource] = useState<'live' | 'unavailable'>('unavailable');
  const [lastFetched, setLastFetched] = useState<Date | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchTopology() {
      try {
        const res = await fetch('/api/fog/topology', { signal: AbortSignal.timeout(5000) });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (cancelled) return;

        // Map topology response to FogNode[] if devices are returned
        if (data.devices && Array.isArray(data.devices)) {
          setNodes(
            data.devices.map((d: any) => ({
              id: d.id || d.device_id,
              lat: d.lat ?? 0,
              lng: d.lng ?? 0,
              type: d.type ?? 'betanet',
              status: d.status === 'offline' ? 'offline' : 'online',
            }))
          );
        } else {
          // Topology API returned aggregate stats but no per-device list - show empty
          setNodes([]);
        }
        setDataSource('live');
        setLastFetched(new Date());
      } catch {
        if (cancelled) return;
        // SIN-027: No hardcoded fallback - show empty state
        setNodes([]);
        setDataSource('unavailable');
      }
    }

    fetchTopology();
    // Refresh every 30 seconds
    const interval = setInterval(fetchTopology, 30_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const getNodeColor = (node: FogNode) => {
    if (node.status === 'offline') return '#ef4444';
    if (node.type === 'betanet') return '#06b6d4';
    if (node.type === 'bitchat') return '#7c3aed';
    return '#10b981';
  };

  return (
    <div className="glass rounded-xl p-6 h-full" data-testid="fog-map">
      <h2 className="text-xl font-semibold mb-4">Global Fog Node Distribution</h2>

      {/* SIN-027: Data source indicator */}
      {dataSource === 'unavailable' && (
        <div className="mb-3 px-3 py-1.5 bg-yellow-900/40 border border-yellow-600/50 rounded text-yellow-300 text-xs">
          Topology API unavailable - no node data to display
        </div>
      )}
      {dataSource === 'live' && nodes.length === 0 && (
        <div className="mb-3 px-3 py-1.5 bg-blue-900/40 border border-blue-600/50 rounded text-blue-300 text-xs">
          Connected to topology API - no nodes registered yet
        </div>
      )}

      <div className="relative h-[400px] bg-gradient-to-br from-fog-dark to-black rounded-lg overflow-hidden">
        {/* Simplified world map visualization */}
        <svg className="w-full h-full" viewBox="0 0 800 400">
          {/* Grid lines */}
          {[...Array(9)].map((_, i) => (
            <line
              key={`h-${i}`}
              x1="0"
              y1={i * 50}
              x2="800"
              y2={i * 50}
              stroke="rgba(255,255,255,0.05)"
              strokeWidth="1"
            />
          ))}
          {[...Array(17)].map((_, i) => (
            <line
              key={`v-${i}`}
              x1={i * 50}
              y1="0"
              x2={i * 50}
              y2="400"
              stroke="rgba(255,255,255,0.05)"
              strokeWidth="1"
            />
          ))}

          {/* Nodes */}
          {nodes.map((node) => {
            const x = ((node.lng + 180) / 360) * 800;
            const y = ((90 - node.lat) / 180) * 400;

            return (
              <g key={node.id}>
                <circle
                  cx={x}
                  cy={y}
                  r="8"
                  fill={getNodeColor(node)}
                  opacity="0.3"
                >
                  <animate
                    attributeName="r"
                    from="8"
                    to="16"
                    dur="2s"
                    repeatCount="indefinite"
                  />
                  <animate
                    attributeName="opacity"
                    from="0.3"
                    to="0"
                    dur="2s"
                    repeatCount="indefinite"
                  />
                </circle>
                <circle
                  cx={x}
                  cy={y}
                  r="6"
                  fill={getNodeColor(node)}
                />
              </g>
            );
          })}
        </svg>
      </div>


      {/* Zoom Controls */}
      <div className="absolute top-4 right-4 flex flex-col gap-2">
        <button
          aria-label="Zoom in"
          className="w-8 h-8 bg-white/10 rounded hover:bg-white/20 flex items-center justify-center"
        >
          +
        </button>
        <button
          aria-label="Zoom out"
          className="w-8 h-8 bg-white/10 rounded hover:bg-white/20 flex items-center justify-center"
        >
          −
        </button>
      </div>

      {/* Legend */}
      <div className="mt-4 flex flex-wrap gap-4 text-sm">
        <div className="flex items-center space-x-2">
          <div className="w-3 h-3 rounded-full bg-fog-cyan"></div>
          <span className="text-gray-400">Betanet Nodes</span>
        </div>
        <div className="flex items-center space-x-2">
          <div className="w-3 h-3 rounded-full bg-fog-purple"></div>
          <span className="text-gray-400">BitChat Nodes</span>
        </div>
        <div className="flex items-center space-x-2">
          <div className="w-3 h-3 rounded-full bg-green-400"></div>
          <span className="text-gray-400">Benchmark Nodes</span>
        </div>
        <div className="flex items-center space-x-2">
          <div className="w-3 h-3 rounded-full bg-red-400"></div>
          <span className="text-gray-400">Offline</span>
        </div>
      </div>
    </div>
  );
}