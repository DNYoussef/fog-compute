import { NextRequest, NextResponse } from 'next/server';

/**
 * Betanet Deploy API Route
 * Proxies deployment requests to the FastAPI backend server
 */
export async function POST(request: NextRequest) {
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  try {
    const body = await request.json();

    // Validate required fields
    if (!body.node_type) {
      return NextResponse.json(
        { success: false, error: 'node_type is required' },
        { status: 400 }
      );
    }

    // Call FastAPI backend
    const response = await fetch(`${backendUrl}/api/betanet/deploy`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(30000), // 30s timeout for deployment
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return NextResponse.json(
        { success: false, error: errorData.detail || `Backend returned ${response.status}` },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json({ success: true, ...data });

  } catch (error) {
    console.error('Error deploying Betanet node:', error);

    // Return mock success if backend is unavailable (for development)
    if (process.env.NODE_ENV === 'development') {
      return NextResponse.json({
        success: true,
        nodeId: `mock-node-${Date.now().toString(36)}`,
        status: 'deploying',
        note: 'Backend unavailable - mock deployment created',
      });
    }

    return NextResponse.json(
      { success: false, error: 'Backend unavailable' },
      { status: 503 }
    );
  }
}
