'use client';

import { useEffect } from 'react';
import Link from 'next/link';

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function IdleComputeError({ error, reset }: ErrorProps) {
  useEffect(() => {
    console.error('Idle Compute page error:', error);
  }, [error]);

  return (
    <div className="flex items-center justify-center min-h-[60vh]" data-testid="idle-compute-error">
      <div className="glass rounded-xl p-8 max-w-xl mx-4">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 bg-red-500/20 rounded-full flex items-center justify-center">
            <span className="text-xl">📱</span>
          </div>
          <div>
            <h3 className="text-xl font-semibold text-red-400">Idle Compute Error</h3>
            <p className="text-gray-400 text-sm">
              Failed to load idle compute dashboard
            </p>
          </div>
        </div>

        {error && (
          <div className="bg-black/30 rounded-lg p-4 mb-4">
            <p className="font-mono text-sm text-red-400">
              {error.message || 'Unknown error occurred'}
            </p>
          </div>
        )}

        <div className="flex gap-3">
          <button
            onClick={reset}
            className="px-4 py-2 bg-fog-cyan hover:bg-fog-cyan/80 text-black font-semibold rounded-lg transition-colors"
          >
            Retry
          </button>
          <Link
            href="/"
            className="px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors inline-flex items-center"
          >
            Dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
