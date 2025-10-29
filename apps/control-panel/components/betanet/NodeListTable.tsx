'use client';

import { useState, useEffect } from 'react';
import { Edit2, Trash2, Activity } from 'lucide-react';
import { showSuccess, showError } from '@/components/SuccessNotification';

interface Node {
  id: string;
  node_type: string;
  region?: string;
  name?: string;
  status: string;
  packets_processed: number;
  avg_latency_ms: number;
  created_at: string;
}

interface NodeListTableProps {
  onEdit: (nodeId: string) => void;
  onNodeClick?: (node: Node) => void;
  refreshTrigger: number;
}

export function NodeListTable({ onEdit, onNodeClick, refreshTrigger }: NodeListTableProps) {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    fetchNodes();
  }, [refreshTrigger]);

  const fetchNodes = async () => {
    setIsLoading(true);
    try {
      const response = await fetch('/api/betanet/nodes');
      if (!response.ok) throw new Error('Failed to fetch nodes');
      const data = await response.json();
      setNodes(data);
    } catch (err: any) {
      showError(`Failed to load nodes: ${err.message}`);
      setNodes([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async (nodeId: string, nodeName?: string) => {
    if (!confirm(`Delete node ${nodeName || nodeId}?`)) return;

    setDeletingId(nodeId);
    try {
      const response = await fetch(`/api/betanet/nodes/${nodeId}`, {
        method: 'DELETE',
      });

      if (!response.ok) throw new Error('Failed to delete node');

      showSuccess(`Node ${nodeName || nodeId} deleted`);
      fetchNodes(); // Refresh list
    } catch (err: any) {
      showError(err.message);
    } finally {
      setDeletingId(null);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400">Loading nodes...</div>
      </div>
    );
  }

  if (nodes.length === 0) {
    return (
      <div data-testid="empty-state" className="text-center py-12">
        <Activity className="w-12 h-12 text-gray-600 mx-auto mb-4" />
        <p className="text-gray-400">No nodes deployed yet</p>
        <p className="text-sm text-gray-500 mt-2">Click the + button to add your first node</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto" data-testid="mixnode-list">
      <table className="w-full text-left">
        <thead>
          <tr className="border-b border-gray-800">
            <th className="px-4 py-3 text-sm font-medium text-gray-400">Name/ID</th>
            <th className="px-4 py-3 text-sm font-medium text-gray-400">Type</th>
            <th className="px-4 py-3 text-sm font-medium text-gray-400">Region</th>
            <th className="px-4 py-3 text-sm font-medium text-gray-400">Status</th>
            <th className="px-4 py-3 text-sm font-medium text-gray-400">Packets</th>
            <th className="px-4 py-3 text-sm font-medium text-gray-400">Latency</th>
            <th className="px-4 py-3 text-sm font-medium text-gray-400">Actions</th>
          </tr>
        </thead>
        <tbody>
          {nodes.map((node) => (
            <tr
              key={node.id}
              data-testid={`mixnode-${node.id}`}
              onClick={() => onNodeClick?.(node)}
              className="border-b border-gray-800 hover:bg-gray-800/50 cursor-pointer"
            >
              <td className="px-4 py-3 text-sm text-white">
                {node.name || node.id}
              </td>
              <td className="px-4 py-3 text-sm text-gray-300">{node.node_type}</td>
              <td className="px-4 py-3 text-sm text-gray-300">{node.region || '-'}</td>
              <td className="px-4 py-3">
                <span
                  className={`px-2 py-1 text-xs rounded-full ${
                    node.status === 'active'
                      ? 'bg-green-900/30 text-green-400'
                      : 'bg-gray-700 text-gray-400'
                  }`}
                >
                  {node.status}
                </span>
              </td>
              <td className="px-4 py-3 text-sm text-gray-300">
                {node.packets_processed.toLocaleString()}
              </td>
              <td className="px-4 py-3 text-sm text-gray-300">
                {node.avg_latency_ms.toFixed(1)}ms
              </td>
              <td className="px-4 py-3">
                <div className="flex gap-2">
                  <button
                    onClick={() => onEdit(node.id)}
                    data-testid={`edit-node-${node.id}`}
                    className="p-2 text-blue-400 hover:text-blue-300 hover:bg-blue-900/20 rounded transition-colors"
                    aria-label="Edit node"
                  >
                    <Edit2 className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(node.id, node.name)}
                    data-testid={`delete-node-${node.id}`}
                    disabled={deletingId === node.id}
                    className="p-2 text-red-400 hover:text-red-300 hover:bg-red-900/20 rounded transition-colors disabled:opacity-50"
                    aria-label="Delete node"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
