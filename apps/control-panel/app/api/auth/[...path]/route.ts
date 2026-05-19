import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.FOG_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

type AuthRouteContext = {
  params: {
    path?: string[];
  };
};

async function proxyAuthRequest(request: NextRequest, context: AuthRouteContext) {
  const path = context.params.path?.join('/') || '';
  const backendUrl = new URL(`/api/auth/${path}`, BACKEND_URL);
  backendUrl.search = request.nextUrl.search;

  const headers = new Headers();
  const authorization = request.headers.get('authorization');
  const contentType = request.headers.get('content-type');

  if (authorization) {
    headers.set('authorization', authorization);
  }

  let body: string | undefined;
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    body = await request.text();
    if (contentType && body) {
      headers.set('content-type', contentType);
    }
  }

  try {
    const response = await fetch(backendUrl, {
      method: request.method,
      headers,
      body,
      cache: 'no-store',
    });

    const responseText = await response.text();
    const responseHeaders = new Headers();
    const responseType = response.headers.get('content-type');

    if (responseType) {
      responseHeaders.set('content-type', responseType);
    }

    return new NextResponse(responseText, {
      status: response.status,
      headers: responseHeaders,
    });
  } catch {
    return NextResponse.json(
      {
        detail: 'Authentication backend unavailable',
      },
      { status: 503 }
    );
  }
}

export async function GET(request: NextRequest, context: AuthRouteContext) {
  return proxyAuthRequest(request, context);
}

export async function POST(request: NextRequest, context: AuthRouteContext) {
  return proxyAuthRequest(request, context);
}
