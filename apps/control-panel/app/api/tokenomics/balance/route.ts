import { NextResponse } from 'next/server';
import { proxyToBackend } from '@/lib/backend-proxy';

/**
 * Token Balance API Route
 * Proxies to FastAPI backend - get wallet balance
 */
export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const response = await proxyToBackend('/api/tokenomics/balance', {
      params: searchParams
    });
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching token balance:', error);

    const { searchParams } = new URL(request.url);
    const address = searchParams.get('address') || '';

    return NextResponse.json({
      address,
      balance: 0,
      staked: 0,
      total: 0,
      rewards: 0,
      error: 'Backend unavailable'
    });
  }
}
