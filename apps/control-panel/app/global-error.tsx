'use client';

import { useEffect } from 'react';

interface GlobalErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

/**
 * Global error boundary that catches errors in the root layout.
 * This is a last-resort error handler.
 */
export default function GlobalError({ error, reset }: GlobalErrorProps) {
  useEffect(() => {
    // Log error to error reporting service (e.g., Sentry)
    console.error('Global error boundary caught:', error);
  }, [error]);

  return (
    <html lang="en">
      <body>
        <div
          className="flex items-center justify-center min-h-screen bg-gray-900"
          data-testid="global-error-boundary"
        >
          <div className="bg-gray-800 rounded-xl p-8 max-w-2xl mx-4 border border-gray-700">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 bg-red-500/20 rounded-full flex items-center justify-center">
                <span className="text-2xl">⚠️</span>
              </div>
              <div>
                <h2 className="text-2xl font-semibold text-red-400">Critical Error</h2>
                <p className="text-gray-400 text-sm">
                  A critical error occurred in the application
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
                data-testid="global-error-retry-button"
                className="px-6 py-2 bg-cyan-500 hover:bg-cyan-600 text-white font-semibold rounded-lg transition-colors"
              >
                Try Again
              </button>
              <button
                onClick={() => window.location.href = '/'}
                className="px-6 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors text-white"
              >
                Go Home
              </button>
            </div>
          </div>
        </div>
      </body>
    </html>
  );
}
