'use client';

import { LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { MultiChartSkeleton } from './skeletons/ChartSkeleton';

interface BenchmarkData {
  timestamp: number;
  latency: number;
  throughput: number;
  cpuUsage: number;
  memoryUsage: number;
  networkUtilization: number;
}

interface BenchmarkChartsProps {
  data: BenchmarkData[];
}

export function BenchmarkCharts({ data }: BenchmarkChartsProps) {
  // Show skeleton while waiting for initial data
  if (data.length === 0) {
    return <MultiChartSkeleton count={3} />;
  }

  const chartData = data.map(d => ({
    time: new Date(d.timestamp).toLocaleTimeString(),
    ...d,
  }));

  return (
    <div className="space-y-6" data-testid="benchmark-charts">
      {/* Latency and Throughput */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <h3 className="text-sm font-semibold text-gray-400 mb-3">Latency (ms)</h3>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
              <XAxis dataKey="time" stroke="#9ca3af" fontSize={12} />
              <YAxis stroke="#9ca3af" fontSize={12} />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'rgba(0,0,0,0.8)',
                  border: '1px solid rgba(255,255,255,0.2)',
                  borderRadius: '8px',
                }}
              />
              <Line type="monotone" dataKey="latency" stroke="#3b82f6" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div>
          <h3 className="text-sm font-semibold text-gray-400 mb-3">Throughput (MB/s)</h3>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
              <XAxis dataKey="time" stroke="#9ca3af" fontSize={12} />
              <YAxis stroke="#9ca3af" fontSize={12} />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'rgba(0,0,0,0.8)',
                  border: '1px solid rgba(255,255,255,0.2)',
                  borderRadius: '8px',
                }}
              />
              <Line type="monotone" dataKey="throughput" stroke="#10b981" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* System Resources */}
      <div>
        <h3 className="text-sm font-semibold text-gray-400 mb-3">System Resources</h3>
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
            <XAxis dataKey="time" stroke="#9ca3af" fontSize={12} />
            <YAxis stroke="#9ca3af" fontSize={12} />
            <Tooltip
              contentStyle={{
                backgroundColor: 'rgba(0,0,0,0.8)',
                border: '1px solid rgba(255,255,255,0.2)',
                borderRadius: '8px',
              }}
            />
            <Legend />
            <Area
              type="monotone"
              dataKey="cpuUsage"
              stackId="1"
              stroke="#f59e0b"
              fill="#f59e0b"
              fillOpacity={0.6}
              name="CPU %"
            />
            <Area
              type="monotone"
              dataKey="memoryUsage"
              stackId="2"
              stroke="#8b5cf6"
              fill="#8b5cf6"
              fillOpacity={0.6}
              name="Memory %"
            />
            <Area
              type="monotone"
              dataKey="networkUtilization"
              stackId="3"
              stroke="#06b6d4"
              fill="#06b6d4"
              fillOpacity={0.6}
              name="Network %"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}