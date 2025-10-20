'use client';

interface EmptyStateProps {
  title?: string;
  description?: string;
  icon?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export function EmptyState({
  title = 'No data available',
  description = 'There is nothing to display at the moment',
  icon = '📭',
  action,
}: EmptyStateProps) {
  return (
    <div
      className="flex flex-col items-center justify-center py-16 px-4"
      data-testid="empty-state"
    >
      <div className="w-20 h-20 bg-white/5 rounded-full flex items-center justify-center mb-4">
        <span className="text-4xl">{icon}</span>
      </div>

      <h3 className="text-xl font-semibold mb-2">{title}</h3>
      <p className="text-gray-400 text-center max-w-md mb-6">{description}</p>

      {action && (
        <button
          onClick={action.onClick}
          className="px-6 py-2 bg-fog-cyan hover:bg-fog-cyan/80 text-black font-semibold rounded-lg transition-colors"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
