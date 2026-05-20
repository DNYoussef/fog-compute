'use client';

interface BenchmarkControlsProps {
  isRunning: boolean;
  testType: 'latency' | 'throughput' | 'stress';
  error?: string | null;
  onStart: (type: 'latency' | 'throughput' | 'stress') => void;
  onStop: () => void;
  onRetry?: () => void;
  onExport?: () => void;
}

const testTypes: Array<{
  value: 'latency' | 'throughput' | 'stress';
  label: string;
  description: string;
  color: string;
}> = [
  {
    value: 'latency',
    label: 'Latency Test',
    description: 'Measure response time and network delays',
    color: 'text-blue-400',
  },
  {
    value: 'throughput',
    label: 'Throughput Test',
    description: 'Measure data transfer rates and bandwidth',
    color: 'text-green-400',
  },
  {
    value: 'stress',
    label: 'Stress Test',
    description: 'Test system limits under heavy load',
    color: 'text-yellow-400',
  },
];

export function BenchmarkControls({
  isRunning,
  testType,
  error,
  onStart,
  onStop,
  onRetry,
  onExport,
}: BenchmarkControlsProps) {
  return (
    <div className="glass rounded-xl p-6" data-testid="benchmark-controls">
      <h2 className="text-xl font-semibold mb-4">Benchmark Controls</h2>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div>
          <label className="mb-2 block text-sm font-medium text-gray-400">Test Type</label>
          <div className="space-y-2">
            {testTypes.map((type) => (
              <button
                key={type.value}
                type="button"
                onClick={() => !isRunning && onStart(type.value)}
                disabled={isRunning}
                data-testid={type.value === 'latency' ? 'latency-benchmark-button' : type.value === 'throughput' ? 'quick-benchmark-button' : 'stress-benchmark-button'}
                className={`w-full rounded-lg p-3 text-left transition-all glass-hover ${
                  testType === type.value && isRunning ? 'ring-2 ring-fog-cyan' : ''
                } ${isRunning ? 'cursor-not-allowed opacity-50' : ''}`}
              >
                <div className={`font-semibold ${type.color}`}>{type.label}</div>
                <div className="text-xs text-gray-400">{type.description}</div>
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="mb-2 block text-sm font-medium text-gray-400">Controls</label>
          <div className="space-y-4">
            <button
              type="button"
              onClick={() => onStart(testType)}
              disabled={isRunning}
              data-testid="start-benchmark-button"
              className="w-full rounded-lg bg-fog-cyan px-6 py-3 font-semibold text-black transition-colors hover:bg-fog-cyan/80 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Start Test
            </button>

            {isRunning && (
              <button
                type="button"
                onClick={onStop}
                data-testid="stop-benchmark-button"
                className="flex w-full items-center justify-center rounded-lg bg-red-500 px-6 py-3 font-semibold text-white transition-colors hover:bg-red-600"
              >
                Stop Test
              </button>
            )}

            {error && (
              <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4" role="alert">
                <p className="mb-3 text-sm text-red-300">{error}</p>
                <button
                  type="button"
                  onClick={onRetry ?? (() => onStart(testType))}
                  className="w-full rounded-lg bg-red-500/20 px-4 py-2 font-semibold text-red-300 transition-colors hover:bg-red-500/30"
                >
                  Retry
                </button>
              </div>
            )}

            <button
              type="button"
              onClick={onExport}
              className="w-full rounded-lg bg-white/10 px-4 py-3 font-semibold text-white transition-colors hover:bg-white/20"
            >
              Export Results
            </button>

            <div className="rounded-lg p-4 glass-dark" data-testid="benchmark-status">
              {isRunning ? (
                <div className="text-center">
                  <div className="mb-2 flex items-center justify-center space-x-2">
                    <div className="h-2 w-2 animate-pulse rounded-full bg-green-400" />
                    <span className="text-sm text-gray-300">Running</span>
                  </div>
                  <div className="text-xs text-gray-500">{testType} benchmark active</div>
                </div>
              ) : (
                <div className="text-center text-sm text-gray-400">Stopped</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
