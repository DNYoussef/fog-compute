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

    // Fallback mock data matching expected format
    return NextResponse.json({
      betanet: {
        mixnodes: 2,
        activeConnections: 6,
        packetsProcessed: 22274,
        status: 'online' as const
      },
      bitchat: {
        activePeers: 0,
        messagesDelivered: 0,
        encryptionStatus: true,
        meshHealth: 'good' as const
      },
      benchmarks: {
        avgLatency: 0.00,
        throughput: 0.00,
        cpuUsage: 0.0,
        memoryUsage: 0.0
      }
    });
  }
}
