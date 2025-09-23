'use client';

import { useEffect, useState } from 'react';
import { BenchmarkCharts } from '@/components/BenchmarkCharts';
import { BenchmarkControls } from '@/components/BenchmarkControls';

interface BenchmarkData {
  timestamp: number;
  latency: number;
  throughput: number;
  cpuUsage: number;
  memoryUsage: number;
  networkUtilization: number;
}

export default function BenchmarksPage() {
  const [benchmarkData, setBenchmarkData] = useState<BenchmarkData[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [testType, setTestType] = useState<'latency' | 'throughput' | 'stress'>('latency');

  useEffect(() => {
    const fetchBenchmarkData = async () => {
      try {
        const response = await fetch('/api/benchmarks/data');
        const data = await response.json();
        setBenchmarkData(prev => [...prev.slice(-50), data].slice(-100)); // Keep last 100 points
      } catch (error) {
        console.error('Failed to fetch benchmark data:', error);
      }
    };

    const interval = setInterval(fetchBenchmarkData, 1000);
    return () => clearInterval(interval);
  }, []);

  const startBenchmark = async (type: 'latency' | 'throughput' | 'stress') => {
    setTestType(type);
    setIsRunning(true);
    try {
      await fetch('/api/benchmarks/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type }),
      });
    } catch (error) {
      console.error('Failed to start benchmark:', error);
      setIsRunning(false);
    }
  };

  const stopBenchmark = async () => {
    setIsRunning(false);
    try {
      await fetch('/api/benchmarks/stop', { method: 'POST' });
    } catch (error) {
      console.error('Failed to stop benchmark:', error);
    }
  };

  const latestData = benchmarkData[benchmarkData.length - 1] || {
    latency: 0,
    throughput: 0,
    cpuUsage: 0,
    memoryUsage: 0,
    networkUtilization: 0,
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="glass rounded-xl p-6">
        <h1 className="text-3xl font-bold text-green-400">Performance Benchmarks</h1>
        <p className="text-gray-400 mt-2">
          Real-time performance monitoring and stress testing for fog compute nodes
        </p>
      </div>

      {/* Current Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="glass rounded-lg p-4">
          <div className="text-2xl font-bold text-blue-400">{latestData.latency.toFixed(2)}ms</div>
          <div className="text-sm text-gray-400">Latency</div>
        </div>
        <div className="glass rounded-lg p-4">
          <div className="text-2xl font-bold text-green-400">{latestData.throughput.toFixed(2)} MB/s</div>
          <div className="text-sm text-gray-400">Throughput</div>
        </div>
        <div className="glass rounded-lg p-4">
          <div className="text-2xl font-bold text-yellow-400">{latestData.cpuUsage.toFixed(1)}%</div>
          <div className="text-sm text-gray-400">CPU Usage</div>
        </div>
        <div className="glass rounded-lg p-4">
          <div className="text-2xl font-bold text-purple-400">{latestData.memoryUsage.toFixed(1)}%</div>
          <div className="text-sm text-gray-400">Memory Usage</div>
        </div>
        <div className="glass rounded-lg p-4">
          <div className="text-2xl font-bold text-cyan-400">{latestData.networkUtilization.toFixed(1)}%</div>
          <div className="text-sm text-gray-400">Network</div>
        </div>
      </div>

      {/* Benchmark Controls */}
      <BenchmarkControls
        isRunning={isRunning}
        testType={testType}
        onStart={startBenchmark}
        onStop={stopBenchmark}
      />

      {/* Performance Charts */}
      <div className="glass rounded-xl p-6">
        <h2 className="text-xl font-semibold mb-4">Real-Time Performance Metrics</h2>
        <BenchmarkCharts data={benchmarkData} />
      </div>

      {/* System Info */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="glass rounded-xl p-6">
          <h3 className="text-lg font-semibold mb-4">Test Configuration</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-400">Test Type:</span>
              <span className="font-semibold uppercase">{testType}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Sample Rate:</span>
              <span className="font-semibold">1 second</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Data Points:</span>
              <span className="font-semibold">{benchmarkData.length}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Status:</span>
              <span className={`font-semibold ${isRunning ? 'text-green-400' : 'text-gray-400'}`}>
                {isRunning ? 'Running' : 'Stopped'}
              </span>
            </div>
          </div>
        </div>

        <div className="glass rounded-xl p-6">
          <h3 className="text-lg font-semibold mb-4">Performance Summary</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-400">Avg Latency:</span>
              <span className="font-semibold">
                {(benchmarkData.reduce((acc, d) => acc + d.latency, 0) / benchmarkData.length || 0).toFixed(2)}ms
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Avg Throughput:</span>
              <span className="font-semibold">
                {(benchmarkData.reduce((acc, d) => acc + d.throughput, 0) / benchmarkData.length || 0).toFixed(2)} MB/s
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Peak CPU:</span>
              <span className="font-semibold">
                {Math.max(...benchmarkData.map(d => d.cpuUsage), 0).toFixed(1)}%
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Peak Memory:</span>
              <span className="font-semibold">
                {Math.max(...benchmarkData.map(d => d.memoryUsage), 0).toFixed(1)}%
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}