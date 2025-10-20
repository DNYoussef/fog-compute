import { NextResponse } from 'next/server';

/**
 * Mock API endpoint for starting benchmarks
 * Returns simulated benchmark start response for E2E tests
 */
export async function POST(request: Request) {
  const body = await request.json().catch(() => ({}));

  return NextResponse.json({
    benchmarkId: 'bench-' + Date.now(),
    status: 'started',
    config: body,
    estimatedDuration: 60,
    startedAt: new Date().toISOString(),
  });
}
