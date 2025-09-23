'use client';

import { useEffect, useState } from 'react';

interface MixnodeInfo {
  id: string;
  packetsProcessed: number;
  status: 'active' | 'inactive' | 'degraded';
}

interface PacketFlow {
  from: string;
  to: string;
  packets: number;
  timestamp: number;
}

export function PacketFlowMonitor({ mixnodes }: { mixnodes: MixnodeInfo[] }) {
  const [flows, setFlows] = useState<PacketFlow[]>([]);

  useEffect(() => {
    const interval = setInterval(() => {
      if (mixnodes.length < 2) return;

      const activeNodes = mixnodes.filter(n => n.status === 'active');
      if (activeNodes.length < 2) return;

      const from = activeNodes[Math.floor(Math.random() * activeNodes.length)];
      const to = activeNodes[Math.floor(Math.random() * activeNodes.length)];

      if (from.id !== to.id) {
        setFlows(prev => [
          ...prev.slice(-9),
          {
            from: from.id.substring(0, 8),
            to: to.id.substring(0, 8),
            packets: Math.floor(Math.random() * 100) + 10,
            timestamp: Date.now(),
          }
        ]);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [mixnodes]);

  return (
    <div className="h-[300px] overflow-y-auto space-y-2">
      {flows.length === 0 ? (
        <div className="text-center text-gray-400 py-8">
          Waiting for packet flows...
        </div>
      ) : (
        flows.slice().reverse().map((flow, index) => (
          <div
            key={`${flow.timestamp}-${index}`}
            className="glass-dark rounded-lg p-3 animate-fade-in"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                <span className="text-sm font-mono">{flow.from}</span>
                <span className="text-gray-400">→</span>
                <span className="text-sm font-mono">{flow.to}</span>
              </div>
              <div className="text-sm text-gray-400">
                {flow.packets} packets
              </div>
            </div>
            <div className="text-xs text-gray-500 mt-1">
              {new Date(flow.timestamp).toLocaleTimeString()}
            </div>
          </div>
        ))
      )}
    </div>
  );
}