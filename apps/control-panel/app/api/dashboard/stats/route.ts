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
        mixnodes: 3,
        activeConnections: 6,
        packetsProcessed: 266000,
        status: 'online' as const
      },
      bitchat: {
        activePeers: 2,
        messagesDelivered: 128,
        encryptionStatus: true,
        meshHealth: 'good' as const
      },
      benchmarks: {
        avgLatency: 18.3,
        throughput: 250.0,
        cpuUsage: 21.5,
        memoryUsage: 42.0
      }
    });
  }
}
