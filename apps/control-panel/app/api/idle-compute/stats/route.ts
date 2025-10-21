import { NextResponse } from 'next/server';
import { proxyToBackend } from '@/lib/backend-proxy';

/**
 * Idle Compute Stats API Route
 * Proxies to FastAPI backend - device harvesting metrics
 */
export async function GET() {
  try {
    const response = await proxyToBackend('/api/idle-compute/stats');
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching idle compute stats:', error);

    return NextResponse.json({
      totalDevices: 0,
      activeDevices: 0,
      harvestingDevices: 0,
      idleDevices: 0,
      totalResources: { cpu: 0, memory: 0, avgBattery: 0 },
      harvestMetrics: { tasksCompleted: 0, totalComputeHours: 0, efficiency: 0 },
      deviceTypes: { android: 0, ios: 0, desktop: 0 },
      error: 'Backend unavailable'
    });
  }
}
