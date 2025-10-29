'use client';

import { useEffect, useState } from 'react';

interface Job {
  id: string;
  name: string;
  sla: 'platinum' | 'gold' | 'silver' | 'bronze';
  status: 'queued' | 'running' | 'completed' | 'failed';
  progress: number;
  eta: string;
}

interface JobQueueProps {
  stats: any;
}

export function JobQueue({ stats }: JobQueueProps) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchJobs = async () => {
      try {
        const response = await fetch('/api/scheduler/jobs');
        const data = await response.json();
        setJobs(data.jobs || []);
        setIsLoading(false);
      } catch (error) {
        console.error('Failed to fetch jobs:', error);
        setIsLoading(false);
      }
    };

    fetchJobs();
    const interval = setInterval(fetchJobs, 3000);
    return () => clearInterval(interval);
  }, []);

  const getSLAColor = (sla: string) => {
    switch (sla) {
      case 'platinum': return 'from-purple-400 to-pink-400';
      case 'gold': return 'from-yellow-400 to-orange-400';
      case 'silver': return 'from-gray-300 to-gray-400';
      case 'bronze': return 'from-orange-600 to-orange-800';
      default: return 'from-gray-400 to-gray-500';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running': return 'text-blue-400';
      case 'completed': return 'text-green-400';
      case 'failed': return 'text-red-400';
      default: return 'text-gray-400';
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-fog-cyan"></div>
          <p className="mt-2 text-gray-400">Loading job queue...</p>
        </div>
      </div>
    );
  }

  if (jobs.length === 0) {
    return (
      <div className="text-center py-12 text-gray-400">
        No jobs in queue
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {jobs.map((job) => (
        <div key={job.id} className="glass rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <div className={`px-3 py-1 rounded-full text-sm font-semibold bg-gradient-to-r ${getSLAColor(job.sla)}`}>
                {job.sla.toUpperCase()}
              </div>
              <div className="font-semibold">{job.name}</div>
            </div>
            <div className="flex items-center gap-4">
              <div className={`font-semibold ${getStatusColor(job.status)}`}>
                {job.status.toUpperCase()}
              </div>
              {job.status === 'running' && (
                <div className="text-sm text-gray-400">ETA: {job.eta}</div>
              )}
            </div>
          </div>
          {job.status === 'running' && (
            <div className="relative pt-1">
              <div className="flex mb-2 items-center justify-between">
                <div className="text-xs text-gray-400">Progress</div>
                <div className="text-xs font-semibold">{job.progress}%</div>
              </div>
              <div className="overflow-hidden h-2 text-xs flex rounded-full bg-dark-bg-lighter">
                <div
                  style={{ width: `${job.progress}%` }}
                  className={`shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center bg-gradient-to-r ${getSLAColor(job.sla)} transition-all`}
                />
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}