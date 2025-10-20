import { NextResponse } from 'next/server';

/**
 * Mock API endpoint for betanet status
 * Returns simulated betanet network status for E2E tests
 */
export async function GET() {
  return NextResponse.json({
    status: 'operational',
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
