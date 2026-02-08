import { NextResponse } from 'next/server';

/**
 * Betanet Status API Route
 * Proxies to FastAPI backend and adapts response shape for the UI.
 *
 * SIN-006: The betanet page expects `mixnodes` (array) and `health` (number)
 * in addition to the canonical status fields. This route fetches both
 * /api/betanet/status and /api/betanet/nodes and merges them.
 */
export async function GET() {
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  try {
    // Fetch status and nodes in parallel
    const [statusRes, nodesRes] = await Promise.all([
      fetch(`${backendUrl}/api/betanet/status`, {
        headers: { 'Content-Type': 'application/json' },
        signal: AbortSignal.timeout(5000),
      }),
      fetch(`${backendUrl}/api/betanet/nodes`, {
        headers: { 'Content-Type': 'application/json' },
        signal: AbortSignal.timeout(5000),
      }),
    ]);

    if (!statusRes.ok) {
      throw new Error(`Status endpoint returned ${statusRes.status}`);
    }

    const statusData = await statusRes.json();
    const nodesData = nodesRes.ok ? await nodesRes.json() : [];

    // Compute health score: percentage of active nodes
    const totalNodes = Array.isArray(nodesData) ? nodesData.length : 0;
    const activeNodes = Array.isArray(nodesData)
      ? nodesData.filter((n: any) => n.status === 'active').length
      : 0;
    const health = totalNodes > 0 ? Math.round((activeNodes / totalNodes) * 100) : 0;

    // Adapt nodes to the MixnodeInfo shape the page expects
    const mixnodes = Array.isArray(nodesData)
      ? nodesData.map((n: any, i: number) => ({
          id: n.id,
          address: `mix-${n.id.slice(0, 8)}`,
          status: n.status === 'active' ? 'active' : n.status === 'maintenance' ? 'degraded' : 'inactive',
          packetsProcessed: n.packets_processed || 0,
          uptime: 0, // Rust provides uptime_seconds, backend doesn't persist yet
          latency: n.avg_latency_ms || 0,
          reputation: n.status === 'active' ? 95 : 50,
          position: {
            x: Math.cos((i * 2 * Math.PI) / Math.max(totalNodes, 1)) * 5,
            y: Math.sin((i * 2 * Math.PI) / Math.max(totalNodes, 1)) * 5,
            z: 0,
          },
        }))
      : [];

    return NextResponse.json({
      ...statusData,
      mixnodes,
      health,
    });
  } catch (error) {
    console.error('Error fetching Betanet status from backend:', error);

    // Return empty state instead of mock data with inflated numbers
    return NextResponse.json({
      status: 'unavailable',
      nodes: { total: 0, active: 0, inactive: 0 },
      network: { latency: 0, bandwidth: 0, throughput: 0, packetsProcessed: 0 },
      lastUpdated: new Date().toISOString(),
      mixnodes: [],
      health: 0,
    });
  }
}
