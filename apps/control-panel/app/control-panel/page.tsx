"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Activity,
  Server,
  Network,
  Cpu,
  Database,
  Shield,
  Zap,
  Users,
  Globe,
  RefreshCw,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Loader2,
} from "lucide-react";

interface ServiceStatus {
  dao: string;
  scheduler: string;
  edge: string;
  harvest: string;
  fog_coordinator: string;
  onion: string;
  vpn_coordinator: string;
  p2p: string;
  betanet: string;
}

interface SystemHealth {
  status: string;
  services: ServiceStatus;
  version: string;
}

interface ServiceMetadata {
  icon: typeof Server;
  title: string;
  description: string;
  category: "compute" | "privacy" | "network" | "governance";
}

const serviceMetadata: Record<keyof ServiceStatus, ServiceMetadata> = {
  dao: {
    icon: Users,
    title: "DAO Tokenomics",
    description: "Decentralized governance and token economics",
    category: "governance",
  },
  scheduler: {
    icon: Cpu,
    title: "NSGA-II Scheduler",
    description: "Multi-objective task scheduling with SLA awareness",
    category: "compute",
  },
  edge: {
    icon: Server,
    title: "Edge Manager",
    description: "Edge device and resource management",
    category: "compute",
  },
  harvest: {
    icon: Zap,
    title: "Harvest Manager",
    description: "Idle compute resource harvesting",
    category: "compute",
  },
  fog_coordinator: {
    icon: Network,
    title: "Fog Coordinator",
    description: "Network coordination and task routing",
    category: "network",
  },
  onion: {
    icon: Shield,
    title: "Onion Circuits",
    description: "Multi-layer encryption and privacy routing",
    category: "privacy",
  },
  vpn_coordinator: {
    icon: Globe,
    title: "VPN Coordinator",
    description: "Privacy-aware fog network coordination",
    category: "privacy",
  },
  p2p: {
    icon: Activity,
    title: "P2P System",
    description: "Unified decentralized peer-to-peer networking",
    category: "network",
  },
  betanet: {
    icon: Database,
    title: "Betanet Network",
    description: "Privacy-first network layer (HTX protocol)",
    category: "privacy",
  },
};

const statusColors = {
  healthy: "bg-green-500",
  unknown: "bg-yellow-500",
  unavailable: "bg-red-500",
  unhealthy: "bg-orange-500",
};

const statusIcons = {
  healthy: CheckCircle2,
  unknown: AlertCircle,
  unavailable: XCircle,
  unhealthy: AlertCircle,
};

export default function ControlPanelPage() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  const fetchHealth = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch("http://localhost:8000/health");

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      setHealth(data);
      setLastUpdate(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch health status");
      console.error("Health check error:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();

    // Auto-refresh every 10 seconds
    const interval = setInterval(fetchHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  const getStatusIcon = (status: string) => {
    const Icon = statusIcons[status as keyof typeof statusIcons] || AlertCircle;
    return Icon;
  };

  const getStatusBadge = (status: string) => {
    const colorClass = statusColors[status as keyof typeof statusColors] || statusColors.unknown;
    return (
      <Badge
        variant="secondary"
        className={`${colorClass} text-white border-none`}
        data-testid={`status-badge-${status}`}
      >
        {status}
      </Badge>
    );
  };

  const groupedServices = {
    compute: ["scheduler", "edge", "harvest"],
    privacy: ["onion", "vpn_coordinator", "betanet"],
    network: ["fog_coordinator", "p2p"],
    governance: ["dao"],
  };

  return (
    <div className="container mx-auto p-6 space-y-6" data-testid="control-panel-header">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Control Panel</h1>
          <p className="text-muted-foreground mt-1">
            Unified dashboard for Fog Compute infrastructure
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-sm text-muted-foreground">
            Last updated: {lastUpdate.toLocaleTimeString()}
          </div>
          <Button onClick={fetchHealth} disabled={loading} size="sm" data-testid="refresh-button">
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* System Health Summary */}
      {error ? (
        <Card className="border-red-200 bg-red-50" data-testid="error-card">
          <CardHeader>
            <CardTitle className="text-red-800 flex items-center">
              <XCircle className="mr-2 h-5 w-5" />
              Connection Error
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-red-700">{error}</p>
            <Button onClick={fetchHealth} className="mt-4" variant="outline">
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : loading && !health ? (
        <Card data-testid="loading-card">
          <CardContent className="flex items-center justify-center p-12">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <span className="ml-3 text-lg">Loading system health...</span>
          </CardContent>
        </Card>
      ) : health ? (
        <>
          {/* System Status Overview */}
          <Card data-testid="system-status-card">
            <CardHeader>
              <CardTitle className="flex items-center">
                <Activity className="mr-2 h-5 w-5" />
                System Status
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="flex items-center space-x-3">
                  <CheckCircle2 className="h-8 w-8 text-green-500" />
                  <div>
                    <div className="text-2xl font-bold">{health.status}</div>
                    <div className="text-sm text-muted-foreground">Overall Status</div>
                  </div>
                </div>
                <div className="flex items-center space-x-3">
                  <Server className="h-8 w-8 text-blue-500" />
                  <div>
                    <div className="text-2xl font-bold">
                      {Object.values(health.services).filter((s) => s === "healthy" || s === "unknown").length}/
                      {Object.keys(health.services).length}
                    </div>
                    <div className="text-sm text-muted-foreground">Services Operational</div>
                  </div>
                </div>
                <div className="flex items-center space-x-3">
                  <Database className="h-8 w-8 text-purple-500" />
                  <div>
                    <div className="text-2xl font-bold">{health.version}</div>
                    <div className="text-sm text-muted-foreground">System Version</div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Services by Category */}
          {(Object.keys(groupedServices) as Array<keyof typeof groupedServices>).map((category) => (
            <div key={category} data-testid={`category-${category}`}>
              <h2 className="text-xl font-semibold mb-4 capitalize flex items-center">
                {category === "compute" && <Cpu className="mr-2 h-5 w-5" />}
                {category === "privacy" && <Shield className="mr-2 h-5 w-5" />}
                {category === "network" && <Network className="mr-2 h-5 w-5" />}
                {category === "governance" && <Users className="mr-2 h-5 w-5" />}
                {category} Services
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {groupedServices[category].map((serviceKey) => {
                  const service = serviceKey as keyof ServiceStatus;
                  const metadata = serviceMetadata[service];
                  const status = health.services[service];
                  const StatusIcon = getStatusIcon(status);
                  const ServiceIcon = metadata.icon;

                  return (
                    <Card
                      key={service}
                      className="hover:shadow-lg transition-shadow"
                      data-testid={`service-status-${service}`}
                    >
                      <CardHeader className="pb-3">
                        <div className="flex items-start justify-between">
                          <div className="flex items-center space-x-3">
                            <div className="p-2 bg-primary/10 rounded-lg">
                              <ServiceIcon className="h-5 w-5 text-primary" />
                            </div>
                            <div>
                              <CardTitle className="text-base">{metadata.title}</CardTitle>
                            </div>
                          </div>
                          <StatusIcon
                            className={`h-5 w-5 ${
                              status === "healthy" || status === "unknown"
                                ? "text-green-500"
                                : status === "unavailable"
                                  ? "text-red-500"
                                  : "text-yellow-500"
                            }`}
                          />
                        </div>
                        <CardDescription className="text-xs mt-2">
                          {metadata.description}
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="flex items-center justify-between">
                          {getStatusBadge(status)}
                          <Button variant="ghost" size="sm" data-testid={`view-details-${service}`}>
                            View Details
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </div>
          ))}
        </>
      ) : null}

      {/* Quick Actions */}
      <Card data-testid="quick-actions-panel">
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
          <CardDescription>Common operations and shortcuts</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Button variant="outline" className="h-20 flex-col" data-testid="quick-action-deploy-node">
              <Server className="h-6 w-6 mb-2" />
              Deploy Node
            </Button>
            <Button variant="outline" className="h-20 flex-col" data-testid="quick-action-submit-job">
              <Zap className="h-6 w-6 mb-2" />
              Submit Job
            </Button>
            <Button variant="outline" className="h-20 flex-col" data-testid="quick-action-create-circuit">
              <Shield className="h-6 w-6 mb-2" />
              Create Circuit
            </Button>
            <Button variant="outline" className="h-20 flex-col" data-testid="quick-action-view-metrics">
              <Activity className="h-6 w-6 mb-2" />
              View Metrics
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
