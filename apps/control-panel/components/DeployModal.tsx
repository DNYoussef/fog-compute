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
  replicas: number;
  resources: {
    cpu: number;
    memory: number;
  };
  env?: Record<string, string>;
}

export function DeployModal({ isOpen, onClose, onDeploy }: DeployModalProps) {
  const [config, setConfig] = useState<NodeConfig>({
    name: '',
    ip: '',
    type: 'compute',
    replicas: 1,
    resources: {
      cpu: 2,
      memory: 4096
    },
    env: {}
  });
  const [showEnvVars, setShowEnvVars] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onDeploy(config);
    setConfig({
      name: '',
      ip: '',
      type: 'compute',
      replicas: 1,
      resources: { cpu: 2, memory: 4096 },
      env: {}
    });
    setShowEnvVars(false);
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

        <form onSubmit={handleSubmit} className="space-y-6 max-h-[70vh] overflow-y-auto pr-2">
          {/* Basic Configuration Section */}
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-gray-300 border-b border-white/10 pb-2">
              Basic Configuration
            </h3>

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
          </div>

          {/* Scaling Configuration Section */}
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-gray-300 border-b border-white/10 pb-2">
              Scaling & Resources
            </h3>

            <div>
              <label htmlFor="replicas" className="block text-sm font-medium mb-2">
                Replicas
                <span className="text-xs text-gray-400 ml-2">
                  (Number of instances to deploy)
                </span>
              </label>
              <input
                id="replicas"
                type="number"
                data-testid="scale-replicas-input"
                value={config.replicas}
                onChange={(e) => setConfig({ ...config, replicas: parseInt(e.target.value) || 1 })}
                className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:ring-2 focus:ring-fog-cyan"
                min="1"
                max="10"
                required
              />
            </div>

            <div className="space-y-3">
              <h4 className="text-sm font-medium text-gray-300">
                Resource Limits
              </h4>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label htmlFor="cpu" className="block text-xs text-gray-400 mb-1">
                    CPU Cores
                  </label>
                  <input
                    id="cpu"
                    type="number"
                    data-testid="cpu-limit-input"
                    value={config.resources.cpu}
                    onChange={(e) => setConfig({
                      ...config,
                      resources: { ...config.resources, cpu: parseFloat(e.target.value) || 1 }
                    })}
                    className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-fog-cyan"
                    min="0.5"
                    max="16"
                    step="0.5"
                  />
                </div>

                <div>
                  <label htmlFor="memory" className="block text-xs text-gray-400 mb-1">
                    Memory (MB)
                  </label>
                  <input
                    id="memory"
                    type="number"
                    data-testid="memory-limit-input"
                    value={config.resources.memory}
                    onChange={(e) => setConfig({
                      ...config,
                      resources: { ...config.resources, memory: parseInt(e.target.value) || 512 }
                    })}
                    className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-fog-cyan"
                    min="512"
                    max="16384"
                    step="512"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Environment Variables Section */}
          <div className="space-y-4">
            <button
              type="button"
              onClick={() => setShowEnvVars(!showEnvVars)}
              className="text-sm text-gray-400 hover:text-white flex items-center transition-colors"
            >
              Environment Variables (Optional)
              <span className="ml-2">{showEnvVars ? '▼' : '▶'}</span>
            </button>

            {showEnvVars && (
              <div className="p-3 bg-white/5 rounded-lg">
                <textarea
                  placeholder="KEY=value&#10;ANOTHER_KEY=value"
                  data-testid="env-vars-input"
                  className="w-full px-3 py-2 bg-white/10 border border-white/10 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-fog-cyan font-mono"
                  rows={4}
                  onChange={(e) => {
                    const envObj: Record<string, string> = {};
                    e.target.value.split('\n').forEach(line => {
                      const [key, value] = line.split('=');
                      if (key && value) envObj[key.trim()] = value.trim();
                    });
                    setConfig({ ...config, env: envObj });
                  }}
                />
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex gap-4 pt-4 border-t border-white/10">
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
