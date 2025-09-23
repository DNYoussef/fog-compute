import { NextResponse } from 'next/server';

export async function GET() {
  // Mock real-time benchmark data
  const data = {
    timestamp: Date.now(),
    latency: Math.random() * 100 + 20,
    throughput: Math.random() * 150 + 50,
    cpuUsage: Math.random() * 60 + 20,
    memoryUsage: Math.random() * 50 + 30,
    networkUtilization: Math.random() * 80 + 20,
  };

  return NextResponse.json(data);
}