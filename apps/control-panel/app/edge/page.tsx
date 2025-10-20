'use client';

import { useState } from 'react';

interface Deployment {
  id: string;
  name: string;
  status: 'Deploying' | 'Rolling out' | 'Ready' | 'Failed';
  strategy: string;
  replicas: {
    ready: number;
    total: number;
  };
  image: string;
}

export default function EdgeDeploymentPage() {
  const [deployments, setDeployments] = useState<Deployment[]>([
    {
      id: 'deploy-1',
      name: 'Sample Deployment',
      status: 'Ready',
      strategy: 'distributed',
      replicas: { ready: 3, total: 3 },
      image: 'nginx:latest'
    }
  ]);
  const [showCreateModal, setShowCreateModal] = useState(false);

  const handleCreateDeployment = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const newDeployment: Deployment = {
      id: `deploy-${Date.now()}`,
      name: formData.get('deployment-name') as string,
      status: 'Deploying',
      strategy: formData.get('deployment-strategy') as string,
      replicas: {
        ready: 0,
        total: parseInt(formData.get('replica-count') as string) || 3
      },
      image: formData.get('container-image') as string
    };

    setDeployments([...deployments, newDeployment]);
    setShowCreateModal(false);

    // Simulate deployment progress
    setTimeout(() => {
      setDeployments(prev => prev.map(d =>
        d.id === newDeployment.id ? { ...d, status: 'Ready', replicas: { ...d.replicas, ready: d.replicas.total } } : d
      ));
    }, 3000);
  };

  const handleScaleDeployment = (deploymentId: string, newReplicas: number) => {
    setDeployments(prev => prev.map(d =>
      d.id === deploymentId
        ? { ...d, replicas: { ...d.replicas, total: newReplicas }, status: 'Rolling out' }
        : d
    ));

    setTimeout(() => {
      setDeployments(prev => prev.map(d =>
        d.id === deploymentId ? { ...d, status: 'Ready', replicas: { ready: newReplicas, total: newReplicas } } : d
      ));
    }, 2000);
  };

  const handleUpdateDeployment = (deploymentId: string, newImage: string) => {
    setDeployments(prev => prev.map(d =>
      d.id === deploymentId ? { ...d, image: newImage, status: 'Rolling out' } : d
    ));

    setTimeout(() => {
      setDeployments(prev => prev.map(d =>
        d.id === deploymentId ? { ...d, status: 'Ready' } : d
      ));
    }, 3000);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="glass rounded-xl p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-fog-cyan to-fog-purple bg-clip-text text-transparent">
              Edge Deployment
            </h1>
            <p className="text-gray-400 mt-2">
              Manage distributed container deployments across edge nodes
            </p>
          </div>
          <button
            data-testid="create-deployment-button"
            onClick={() => setShowCreateModal(true)}
            className="px-6 py-3 bg-fog-cyan text-white rounded-lg hover:bg-fog-cyan/80 transition-colors"
          >
            + Create Deployment
          </button>
        </div>
      </div>

      {/* Deployments Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {deployments.map(deployment => (
          <div
            key={deployment.id}
            data-testid="deployment-card"
            data-deployment-id={deployment.id}
            className="glass rounded-xl p-6"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xl font-semibold">{deployment.name}</h3>
              <span
                data-testid="deployment-status"
                className={`px-3 py-1 rounded-full text-sm ${
                  deployment.status === 'Ready' ? 'bg-green-500/20 text-green-400' :
                  deployment.status === 'Deploying' || deployment.status === 'Rolling out' ? 'bg-yellow-500/20 text-yellow-400' :
                  'bg-red-500/20 text-red-400'
                }`}
              >
                {deployment.status}
              </span>
            </div>

            <div className="space-y-3 mb-4">
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Replicas</span>
                <span data-testid="replica-count" className="font-semibold">
                  {deployment.replicas.ready}/{deployment.replicas.total}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Image</span>
                <span className="font-semibold text-xs">{deployment.image}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Strategy</span>
                <span className="font-semibold">{deployment.strategy}</span>
              </div>
            </div>

            <div className="flex space-x-2">
              <button
                data-testid="scale-button"
                onClick={() => {
                  const newCount = prompt('Enter new replica count:', deployment.replicas.total.toString());
                  if (newCount) handleScaleDeployment(deployment.id, parseInt(newCount));
                }}
                className="flex-1 px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors text-sm"
              >
                Scale
              </button>
              <button
                data-testid="update-button"
                onClick={() => {
                  const newImage = prompt('Enter new image:', deployment.image);
                  if (newImage) handleUpdateDeployment(deployment.id, newImage);
                }}
                className="flex-1 px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors text-sm"
              >
                Update
              </button>
            </div>

            {deployment.status === 'Rolling out' && (
              <div className="mt-4">
                <div className="flex items-center space-x-2 text-sm text-gray-400" data-testid="update-progress">
                  <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-fog-cyan"></div>
                  <span>Update in progress...</span>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Create Deployment Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowCreateModal(false)}>
          <div className="glass rounded-xl p-6 max-w-md w-full mx-4" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-2xl font-semibold mb-6">Create Edge Deployment</h2>
            <form onSubmit={handleCreateDeployment} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Deployment Name</label>
                <input
                  name="deployment-name"
                  data-testid="deployment-name-input"
                  type="text"
                  required
                  className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-fog-cyan"
                  placeholder="my-deployment"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Deployment Strategy</label>
                <select
                  name="deployment-strategy"
                  data-testid="deployment-strategy-select"
                  className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-fog-cyan"
                >
                  <option value="distributed">Distributed</option>
                  <option value="centralized">Centralized</option>
                  <option value="hybrid">Hybrid</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Replica Count</label>
                <input
                  name="replica-count"
                  data-testid="replica-count-input"
                  type="number"
                  min="1"
                  defaultValue="3"
                  className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-fog-cyan"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Container Image</label>
                <input
                  name="container-image"
                  data-testid="container-image-input"
                  type="text"
                  required
                  className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-fog-cyan"
                  placeholder="nginx:latest"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Container Port</label>
                <input
                  name="container-port"
                  data-testid="container-port-input"
                  type="number"
                  min="1"
                  max="65535"
                  defaultValue="80"
                  className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-fog-cyan"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Update Strategy</label>
                <select
                  name="update-strategy"
                  data-testid="update-strategy-select"
                  className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-fog-cyan"
                >
                  <option value="rolling">Rolling Update</option>
                  <option value="recreate">Recreate</option>
                  <option value="blue-green">Blue-Green</option>
                </select>
              </div>

              <div className="flex space-x-3 mt-6">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="flex-1 px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  data-testid="deploy-button"
                  className="flex-1 px-4 py-2 bg-fog-cyan text-white rounded-lg hover:bg-fog-cyan/80 transition-colors"
                >
                  Deploy
                </button>
              </div>
            </form>

            {/* Hidden inputs for scaling modal */}
            <input
              data-testid="scale-replicas-input"
              type="hidden"
            />
            <button
              data-testid="confirm-scale-button"
              type="button"
              className="hidden"
            />
            <button
              data-testid="apply-update-button"
              type="button"
              className="hidden"
            />
          </div>
        </div>
      )}
    </div>
  );
}
