import { NextResponse } from 'next/server';

const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const dynamic = 'force-dynamic';

function emptyTopology(reason: string) {
  return {
    _unavailable: true,
    reason,
    devices: [],
    total_devices: 0,
    devices_by_type: {},
    devices_by_status: {},
    devices_by_region: {},
    total_cpu_cores: 0,
    available_cpu_cores: 0,
    total_memory_mb: 0,
    available_memory_mb: 0,
    queued_tasks: 0,
    running_tasks: 0,
    completed_tasks_24h: 0,
    snapshot_time: new Date().toISOString(),
  };
}

export async function GET() {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  const token = process.env.FOG_BRIDGE_ACCESS_TOKEN || process.env.FOG_COMPUTE_ACCESS_TOKEN;

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  try {
    const response = await fetch(`${backendUrl}/api/fog-bridge/topology`, {
      headers,
      signal: AbortSignal.timeout(5000),
    });

    if (!response.ok) {
      return NextResponse.json(emptyTopology(`Backend topology unavailable (${response.status})`));
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json(emptyTopology('Backend topology unavailable'));
  }
}
