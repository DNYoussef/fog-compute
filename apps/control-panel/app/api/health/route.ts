import { NextResponse } from 'next/server';

/**
 * Mock API endpoint for health check
 * Returns simulated health status for E2E tests
 */
export async function GET() {
  return NextResponse.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    services: {
      database: 'up',
      cache: 'up',
      messageQueue: 'up',
    },
    version: '1.0.0',
  });
}
