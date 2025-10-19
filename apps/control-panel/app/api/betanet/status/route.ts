import { NextResponse } from 'next/server';

export async function GET() {
  // Mock betanet status data for E2E tests
  const mockData = {
    status: 'active',
    activeNodes: 24,
    totalConnections: 156,
    networkThroughput: 25234,
    p99Latency: 45,
    nodes: [
      {
        id: 'node-1',
        status: 'active',
        packetsProcessed: 125000,
        reputation: 98.5,
        connections: 12,
        uptime: 99.9,
        responseTime: 32
      },
      {
        id: 'node-2',
        status: 'active',
        packetsProcessed: 98000,
        reputation: 97.2,
        connections: 10,
        uptime: 99.7,
        responseTime: 28
      },
      {
        id: 'node-3',
        status: 'active',
        packetsProcessed: 142000,
        reputation: 99.1,
        connections: 14,
        uptime: 99.95,
        responseTime: 25
      }
    ],
    metrics: {
      throughputPps: 25234,
      latencyMs: {
        p50: 18,
        p95: 42,
        p99: 45
      },
      bandwidth: {
        in: 1250,
        out: 980
      },
      packetLoss: 0.02
    }
  };

  return NextResponse.json(mockData);
}
