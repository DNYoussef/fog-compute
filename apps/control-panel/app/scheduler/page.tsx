'use client';

import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/Card';
import { JobQueue } from '@/components/JobQueue';

interface SchedulerStats {
  jobs: {
    queued: number;
    running: number;
    completed: number;
    failed: number;
  };
  nsga: {
    generationsRun: number;
    paretoFront: number;
    convergenceRate: number;
  };
  sla: {
    platinum: { count: number; compliance: number };
    gold: { count: number; compliance: number };
    silver: { count: number; compliance: number };
    bronze: { count: number; compliance: number };
  };
  performance: {
    avgPlacementTime: number;
    resourceUtilization: number;
    costEfficiency: number;
  };
}

export default function SchedulerPage() {
  const [stats, setStats] = useState<SchedulerStats | null>(null);
  const [optimizationMode, setOptimizationMode] = useState<'cost' | 'performance' | 'balanced'>('balanced');

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await fetch('/api/scheduler/stats');
        const data = await response.json();
        setStats(data);
      } catch (error) {
        console.error('Failed to fetch scheduler stats:', error);
      }
    };

    fetchStats();
    const interval = setInterval(fetchStats, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="glass rounded-xl p-6">
        <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-fog-cyan bg-clip-text text-transparent">
          Batch Job Scheduler
        </h1>
        <p className="text-gray-400 mt-2">
          NSGA-II multi-objective optimization with SLA-aware job placement
        </p>
      </div>

      {/* Optimization Mode */}
      <div className="glass rounded-xl p-6">
        <h3 className="text-xl font-semibold mb-4">Optimization Mode</h3>
        <div className="grid grid-cols-3 gap-4">
          {[
            { mode: 'cost', icon: '💰', desc: 'Minimize cost, accept longer wait times' },
            { mode: 'performance', icon: '⚡', desc: 'Maximize speed, higher cost acceptable' },
            { mode: 'balanced', icon: '⚖️', desc: 'Balance cost and performance' },
          ].map(({ mode, icon, desc }) => (
            <button
              key={mode}
              onClick={() => setOptimizationMode(mode as any)}
              className={`p-6 rounded-lg transition-all ${
                optimizationMode === mode
                  ? 'bg-gradient-to-r from-blue-400 to-fog-cyan text-dark-bg'
                  : 'glass hover:border-blue-400 border-2 border-transparent'
              }`}
            >
              <div className="text-4xl mb-2">{icon}</div>
              <div className="font-semibold capitalize">{mode}</div>
              <div className="text-sm mt-2 opacity-80">{desc}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Job Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <Card title="Queued Jobs" className="border-l-4 border-yellow-400">
          <div className="text-4xl font-bold text-yellow-400">
            {stats?.jobs.queued || 0}
          </div>
          <div className="text-gray-400 text-sm mt-2">Waiting for placement</div>
        </Card>

        <Card title="Running Jobs" className="border-l-4 border-green-400">
          <div className="text-4xl font-bold text-green-400">
            {stats?.jobs.running || 0}
          </div>
          <div className="text-gray-400 text-sm mt-2">Currently executing</div>
        </Card>

        <Card title="Completed" className="border-l-4 border-fog-cyan">
          <div className="text-4xl font-bold text-fog-cyan">
            {stats?.jobs.completed?.toLocaleString() || 0}
          </div>
          <div className="text-gray-400 text-sm mt-2">Successfully finished</div>
        </Card>

        <Card title="Failed" className="border-l-4 border-red-400">
          <div className="text-4xl font-bold text-red-400">
            {stats?.jobs.failed || 0}
          </div>
          <div className="text-gray-400 text-sm mt-2">Error/timeout</div>
        </Card>
      </div>

      {/* NSGA-II Optimization Metrics */}
      <Card title="NSGA-II Optimization Engine">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="text-center p-6 glass rounded-lg">
            <div className="text-4xl font-bold text-blue-400">
              {stats?.nsga.generationsRun?.toLocaleString() || 0}
            </div>
            <div className="text-gray-400 mt-2">Generations Run</div>
          </div>
          <div className="text-center p-6 glass rounded-lg">
            <div className="text-4xl font-bold text-fog-cyan">
              {stats?.nsga.paretoFront || 0}
            </div>
            <div className="text-gray-400 mt-2">Pareto-Optimal Solutions</div>
          </div>
          <div className="text-center p-6 glass rounded-lg">
            <div className="text-4xl font-bold text-green-400">
              {stats?.nsga.convergenceRate?.toFixed(1) || 0}%
            </div>
            <div className="text-gray-400 mt-2">Convergence Rate</div>
          </div>
        </div>
      </Card>

      {/* SLA Compliance */}
      <Card title="SLA Tier Compliance">
        <div className="space-y-4">
          {[
            { tier: 'platinum', color: 'from-purple-400 to-pink-400', name: 'Platinum' },
            { tier: 'gold', color: 'from-yellow-400 to-orange-400', name: 'Gold' },
            { tier: 'silver', color: 'from-gray-300 to-gray-400', name: 'Silver' },
            { tier: 'bronze', color: 'from-orange-600 to-orange-800', name: 'Bronze' },
          ].map(({ tier, color, name }) => {
            const tierStats = stats?.sla[tier as keyof typeof stats.sla];
            return (
              <div key={tier} className="glass rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className={`text-xl font-bold bg-gradient-to-r ${color} bg-clip-text text-transparent`}>
                    {name} Tier
                  </div>
                  <div className="text-gray-400">
                    {tierStats?.count || 0} jobs
                  </div>
                </div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-400">SLA Compliance</span>
                  <span className="font-semibold">
                    {tierStats?.compliance?.toFixed(1) || 0}%
                  </span>
                </div>
                <div className="w-full bg-dark-bg-lighter rounded-full h-2">
                  <div
                    className={`h-2 rounded-full transition-all bg-gradient-to-r ${color}`}
                    style={{ width: `${tierStats?.compliance || 0}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      {/* Performance Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card title="Avg Placement Time">
          <div className="text-3xl font-bold text-blue-400">
            {stats?.performance.avgPlacementTime?.toFixed(2) || 0}s
          </div>
          <div className="text-sm text-gray-400 mt-2">
            Time to find optimal placement
          </div>
        </Card>

        <Card title="Resource Utilization">
          <div className="text-3xl font-bold text-green-400">
            {stats?.performance.resourceUtilization?.toFixed(1) || 0}%
          </div>
          <div className="text-sm text-gray-400 mt-2">
            Overall cluster efficiency
          </div>
        </Card>

        <Card title="Cost Efficiency">
          <div className="text-3xl font-bold text-fog-cyan">
            {stats?.performance.costEfficiency?.toFixed(1) || 0}%
          </div>
          <div className="text-sm text-gray-400 mt-2">
            Cost optimization score
          </div>
        </Card>
      </div>

      {/* Job Queue */}
      <Card title="Job Queue" className="min-h-[400px]">
        <JobQueue stats={stats} />
      </Card>

      {/* Scheduler Controls */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <button className="btn-primary p-6 rounded-lg text-left">
          <div className="text-xl font-semibold">Submit Batch Job</div>
          <p className="text-sm text-gray-400 mt-2">
            Submit a new batch job for NSGA-II optimization
          </p>
        </button>
        <button className="btn-secondary p-6 rounded-lg text-left">
          <div className="text-xl font-semibold">View Placement History</div>
          <p className="text-sm text-gray-400 mt-2">
            Analyze historical placement decisions
          </p>
        </button>
      </div>

      {/* Advanced Configuration */}
      <Card title="Advanced Scheduler Configuration">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 glass rounded-lg">
              <div>
                <div className="font-semibold">Population Size</div>
                <div className="text-sm text-gray-400">NSGA-II population per generation</div>
              </div>
              <input
                type="number"
                defaultValue={100}
                className="w-24 bg-dark-bg-lighter border border-gray-700 rounded-lg px-3 py-2"
              />
            </div>
            <div className="flex items-center justify-between p-4 glass rounded-lg">
              <div>
                <div className="font-semibold">Max Generations</div>
                <div className="text-sm text-gray-400">Stop after N generations</div>
              </div>
              <input
                type="number"
                defaultValue={50}
                className="w-24 bg-dark-bg-lighter border border-gray-700 rounded-lg px-3 py-2"
              />
            </div>
          </div>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 glass rounded-lg">
              <div>
                <div className="font-semibold">Crossover Rate</div>
                <div className="text-sm text-gray-400">Genetic algorithm parameter</div>
              </div>
              <input
                type="number"
                step="0.1"
                defaultValue={0.9}
                className="w-24 bg-dark-bg-lighter border border-gray-700 rounded-lg px-3 py-2"
              />
            </div>
            <div className="flex items-center justify-between p-4 glass rounded-lg">
              <div>
                <div className="font-semibold">Mutation Rate</div>
                <div className="text-sm text-gray-400">Exploration parameter</div>
              </div>
              <input
                type="number"
                step="0.01"
                defaultValue={0.05}
                className="w-24 bg-dark-bg-lighter border border-gray-700 rounded-lg px-3 py-2"
              />
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}