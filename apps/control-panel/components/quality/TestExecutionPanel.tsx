'use client';

import { useState } from 'react';

interface Props {
  isRunning: boolean;
  output: string[];
  onRunTests: (suite: 'rust' | 'python' | 'all') => Promise<void>;
  onRunBenchmarks: () => Promise<void>;
}

export function TestExecutionPanel({ isRunning, output, onRunTests, onRunBenchmarks }: Props) {
  const [selectedSuite, setSelectedSuite] = useState<'rust' | 'python' | 'all'>('all');

  return (
    <div className="glass rounded-xl p-6">
      <h2 className="text-xl font-semibold mb-4 flex items-center">
        <span className="text-2xl mr-2">🎮</span>
        Test Execution
      </h2>

      {/* Controls */}
      <div className="flex flex-wrap gap-4 mb-4">
        {/* Test Suite Selection */}
        <div className="flex-1 min-w-[200px]">
          <label className="block text-sm text-gray-400 mb-2">Test Suite</label>
          <select
            value={selectedSuite}
            onChange={(e) => setSelectedSuite(e.target.value as 'rust' | 'python' | 'all')}
            disabled={isRunning}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 focus:outline-none focus:border-fog-cyan disabled:opacity-50"
          >
            <option value="all">All Tests</option>
            <option value="rust">Rust Tests (111)</option>
            <option value="python">Python Tests (202)</option>
          </select>
        </div>

        {/* Action Buttons */}
        <div className="flex-1 min-w-[200px] flex items-end space-x-2">
          <button
            onClick={() => onRunTests(selectedSuite)}
            disabled={isRunning}
            className="flex-1 bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 disabled:from-gray-600 disabled:to-gray-700 text-white font-semibold py-2 px-4 rounded-lg transition-all duration-200 disabled:cursor-not-allowed"
          >
            {isRunning ? (
              <span className="flex items-center justify-center">
                <svg className="animate-spin h-5 w-5 mr-2" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Running...
              </span>
            ) : (
              '▶ Run Tests'
            )}
          </button>

          <button
            onClick={onRunBenchmarks}
            disabled={isRunning}
            className="flex-1 bg-gradient-to-r from-purple-500 to-purple-600 hover:from-purple-600 hover:to-purple-700 disabled:from-gray-600 disabled:to-gray-700 text-white font-semibold py-2 px-4 rounded-lg transition-all duration-200 disabled:cursor-not-allowed"
          >
            {isRunning ? 'Running...' : '⚡ Run Benchmarks'}
          </button>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
        <button
          onClick={() => onRunTests('rust')}
          disabled={isRunning}
          className="glass-dark hover:bg-white/10 disabled:opacity-50 px-3 py-2 rounded-lg text-sm transition-colors"
        >
          <div className="font-semibold">🦀 Rust</div>
          <div className="text-xs text-gray-400">111 tests</div>
        </button>
        <button
          onClick={() => onRunTests('python')}
          disabled={isRunning}
          className="glass-dark hover:bg-white/10 disabled:opacity-50 px-3 py-2 rounded-lg text-sm transition-colors"
        >
          <div className="font-semibold">🐍 Python</div>
          <div className="text-xs text-gray-400">202 tests</div>
        </button>
        <button
          disabled={isRunning}
          className="glass-dark hover:bg-white/10 disabled:opacity-50 px-3 py-2 rounded-lg text-sm transition-colors"
          onClick={() => {
            // TODO: Implement integration tests
            alert('Integration tests require Docker services running. Run: docker-compose -f docker-compose.test.yml up -d');
          }}
        >
          <div className="font-semibold">🔗 Integration</div>
          <div className="text-xs text-gray-400">Requires Docker</div>
        </button>
        <button
          disabled={isRunning}
          className="glass-dark hover:bg-white/10 disabled:opacity-50 px-3 py-2 rounded-lg text-sm transition-colors"
          onClick={() => {
            // TODO: Implement E2E tests
            alert('E2E tests use Playwright. Run: npm run test:e2e');
          }}
        >
          <div className="font-semibold">🎭 E2E</div>
          <div className="text-xs text-gray-400">Playwright</div>
        </button>
      </div>

      {/* Output Console */}
      <div className="glass-dark rounded-lg p-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-semibold text-sm">Console Output</h3>
          <div className="flex items-center space-x-2">
            {isRunning && (
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                <span className="text-xs text-green-400">Running</span>
              </div>
            )}
            <button
              onClick={() => {
                // Clear output by re-rendering
                window.location.reload();
              }}
              className="text-xs text-gray-400 hover:text-white transition-colors px-2 py-1 rounded hover:bg-white/10"
            >
              Clear
            </button>
          </div>
        </div>

        <div className="bg-black/50 rounded-lg p-3 font-mono text-xs max-h-96 overflow-y-auto">
          {output.length === 0 ? (
            <div className="text-gray-500">
              No output yet. Click "Run Tests" or "Run Benchmarks" to start.
            </div>
          ) : (
            <div className="space-y-1">
              {output.map((line, idx) => (
                <div
                  key={idx}
                  className={
                    line.includes('✓') || line.includes('PASS') || line.includes('OK') ? 'text-green-400' :
                    line.includes('✗') || line.includes('FAIL') || line.includes('ERROR') ? 'text-red-400' :
                    line.includes('WARN') ? 'text-yellow-400' :
                    line.includes('Starting') || line.includes('Running') ? 'text-blue-400' :
                    'text-gray-300'
                  }
                >
                  {line}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Test Commands Reference */}
      <details className="mt-4">
        <summary className="cursor-pointer text-sm text-gray-400 hover:text-white transition-colors">
          Show manual test commands
        </summary>
        <div className="mt-2 p-4 bg-black/30 rounded-lg font-mono text-xs space-y-2">
          <div>
            <div className="text-gray-500 mb-1"># Run Rust tests</div>
            <code className="text-fog-cyan">cargo test --all</code>
          </div>
          <div>
            <div className="text-gray-500 mb-1"># Run Python tests</div>
            <code className="text-fog-cyan">cd backend && python -m pytest tests/ -v</code>
          </div>
          <div>
            <div className="text-gray-500 mb-1"># Run comprehensive benchmarks</div>
            <code className="text-fog-cyan">python scripts/benchmark_comprehensive.py</code>
          </div>
          <div>
            <div className="text-gray-500 mb-1"># Start test services (PostgreSQL, Redis)</div>
            <code className="text-fog-cyan">docker-compose -f docker-compose.test.yml up -d</code>
          </div>
          <div>
            <div className="text-gray-500 mb-1"># Run E2E tests</div>
            <code className="text-fog-cyan">npm run test:e2e</code>
          </div>
        </div>
      </details>
    </div>
  );
}
