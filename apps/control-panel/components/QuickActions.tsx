'use client';

import { toast } from 'react-hot-toast';

export function QuickActions() {
  const deployNode = async () => {
    const loadingToast = toast.loading('Deploying mixnode...');

    try {
      const response = await fetch('/api/betanet/deploy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          node_type: 'mixnode',
          region: 'us-east'
        })
      });

      const result = await response.json();

      if (result.success) {
        toast.success(`Node ${result.nodeId?.slice(0, 8)}... deployed successfully!`, {
          id: loadingToast
        });
      } else {
        toast.error('Deployment failed', { id: loadingToast });
      }
    } catch (error) {
      toast.error('Backend unavailable', { id: loadingToast });
    }
  };

  const startBenchmark = async () => {
    const loadingToast = toast.loading('Starting benchmark test...');

    try {
      const response = await fetch('/api/benchmarks/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: 'throughput',
          duration: 60
        })
      });

      const result = await response.json();

      if (result.success) {
        toast.success(`Benchmark ${result.benchmarkId?.slice(0, 8)}... started!`, {
          id: loadingToast
        });
      } else {
        toast.error('Failed to start benchmark', { id: loadingToast });
      }
    } catch (error) {
      toast.error('Backend unavailable', { id: loadingToast });
    }
  };

  const connectBitChat = () => {
    toast.success('Opening BitChat interface...');
    // Navigate to BitChat page
    window.location.href = '/bitchat';
  };

  const viewLogs = () => {
    toast.success('Opening log viewer...');
    // Open Grafana Loki (if available) or dashboard logs
    window.open('http://localhost:3100/explore', '_blank');
  };

  const actions = [
    {
      title: 'Deploy Node',
      description: 'Add a new mixnode to the Betanet network',
      icon: '🚀',
      color: 'from-fog-cyan to-blue-500',
      action: deployNode,
    },
    {
      title: 'Start Benchmark',
      description: 'Run performance tests on fog nodes',
      icon: '⚡',
      color: 'from-green-400 to-emerald-500',
      action: startBenchmark,
    },
    {
      title: 'Connect BitChat',
      description: 'Join the P2P messaging mesh',
      icon: '💬',
      color: 'from-fog-purple to-purple-500',
      action: connectBitChat,
    },
    {
      title: 'View Logs',
      description: 'Access system logs and diagnostics',
      icon: '📋',
      color: 'from-yellow-400 to-orange-500',
      action: viewLogs,
    },
  ];

  return (
    <div className="glass rounded-xl p-6" data-testid="quick-actions">
      <h2 className="text-xl font-semibold mb-4">Quick Actions</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {actions.map((action, index) => (
          <button
            key={index}
            onClick={action.action}
            data-testid={index === 0 ? "add-node-button" : undefined}
            className="glass glass-hover rounded-lg p-4 text-left transition-all duration-300 hover:scale-105"
          >
            <div className={`text-3xl mb-2 bg-gradient-to-r ${action.color} w-12 h-12 rounded-lg flex items-center justify-center`}>
              {action.icon}
            </div>
            <h3 className="font-semibold mb-1">{action.title}</h3>
            <p className="text-sm text-gray-400">{action.description}</p>
          </button>
        ))}
      </div>
    </div>
  );
}