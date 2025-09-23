import { NextResponse } from 'next/server';

export async function GET() {
  // Mock mixnode data
  const mixnodeCount = 15;
  const mixnodes = Array.from({ length: mixnodeCount }, (_, i) => ({
    id: `mixnode-${i + 1}-${Math.random().toString(36).substr(2, 9)}`,
    address: `192.168.1.${100 + i}`,
    status: ['active', 'active', 'active', 'degraded', 'inactive'][Math.floor(Math.random() * 5)] as 'active' | 'inactive' | 'degraded',
    packetsProcessed: Math.floor(Math.random() * 100000) + 10000,
    uptime: Math.floor(Math.random() * 86400) + 3600,
    latency: Math.random() * 100 + 10,
    reputation: Math.random() * 0.3 + 0.7,
    position: {
      x: (Math.random() - 0.5) * 10,
      y: (Math.random() - 0.5) * 10,
      z: (Math.random() - 0.5) * 10,
    },
  }));

  const activeNodes = mixnodes.filter(n => n.status === 'active').length;
  const health = Math.round((activeNodes / mixnodeCount) * 100);

  return NextResponse.json({
    mixnodes,
    health,
    totalNodes: mixnodeCount,
    activeNodes,
  });
}