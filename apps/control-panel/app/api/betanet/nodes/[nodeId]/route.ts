import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

/**
 * Betanet Node Detail API Routes (SIN-007)
 * Proxies to FastAPI backend /api/betanet/nodes/:nodeId
 */

const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function GET(
  request: NextRequest,
  { params }: { params: { nodeId: string } }
) {
  try {
    const response = await fetch(`${backendUrl}/api/betanet/nodes/${params.nodeId}`, {
      headers: { 'Content-Type': 'application/json' },
      signal: AbortSignal.timeout(5000),
    });

    if (response.status === 404) {
      return NextResponse.json({ detail: 'Node not found' }, { status: 404 });
    }

    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching node:', error);
    return NextResponse.json({ detail: 'Backend unavailable' }, { status: 503 });
  }
}

export async function PUT(
  request: NextRequest,
  { params }: { params: { nodeId: string } }
) {
  try {
    const body = await request.json();
    const response = await fetch(`${backendUrl}/api/betanet/nodes/${params.nodeId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(5000),
    });

    if (response.status === 404) {
      return NextResponse.json({ detail: 'Node not found' }, { status: 404 });
    }

    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error updating node:', error);
    return NextResponse.json({ detail: 'Backend unavailable' }, { status: 503 });
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: { nodeId: string } }
) {
  try {
    const response = await fetch(`${backendUrl}/api/betanet/nodes/${params.nodeId}`, {
      method: 'DELETE',
      signal: AbortSignal.timeout(5000),
    });

    if (response.status === 404) {
      return NextResponse.json({ detail: 'Node not found' }, { status: 404 });
    }

    if (response.status === 204 || response.ok) {
      return new NextResponse(null, { status: 204 });
    }

    throw new Error(`Backend returned ${response.status}`);
  } catch (error) {
    console.error('Error deleting node:', error);
    return NextResponse.json({ detail: 'Backend unavailable' }, { status: 503 });
  }
}
