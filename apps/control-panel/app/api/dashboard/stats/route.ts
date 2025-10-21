import { NextResponse } from 'next/server';
import { proxyToBackend } from '@/lib/backend-proxy';

/**
 * Dashboard Stats API Route
 * Proxies to FastAPI backend - aggregates all service metrics
 */
export async function GET() {
  try {
    const response = await proxyToBackend('/api/dashboard/stats');
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching dashboard stats:', error);

    // Fallback mock data
    return NextResponse.json({
      betanet: { mixnodes: 0, activeConnections: 0, avgLatency: 0, packetsProcessed: 0 },
      bitchat: { activePeers: 0, messagesProcessed: 0 },
      benchmarks: { testsRun: 0, avgScore: 0, queueLength: 0 },
      idleCompute: { totalDevices: 0, harvestingDevices: 0, computeHours: 0 },
      tokenomics: { totalSupply: 0, activeStakers: 0 },
      privacy: { activeCircuits: 0, circuitHealth: 0 },
      error: 'Backend unavailable'
    });
  }
}
