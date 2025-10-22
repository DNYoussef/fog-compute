'use client';

import { useAlerts } from '@/lib/websocket/hooks';
import { WebSocketClient } from '@/lib/websocket/client';

interface AlertNotificationsProps {
  client: WebSocketClient | null;
}

export function AlertNotifications({ client }: AlertNotificationsProps) {
  const { alerts, clearAlerts } = useAlerts(client);

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'bg-red-500/20 border-red-500 text-red-400';
      case 'high':
        return 'bg-orange-500/20 border-orange-500 text-orange-400';
      case 'warning':
      case 'medium':
        return 'bg-yellow-500/20 border-yellow-500 text-yellow-400';
      case 'info':
      case 'low':
        return 'bg-blue-500/20 border-blue-500 text-blue-400';
      default:
        return 'bg-gray-500/20 border-gray-500 text-gray-400';
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'critical':
        return '🚨';
      case 'high':
      case 'warning':
      case 'medium':
        return '⚠️';
      case 'info':
      case 'low':
        return 'ℹ️';
      default:
        return '📢';
    }
  };

  return (
    <div className="bg-white/5 rounded-lg p-6 border border-white/10">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">Live Alerts</h3>
        {alerts.length > 0 && (
          <button
            onClick={clearAlerts}
            className="px-3 py-1 text-xs bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white rounded transition-colors"
          >
            Clear All
          </button>
        )}
      </div>

      <div className="space-y-3 max-h-96 overflow-y-auto">
        {alerts.length === 0 ? (
          <div className="text-center py-8 text-gray-400">
            <div className="text-4xl mb-2">✓</div>
            <div>No alerts - all systems operational</div>
          </div>
        ) : (
          alerts.map((alert, index) => {
            const severity = alert.severity || alert.priority || 'info';
            const colorClass = getSeverityColor(severity);
            const icon = getSeverityIcon(severity);

            return (
              <div
                key={index}
                className={`p-4 rounded border-l-4 ${colorClass} animate-in fade-in slide-in-from-right duration-300`}
              >
                <div className="flex items-start gap-3">
                  <span className="text-2xl">{icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-white capitalize">{alert.type || 'Alert'}</span>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium uppercase ${colorClass}`}>
                        {severity}
                      </span>
                    </div>

                    {alert.metric && (
                      <div className="text-sm text-gray-300 mb-2">
                        Metric: <span className="font-mono">{alert.metric}</span>
                      </div>
                    )}

                    {alert.value !== undefined && (
                      <div className="text-sm text-gray-300 mb-2">
                        Value: <span className="font-bold">{alert.value}</span>
                        {alert.threshold && <span className="text-gray-400"> (threshold: {alert.threshold})</span>}
                      </div>
                    )}

                    {alert.anomaly && (
                      <div className="text-sm text-gray-300 mb-2">
                        <div>Expected: {alert.anomaly.expected.toFixed(2)}</div>
                        <div>Actual: {alert.anomaly.value.toFixed(2)}</div>
                        <div>Z-Score: {alert.anomaly.z_score.toFixed(2)}</div>
                      </div>
                    )}

                    {alert.message && (
                      <div className="text-sm text-gray-400 mb-2">{alert.message}</div>
                    )}

                    <div className="text-xs text-gray-500">
                      {alert.timestamp
                        ? new Date(alert.timestamp).toLocaleString()
                        : new Date().toLocaleString()}
                    </div>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
