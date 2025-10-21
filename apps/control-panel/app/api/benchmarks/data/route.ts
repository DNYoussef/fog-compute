import { NextResponse } from 'next/server';
import { proxyToBackend } from '@/lib/backend-proxy';

/**
 * Benchmarks Data API Route
 * Proxies to FastAPI backend - real-time benchmark metrics
 */
export async function GET() {
  try {
    const response = await proxyToBackend('/api/benchmarks/data');
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching benchmark data:', error);

    return NextResponse.json({
      metrics: [],
      timestamp: null,
      error: 'Backend unavailable'
    });
  }
}
