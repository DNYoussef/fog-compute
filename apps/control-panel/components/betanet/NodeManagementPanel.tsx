'use client';

import { useState } from 'react';
import { AddNodeButton } from './AddNodeButton';
import { NodeConfigForm } from './NodeConfigForm';
import { NodeListTable } from './NodeListTable';
import { NodeDetailsPanel } from '../NodeDetailsPanel';

export function NodeManagementPanel() {
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingNode, setEditingNode] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const handleAddClick = () => {
    setEditingNode(null);
    setIsFormOpen(true);
  };

  const handleEditClick = (nodeId: string) => {
    setEditingNode(nodeId);
    setIsFormOpen(true);
  };

  const handleNodeClick = (node: any) => {
    setSelectedNode(node);
  };

  const handleFormClose = () => {
    setIsFormOpen(false);
    setEditingNode(null);
  };

  const handleFormSuccess = () => {
    setIsFormOpen(false);
    setEditingNode(null);
    setRefreshTrigger(prev => prev + 1); // Trigger node list refresh
  };

  return (
    <div data-testid="node-management-panel" className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-white">Betanet Nodes</h2>
      </div>

      <NodeListTable
        onEdit={handleEditClick}
        onNodeClick={handleNodeClick}
        refreshTrigger={refreshTrigger}
      />

      <AddNodeButton onClick={handleAddClick} />

      {isFormOpen && (
        <NodeConfigForm
          nodeId={editingNode}
          onClose={handleFormClose}
          onSuccess={handleFormSuccess}
        />
      )}

      {selectedNode && (
        <NodeDetailsPanel
          node={selectedNode}
          onClose={() => setSelectedNode(null)}
        />
      )}
    </div>
  );
}
