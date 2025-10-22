'use client';

import { useTaskProgress } from '@/lib/websocket/hooks';
import { WebSocketClient } from '@/lib/websocket/client';

interface Task {
  id: string;
  name: string;
  status: string;
  progress: number;
  start_time: string | null;
  estimated_completion: string | null;
}

interface TaskData {
  tasks: Task[];
  summary: {
    total: number;
    pending: number;
    running: number;
    completed: number;
    failed: number;
  };
}

interface TaskProgressListProps {
  client: WebSocketClient | null;
}

export function TaskProgressList({ client }: TaskProgressListProps) {
  const { data: taskData, lastUpdate, isLoading } = useTaskProgress(client);

  if (isLoading) {
    return (
      <div className="bg-white/5 rounded-lg p-6 border border-white/10">
        <h3 className="text-lg font-semibold text-white mb-4">Task Progress</h3>
        <div className="flex items-center justify-center h-48">
          <div className="animate-pulse text-gray-400">Loading tasks...</div>
        </div>
      </div>
    );
  }

  const data = taskData as TaskData;

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'text-green-400 bg-green-500/10 border-green-500/20';
      case 'running':
        return 'text-blue-400 bg-blue-500/10 border-blue-500/20';
      case 'pending':
        return 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20';
      case 'failed':
        return 'text-red-400 bg-red-500/10 border-red-500/20';
      default:
        return 'text-gray-400 bg-gray-500/10 border-gray-500/20';
    }
  };

  return (
    <div className="bg-white/5 rounded-lg p-6 border border-white/10">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold text-white">Task Progress</h3>
        {lastUpdate && (
          <span className="text-xs text-gray-400">
            Updated {lastUpdate.toLocaleTimeString()}
          </span>
        )}
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
        <div className="p-3 bg-white/5 rounded text-center">
          <div className="text-2xl font-bold text-white">{data.summary.total}</div>
          <div className="text-xs text-gray-400">Total</div>
        </div>

        <div className="p-3 bg-yellow-500/10 rounded text-center border border-yellow-500/20">
          <div className="text-2xl font-bold text-yellow-400">{data.summary.pending}</div>
          <div className="text-xs text-gray-400">Pending</div>
        </div>

        <div className="p-3 bg-blue-500/10 rounded text-center border border-blue-500/20">
          <div className="text-2xl font-bold text-blue-400">{data.summary.running}</div>
          <div className="text-xs text-gray-400">Running</div>
        </div>

        <div className="p-3 bg-green-500/10 rounded text-center border border-green-500/20">
          <div className="text-2xl font-bold text-green-400">{data.summary.completed}</div>
          <div className="text-xs text-gray-400">Completed</div>
        </div>

        <div className="p-3 bg-red-500/10 rounded text-center border border-red-500/20">
          <div className="text-2xl font-bold text-red-400">{data.summary.failed}</div>
          <div className="text-xs text-gray-400">Failed</div>
        </div>
      </div>

      {/* Task List */}
      <div className="space-y-3 max-h-96 overflow-y-auto">
        {data.tasks.length === 0 ? (
          <div className="text-center py-8 text-gray-400">No tasks available</div>
        ) : (
          data.tasks.map((task) => (
            <div
              key={task.id}
              className="p-4 bg-white/5 rounded border border-white/10 hover:bg-white/10 transition-colors"
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex-1">
                  <h4 className="font-medium text-white">{task.name}</h4>
                  <p className="text-xs text-gray-400 mt-1">ID: {task.id}</p>
                </div>
                <span className={`px-3 py-1 rounded-full text-xs font-medium border ${getStatusColor(task.status)}`}>
                  {task.status}
                </span>
              </div>

              {/* Progress Bar */}
              {task.status === 'running' && (
                <div className="mt-3">
                  <div className="flex items-center justify-between text-xs text-gray-400 mb-1">
                    <span>Progress</span>
                    <span>{task.progress}%</span>
                  </div>
                  <div className="w-full h-2 bg-white/10 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-fog-cyan to-fog-green transition-all duration-500"
                      style={{ width: `${task.progress}%` }}
                    />
                  </div>
                </div>
              )}

              {/* Timing Info */}
              {task.start_time && (
                <div className="mt-2 text-xs text-gray-400">
                  <span>Started: {new Date(task.start_time).toLocaleTimeString()}</span>
                  {task.estimated_completion && (
                    <span className="ml-4">
                      ETA: {new Date(task.estimated_completion).toLocaleTimeString()}
                    </span>
                  )}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
