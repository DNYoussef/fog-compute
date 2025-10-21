/**
 * Backend Proxy Utilities
 * Helper functions for proxying requests to FastAPI backend
 */

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const DEFAULT_TIMEOUT = 5000; // 5 seconds

interface ProxyOptions {
  timeout?: number;
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
  body?: any;
  params?: URLSearchParams | Record<string, string>;
}

/**
 * Proxy a request to the FastAPI backend
 */
export async function proxyToBackend(
  endpoint: string,
  options: ProxyOptions = {}
): Promise<Response> {
  const {
    timeout = DEFAULT_TIMEOUT,
    method = 'GET',
    body,
    params,
  } = options;

  // Build URL with query parameters
  let url = `${BACKEND_URL}${endpoint}`;
  if (params) {
    const searchParams = params instanceof URLSearchParams
      ? params
      : new URLSearchParams(params);
    const queryString = searchParams.toString();
    if (queryString) {
      url += `?${queryString}`;
    }
  }

  // Build request options
  const fetchOptions: RequestInit = {
    method,
    headers: {
      'Content-Type': 'application/json',
    },
    signal: AbortSignal.timeout(timeout),
  };

  if (body) {
    fetchOptions.body = JSON.stringify(body);
  }

  // Make request
  return fetch(url, fetchOptions);
}

/**
 * Create a mock fallback response when backend is unavailable
 */
export function createMockResponse(mockData: any, status: number = 200): Response {
  return new Response(JSON.stringify(mockData), {
    status,
    headers: {
      'Content-Type': 'application/json',
    },
  });
}
