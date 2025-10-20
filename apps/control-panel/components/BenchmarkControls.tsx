'use client';

interface BenchmarkControlsProps {
  isRunning: boolean;
  testType: 'latency' | 'throughput' | 'stress';
  onStart: (type: 'latency' | 'throughput' | 'stress') => void;
  onStop: () => void;
}

export function BenchmarkControls({ isRunning, testType, onStart, onStop }: BenchmarkControlsProps) {
  return (
    <div className="glass rounded-xl p-6" data-testid="benchmark-controls">
      <h2 className="text-xl font-semibold mb-4">Benchmark Controls</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-400 mb-2">Test Type</label>
          <div className="space-y-2">
            <button
              onClick={() => !isRunning && onStart('latency')}
              disabled={isRunning}
              className={`w-full glass-hover rounded-lg p-3 text-left transition-all ${
                testType === 'latency' && isRunning ? 'ring-2 ring-blue-400' : ''
              } ${isRunning ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <div className="font-semibold text-blue-400">Latency Test</div>
              <div className="text-xs text-gray-400">Measure response time and network delays</div>
            </button>

            <button
              onClick={() => !isRunning && onStart('throughput')}
              disabled={isRunning}
              className={`w-full glass-hover rounded-lg p-3 text-left transition-all ${
                testType === 'throughput' && isRunning ? 'ring-2 ring-green-400' : ''
              } ${isRunning ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <div className="font-semibold text-green-400">Throughput Test</div>
              <div className="text-xs text-gray-400">Measure data transfer rates and bandwidth</div>
            </button>

            <button
              onClick={() => !isRunning && onStart('stress')}
              disabled={isRunning}
              className={`w-full glass-hover rounded-lg p-3 text-left transition-all ${
                testType === 'stress' && isRunning ? 'ring-2 ring-yellow-400' : ''
              } ${isRunning ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <div className="font-semibold text-yellow-400">Stress Test</div>
              <div className="text-xs text-gray-400">Test system limits under heavy load</div>
            </button>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-400 mb-2">Controls</label>
          <div className="space-y-4">
            {isRunning ? (
              <button
                onClick={onStop}
                className="w-full bg-red-500 hover:bg-red-600 text-white font-semibold py-3 px-6 rounded-lg transition-all duration-200 flex items-center justify-center space-x-2"
              >
                <span>⏹</span>
                <span>Stop Test</span>
              </button>
            ) : (
              <div className="text-center py-3 text-gray-400">
                Select a test type to begin
              </div>
            )}

            {isRunning && (
              <div className="glass-dark rounded-lg p-4">
                <div className="flex items-center justify-center space-x-2">
                  <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                  <span className="text-sm text-gray-400">Test in progress...</span>
                </div>
                <div className="mt-2 text-center text-xs text-gray-500">
                  Running {testType} benchmark
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}