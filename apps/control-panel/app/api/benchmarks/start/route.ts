import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  const body = await request.json();
  const { type } = body;

  // In production, this would start actual benchmark tests
  console.log(`Starting ${type} benchmark test`);

  return NextResponse.json({
    success: true,
    message: `${type} benchmark started`,
    testId: `test-${Date.now()}`,
  });
}