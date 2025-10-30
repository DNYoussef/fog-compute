'use client';

interface MixnodeInfo {
  id: string;
  address: string;
  status: 'active' | 'inactive' | 'degraded';
  packetsProcessed: number;
  uptime: number;
  latency: number;
  reputation: number;
}

export function MixnodeList({
  mixnodes,
  selectedNode,
  onNodeSelect
}: {
  mixnodes: MixnodeInfo[];
  selectedNode: string | null;
  onNodeSelect: (id: string) => void;
}) {
  return (
    <div className="h-[300px] overflow-y-auto space-y-2" data-testid="mixnode-list">
      {mixnodes.length === 0 ? (
        <div className="text-center text-gray-400 py-8">
          No mixnodes available
        </div>
      ) : (
        mixnodes.map((node) => (
          <div
            key={node.id}
            data-testid={`mixnode-${node.id}`}
            onClick={() => onNodeSelect(node.id)}
            className={`glass-dark rounded-lg p-3 cursor-pointer transition-all duration-200 ${
              selectedNode === node.id ? 'ring-2 ring-fog-cyan' : 'hover:bg-white/10'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center space-x-2">
                <div className={`w-2 h-2 rounded-full status-${
                  node.status === 'active' ? 'online' :
                  node.status === 'degraded' ? 'warning' : 'offline'
                }`} />
                <span className="text-sm font-mono">{node.id.substring(0, 12)}...</span>
              </div>
              <span className={`text-xs px-2 py-1 rounded ${
                node.status === 'active' ? 'bg-green-400/20 text-green-400' :
                node.status === 'degraded' ? 'bg-yellow-400/20 text-yellow-400' :
                'bg-red-400/20 text-red-400'
              }`}>
                {node.status.toUpperCase()}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <span className="text-gray-400">Packets: </span>
                <span className="font-semibold">{node.packetsProcessed.toLocaleString()}</span>
              </div>
              <div>
                <span className="text-gray-400">Latency: </span>
                <span className="font-semibold">{node.latency.toFixed(2)}ms</span>
              </div>
              <div>
                <span className="text-gray-400">Uptime: </span>
                <span className="font-semibold">{Math.floor(node.uptime / 3600)}h</span>
              </div>
              <div>
                <span className="text-gray-400">Rep: </span>
                <span className="font-semibold">{(node.reputation * 100).toFixed(0)}%</span>
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  );
}