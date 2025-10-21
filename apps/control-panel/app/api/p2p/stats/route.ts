import { NextResponse } from 'next/server';
import { proxyToBackend } from '@/lib/backend-proxy';

/**
 * P2P Stats API Route
 * Proxies to FastAPI backend - P2P network metrics
 */
export async function GET() {
  try {
    const response = await proxyToBackend('/api/p2p/stats');
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching P2P stats:', error);

    return NextResponse.json({
      connectedPeers: 0,
      messagesSent: 0,
      messagesReceived: 0,
      protocols: { ble: 0, htx: 0, mesh: 0 },
      networkHealth: 0,
      error: 'Backend unavailable'
    });
  }
}
