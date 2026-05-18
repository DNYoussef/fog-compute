import { NextResponse } from 'next/server';
import { proxyToBackend } from '@/lib/backend-proxy';

export const dynamic = 'force-dynamic';

/**
 * Dashboard Stats API Route
 * Proxies to FastAPI backend - aggregates all service metrics
 *
 * SIN-026: Mock fallback restricted to non-production with explicit _mock flag.
 */
export async function GET() {
  try {
    const response = await proxyToBackend('/api/dashboard/stats');
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching dashboard stats:', error);

    const isProduction = process.env.NODE_ENV === 'production';

    if (isProduction) {
      // SIN-026: No silent mock fallback in production
      return NextResponse.json(
        {
          error: 'Backend unavailable',
          message: 'Dashboard stats could not be fetched from backend.',
          _mock: false,
        },
        { status: 503 }
      );
    }

    // Development only: fallback mock data with explicit flag
    return NextResponse.json({
      _mock: true,
      _warning: 'Backend unavailable - showing mock data (dev only)',
      betanet: {
        mixnodes: 0,
        activeConnections: 0,
        packetsProcessed: 0,
        status: 'offline' as const
      },
      bitchat: {
        activePeers: 0,
        messagesDelivered: 0,
        encryptionStatus: false,
        meshHealth: 'unknown' as const
      },
      benchmarks: {
        avgLatency: 0.0,
        throughput: 0.0,
        cpuUsage: 0.0,
        memoryUsage: 0.0
      }
    });
  }
}
