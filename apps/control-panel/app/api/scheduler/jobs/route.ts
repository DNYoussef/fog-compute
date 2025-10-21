import { NextResponse } from 'next/server';
import { proxyToBackend } from '@/lib/backend-proxy';

/**
 * Scheduler Jobs API Route
 * Proxies to FastAPI backend - get jobs list and submit new jobs
 */
export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const response = await proxyToBackend('/api/scheduler/jobs', {
      params: searchParams
    });
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching jobs:', error);

    return NextResponse.json({
      jobs: [],
      total: 0,
      error: 'Backend unavailable'
    });
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const response = await proxyToBackend('/api/scheduler/jobs', {
      method: 'POST',
      body
    });
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error submitting job:', error);

    return NextResponse.json({
      success: false,
      error: 'Backend unavailable'
    }, { status: 503 });
  }
}
