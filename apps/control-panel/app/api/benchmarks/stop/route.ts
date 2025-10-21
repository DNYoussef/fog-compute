import { NextResponse } from 'next/server';
import { proxyToBackend } from '@/lib/backend-proxy';

/**
 * Stop Benchmark API Route
 * Proxies to FastAPI backend - stop a running benchmark
 */
export async function POST(request: Request) {
  try {
    const body = await request.json();
    const response = await proxyToBackend('/api/benchmarks/stop', {
      method: 'POST',
      body
    });
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error stopping benchmark:', error);

    return NextResponse.json({
      success: false,
      error: 'Backend unavailable'
    }, { status: 503 });
  }
}
