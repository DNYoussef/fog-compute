"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  ListTodo,
  PlayCircle,
  CheckCircle2,
  XCircle,
  Clock,
  Cpu,
  MemoryStick,
  Server,
  RefreshCw,
  Zap,
  AlertCircle,
  Award,
} from "lucide-react";

interface Task {
  id: string;
  name: string;
  status: "pending" | "running" | "completed" | "failed";
  sla: "bronze" | "silver" | "gold" | "platinum";
  cpu: number;
  memory: number;
  gpu: number;
  node: string | null;
  submitted: string;
  started: string | null;
  completed: string | null;
  progress: number;
}

interface TasksResponse {
  jobs: Task[];
  total: number;
  filtered: boolean;
}

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<string>("all");
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  const fetchTasks = async (status?: string) => {
    try {
      setLoading(true);
      const url = status
        ? `http://localhost:8000/api/scheduler/jobs?status=${status}`
        : "http://localhost:8000/api/scheduler/jobs";
      const response = await fetch(url);
      const data: TasksResponse = await response.json();
      setTasks(data.jobs || []);
      setLastUpdate(new Date());
    } catch (error) {
      console.error("Failed to fetch tasks:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const status = activeTab === "all" ? undefined : activeTab;
    fetchTasks(status);
    const interval = setInterval(() => fetchTasks(status), 5000); // Refresh every 5s
    return () => clearInterval(interval);
  }, [activeTab]);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "pending":
        return <Clock className="w-4 h-4 text-yellow-400" />;
      case "running":
        return <PlayCircle className="w-4 h-4 text-blue-400" />;
      case "completed":
        return <CheckCircle2 className="w-4 h-4 text-green-400" />;
      case "failed":
        return <XCircle className="w-4 h-4 text-red-400" />;
      default:
        return <AlertCircle className="w-4 h-4 text-gray-400" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "pending":
        return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
      case "running":
        return "bg-blue-500/20 text-blue-400 border-blue-500/30";
      case "completed":
        return "bg-green-500/20 text-green-400 border-green-500/30";
      case "failed":
        return "bg-red-500/20 text-red-400 border-red-500/30";
      default:
        return "bg-gray-500/20 text-gray-400 border-gray-500/30";
    }
  };

  const getSlaColor = (sla: string) => {
    switch (sla) {
      case "platinum":
        return "bg-purple-500/20 text-purple-400 border-purple-500/30";
      case "gold":
        return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
      case "silver":
        return "bg-gray-400/20 text-gray-300 border-gray-400/30";
      case "bronze":
        return "bg-orange-500/20 text-orange-400 border-orange-500/30";
      default:
        return "bg-gray-500/20 text-gray-400 border-gray-500/30";
    }
  };

  const getSlaIcon = (sla: string) => {
    return <Award className="w-3 h-3" />;
  };

  const formatDuration = (start: string | null, end: string | null) => {
    if (!start) return "Not started";
    const startTime = new Date(start).getTime();
    const endTime = end ? new Date(end).getTime() : Date.now();
    const duration = Math.floor((endTime - startTime) / 1000);
    if (duration < 60) return `${duration}s`;
    if (duration < 3600) return `${Math.floor(duration / 60)}m`;
    return `${Math.floor(duration / 3600)}h ${Math.floor((duration % 3600) / 60)}m`;
  };

  const pendingTasks = tasks.filter((t) => t.status === "pending");
  const runningTasks = tasks.filter((t) => t.status === "running");
  const completedTasks = tasks.filter((t) => t.status === "completed");
  const failedTasks = tasks.filter((t) => t.status === "failed");

  return (
    <div className="space-y-6" data-testid="tasks-page">
      {/* Header */}
      <div className="glass rounded-xl p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-fog-cyan" data-testid="tasks-header">
              Task Queue
            </h1>
            <p className="text-gray-400 mt-2">
              Monitor and manage scheduled compute tasks
            </p>
          </div>
          <Button
            onClick={() => fetchTasks(activeTab === "all" ? undefined : activeTab)}
            disabled={loading}
            className="bg-fog-cyan hover:bg-fog-cyan/80"
            data-testid="refresh-button"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="glass border-fog-cyan/20" data-testid="total-tasks-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-gray-400">Total Tasks</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <ListTodo className="w-5 h-5 text-fog-cyan" />
              <span className="text-2xl font-bold text-white">{tasks.length}</span>
            </div>
          </CardContent>
        </Card>

        <Card className="glass border-fog-cyan/20" data-testid="running-tasks-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-gray-400">Running</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <PlayCircle className="w-5 h-5 text-blue-400" />
              <span className="text-2xl font-bold text-blue-400">{runningTasks.length}</span>
            </div>
          </CardContent>
        </Card>

        <Card className="glass border-fog-cyan/20" data-testid="completed-tasks-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-gray-400">Completed</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-green-400" />
              <span className="text-2xl font-bold text-green-400">{completedTasks.length}</span>
            </div>
          </CardContent>
        </Card>

        <Card className="glass border-fog-cyan/20" data-testid="pending-tasks-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-gray-400">Pending</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Clock className="w-5 h-5 text-yellow-400" />
              <span className="text-2xl font-bold text-yellow-400">{pendingTasks.length}</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tasks Tabs */}
      <Tabs defaultValue="all" value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="glass border-fog-cyan/20">
          <TabsTrigger value="all" data-testid="tab-all">
            All ({tasks.length})
          </TabsTrigger>
          <TabsTrigger value="running" data-testid="tab-running">
            Running ({runningTasks.length})
          </TabsTrigger>
          <TabsTrigger value="pending" data-testid="tab-pending">
            Pending ({pendingTasks.length})
          </TabsTrigger>
          <TabsTrigger value="completed" data-testid="tab-completed">
            Completed ({completedTasks.length})
          </TabsTrigger>
          <TabsTrigger value="failed" data-testid="tab-failed">
            Failed ({failedTasks.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value={activeTab} className="space-y-4 mt-6">
          {/* Tasks List */}
          <div className="space-y-3">
            {tasks.map((task) => (
              <Card
                key={task.id}
                className="glass border-fog-cyan/20 hover:border-fog-cyan/40 transition-all"
                data-testid={`task-card-${task.id}`}
              >
                <CardContent className="p-6">
                  <div className="flex items-start justify-between gap-4">
                    {/* Task Info */}
                    <div className="flex-1 space-y-3">
                      <div className="flex items-start gap-3">
                        {getStatusIcon(task.status)}
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <h3 className="font-semibold text-white">{task.name}</h3>
                            <Badge
                              variant="outline"
                              className={`${getStatusColor(task.status)} text-xs`}
                            >
                              {task.status}
                            </Badge>
                            <Badge
                              variant="outline"
                              className={`${getSlaColor(task.sla)} text-xs flex items-center gap-1`}
                            >
                              {getSlaIcon(task.sla)}
                              {task.sla.toUpperCase()}
                            </Badge>
                          </div>
                          <p className="text-sm text-gray-400">Task ID: {task.id}</p>
                        </div>
                      </div>

                      {/* Resources */}
                      <div className="flex items-center gap-6 text-sm">
                        <div className="flex items-center gap-2">
                          <Cpu className="w-4 h-4 text-blue-400" />
                          <span className="text-gray-400">CPU:</span>
                          <span className="text-white font-medium">{task.cpu} cores</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <MemoryStick className="w-4 h-4 text-green-400" />
                          <span className="text-gray-400">Memory:</span>
                          <span className="text-white font-medium">{task.memory} GB</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Zap className="w-4 h-4 text-yellow-400" />
                          <span className="text-gray-400">GPU:</span>
                          <span className="text-white font-medium">{task.gpu}</span>
                        </div>
                        {task.node && (
                          <div className="flex items-center gap-2">
                            <Server className="w-4 h-4 text-purple-400" />
                            <span className="text-gray-400">Node:</span>
                            <span className="text-white font-medium">{task.node.slice(0, 8)}</span>
                          </div>
                        )}
                      </div>

                      {/* Progress */}
                      {task.status === "running" && (
                        <div className="space-y-2">
                          <div className="flex items-center justify-between text-sm">
                            <span className="text-gray-400">Progress</span>
                            <span className="text-white font-medium">{task.progress}%</span>
                          </div>
                          <Progress value={task.progress} className="h-2" />
                        </div>
                      )}

                      {/* Timing */}
                      <div className="flex items-center gap-6 text-xs text-gray-500">
                        <div>
                          <span className="text-gray-400">Submitted:</span>{" "}
                          {new Date(task.submitted).toLocaleString()}
                        </div>
                        {task.started && (
                          <div>
                            <span className="text-gray-400">Duration:</span>{" "}
                            {formatDuration(task.started, task.completed)}
                          </div>
                        )}
                        {task.completed && (
                          <div>
                            <span className="text-gray-400">Completed:</span>{" "}
                            {new Date(task.completed).toLocaleString()}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Empty State */}
          {tasks.length === 0 && !loading && (
            <div className="glass rounded-xl p-12 text-center" data-testid="empty-state">
              <ListTodo className="w-16 h-16 text-gray-600 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-gray-400 mb-2">No Tasks Found</h3>
              <p className="text-gray-500">
                {activeTab === "all"
                  ? "No tasks have been submitted to the queue."
                  : `No tasks with status "${activeTab}".`}
              </p>
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* Last Update */}
      <div className="text-center text-sm text-gray-500">
        Last updated: {lastUpdate.toLocaleTimeString()}
      </div>
    </div>
  );
}
