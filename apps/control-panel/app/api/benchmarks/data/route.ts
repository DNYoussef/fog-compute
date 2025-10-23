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

    // Return mock data point for frontend compatibility
    return NextResponse.json({
      timestamp: Date.now(),
      latency: 0,
      throughput: 0,
      cpuUsage: 0,
      memoryUsage: 0,
      networkUtilization: 0
    });
  }
}
