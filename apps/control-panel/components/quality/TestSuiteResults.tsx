'use client';

import { useEffect, useState } from 'react';

interface TestStats {
  rust_passing: number;
  rust_total: number;
  python_passing: number;
  python_total: number;
  overall_passing: number;
  overall_total: number;
  last_updated: string;
}

interface Props {
  stats: TestStats;
}

interface TestDetail {
  name: string;
  status: 'pass' | 'fail' | 'skip';
  duration_ms: number;
  category: string;
}

export function TestSuiteResults({ stats }: Props) {
  const [expandedSuite, setExpandedSuite] = useState<string | null>(null);
  const [testDetails, setTestDetails] = useState<TestDetail[]>([]);

  const rustPassRate = (stats.rust_passing / stats.rust_total) * 100;
  const pythonPassRate = (stats.python_passing / stats.python_total) * 100;

  const suites = [
    {
      id: 'rust',
      name: 'Rust Tests',
      icon: '🦀',
      passing: stats.rust_passing,
      total: stats.rust_total,
      passRate: rustPassRate,
      color: 'orange',
      categories: [
        { name: 'BetaNet Core', passing: 111, total: 111 },
      ],
    },
    {
      id: 'python',
      name: 'Python Tests',
      icon: '🐍',
      passing: stats.python_passing,
      total: stats.python_total,
      passRate: pythonPassRate,
      color: 'blue',
      categories: [
        { name: 'VPN Integration', passing: 23, total: 23 },
        { name: 'Resource Optimization', passing: 20, total: 23 },
        { name: 'FOG Layer', passing: 71, total: 82 },
        { name: 'Scheduler', passing: 15, total: 15 },
        { name: 'Security/Auth', passing: 13, total: 26 },
        { name: 'BitChat', passing: 25, total: 43 },
      ],
    },
  ];

  const toggleSuite = async (suiteId: string) => {
    if (expandedSuite === suiteId) {
      setExpandedSuite(null);
    } else {
      setExpandedSuite(suiteId);
      // Fetch test details for this suite
      try {
        const response = await fetch(`/api/quality/test-details?suite=${suiteId}`);
        if (response.ok) {
          const data = await response.json();
          setTestDetails(data);
        }
      } catch (error) {
        console.error('Failed to fetch test details:', error);
      }
    }
  };

  return (
    <div className="glass rounded-xl p-6">
      <h2 className="text-xl font-semibold mb-4 flex items-center">
        <span className="text-2xl mr-2">🧪</span>
        Test Suite Results
      </h2>

      <div className="space-y-4">
        {suites.map(suite => {
          const isExpanded = expandedSuite === suite.id;
          const colorClass = {
            orange: 'from-orange-500 to-orange-600',
            blue: 'from-blue-500 to-blue-600',
          }[suite.color];

          return (
            <div key={suite.id} className="glass-dark rounded-lg overflow-hidden">
              {/* Suite Header */}
              <button
                onClick={() => toggleSuite(suite.id)}
                className="w-full p-4 hover:bg-white/5 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <span className="text-2xl">{suite.icon}</span>
                    <div className="text-left">
                      <div className="font-semibold">{suite.name}</div>
                      <div className="text-sm text-gray-400">
                        {suite.passing}/{suite.total} tests passing
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center space-x-4">
                    <div className="text-right">
                      <div className={`text-2xl font-bold ${
                        suite.passRate === 100 ? 'text-green-400' :
                        suite.passRate >= 90 ? 'text-yellow-400' : 'text-red-400'
                      }`}>
                        {suite.passRate.toFixed(1)}%
                      </div>
                    </div>
                    <svg
                      className={`w-6 h-6 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                </div>

                {/* Progress Bar */}
                <div className="mt-3 w-full bg-gray-700 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full bg-gradient-to-r ${colorClass} transition-all duration-300`}
                    style={{ width: `${suite.passRate}%` }}
                  />
                </div>
              </button>

              {/* Expanded Details */}
              {isExpanded && (
                <div className="p-4 border-t border-white/10 space-y-3">
                  <h4 className="font-semibold text-sm text-gray-400">Test Categories</h4>
                  {suite.categories.map((category, idx) => {
                    const categoryPassRate = (category.passing / category.total) * 100;
                    return (
                      <div key={idx} className="flex items-center justify-between text-sm">
                        <span className="text-gray-300">{category.name}</span>
                        <div className="flex items-center space-x-3">
                          <span className="text-gray-400">
                            {category.passing}/{category.total}
                          </span>
                          <span className={`font-semibold ${
                            categoryPassRate === 100 ? 'text-green-400' :
                            categoryPassRate >= 90 ? 'text-yellow-400' : 'text-red-400'
                          }`}>
                            {categoryPassRate.toFixed(0)}%
                          </span>
                        </div>
                      </div>
                    );
                  })}

                  {testDetails.length > 0 && (
                    <div className="mt-4 max-h-64 overflow-y-auto">
                      <h4 className="font-semibold text-sm text-gray-400 mb-2">Recent Test Results</h4>
                      <div className="space-y-1 text-xs">
                        {testDetails.slice(0, 20).map((test, idx) => (
                          <div
                            key={idx}
                            className="flex items-center justify-between py-1 px-2 rounded hover:bg-white/5"
                          >
                            <span className="font-mono text-gray-300">{test.name}</span>
                            <div className="flex items-center space-x-2">
                              <span className="text-gray-500">{test.duration_ms}ms</span>
                              <span className={
                                test.status === 'pass' ? 'text-green-400' :
                                test.status === 'fail' ? 'text-red-400' : 'text-gray-400'
                              }>
                                {test.status === 'pass' ? '✓' : test.status === 'fail' ? '✗' : '⊝'}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Last Updated */}
      <div className="mt-4 text-xs text-gray-500 text-right">
        Last updated: {new Date(stats.last_updated).toLocaleString()}
      </div>
    </div>
  );
}
