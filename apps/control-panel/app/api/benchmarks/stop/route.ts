import { NextResponse } from 'next/server';

export async function POST() {
  // In production, this would stop running benchmark tests
  console.log('Stopping benchmark test');

  return NextResponse.json({
    success: true,
    message: 'Benchmark stopped',
  });
}