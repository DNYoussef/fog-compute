import { NextResponse } from 'next/server';

export async function GET() {
  const stats = {
    jobs: {
      queued: Math.floor(Math.random() * 30) + 10,
      running: Math.floor(Math.random() * 25) + 10,
      completed: Math.floor(Math.random() * 10000) + 5000,
      failed: Math.floor(Math.random() * 50) + 10
    },
    nsga: {
      generationsRun: Math.floor(Math.random() * 1000) + 500,
      paretoFront: Math.floor(Math.random() * 50) + 20,
      convergenceRate: Math.random() * 20 + 80
    },
    sla: {
      platinum: {
        count: Math.floor(Math.random() * 100) + 50,
        compliance: Math.random() * 5 + 95
      },
      gold: {
        count: Math.floor(Math.random() * 150) + 100,
        compliance: Math.random() * 10 + 90
      },
      silver: {
        count: Math.floor(Math.random() * 200) + 150,
        compliance: Math.random() * 15 + 85
      },
      bronze: {
        count: Math.floor(Math.random() * 250) + 200,
        compliance: Math.random() * 20 + 80
      }
    },
    performance: {
      avgPlacementTime: Math.random() * 3 + 1,
      resourceUtilization: Math.random() * 20 + 75,
      costEfficiency: Math.random() * 15 + 85
    }
  };

  return NextResponse.json(stats);
}