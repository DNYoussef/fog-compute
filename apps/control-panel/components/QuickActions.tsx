'use client';

export function QuickActions() {
  const actions = [
    {
      title: 'Deploy Node',
      description: 'Add a new mixnode to the Betanet network',
      icon: '🚀',
      color: 'from-fog-cyan to-blue-500',
      action: () => console.log('Deploy mixnode'),
    },
    {
      title: 'Start Benchmark',
      description: 'Run performance tests on fog nodes',
      icon: '⚡',
      color: 'from-green-400 to-emerald-500',
      action: () => console.log('Start benchmark'),
    },
    {
      title: 'Connect BitChat',
      description: 'Join the P2P messaging mesh',
      icon: '💬',
      color: 'from-fog-purple to-purple-500',
      action: () => console.log('Connect BitChat'),
    },
    {
      title: 'View Logs',
      description: 'Access system logs and diagnostics',
      icon: '📋',
      color: 'from-yellow-400 to-orange-500',
      action: () => console.log('View logs'),
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