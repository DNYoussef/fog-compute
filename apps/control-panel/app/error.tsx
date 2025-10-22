'use client';

import { useEffect } from 'react';
import Link from 'next/link';

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function Error({ error, reset }: ErrorProps) {
  useEffect(() => {
    // Log error to error reporting service
    console.error('Global error boundary caught:', error);
  }, [error]);

  return (
    <div
      className="flex items-center justify-center min-h-screen bg-fog-dark"
      data-testid="error-boundary"
    >
      <div className="glass rounded-xl p-8 max-w-2xl mx-4">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-12 h-12 bg-red-500/20 rounded-full flex items-center justify-center">
            <span className="text-2xl">⚠️</span>
          </div>
          <div>
            <h2 className="text-2xl font-semibold text-red-400">Something went wrong</h2>
            <p className="text-gray-400 text-sm">
              An unexpected error occurred while rendering this page
            </p>
          </div>
        </div>

        {error && (
          <div className="bg-black/30 rounded-lg p-4 mb-4">
            <p className="font-mono text-sm text-red-400 mb-2">
              {error.message || error.toString()}
            </p>
            {error.digest && (
              <p className="text-xs text-gray-500">
                Error ID: {error.digest}
              </p>
            )}
          </div>
        )}

        <div className="flex gap-4">
          <button
            onClick={reset}
            data-testid="error-retry-button"
            className="px-6 py-2 bg-fog-cyan hover:bg-fog-cyan/80 text-black font-semibold rounded-lg transition-colors"
          >
            Try Again
          </button>
          <Link
            href="/"
            className="px-6 py-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors inline-flex items-center"
          >
            Go Home
          </Link>
          <button
            onClick={() => window.location.reload()}
            className="px-6 py-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors"
          >
            Reload Page
          </button>
        </div>
      </div>
    </div>
  );
}
