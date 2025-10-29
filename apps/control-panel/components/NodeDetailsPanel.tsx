'use client';

interface NodeDetailsPanelProps {
  node: {
    id: string;
    name?: string;
    ip?: string;
    type?: string;
    node_type?: string;
    status: string;
    cpu?: number;
    memory?: number;
    uptime?: string;
    region?: string;
    packets_processed?: number;
    avg_latency_ms?: number;
  } | null;
  onClose: () => void;
}

export function NodeDetailsPanel({ node, onClose }: NodeDetailsPanelProps) {
  if (!node) return null;

  const nodeType = node.type || node.node_type || 'unknown';
  const nodeName = node.name || node.id;
  const nodeIp = node.ip || 'N/A';

  return (
    <div
      className="fixed right-0 top-0 h-full w-96 glass border-l border-white/10 z-40 p-6 overflow-y-auto"
      data-testid="node-details"
    >
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-semibold">Node Details</h2>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-white transition-colors"
          aria-label="Close panel"
        >
          ✕
        </button>
      </div>

      <div className="space-y-6">
        {/* Basic Information */}
        <div>
          <h3 className="text-sm font-medium text-gray-400 mb-3">Basic Information</h3>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-gray-400">Name:</span>
              <span className="font-medium">{nodeName}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">ID:</span>
              <span className="font-mono text-sm">{node.id}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">IP Address:</span>
              <span className="font-mono text-sm">{nodeIp}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Type:</span>
              <span className="capitalize">{nodeType}</span>
            </div>
            {node.region && (
              <div className="flex justify-between">
                <span className="text-gray-400">Region:</span>
                <span className="capitalize">{node.region}</span>
              </div>
            )}
            <div className="flex justify-between">
              <span className="text-gray-400">Status:</span>
              <span
                className={`px-2 py-1 rounded text-xs font-semibold ${
                  node.status === 'active'
                    ? 'bg-green-500/20 text-green-400'
                    : 'bg-red-500/20 text-red-400'
                }`}
              >
                {node.status}
              </span>
            </div>
          </div>
        </div>

        {/* Performance Metrics */}
        {(node.cpu !== undefined || node.memory !== undefined || node.packets_processed !== undefined || node.avg_latency_ms !== undefined) && (
          <div>
            <h3 className="text-sm font-medium text-gray-400 mb-3">Performance Metrics</h3>
            <div className="space-y-3">
              {node.cpu !== undefined && (
                <div>
                  <div className="flex justify-between mb-1">
                    <span className="text-sm text-gray-400">CPU Usage</span>
                    <span className="text-sm font-medium">{node.cpu}%</span>
                  </div>
                  <div className="w-full bg-white/5 rounded-full h-2">
                    <div
                      className="bg-fog-cyan h-2 rounded-full transition-all"
                      style={{ width: `${node.cpu}%` }}
                    />
                  </div>
                </div>
              )}
              {node.memory !== undefined && (
                <div>
                  <div className="flex justify-between mb-1">
                    <span className="text-sm text-gray-400">Memory Usage</span>
                    <span className="text-sm font-medium">{node.memory}%</span>
                  </div>
                  <div className="w-full bg-white/5 rounded-full h-2">
                    <div
                      className="bg-fog-purple h-2 rounded-full transition-all"
                      style={{ width: `${node.memory}%` }}
                    />
                  </div>
                </div>
              )}
              {node.packets_processed !== undefined && (
                <div className="flex justify-between">
                  <span className="text-sm text-gray-400">Packets Processed</span>
                  <span className="text-sm font-medium">{node.packets_processed.toLocaleString()}</span>
                </div>
              )}
              {node.avg_latency_ms !== undefined && (
                <div className="flex justify-between">
                  <span className="text-sm text-gray-400">Avg Latency</span>
                  <span className="text-sm font-medium">{node.avg_latency_ms.toFixed(1)}ms</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* System Information */}
        {node.uptime && (
          <div>
            <h3 className="text-sm font-medium text-gray-400 mb-3">System Information</h3>
            <div className="flex justify-between">
              <span className="text-gray-400">Uptime:</span>
              <span className="font-medium">{node.uptime}</span>
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="pt-4 border-t border-white/10">
          <h3 className="text-sm font-medium text-gray-400 mb-3">Actions</h3>
          <div className="flex flex-col gap-2">
            <button className="w-full px-4 py-2 bg-fog-cyan/20 hover:bg-fog-cyan/30 text-fog-cyan rounded-lg transition-colors">
              Restart Node
            </button>
            <button className="w-full px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors">
              View Logs
            </button>
            <button className="w-full px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg transition-colors">
              Remove Node
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
