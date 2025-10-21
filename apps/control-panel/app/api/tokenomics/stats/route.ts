import { NextResponse } from 'next/server';
import { proxyToBackend } from '@/lib/backend-proxy';

/**
 * Tokenomics Stats API Route
 * Proxies to FastAPI backend - token supply, staking, DAO metrics
 */
export async function GET() {
  try {
    const response = await proxyToBackend('/api/tokenomics/stats');
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching tokenomics stats:', error);

    return NextResponse.json({
      totalSupply: 0,
      circulatingSupply: 0,
      stakedTokens: 0,
      activeStakers: 0,
      proposalsActive: 0,
      proposalsTotal: 0,
      marketCap: 0,
      stakingAPR: 0,
      error: 'Backend unavailable'
    });
  }
}
