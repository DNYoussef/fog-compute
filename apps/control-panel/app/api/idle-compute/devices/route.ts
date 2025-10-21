import { NextResponse } from 'next/server';
import { proxyToBackend } from '@/lib/backend-proxy';

/**
 * Idle Compute Devices API Route
 * Proxies to FastAPI backend - list devices and register new ones
 */
export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const response = await proxyToBackend('/api/idle-compute/devices', {
      params: searchParams
    });
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching devices:', error);

    return NextResponse.json({
      devices: [],
      total: 0,
      error: 'Backend unavailable'
    });
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const response = await proxyToBackend('/api/idle-compute/devices', {
      method: 'POST',
      body
    });
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error registering device:', error);

    return NextResponse.json({
      success: false,
      error: 'Backend unavailable'
    }, { status: 503 });
  }
}
