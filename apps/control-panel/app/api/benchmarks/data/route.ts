import { NextResponse } from 'next/server';
import { proxyToBackend } from '@/lib/backend-proxy';

export const dynamic = 'force-dynamic';

/**
 * Benchmarks Data API Route
 * Proxies to FastAPI backend - real-time benchmark metrics
 *
 * SIN-026: Mock fallback restricted to non-production with explicit _mock flag.
 */
export async function GET() {
  try {
    const response = await proxyToBackend('/api/benchmarks/data');
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching benchmark data:', error);

    const isProduction = process.env.NODE_ENV === 'production';

    if (isProduction) {
      // SIN-026: No silent mock fallback in production
      return NextResponse.json(
        {
          error: 'Backend unavailable',
          message: 'Benchmark data could not be fetched from backend.',
          _mock: false,
        },
        { status: 503 }
      );
    }

    // Development only: fallback with explicit mock flag
    return NextResponse.json({
      _mock: true,
      _warning: 'Backend unavailable - showing mock data (dev only)',
      timestamp: Date.now(),
      latency: 0,
      throughput: 0,
      cpuUsage: 0,
      memoryUsage: 0,
      networkUtilization: 0,
    });
  }
}
