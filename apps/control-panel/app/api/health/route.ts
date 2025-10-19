import { NextResponse } from 'next/server';

export async function GET() {
  // Mock health check response
  const mockHealth = {
    status: 'healthy',
    timestamp: new Date().toISOString(),
    services: {
      betanet: 'up',
      bitchat: 'up',
      database: 'up',
      cache: 'up'
    },
    uptime: 99.95,
    version: '0.1.0'
  };

  return NextResponse.json(mockHealth);
}
