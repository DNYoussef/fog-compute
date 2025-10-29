'use client';

/**
 * ChartSkeleton Component
 *
 * Displays an animated placeholder skeleton while chart data is loading.
 * Improves perceived performance by showing content structure immediately.
 */

export function ChartSkeleton() {
  return (
    <div className="animate-pulse space-y-4" data-testid="chart-skeleton">
      {/* Chart title placeholder */}
      <div className="h-4 bg-gray-700/50 rounded w-1/4"></div>

      {/* Chart area placeholder with animated bars */}
      <div className="h-64 bg-gray-800/30 rounded-lg p-4">
        <div className="flex items-end justify-around h-full space-x-2">
          {[...Array(10)].map((_, i) => (
            <div
              key={i}
              className="bg-gray-700/50 rounded-t transition-all duration-1000"
              style={{
                width: '8%',
                height: `${30 + (i * 7) % 70}%`,
                animationDelay: `${i * 100}ms`
              }}
            />
          ))}
        </div>
      </div>

      {/* Legend placeholder */}
      <div className="flex space-x-4">
        <div className="h-3 bg-gray-700/50 rounded w-20"></div>
        <div className="h-3 bg-gray-700/50 rounded w-20"></div>
        <div className="h-3 bg-gray-700/50 rounded w-20"></div>
      </div>
    </div>
  );
}

/**
 * MultiChartSkeleton Component
 *
 * Displays multiple chart skeletons for layouts with several charts.
 * Used in benchmark dashboards and analytics pages.
 */

export function MultiChartSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-6" data-testid="multi-chart-skeleton">
      {/* Grid layout for multiple charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {[...Array(count)].map((_, i) => (
          <ChartSkeleton key={i} />
        ))}
      </div>
    </div>
  );
}

/**
 * TableSkeleton Component
 *
 * Displays an animated placeholder skeleton for data tables.
 */

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="animate-pulse space-y-2" data-testid="table-skeleton">
      {/* Table header */}
      <div className="flex space-x-4 pb-2 border-b border-gray-800">
        <div className="h-4 bg-gray-700/50 rounded w-1/4"></div>
        <div className="h-4 bg-gray-700/50 rounded w-1/4"></div>
        <div className="h-4 bg-gray-700/50 rounded w-1/4"></div>
        <div className="h-4 bg-gray-700/50 rounded w-1/4"></div>
      </div>

      {/* Table rows */}
      {[...Array(rows)].map((_, i) => (
        <div key={i} className="flex space-x-4 py-3">
          <div className="h-4 bg-gray-800/30 rounded w-1/4"></div>
          <div className="h-4 bg-gray-800/30 rounded w-1/4"></div>
          <div className="h-4 bg-gray-800/30 rounded w-1/4"></div>
          <div className="h-4 bg-gray-800/30 rounded w-1/4"></div>
        </div>
      ))}
    </div>
  );
}

/**
 * MetricCardSkeleton Component
 *
 * Displays an animated placeholder for metric cards/stats.
 */

export function MetricCardSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="metric-card-skeleton">
      {[...Array(count)].map((_, i) => (
        <div key={i} className="glass rounded-lg p-4 animate-pulse">
          <div className="h-8 bg-gray-700/50 rounded w-3/4 mb-2"></div>
          <div className="h-3 bg-gray-800/30 rounded w-1/2"></div>
        </div>
      ))}
    </div>
  );
}
