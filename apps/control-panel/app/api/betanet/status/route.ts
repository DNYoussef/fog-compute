import { NextResponse } from 'next/server';

/**
 * Betanet Status API Route
 * Proxies requests to the FastAPI backend server
 *
 * UPDATED: Now calls real backend instead of returning mock data
 */
export async function GET() {
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  try {
    // Call FastAPI backend
    const response = await fetch(`${backendUrl}/api/betanet/status`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      // Add timeout
      signal: AbortSignal.timeout(5000),
    });

    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}`);
    }

    const data = await response.json();
    return NextResponse.json(data);

  } catch (error) {
    console.error('Error fetching Betanet status from backend:', error);

    // Fallback to mock data if backend is unavailable
    return NextResponse.json({
      status: 'mock',
      note: 'Backend unavailable - showing mock data',
      nodes: {
        total: 15,
        active: 12,
        inactive: 3,
      },
      network: {
        latency: 45,
        bandwidth: 1024,
        throughput: 850,
      },
      lastUpdated: new Date().toISOString(),
    });
  }
}
