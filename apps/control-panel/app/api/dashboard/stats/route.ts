import { NextResponse } from 'next/server';

export async function GET() {
  // Mock data - in production, this would fetch from actual services
  const stats = {
    betanet: {
      mixnodes: Math.floor(Math.random() * 20) + 10,
      activeConnections: Math.floor(Math.random() * 100) + 50,
      packetsProcessed: Math.floor(Math.random() * 1000000) + 500000,
      status: Math.random() > 0.1 ? 'online' : 'degraded' as 'online' | 'offline' | 'degraded',
    },
    bitchat: {
      activePeers: Math.floor(Math.random() * 15) + 5,
      messagesDelivered: Math.floor(Math.random() * 10000) + 5000,
      encryptionStatus: true,
      meshHealth: ['good', 'fair', 'poor'][Math.floor(Math.random() * 3)] as 'good' | 'fair' | 'poor',
    },
    benchmarks: {
      avgLatency: Math.random() * 50 + 10,
      throughput: Math.random() * 100 + 50,
      cpuUsage: Math.random() * 60 + 20,
      memoryUsage: Math.random() * 50 + 30,
      networkUtilization: Math.random() * 70 + 20,
    },
  };

  return NextResponse.json(stats);
}