'use client';

import { useState } from 'react';

interface DeployModalProps {
  isOpen: boolean;
  onClose: () => void;
  onDeploy: (config: NodeConfig) => void;
}

interface NodeConfig {
  name: string;
  ip: string;
  type: 'compute' | 'storage' | 'gateway';
}

export function DeployModal({ isOpen, onClose, onDeploy }: DeployModalProps) {
  const [config, setConfig] = useState<NodeConfig>({
    name: '',
    ip: '',
    type: 'compute',
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onDeploy(config);
    setConfig({ name: '', ip: '', type: 'compute' });
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      data-testid="deploy-modal"
      onClick={onClose}
    >
      <div
        className="glass rounded-xl p-6 max-w-md w-full mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-2xl font-semibold">Deploy New Node</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
            aria-label="Close modal"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="node-name" className="block text-sm font-medium mb-2">
              Node Name
            </label>
            <input
              id="node-name"
              type="text"
              data-testid="node-name-input"
              value={config.name}
              onChange={(e) => setConfig({ ...config, name: e.target.value })}
              className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:ring-2 focus:ring-fog-cyan"
              placeholder="e.g., node-001"
              required
            />
          </div>

          <div>
            <label htmlFor="node-ip" className="block text-sm font-medium mb-2">
              IP Address
            </label>
            <input
              id="node-ip"
              type="text"
              data-testid="node-ip-input"
              value={config.ip}
              onChange={(e) => setConfig({ ...config, ip: e.target.value })}
              className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:ring-2 focus:ring-fog-cyan"
              placeholder="e.g., 192.168.1.100"
              pattern="^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$"
              required
            />
          </div>

          <div>
            <label htmlFor="node-type" className="block text-sm font-medium mb-2">
              Node Type
            </label>
            <select
              id="node-type"
              data-testid="node-type-select"
              value={config.type}
              onChange={(e) => setConfig({ ...config, type: e.target.value as NodeConfig['type'] })}
              className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:ring-2 focus:ring-fog-cyan"
            >
              <option value="compute">Compute</option>
              <option value="storage">Storage</option>
              <option value="gateway">Gateway</option>
            </select>
          </div>

          <div className="flex gap-4 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              data-testid="create-node-button"
              className="flex-1 px-4 py-2 bg-fog-cyan hover:bg-fog-cyan/80 text-black font-semibold rounded-lg transition-colors"
            >
              Deploy Node
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
