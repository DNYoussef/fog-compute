'use client';

import { useEffect, useState } from 'react';

interface FogNode {
  id: string;
  lat: number;
  lng: number;
  type: 'betanet' | 'bitchat' | 'benchmark';
  status: 'online' | 'offline';
}

export function FogMap() {
  const [nodes, setNodes] = useState<FogNode[]>([]);

  useEffect(() => {
    // Simulate fog nodes distribution
    const mockNodes: FogNode[] = [
      { id: '1', lat: 40.7128, lng: -74.0060, type: 'betanet', status: 'online' },
      { id: '2', lat: 51.5074, lng: -0.1278, type: 'bitchat', status: 'online' },
      { id: '3', lat: 35.6762, lng: 139.6503, type: 'benchmark', status: 'online' },
      { id: '4', lat: -33.8688, lng: 151.2093, type: 'betanet', status: 'online' },
      { id: '5', lat: 37.7749, lng: -122.4194, type: 'bitchat', status: 'offline' },
    ];
    setNodes(mockNodes);
  }, []);

  const getNodeColor = (node: FogNode) => {
    if (node.status === 'offline') return '#ef4444';
    if (node.type === 'betanet') return '#06b6d4';
    if (node.type === 'bitchat') return '#7c3aed';
    return '#10b981';
  };

  return (
    <div className="glass rounded-xl p-6 h-full">
      <h2 className="text-xl font-semibold mb-4">Global Fog Node Distribution</h2>

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