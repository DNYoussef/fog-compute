import { NextResponse } from 'next/server';
import { proxyToBackend } from '@/lib/backend-proxy';

/**
 * Scheduler Stats API Route
 * Proxies to FastAPI backend - job queue metrics, SLA compliance
 */
export async function GET() {
  try {
    const response = await proxyToBackend('/api/scheduler/stats');
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching scheduler stats:', error);

    return NextResponse.json({
      totalJobs: 0,
      runningJobs: 0,
      pendingJobs: 0,
      completedJobs: 0,
      queueLength: 0,
      avgWaitTime: 0,
      slaCompliance: { platinum: 100, gold: 95, silver: 90, bronze: 85 },
      resourceUtilization: { cpu: 0, memory: 0, gpu: 0 },
      optimizationScore: 0,
      error: 'Backend unavailable'
    });
  }
}
