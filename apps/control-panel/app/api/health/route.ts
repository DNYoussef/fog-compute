import { NextResponse } from 'next/server';
import { proxyToBackend } from '@/lib/backend-proxy';

/**
 * Health Check API Route
 * Proxies to FastAPI backend health endpoint
 */
export async function GET() {
  try {
    const response = await proxyToBackend('/health');
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json({
      status: 'unhealthy',
      error: 'Backend unavailable'
    }, { status: 503 });
  }
}
