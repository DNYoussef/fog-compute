import { NextResponse } from 'next/server';

export async function POST() {
  // Mock benchmark start response
  const mockResponse = {
    benchmarkId: 'bench-' + Date.now(),
    status: 'started',
    estimatedDuration: 30,
    tests: [
      { name: 'system', status: 'pending' },
      { name: 'privacy', status: 'pending' },
      { name: 'graph', status: 'pending' }
    ]
  };

  return NextResponse.json(mockResponse);
}

export async function GET() {
  // Mock benchmark status/results
  const mockResults = {
    status: 'completed',
    results: {
      system: {
        throughput: 25234,
        latency: 45,
        score: 92.5
      },
      privacy: {
        encryption: 'AES-256',
        circuits: 3,
        score: 95.0
      },
      graph: {
        nodes: 24,
        edges: 156,
        diameter: 4,
        score: 88.5
      }
    },
    charts: {
      throughput: [20000, 22000, 25234, 24800, 25100],
      latency: [50, 48, 45, 46, 44]
    }
  };

  return NextResponse.json(mockResults);
}
