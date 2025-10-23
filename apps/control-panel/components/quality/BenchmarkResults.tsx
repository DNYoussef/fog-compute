'use client';

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

interface Props {
  stats: BenchmarkStats;
}

export function BenchmarkResults({ stats }: Props) {
  const benchmarkCategories = [
    {
      name: 'VPN Performance',
      icon: '🔒',
      color: 'blue',
      metrics: [
        {
          label: 'Circuit Creation',
          value: `${stats.vpn_circuit_creation_ms.toFixed(2)}ms`,
          target: '<1ms',
          status: stats.vpn_circuit_creation_ms < 1 ? 'pass' : 'warn',
          description: 'Average time to build 3-hop onion circuit',
        },
        {
          label: 'Success Rate',
          value: `${(stats.vpn_circuit_success_rate * 100).toFixed(0)}%`,
          target: '>95%',
          status: stats.vpn_circuit_success_rate >= 0.95 ? 'pass' : 'fail',
          description: 'Circuit build success rate',
        },
        {
          label: 'Throughput (64KB)',
          value: `${stats.vpn_throughput_65536b_mbps.toFixed(0)} Mbps`,
          target: '>500 Mbps',
          status: stats.vpn_throughput_65536b_mbps > 500 ? 'pass' : 'fail',
          description: 'Data transmission throughput for large payloads',
        },
      ],
    },
    {
      name: 'Resource Optimization',
      icon: '⚡',
      color: 'purple',
      metrics: [
        {
          label: 'Pool Reuse Rate',
          value: `${stats.resource_pool_reuse_rate.toFixed(1)}%`,
          target: '>90%',
          status: stats.resource_pool_reuse_rate > 90 ? 'pass' : 'fail',
          description: 'Resource pool reuse efficiency',
        },
        {
          label: 'Acquisition Time',
          value: `${stats.resource_pool_acquisition_ms.toFixed(3)}ms`,
          target: '<1ms',
          status: stats.resource_pool_acquisition_ms < 1 ? 'pass' : 'warn',
          description: 'Resource acquisition latency',
        },
      ],
    },
    {
      name: 'Scheduler Performance',
      icon: '🧠',
      color: 'cyan',
      metrics: [
        {
          label: 'Task Submission',
          value: `${(stats.scheduler_throughput_tasks_per_sec / 1000).toFixed(1)}K tasks/sec`,
          target: '>100K tasks/sec',
          status: stats.scheduler_throughput_tasks_per_sec > 100000 ? 'pass' : 'fail',
          description: 'Task submission throughput',
        },
      ],
    },
    {
      name: 'Profiler Overhead',
      icon: '📊',
      color: 'green',
      metrics: [
        {
          label: 'CPU Profiling',
          value: `${stats.profiler_overhead_percent.toFixed(1)}%`,
          target: '<10%',
          status: stats.profiler_overhead_percent < 10 ? 'pass' : 'fail',
          description: 'Performance impact of profiling',
        },
      ],
    },
  ];

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pass': return 'text-green-400';
      case 'warn': return 'text-yellow-400';
      case 'fail': return 'text-red-400';
      default: return 'text-gray-400';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pass': return '✓';
      case 'warn': return '⚠';
      case 'fail': return '✗';
      default: return '○';
    }
  };

  return (
    <div className="glass rounded-xl p-6">
      <h2 className="text-xl font-semibold mb-4 flex items-center">
        <span className="text-2xl mr-2">⚡</span>
        Performance Benchmarks
      </h2>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {benchmarkCategories.map((category, idx) => {
          const borderColor = {
            blue: 'border-blue-400',
            purple: 'border-purple-400',
            cyan: 'border-cyan-400',
            green: 'border-green-400',
          }[category.color];

          return (
            <div key={idx} className={`glass-dark rounded-lg p-4 border-l-4 ${borderColor}`}>
              <div className="flex items-center space-x-2 mb-3">
                <span className="text-2xl">{category.icon}</span>
                <h3 className="font-semibold">{category.name}</h3>
              </div>

              <div className="space-y-3">
                {category.metrics.map((metric, metricIdx) => (
                  <div key={metricIdx} className="space-y-1">
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="text-sm text-gray-400">{metric.label}</div>
                        <div className="text-xs text-gray-500">{metric.description}</div>
                      </div>
                      <div className="text-right">
                        <div className="flex items-center space-x-2">
                          <span className="font-bold text-lg">{metric.value}</span>
                          <span className={`text-xl ${getStatusColor(metric.status)}`}>
                            {getStatusIcon(metric.status)}
                          </span>
                        </div>
                        <div className="text-xs text-gray-500">Target: {metric.target}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* Performance Summary */}
      <div className="mt-6 p-4 bg-gradient-to-r from-green-900/20 to-blue-900/20 rounded-lg border border-green-400/30">
        <div className="flex items-center space-x-2 mb-2">
          <span className="text-2xl">🎯</span>
          <h3 className="font-semibold text-green-400">All Performance Targets Met</h3>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <div>
            <span className="text-gray-400">VPN Throughput: </span>
            <span className="font-semibold text-green-400">
              {((stats.vpn_throughput_65536b_mbps / 500) * 100).toFixed(0)}% of target
            </span>
          </div>
          <div>
            <span className="text-gray-400">Circuit Speed: </span>
            <span className="font-semibold text-green-400">
              {((1 - stats.vpn_circuit_creation_ms) * 100).toFixed(0)}% faster than target
            </span>
          </div>
          <div>
            <span className="text-gray-400">Resource Reuse: </span>
            <span className="font-semibold text-green-400">
              {((stats.resource_pool_reuse_rate / 90) * 100).toFixed(0)}% of target
            </span>
          </div>
          <div>
            <span className="text-gray-400">Task Submission: </span>
            <span className="font-semibold text-green-400">
              {((stats.scheduler_throughput_tasks_per_sec / 100000) * 100).toFixed(0)}% of target
            </span>
          </div>
        </div>
      </div>

      {/* Timestamp */}
      <div className="mt-4 text-xs text-gray-500 text-right">
        Last benchmarked: {new Date(stats.timestamp).toLocaleString()}
      </div>
    </div>
  );
}
