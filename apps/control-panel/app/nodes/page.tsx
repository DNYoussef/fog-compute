"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Server,
  Cpu,
  MemoryStick,
  HardDrive,
  Activity,
  CheckCircle2,
  XCircle,
  AlertCircle,
  RefreshCw,
  Shield,
  Zap,
} from "lucide-react";

interface ComputeNode {
  id: string;
  status: "active" | "inactive" | "maintenance";
  cpu: number;
  memory: number;
  gpu: number;
  load: number;
  trust: number;
}

interface NodesResponse {
  nodes: ComputeNode[];
  total: number;
}

export default function NodesPage() {
  const [nodes, setNodes] = useState<ComputeNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  const fetchNodes = async () => {
    try {
      setLoading(true);
      const response = await fetch("http://localhost:8000/api/scheduler/nodes");
      const data: NodesResponse = await response.json();
      setNodes(data.nodes || []);
      setLastUpdate(new Date());
    } catch (error) {
      console.error("Failed to fetch nodes:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    document.title = 'Nodes | Fog Compute';
  }, []);

  useEffect(() => {
    fetchNodes();
    const interval = setInterval(fetchNodes, 10000); // Refresh every 10s
    return () => clearInterval(interval);
  }, []);

  const getStatusColor = (status: string) => {
    switch (status) {
      case "active":
        return "bg-green-500";
      case "inactive":
        return "bg-red-500";
      case "maintenance":
        return "bg-yellow-500";
      default:
        return "bg-gray-500";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "active":
        return <CheckCircle2 className="w-5 h-5 text-green-400" />;
      case "inactive":
        return <XCircle className="w-5 h-5 text-red-400" />;
      case "maintenance":
        return <AlertCircle className="w-5 h-5 text-yellow-400" />;
      default:
        return <Activity className="w-5 h-5 text-gray-400" />;
    }
  };

  const getTrustLevel = (trust: number) => {
    if (trust >= 0.9) return { label: "Excellent", color: "text-green-400" };
    if (trust >= 0.7) return { label: "Good", color: "text-blue-400" };
    if (trust >= 0.5) return { label: "Fair", color: "text-yellow-400" };
    return { label: "Poor", color: "text-red-400" };
  };

  const activeNodes = nodes.filter((n) => n.status === "active");
  const totalCpu = nodes.reduce((sum, n) => sum + n.cpu, 0);
  const totalMemory = nodes.reduce((sum, n) => sum + n.memory, 0);
  const totalGpu = nodes.reduce((sum, n) => sum + n.gpu, 0);
  const avgLoad = nodes.length > 0 ? nodes.reduce((sum, n) => sum + n.load, 0) / nodes.length : 0;

  return (
    <div className="space-y-6" data-testid="nodes-page">
      {/* Header */}
      <div className="glass rounded-xl p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-fog-cyan" data-testid="nodes-header">
              Compute Nodes
            </h1>
            <p className="text-gray-400 mt-2">
              Manage and monitor distributed compute nodes
            </p>
          </div>
          <Button
            onClick={fetchNodes}
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
        <Card className="glass border-fog-cyan/20" data-testid="total-nodes-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-gray-400">Total Nodes</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Server className="w-5 h-5 text-fog-cyan" />
              <span className="text-2xl font-bold text-white">{nodes.length}</span>
            </div>
          </CardContent>
        </Card>

        <Card className="glass border-fog-cyan/20" data-testid="active-nodes-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-gray-400">Active Nodes</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-green-400" />
              <span className="text-2xl font-bold text-green-400">{activeNodes.length}</span>
            </div>
          </CardContent>
        </Card>

        <Card className="glass border-fog-cyan/20" data-testid="total-resources-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-gray-400">Total Resources</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-gray-400">CPU:</span>
                <span className="text-white font-medium">{totalCpu} cores</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-400">Memory:</span>
                <span className="text-white font-medium">{totalMemory} GB</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-400">GPU:</span>
                <span className="text-white font-medium">{totalGpu}</span>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="glass border-fog-cyan/20" data-testid="avg-load-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-gray-400">Avg Load</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Activity className="w-5 h-5 text-purple-400" />
              <span className="text-2xl font-bold text-purple-400">
                {avgLoad.toFixed(1)}%
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Nodes Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {nodes.map((node) => {
          const trustInfo = getTrustLevel(node.trust);
          return (
            <Card
              key={node.id}
              className="glass border-fog-cyan/20 hover:border-fog-cyan/40 transition-all"
              data-testid={`node-card-${node.id}`}
            >
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    {getStatusIcon(node.status)}
                    <div>
                      <CardTitle className="text-white text-sm">
                        Node {node.id.slice(0, 8)}
                      </CardTitle>
                      <CardDescription className="text-xs">
                        {node.status.charAt(0).toUpperCase() + node.status.slice(1)}
                      </CardDescription>
                    </div>
                  </div>
                  <div className={`w-2 h-2 rounded-full ${getStatusColor(node.status)}`} />
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Resources */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <Cpu className="w-4 h-4 text-blue-400" />
                      <span className="text-gray-400">CPU</span>
                    </div>
                    <span className="text-white font-medium">{node.cpu} cores</span>
                  </div>

                  <div className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <MemoryStick className="w-4 h-4 text-green-400" />
                      <span className="text-gray-400">Memory</span>
                    </div>
                    <span className="text-white font-medium">{node.memory} GB</span>
                  </div>

                  <div className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <Zap className="w-4 h-4 text-yellow-400" />
                      <span className="text-gray-400">GPU</span>
                    </div>
                    <span className="text-white font-medium">{node.gpu}</span>
                  </div>
                </div>

                {/* Load */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-400">Current Load</span>
                    <span className="text-white font-medium">{node.load.toFixed(1)}%</span>
                  </div>
                  <Progress value={node.load} className="h-2" />
                </div>

                {/* Trust Score */}
                <div className="flex items-center justify-between pt-2 border-t border-gray-700">
                  <div className="flex items-center gap-2">
                    <Shield className="w-4 h-4 text-fog-cyan" />
                    <span className="text-sm text-gray-400">Trust Score</span>
                  </div>
                  <div className="text-right">
                    <div className={`text-sm font-medium ${trustInfo.color}`}>
                      {trustInfo.label}
                    </div>
                    <div className="text-xs text-gray-500">
                      {(node.trust * 100).toFixed(0)}%
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Empty State */}
      {nodes.length === 0 && !loading && (
        <div className="glass rounded-xl p-12 text-center" data-testid="empty-state">
          <Server className="w-16 h-16 text-gray-600 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-gray-400 mb-2">No Nodes Available</h3>
          <p className="text-gray-500">
            No compute nodes are currently registered in the system.
          </p>
        </div>
      )}

      {/* Last Update */}
      <div className="text-center text-sm text-gray-500">
        Last updated: {lastUpdate.toLocaleTimeString()}
      </div>
    </div>
  );
}
