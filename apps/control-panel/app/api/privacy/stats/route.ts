import { NextResponse } from 'next/server';
import { proxyToBackend } from '@/lib/backend-proxy';

/**
 * Privacy Stats API Route
 * Proxies to FastAPI backend - circuit and VPN metrics
 */
export async function GET() {
  try {
    const response = await proxyToBackend('/api/privacy/stats');
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching privacy stats:', error);

    return NextResponse.json({
      activeCircuits: 0,
      totalBandwidth: 0,
      avgLatency: 0,
      circuitHealth: 0,
      onionLayers: { average: 3, min: 3, max: 5 },
      hiddenServices: 0,
      vpnConnections: 0,
      error: 'Backend unavailable'
    });
  }
}
