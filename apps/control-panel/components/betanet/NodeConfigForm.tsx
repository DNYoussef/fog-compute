'use client';

import { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import { showSuccess, showError } from '@/components/SuccessNotification';

interface NodeConfigFormProps {
  nodeId: string | null; // null for create, string for edit
  onClose: () => void;
  onSuccess: () => void;
}

export function NodeConfigForm({ nodeId, onClose, onSuccess }: NodeConfigFormProps) {
  const [formData, setFormData] = useState({
    node_type: 'mixnode',
    region: 'us-east',
    name: '',
  });
  const [isLoading, setIsLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const isEditMode = nodeId !== null;

  // Load existing node data if editing
  useEffect(() => {
    if (nodeId) {
      setIsLoading(true);
      fetch(`/api/betanet/nodes/${nodeId}`)
        .then(res => res.json())
        .then(data => {
          setFormData({
            node_type: data.node_type,
            region: data.region || 'us-east',
            name: data.name || '',
          });
        })
        .catch(err => {
          showError(`Failed to load node: ${err.message}`);
        })
        .finally(() => setIsLoading(false));
    }
  }, [nodeId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrors({});

    try {
      const url = nodeId
        ? `/api/betanet/nodes/${nodeId}`
        : '/api/betanet/nodes';

      const method = nodeId ? 'PUT' : 'POST';

      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Operation failed');
      }

      const result = await response.json();
      showSuccess(
        nodeId
          ? `Node ${result.name || result.id} updated successfully`
          : `Node ${result.name || result.id} created successfully`
      );
      onSuccess();
    } catch (err: any) {
      showError(err.message);
      setErrors({ submit: err.message });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" data-testid="node-config-form">
      <div className="bg-gray-900 rounded-lg shadow-xl max-w-md w-full border border-gray-800">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-800">
          <h3 className="text-xl font-semibold text-white">
            {isEditMode ? 'Edit Node' : 'Add New Node'}
          </h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* Node Type */}
          <div>
            <label htmlFor="node_type" className="block text-sm font-medium text-gray-300 mb-2">
              Node Type *
            </label>
            <select
              id="node_type"
              data-testid="node-type-select"
              value={formData.node_type}
              onChange={(e) => setFormData({ ...formData, node_type: e.target.value })}
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={isEditMode} // Cannot change type after creation
            >
              <option value="mixnode">Mixnode</option>
              <option value="gateway">Gateway</option>
              <option value="client">Client</option>
            </select>
          </div>

          {/* Region */}
          <div>
            <label htmlFor="region" className="block text-sm font-medium text-gray-300 mb-2">
              Region
            </label>
            <select
              id="region"
              data-testid="node-region-select"
              value={formData.region}
              onChange={(e) => setFormData({ ...formData, region: e.target.value })}
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="us-east">US East</option>
              <option value="us-west">US West</option>
              <option value="eu-west">EU West</option>
              <option value="eu-central">EU Central</option>
              <option value="ap-southeast">AP Southeast</option>
            </select>
          </div>

          {/* Name */}
          <div>
            <label htmlFor="name" className="block text-sm font-medium text-gray-300 mb-2">
              Node Name (optional)
            </label>
            <input
              type="text"
              id="name"
              data-testid="node-name-input"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="e.g., my-mixnode-1"
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* Error Message */}
          {errors.submit && (
            <div className="p-3 bg-red-900/20 border border-red-800 rounded-lg text-red-400 text-sm">
              {errors.submit}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading}
              data-testid="node-form-submit"
              className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? 'Saving...' : isEditMode ? 'Update' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
