import { NextResponse } from 'next/server';
import { proxyToBackend } from '@/lib/backend-proxy';

/**
 * Start Benchmark API Route
 * Proxies to FastAPI backend - start a benchmark test
 */
export async function POST(request: Request) {
  try {
    const body = await request.json();
    const response = await proxyToBackend('/api/benchmarks/start', {
      method: 'POST',
      body
    });
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error starting benchmark:', error);

    return NextResponse.json({
      success: false,
      error: 'Backend unavailable'
    }, { status: 503 });
  }
}
