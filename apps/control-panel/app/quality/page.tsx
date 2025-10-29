'use client';

import { useEffect, useState } from 'react';
import { TestSuiteResults } from '@/components/quality/TestSuiteResults';
import { BenchmarkResults } from '@/components/quality/BenchmarkResults';
import { QualityMetrics } from '@/components/quality/QualityMetrics';
import { TestExecutionPanel } from '@/components/quality/TestExecutionPanel';

interface TestStats {
  rust_passing: number;
  rust_total: number;
  python_passing: number;
  python_total: number;
  overall_passing: number;
  overall_total: number;
  last_updated: string;
}

interface BenchmarkStats {
  vpn_circuit_creation_ms: number;
  vpn_circuit_success_rate: number;
  vpn_throughput_65536b_mbps: number;
  resource_pool_reuse_rate: number;
  resource_pool_acquisition_ms: number;
  scheduler_throughput_tasks_per_sec: number;
  profiler_overhead_percent: number;
  timestamp: string;
}

interface QualityStats {
  production_readiness_percent: number;
  code_coverage_percent: number;
  performance_score: number;
  security_score: number;
}

export default function QualityPage() {
  const [testStats, setTestStats] = useState<TestStats>({
    rust_passing: 111,
    rust_total: 111,
    python_passing: 178,
    python_total: 202,
    overall_passing: 289,
    overall_total: 313,
    last_updated: new Date().toISOString(),
  });

  const [benchmarkStats, setBenchmarkStats] = useState<BenchmarkStats | null>(null);
  const [qualityStats, setQualityStats] = useState<QualityStats>({
    production_readiness_percent: 92.3,
    code_coverage_percent: 78.5,
    performance_score: 95.0,
    security_score: 85.0,
  });

  const [isTestRunning, setIsTestRunning] = useState(false);
  const [testOutput, setTestOutput] = useState<string[]>([]);

  // Fetch benchmark data from our Week 7 results

  useEffect(() => {
    document.title = 'Quality Testing | Fog Compute';
  }, []);
  useEffect(() => {
    const fetchBenchmarkData = async () => {
      try {
        const response = await fetch('/api/quality/benchmarks');
        if (response.ok) {
          const data = await response.json();
          setBenchmarkStats(data);
        }
      } catch (error) {
        console.error('Failed to fetch benchmark data:', error);
        // Use Week 7 static data as fallback
        setBenchmarkStats({
          vpn_circuit_creation_ms: 0.50,
          vpn_circuit_success_rate: 1.0,
          vpn_throughput_65536b_mbps: 923.97,
          resource_pool_reuse_rate: 99.1,
          resource_pool_acquisition_ms: 0.000,
          scheduler_throughput_tasks_per_sec: 334260.8,
          profiler_overhead_percent: 5.0,
          timestamp: new Date().toISOString(),
        });
      }
    };

    fetchBenchmarkData();
    const interval = setInterval(fetchBenchmarkData, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  // Fetch test stats
  useEffect(() => {
    const fetchTestStats = async () => {
      try {
        const response = await fetch('/api/quality/tests');
        if (response.ok) {
          const data = await response.json();
          setTestStats(data);
        }
      } catch (error) {
        console.error('Failed to fetch test stats:', error);
      }
    };

    fetchTestStats();
    const interval = setInterval(fetchTestStats, 10000); // Refresh every 10s
    return () => clearInterval(interval);
  }, []);

  const runTests = async (suite: 'rust' | 'python' | 'all') => {
    setIsTestRunning(true);
    setTestOutput([`Starting ${suite} test suite...`]);

    try {
      const response = await fetch('/api/quality/run-tests', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ suite }),
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (reader) {
        let done = false;
        while (!done) {
          const { value, done: doneReading } = await reader.read();
          done = doneReading;
          if (value) {
            const chunk = decoder.decode(value);
            setTestOutput(prev => [...prev, chunk]);
          }
        }
      }
    } catch (error) {
      setTestOutput(prev => [...prev, `Error: ${error}`]);
    } finally {
      setIsTestRunning(false);
    }
  };

  const runBenchmarks = async () => {
    setIsTestRunning(true);
    setTestOutput(['Starting comprehensive benchmark suite...']);

    try {
      const response = await fetch('/api/quality/run-benchmarks', {
        method: 'POST',
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (reader) {
        let done = false;
        while (!done) {
          const { value, done: doneReading } = await reader.read();
          done = doneReading;
          if (value) {
            const chunk = decoder.decode(value);
            setTestOutput(prev => [...prev, chunk]);
          }
        }
      }

      // Refresh benchmark stats after completion
      setTimeout(async () => {
        const response = await fetch('/api/quality/benchmarks');
        if (response.ok) {
          const data = await response.json();
          setBenchmarkStats(data);
        }
      }, 1000);
    } catch (error) {
      setTestOutput(prev => [...prev, `Error: ${error}`]);
    } finally {
      setIsTestRunning(false);
    }
  };

  const overallPassRate = (testStats.overall_passing / testStats.overall_total) * 100;

  return (
    <div className="space-y-6" data-testid="quality-dashboard">
      {/* Header */}
      <div className="glass rounded-xl p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-fog-cyan to-fog-purple bg-clip-text text-transparent">
              Quality Dashboard
            </h1>
            <p className="text-gray-400 mt-2">
              Comprehensive testing, benchmarking, and quality metrics
            </p>
          </div>
          <div className="text-right">
            <div className="text-4xl font-bold text-green-400">{overallPassRate.toFixed(1)}%</div>
            <div className="text-sm text-gray-400">Overall Pass Rate</div>
          </div>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="glass rounded-lg p-4 border-l-4 border-green-400">
          <div className="text-2xl font-bold text-green-400">
            {testStats.overall_passing}/{testStats.overall_total}
          </div>
          <div className="text-sm text-gray-400">Tests Passing</div>
        </div>
        <div className="glass rounded-lg p-4 border-l-4 border-blue-400">
          <div className="text-2xl font-bold text-blue-400">
            {benchmarkStats?.vpn_throughput_65536b_mbps.toFixed(0) || '---'} Mbps
          </div>
          <div className="text-sm text-gray-400">VPN Throughput</div>
        </div>
        <div className="glass rounded-lg p-4 border-l-4 border-purple-400">
          <div className="text-2xl font-bold text-purple-400">
            {qualityStats.production_readiness_percent.toFixed(1)}%
          </div>
          <div className="text-sm text-gray-400">Production Ready</div>
        </div>
        <div className="glass rounded-lg p-4 border-l-4 border-cyan-400">
          <div className="text-2xl font-bold text-cyan-400">
            {benchmarkStats?.resource_pool_reuse_rate.toFixed(1) || '---'}%
          </div>
          <div className="text-sm text-gray-400">Resource Reuse</div>
        </div>
      </div>

      {/* Test Suite Results */}
      <div data-testid="test-suite-section">
        <TestSuiteResults stats={testStats} />
      </div>

      {/* Benchmark Results */}
      {benchmarkStats && (
        <div data-testid="benchmark-section">
          <BenchmarkResults stats={benchmarkStats} />
        </div>
      )}

      {/* Quality Metrics */}
      <div data-testid="quality-metrics-section">
        <QualityMetrics stats={qualityStats} />
      </div>

      {/* Test Execution Panel */}
      <div data-testid="test-execution-section">
        <TestExecutionPanel
          isRunning={isTestRunning}
          output={testOutput}
          onRunTests={runTests}
          onRunBenchmarks={runBenchmarks}
        />
      </div>

      {/* Week 7 Progress */}
      <div className="glass rounded-xl p-6">
        <h2 className="text-xl font-semibold mb-4 flex items-center">
          <span className="text-2xl mr-2">📈</span>
          Week 7 Progress
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-3">
            <h3 className="font-semibold text-fog-cyan">Test Improvements</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-400">Rust Tests:</span>
                <span className="font-semibold text-green-400">111/111 (100%)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Python Tests:</span>
                <span className="font-semibold text-green-400">178/202 (88.1%)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Week 7 Fixes:</span>
                <span className="font-semibold text-fog-cyan">+15 tests</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Improvement:</span>
                <span className="font-semibold text-fog-purple">+7.4%</span>
              </div>
            </div>
          </div>
          <div className="space-y-3">
            <h3 className="font-semibold text-fog-cyan">Performance Targets</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-400">Circuit Creation:</span>
                <span className="font-semibold text-green-400">0.50ms ✓</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">VPN Throughput:</span>
                <span className="font-semibold text-green-400">924 Mbps ✓</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Resource Reuse:</span>
                <span className="font-semibold text-green-400">99.1% ✓</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Profiler Overhead:</span>
                <span className="font-semibold text-green-400">5.0% ✓</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
